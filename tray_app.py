import subprocess
import threading
from enum import Enum, auto
from typing import Callable

from PIL import Image, ImageDraw
import pystray


class TrayState(Enum):
    IDLE = auto()
    LOADING = auto()
    RECORDING = auto()
    PROCESSING = auto()
    ERROR = auto()


def _make_icon(state: TrayState) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    colors = {
        TrayState.IDLE: (255, 255, 255, 230),
        TrayState.LOADING: (160, 160, 160, 200),
        TrayState.RECORDING: (220, 50, 50, 255),
        TrayState.PROCESSING: (50, 150, 255, 255),
        TrayState.ERROR: (220, 50, 50, 255),
    }
    color = colors[state]

    if state == TrayState.RECORDING:
        # Roter Kreis
        draw.ellipse([8, 8, 56, 56], fill=color)
    elif state == TrayState.ERROR:
        # Rotes X
        draw.line([12, 12, 52, 52], fill=color, width=8)
        draw.line([52, 12, 12, 52], fill=color, width=8)
    elif state == TrayState.PROCESSING:
        # Blauer Halbkreis (Verarbeitung)
        draw.arc([8, 8, 56, 56], start=0, end=270, fill=color, width=8)
    else:
        # Mikrofon-Symbol (vereinfacht)
        draw.rounded_rectangle([22, 4, 42, 38], radius=10, fill=color)
        draw.arc([14, 28, 50, 52], start=0, end=180, fill=color, width=4)
        draw.line([32, 52, 32, 60], fill=color, width=4)
        draw.line([22, 60, 42, 60], fill=color, width=4)

    return img


def _notify(title: str, message: str) -> None:
    try:
        subprocess.Popen(
            ["notify-send", title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


class TrayApp:
    def __init__(
        self,
        on_settings: Callable[[], None],
        on_reload_model: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_settings = on_settings
        self._on_reload_model = on_reload_model
        self._on_quit = on_quit
        self._state = TrayState.LOADING
        self._icon: pystray.Icon | None = None

    def start(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Einstellungen...", self._settings_clicked),
            pystray.MenuItem("Modell neu laden", self._reload_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._quit_clicked),
        )
        self._icon = pystray.Icon(
            "WhisprTap",
            _make_icon(self._state),
            "WhisprTap",
            menu,
        )
        self._icon.run()

    def set_state(self, state: TrayState) -> None:
        self._state = state
        if self._icon:
            self._icon.icon = _make_icon(state)
            titles = {
                TrayState.IDLE: "WhisprTap",
                TrayState.LOADING: "WhisprTap - Modell ladet...",
                TrayState.RECORDING: "WhisprTap - Aufnahme laeuft",
                TrayState.PROCESSING: "WhisprTap - Verarbeite...",
                TrayState.ERROR: "WhisprTap - Fehler",
            }
            self._icon.title = titles.get(state, "WhisprTap")

    def notify(self, title: str, message: str) -> None:
        threading.Thread(target=_notify, args=(title, message), daemon=True).start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def _settings_clicked(self, icon, item) -> None:
        threading.Thread(target=self._on_settings, daemon=True).start()

    def _reload_clicked(self, icon, item) -> None:
        threading.Thread(target=self._on_reload_model, daemon=True).start()

    def _quit_clicked(self, icon, item) -> None:
        self._on_quit()
