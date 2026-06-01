import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import config
from hotkey_manager import record_hotkey


class SettingsWindow:
    def __init__(self, root: tk.Tk, on_save: Callable[[dict], None]):
        self._root = root
        self._on_save = on_save
        self._window: tk.Toplevel | None = None
        self._lock = threading.Lock()

    def open(self) -> None:
        self._root.after(0, self._open_on_main_thread)

    def _open_on_main_thread(self) -> None:
        with self._lock:
            if self._window and self._window.winfo_exists():
                self._window.lift()
                return
            self._build()

    def _build(self) -> None:
        cfg = config.load()

        win = tk.Toplevel(self._root)
        self._window = win
        win.title("WhisprTap — Einstellungen")
        win.resizable(False, False)
        win.geometry("360x260")

        pad = {"padx": 12, "pady": 6}

        # Hotkey
        tk.Label(win, text="Hotkey:").grid(row=0, column=0, sticky="w", **pad)
        hotkey_var = tk.StringVar(value=cfg["hotkey"])
        hotkey_entry = tk.Entry(win, textvariable=hotkey_var, state="readonly", width=20)
        hotkey_entry.grid(row=0, column=1, sticky="w", **pad)

        def record():
            hotkey_entry.config(state="normal")
            hotkey_var.set("Taste drücken...")
            hotkey_entry.config(state="readonly")
            save_btn.config(state="disabled")
            win.update()

            def _record():
                key = record_hotkey(timeout=5.0)
                if key:
                    win.after(0, lambda: hotkey_var.set(key))
                win.after(0, lambda: save_btn.config(state="normal"))

            threading.Thread(target=_record, daemon=True).start()

        tk.Button(win, text="Aufzeichnen", command=record).grid(row=0, column=2, **pad)

        # Modellgröße
        tk.Label(win, text="Modellgröße:").grid(row=1, column=0, sticky="w", **pad)
        model_var = tk.StringVar(value=cfg["model_size"])
        ttk.Combobox(
            win,
            textvariable=model_var,
            values=["tiny", "small", "medium", "large"],
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", **pad)

        # Sprache
        tk.Label(win, text="Sprache:").grid(row=2, column=0, sticky="w", **pad)
        lang_var = tk.StringVar(value=cfg["language"])
        ttk.Combobox(
            win,
            textvariable=lang_var,
            values=["de", "en", "auto"],
            state="readonly",
            width=18,
        ).grid(row=2, column=1, sticky="w", **pad)

        # Auto-Paste
        tk.Label(win, text="Auto-Paste:").grid(row=3, column=0, sticky="w", **pad)
        paste_var = tk.BooleanVar(value=cfg["auto_paste"])
        tk.Checkbutton(win, variable=paste_var).grid(row=3, column=1, sticky="w", **pad)

        def save():
            new_cfg = config.load()
            new_cfg["hotkey"] = hotkey_var.get()
            new_cfg["model_size"] = model_var.get()
            new_cfg["language"] = lang_var.get()
            new_cfg["auto_paste"] = paste_var.get()
            config.save(new_cfg)
            self._on_save(new_cfg)
            win.destroy()

        btn_frame = tk.Frame(win)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=16)
        save_btn = tk.Button(btn_frame, text="Speichern", command=save, width=12)
        save_btn.pack(side="left", padx=6)
        tk.Button(btn_frame, text="Abbrechen", command=win.destroy, width=12).pack(side="left", padx=6)
