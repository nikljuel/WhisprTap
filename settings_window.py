import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import sounddevice as sd

import autostart
import config
from hotkey_manager import record_hotkey

SIDEBAR_BG = "#e8e8e8"
SIDEBAR_HOVER = "#d0d0d0"
SIDEBAR_ACTIVE_BG = "#ffffff"
SIDEBAR_FG = "#333333"
CONTENT_BG = "#ffffff"
ACCENT = "#0066cc"
SEPARATOR_COLOR = "#cccccc"


def _get_input_devices() -> list[tuple[int, str]]:
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append((i, dev["name"]))
    return devices


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
        win.resizable(True, True)
        win.configure(bg=SEPARATOR_COLOR)

        # ── Hauptlayout: Sidebar | Trennlinie | Content ──────────────────
        outer = tk.Frame(win, bg=SEPARATOR_COLOR)
        outer.pack(fill="both", expand=True)

        sidebar = tk.Frame(outer, bg=SIDEBAR_BG, width=160)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Frame(outer, bg=SEPARATOR_COLOR, width=1).pack(side="left", fill="y")

        content_area = tk.Frame(outer, bg=CONTENT_BG)
        content_area.pack(side="left", fill="both", expand=True)

        # ── Pages (übereinandergestapelt) ─────────────────────────────────
        pages: dict[str, tk.Frame] = {}

        content_area.grid_rowconfigure(0, weight=1)
        content_area.grid_columnconfigure(0, weight=1)

        def make_page(name: str) -> tk.Frame:
            f = tk.Frame(content_area, bg=CONTENT_BG)
            f.grid(row=0, column=0, sticky="nsew")
            pages[name] = f
            return f

        # ── Sidebar-Navigation ────────────────────────────────────────────
        nav_items: list[tuple[tk.Frame, tk.Label]] = []
        active_page: list[str] = [""]

        def select_page(name: str) -> None:
            active_page[0] = name
            pages[name].tkraise()
            for item_name, (bar, lbl) in zip(
                [n for n, _ in nav_items_map], nav_items
            ):
                if item_name == name:
                    bar.configure(bg=ACCENT)
                    lbl.configure(bg=SIDEBAR_ACTIVE_BG, fg="#000000",
                                  font=("TkDefaultFont", 11, "bold"))
                    lbl.master.configure(bg=SIDEBAR_ACTIVE_BG)
                else:
                    bar.configure(bg=SIDEBAR_BG)
                    lbl.configure(bg=SIDEBAR_BG, fg=SIDEBAR_FG,
                                  font=("TkDefaultFont", 11))
                    lbl.master.configure(bg=SIDEBAR_BG)

        nav_items_map: list[tuple[str, str]] = [
            ("Einstellungen", "⚙  Einstellungen"),
        ]

        for page_name, label_text in nav_items_map:
            row_frame = tk.Frame(sidebar, bg=SIDEBAR_BG, cursor="hand2")
            row_frame.pack(fill="x", pady=(4, 0))

            accent_bar = tk.Frame(row_frame, bg=SIDEBAR_BG, width=3)
            accent_bar.pack(side="left", fill="y")

            lbl = tk.Label(
                row_frame,
                text=label_text,
                bg=SIDEBAR_BG,
                fg=SIDEBAR_FG,
                font=("TkDefaultFont", 11),
                anchor="w",
                padx=10,
                pady=8,
            )
            lbl.pack(side="left", fill="x", expand=True)

            nav_items.append((accent_bar, lbl))

            def _make_handler(name):
                def on_click(_event=None):
                    select_page(name)
                return on_click

            def _make_hover(frame, bar, label, is_active_check, name):
                def on_enter(_):
                    if active_page[0] != name:
                        frame.configure(bg=SIDEBAR_HOVER)
                        bar.configure(bg=SIDEBAR_HOVER)
                        label.configure(bg=SIDEBAR_HOVER)
                def on_leave(_):
                    if active_page[0] != name:
                        frame.configure(bg=SIDEBAR_BG)
                        bar.configure(bg=SIDEBAR_BG)
                        label.configure(bg=SIDEBAR_BG)
                return on_enter, on_leave

            handler = _make_handler(page_name)
            on_enter, on_leave = _make_hover(row_frame, accent_bar, lbl, active_page, page_name)

            for widget in (row_frame, lbl):
                widget.bind("<Button-1>", handler)
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)

        # ── Page: Einstellungen ───────────────────────────────────────────
        page = make_page("Einstellungen")
        pad = {"padx": 20, "pady": 7}

        tk.Label(page, text="Einstellungen", bg=CONTENT_BG,
                 font=("TkDefaultFont", 14, "bold"), fg="#111111").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(18, 10))

        # Hotkey
        tk.Label(page, text="Hotkey:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=1, column=0, sticky="w", **pad)
        hotkey_var = tk.StringVar(value=cfg["hotkey"])
        hotkey_entry = tk.Entry(page, textvariable=hotkey_var, state="readonly", width=16)
        hotkey_entry.grid(row=1, column=1, sticky="w", **pad)

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

        tk.Button(page, text="Aufzeichnen", command=record).grid(row=1, column=2, **pad)

        # Modellgröße
        tk.Label(page, text="Modellgröße:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=2, column=0, sticky="w", **pad)
        model_var = tk.StringVar(value=cfg["model_size"])
        ttk.Combobox(page, textvariable=model_var,
                     values=["tiny", "small", "medium", "large"],
                     state="readonly", width=16).grid(row=2, column=1, sticky="w", **pad)

        # Sprache
        tk.Label(page, text="Sprache:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=3, column=0, sticky="w", **pad)
        lang_var = tk.StringVar(value=cfg["language"])
        ttk.Combobox(page, textvariable=lang_var,
                     values=["de", "en", "auto"],
                     state="readonly", width=16).grid(row=3, column=1, sticky="w", **pad)

        # Auto-Paste
        tk.Label(page, text="Auto-Paste:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=4, column=0, sticky="w", **pad)
        paste_var = tk.BooleanVar(value=cfg["auto_paste"])
        tk.Checkbutton(page, variable=paste_var, bg=CONTENT_BG).grid(
            row=4, column=1, sticky="w", **pad)

        # Mikrofon
        tk.Label(page, text="Mikrofon:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=5, column=0, sticky="w", **pad)
        input_devices = _get_input_devices()
        device_labels = ["System-Standard"] + [f"{i}: {name}" for i, name in input_devices]
        device_indices = [None] + [i for i, _ in input_devices]
        saved_device = cfg.get("input_device")
        try:
            default_device_label = device_labels[device_indices.index(saved_device)]
        except ValueError:
            default_device_label = device_labels[0]
        device_var = tk.StringVar(value=default_device_label)
        ttk.Combobox(page, textvariable=device_var, values=device_labels,
                     state="readonly", width=28).grid(
            row=5, column=1, columnspan=2, sticky="w", **pad)

        # Autostart
        tk.Label(page, text="Autostart:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=6, column=0, sticky="w", **pad)
        autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        tk.Checkbutton(page, variable=autostart_var, bg=CONTENT_BG).grid(
            row=6, column=1, sticky="w", **pad)

        # Speichern / Abbrechen
        def save():
            new_cfg = config.load()
            new_cfg["hotkey"] = hotkey_var.get()
            new_cfg["model_size"] = model_var.get()
            new_cfg["language"] = lang_var.get()
            new_cfg["auto_paste"] = paste_var.get()
            selected_label = device_var.get()
            new_cfg["input_device"] = device_indices[device_labels.index(selected_label)]
            new_cfg["autostart"] = autostart_var.get()
            autostart.apply(autostart_var.get())
            config.save(new_cfg)
            self._on_save(new_cfg)
            win.destroy()

        btn_frame = tk.Frame(page, bg=CONTENT_BG)
        btn_frame.grid(row=7, column=0, columnspan=3, sticky="e", padx=20, pady=(10, 18))
        save_btn = tk.Button(btn_frame, text="Speichern", command=save, width=12)
        save_btn.pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Abbrechen", command=win.destroy, width=12).pack(side="left")

        # Erste Seite aktivieren
        select_page("Einstellungen")

        # Fenstergröße an Inhalt anpassen und als Minimum setzen
        win.update_idletasks()
        win.minsize(win.winfo_reqwidth(), win.winfo_reqheight())
