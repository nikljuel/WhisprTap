import platform
import sys
import threading
import traceback


def ensure_macos() -> None:
    if platform.system() != "Darwin":
        print("WhisprTap is a macOS-only app. Please start it on macOS.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    ensure_macos()

import config
from audio_devices import resolve_input_device_index
from hotkey_manager import HotkeyManager
from recorder import Recorder
from settings_window import SettingsWindow
from text_inserter import create_inserter
from transcriber import FasterWhisperTranscriber
from tray_app import TrayApp, TrayState


class App:
    def __init__(self):
        ensure_macos()
        self._cfg = config.load()
        self._recorder = Recorder(device=resolve_input_device_index(self._cfg))
        self._transcriber = FasterWhisperTranscriber(
            model_size=self._cfg["model_size"],
            language=self._cfg["language"],
            model_dir=self._cfg.get("model_dir"),
        )
        self._inserter = create_inserter()
        self._hotkey_manager: HotkeyManager | None = None
        self._settings_window = SettingsWindow(on_save=self._apply_config)
        self._load_generation: int = 0
        self._tray = TrayApp(
            on_settings=self._open_settings,
            on_reload_model=self._reload_model,
            on_quit=self._quit,
        )

    def run(self) -> None:
        threading.Thread(target=self._load_model, daemon=True).start()
        self._tray.start()

    def _load_model(self, transcriber=None, generation: int = 0) -> None:
        if transcriber is None:
            transcriber = self._transcriber
            self._tray.set_state(TrayState.LOADING)
        try:
            transcriber.load()
            if generation != self._load_generation:
                return
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
            print(f"[WhisprTap] Model '{transcriber._model_size}' loaded and ready.")
        except Exception as e:
            if generation == self._load_generation:
                print(f"[WhisprTap] Failed to load model: {e}", file=sys.stderr)
                self._tray.set_state(TrayState.ERROR)
                self._tray.notify("WhisprTap - Error", f"Model could not be loaded: {e}")

    def _on_hotkey(self) -> None:
        if not self._transcriber.is_ready():
            self._tray.notify("WhisprTap", "Model is still loading. Please wait...")
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
            print(f"[WhisprTap] Recording error: {e}", file=sys.stderr)
            self._tray.set_state(TrayState.ERROR)
            self._tray.notify("WhisprTap - Error", f"Microphone is unavailable: {e}")

    def _stop_and_transcribe(self) -> None:
        self._tray.set_state(TrayState.PROCESSING)
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _transcribe_worker(self) -> None:
        try:
            audio_path = self._recorder.stop()
            if audio_path is None:
                self._tray.notify("WhisprTap", "Recording was too short.")
                return

            text = self._transcriber.transcribe(audio_path)
            audio_path.unlink(missing_ok=True)

            if text:
                auto_paste = self._cfg.get("auto_paste", True)
                insertion = self._inserter.insert(text, auto_paste=auto_paste)
                suffix = "..." if len(text) > 60 else ""
                if insertion.error:
                    print(f"[WhisprTap] Text insertion warning: {insertion.error}", file=sys.stderr)
                if auto_paste and insertion.paste_attempted and not insertion.pasted:
                    message = (
                        "Auto-Paste failed; transcript copied to clipboard."
                        if insertion.copied
                        else "Auto-Paste failed; transcript could not be copied."
                    )
                    self._tray.notify("WhisprTap - Error", message)
                elif not insertion.copied:
                    self._tray.notify("WhisprTap - Error", "Transcript could not be copied.")
                else:
                    self._tray.notify("WhisprTap", f"{text[:60]}{suffix}")
            else:
                self._tray.notify("WhisprTap", "No text detected.")

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            print(f"[WhisprTap] Transcription error: {e}", file=sys.stderr)
            self._tray.notify("WhisprTap - Error", f"Transcription failed: {e}")
        finally:
            if not self._recorder.is_recording:
                self._tray.set_state(TrayState.IDLE)

    def _open_settings(self) -> None:
        self._settings_window.open()

    def _apply_config(self, new_cfg: dict) -> None:
        old_device = resolve_input_device_index(self._cfg)
        new_device = resolve_input_device_index(new_cfg)
        self._cfg = new_cfg

        if self._hotkey_manager:
            self._hotkey_manager.update_hotkey(new_cfg["hotkey"])
        if not self._recorder.is_recording and new_device != old_device:
            self._recorder = Recorder(device=new_device)

        model_changed = (
            new_cfg["model_size"] != self._transcriber._model_size
            or new_cfg["language"] != self._transcriber._language
            or new_cfg.get("model_dir") != self._transcriber._model_dir
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
        self._tray.notify("WhisprTap", f"Loading model '{self._cfg['model_size']}'...")
        threading.Thread(
            target=self._load_model,
            args=(new_transcriber, generation),
            daemon=True,
        ).start()

    def _quit(self) -> None:
        self._settings_window.close()
        if self._recorder.is_recording:
            self._recorder.stop()
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        self._tray.stop()


if __name__ == "__main__":
    App().run()
