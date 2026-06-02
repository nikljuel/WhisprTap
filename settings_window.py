import shutil
import threading
import tkinter as tk
from pathlib import Path
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


def _scan_downloaded_models(model_dir: str) -> list[tuple[str, Path, int]]:
    """Gibt Liste von (modellname, pfad, bytes) aller heruntergeladenen Modelle zurück."""
    base = Path(model_dir)
    if not base.exists():
        return []
    results = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or not d.name.startswith("models--"):
            continue
        # models--Systran--faster-whisper-medium  → medium
        # models--Systran--faster-distil-whisper-large-v3 → distil-large-v3
        name = d.name.removeprefix("models--Systran--faster-whisper-")
        name = name.removeprefix("models--Systran--faster-distil-whisper-")
        if name.startswith("models--"):
            continue  # unbekanntes Format überspringen
        blobs = d / "blobs"
        size = sum(f.stat().st_size for f in blobs.iterdir() if f.is_file()) if blobs.exists() else 0
        results.append((name, d, size))
    return results


def _fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    return f"{n / 1_000_000:.0f} MB"


def _open_model_manager(parent: tk.Toplevel, cfg: dict) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Modelle verwalten")
    dlg.resizable(False, False)
    dlg.grab_set()

    model_dir = cfg.get("model_dir", str(Path.home() / ".whisprtap" / "models"))

    container = tk.Frame(dlg, bg=CONTENT_BG)
    container.pack(fill="both", expand=True, padx=16, pady=12)

    header = tk.Label(container, text="Heruntergeladene Modelle",
                      bg=CONTENT_BG, font=("TkDefaultFont", 12, "bold"), anchor="w")
    header.pack(fill="x", pady=(0, 8))

    list_frame = tk.Frame(container, bg=CONTENT_BG)
    list_frame.pack(fill="both", expand=True)

    def refresh():
        for w in list_frame.winfo_children():
            w.destroy()
        models = _scan_downloaded_models(model_dir)
        if not models:
            tk.Label(list_frame, text="Keine Modelle heruntergeladen.",
                     bg=CONTENT_BG, fg="#888888").pack(anchor="w")
            return
        for name, path, size in models:
            row = tk.Frame(list_frame, bg=CONTENT_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, bg=CONTENT_BG, width=22, anchor="w",
                     font=("TkDefaultFont", 10)).pack(side="left")
            tk.Label(row, text=_fmt_size(size), bg=CONTENT_BG, fg="#555555",
                     width=8, anchor="e").pack(side="left")

            def _delete(p=path, n=name):
                shutil.rmtree(p, ignore_errors=True)
                # Locks-Verzeichnis ebenfalls entfernen
                locks = Path(model_dir) / ".locks" / p.name
                if locks.exists():
                    shutil.rmtree(locks, ignore_errors=True)
                refresh()

            tk.Button(row, text="Löschen", fg="#cc0000",
                      command=_delete, padx=6).pack(side="right", padx=(8, 0))
            tk.Frame(list_frame, bg=SEPARATOR_COLOR, height=1).pack(fill="x", pady=(2, 0))

    refresh()

    tk.Button(container, text="Schließen", command=dlg.destroy, width=10).pack(
        anchor="e", pady=(12, 0))


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
        tk.Label(page, text="Modell:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=2, column=0, sticky="w", **pad)
        models = [
            "tiny", "base", "small", "medium",
            "large-v1", "large-v2", "large-v3",
            "distil-small.en", "distil-medium.en", "distil-large-v2", "distil-large-v3",
        ]
        model_var = tk.StringVar(value=cfg["model_size"])
        model_box = ttk.Combobox(page, textvariable=model_var,
                     values=models, state="readonly", width=20)
        model_box.grid(row=2, column=1, sticky="w", **pad)
        tk.Button(page, text="Verwalten", command=lambda: _open_model_manager(win, cfg)).grid(
            row=2, column=2, sticky="w", padx=(0, 12), pady=6)

        model_info = {
            "tiny":             "~75 MB  — sehr schnell, ungenau",
            "base":             "~145 MB — schnell",
            "small":            "~465 MB — gute Balance",
            "medium":           "~1.5 GB — empfohlen",
            "large-v1":         "~3 GB   — sehr genau",
            "large-v2":         "~3 GB   — sehr genau (v2)",
            "large-v3":         "~3 GB   — aktuellste Version",
            "distil-small.en":  "~335 MB — schnell (nur Englisch)",
            "distil-medium.en": "~790 MB — schnell (nur Englisch)",
            "distil-large-v2":  "~1.5 GB — schnell, mehrsprachig",
            "distil-large-v3":  "~1.5 GB — schnell, mehrsprachig (v3)",
        }
        info_lbl = tk.Label(page, text=model_info.get(cfg["model_size"], ""),
                            bg=CONTENT_BG, fg="#888888",
                            font=("TkDefaultFont", 9), anchor="w")
        info_lbl.grid(row=3, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 4))

        def _on_model_change(*_):
            info_lbl.config(text=model_info.get(model_var.get(), ""))
        model_var.trace_add("write", _on_model_change)

        # Sprache
        tk.Label(page, text="Sprache:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=4, column=0, sticky="w", **pad)
        lang_var = tk.StringVar(value=cfg["language"])
        ttk.Combobox(page, textvariable=lang_var,
                     values=["de", "en", "auto"],
                     state="readonly", width=16).grid(row=4, column=1, sticky="w", **pad)

        # Auto-Paste
        tk.Label(page, text="Auto-Paste:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=5, column=0, sticky="w", **pad)
        paste_var = tk.BooleanVar(value=cfg["auto_paste"])
        tk.Checkbutton(page, variable=paste_var, bg=CONTENT_BG).grid(
            row=5, column=1, sticky="w", **pad)

        # Mikrofon
        tk.Label(page, text="Mikrofon:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=6, column=0, sticky="w", **pad)
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
            row=6, column=1, columnspan=2, sticky="w", **pad)

        # Autostart
        tk.Label(page, text="Autostart:", bg=CONTENT_BG, anchor="w", width=14).grid(
            row=7, column=0, sticky="w", **pad)
        autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        tk.Checkbutton(page, variable=autostart_var, bg=CONTENT_BG).grid(
            row=7, column=1, sticky="w", **pad)

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
        btn_frame.grid(row=8, column=0, columnspan=3, sticky="e", padx=20, pady=(10, 18))
        save_btn = tk.Button(btn_frame, text="Speichern", command=save, width=12)
        save_btn.pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Abbrechen", command=win.destroy, width=12).pack(side="left")

        # Erste Seite aktivieren
        select_page("Einstellungen")

        # Fenstergröße an Inhalt anpassen und als Minimum setzen
        win.update_idletasks()
        win.minsize(win.winfo_reqwidth(), win.winfo_reqheight())
