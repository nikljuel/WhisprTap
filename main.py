import os
import shutil
import sys
import threading
import traceback
import tkinter as tk

import config
from hotkey_manager import HotkeyManager
from recorder import Recorder
from settings_window import SettingsWindow
from text_inserter import create_inserter
from transcriber import FasterWhisperTranscriber
from tray_app import TrayApp, TrayState


def check_dependencies() -> list[str]:
    warnings = []
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        if not shutil.which("wl-copy"):
            warnings.append("wl-clipboard nicht gefunden. Installiere: sudo apt install wl-clipboard")
        if not shutil.which("ydotool") and not shutil.which("wtype"):
            warnings.append(
                "Weder ydotool noch wtype gefunden — Text-Eingabe deaktiviert. "
                "Empfohlen: sudo apt install wtype  "
                "oder: sudo apt install ydotool && sudo usermod -a -G input $USER (dann neu anmelden)"
            )
    else:
        if not shutil.which("xdotool"):
            warnings.append("xdotool nicht gefunden — Auto-Paste deaktiviert. Installiere: sudo apt install xdotool")
        if not shutil.which("xclip"):
            warnings.append("xclip nicht gefunden. Installiere: sudo apt install xclip")
    return warnings


class App:
    def __init__(self):
        self._cfg = config.load()
        self._recorder = Recorder(device=self._cfg.get("input_device"))
        self._transcriber = FasterWhisperTranscriber(
            model_size=self._cfg["model_size"],
            language=self._cfg["language"],
            model_dir=self._cfg.get("model_dir"),
        )
        self._inserter = create_inserter()
        self._hotkey_manager: HotkeyManager | None = None
        self._load_generation: int = 0
        self._tray = TrayApp(
            on_settings=self._open_settings,
            on_reload_model=self._reload_model,
            on_quit=self._quit,
        )
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        self._settings_window = SettingsWindow(root=self._tk_root, on_save=self._on_settings_saved)

    def run(self) -> None:
        warnings = check_dependencies()
        for w in warnings:
            print(f"[WhisprTap] WARNUNG: {w}", file=sys.stderr)

        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._tray.start, daemon=True).start()
        self._tk_root.mainloop()  # Main-Thread blockiert hier

    def _load_model(self, transcriber=None, generation: int = 0) -> None:
        if transcriber is None:
            # Erster Start beim App-Launch
            transcriber = self._transcriber
            self._tray.set_state(TrayState.LOADING)
        try:
            transcriber.load()
            if generation != self._load_generation:
                return  # neuerer Reload gestartet → diesen verwerfen
            self._transcriber = transcriber
            if self._hotkey_manager is None:
                self._hotkey_manager = HotkeyManager(
                    hotkey=self._cfg["hotkey"],
                    on_press=self._on_hotkey,
                )
                self._hotkey_manager.start()
            else:
                self._hotkey_manager.update_hotkey(self._cfg["hotkey"])
            self._tray.set_state(TrayState.IDLE)
            print(f"[WhisprTap] Modell '{transcriber._model_size}' geladen, bereit.")
        except Exception as e:
            if generation == self._load_generation:
                print(f"[WhisprTap] Fehler beim Laden des Modells: {e}", file=sys.stderr)
                self._tray.set_state(TrayState.ERROR)
                self._tray.notify("WhisprTap — Fehler", f"Modell konnte nicht geladen werden: {e}")

    def _on_hotkey(self) -> None:
        if not self._transcriber.is_ready():
            self._tray.notify("WhisprTap", "Modell lädt noch, bitte warten...")
            return

        if self._recorder.is_recording:
            self._stop_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
            self._tray.set_state(TrayState.RECORDING)
        except Exception as e:
            print(f"[WhisprTap] Aufnahmefehler: {e}", file=sys.stderr)
            self._tray.set_state(TrayState.ERROR)
            self._tray.notify("WhisprTap — Fehler", f"Mikrofon nicht erreichbar: {e}")

    def _stop_and_transcribe(self) -> None:
        self._tray.set_state(TrayState.PROCESSING)
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _transcribe_worker(self) -> None:
        try:
            audio_path = self._recorder.stop()
            if audio_path is None:
                self._tray.notify("WhisprTap", "Aufnahme zu kurz.")
                return

            text = self._transcriber.transcribe(audio_path)
            audio_path.unlink(missing_ok=True)

            if text:
                self._inserter.insert(text, auto_paste=self._cfg.get("auto_paste", True))
                self._tray.notify("WhisprTap", f"✓ {text[:60]}{'...' if len(text) > 60 else ''}")
            else:
                self._tray.notify("WhisprTap", "Kein Text erkannt.")

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            print(f"[WhisprTap] Transkriptionsfehler: {e}", file=sys.stderr)
            self._tray.notify("WhisprTap - Fehler", f"Transkription fehlgeschlagen: {e}")
        finally:
            if not self._recorder.is_recording:
                self._tray.set_state(TrayState.IDLE)

    def _open_settings(self) -> None:
        self._settings_window.open()

    def _on_settings_saved(self, new_cfg: dict) -> None:
        self._cfg = new_cfg
        if self._hotkey_manager:
            self._hotkey_manager.update_hotkey(new_cfg["hotkey"])
        if not self._recorder.is_recording:
            self._recorder = Recorder(device=new_cfg.get("input_device"))
        model_changed = (
            new_cfg["model_size"] != self._transcriber._model_size
            or new_cfg["language"] != self._transcriber._language
        )
        if model_changed:
            self._reload_model()

    def _reload_model(self) -> None:
        self._load_generation += 1
        generation = self._load_generation
        if self._recorder.is_recording:
            self._recorder.stop()
        new_transcriber = FasterWhisperTranscriber(
            model_size=self._cfg["model_size"],
            language=self._cfg["language"],
            model_dir=self._cfg.get("model_dir"),
        )
        self._tray.set_state(TrayState.LOADING)
        self._tray.notify("WhisprTap", f"Lade Modell '{self._cfg['model_size']}'…")
        threading.Thread(
            target=self._load_model,
            args=(new_transcriber, generation),
            daemon=True,
        ).start()

    def _quit(self) -> None:
        if self._recorder.is_recording:
            self._recorder.stop()
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        self._tray.stop()
        self._tk_root.quit()


if __name__ == "__main__":
    App().run()
