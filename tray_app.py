import queue
import threading
from enum import Enum, auto
from typing import Callable

import rumps


class TrayState(Enum):
    IDLE = auto()
    LOADING = auto()
    RECORDING = auto()
    PROCESSING = auto()
    ERROR = auto()


_TITLES = {
    TrayState.IDLE: "WhisprTap",
    TrayState.LOADING: "WhisprTap Loading",
    TrayState.RECORDING: "WhisprTap Recording",
    TrayState.PROCESSING: "WhisprTap Processing",
    TrayState.ERROR: "WhisprTap Error",
}

_STATUS_TEXT = {
    TrayState.IDLE: "Status: Ready",
    TrayState.LOADING: "Status: Loading model...",
    TrayState.RECORDING: "Status: Recording",
    TrayState.PROCESSING: "Status: Processing...",
    TrayState.ERROR: "Status: Error",
}


class TrayApp(rumps.App):
    def __init__(
        self,
        on_settings: Callable[[], None],
        on_reload_model: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        super().__init__("WhisprTap", title=_TITLES[TrayState.LOADING], quit_button=None)
        self._on_settings = on_settings
        self._on_reload_model = on_reload_model
        self._on_quit = on_quit
        self._state = TrayState.LOADING
        self._ui_queue: queue.Queue[tuple] = queue.Queue()
        self._timer = rumps.Timer(self._drain_queue, 0.1)

        self._status_item = rumps.MenuItem(_STATUS_TEXT[self._state], callback=None)
        self.menu = [
            self._status_item,
            None,
            rumps.MenuItem("Settings...", callback=self._settings_clicked),
            rumps.MenuItem("Reload Model", callback=self._reload_clicked),
            None,
            rumps.MenuItem("Quit", callback=self._quit_clicked),
        ]

    def start(self) -> None:
        self._apply_state(self._state)
        self._timer.start()
        self.run()

    def set_state(self, state: TrayState) -> None:
        self._ui_queue.put(("state", state))

    def notify(self, title: str, message: str) -> None:
        self._ui_queue.put(("notify", title, message))

    def stop(self) -> None:
        self._ui_queue.put(("quit",))

    def _apply_state(self, state: TrayState) -> None:
        self._state = state
        self.title = _TITLES.get(state, "WhisprTap")
        self._status_item.title = _STATUS_TEXT.get(state, "Status: WhisprTap")

    def _drain_queue(self, _sender) -> None:
        while True:
            try:
                item = self._ui_queue.get_nowait()
            except queue.Empty:
                return

            kind = item[0]
            if kind == "state":
                self._apply_state(item[1])
            elif kind == "notify":
                _, title, message = item
                rumps.notification(title, "", message)
            elif kind == "quit":
                self._timer.stop()
                rumps.quit_application()
                return

    def _settings_clicked(self, _sender) -> None:
        self._on_settings()

    def _reload_clicked(self, _sender) -> None:
        threading.Thread(target=self._on_reload_model, daemon=True).start()

    def _quit_clicked(self, _sender) -> None:
        threading.Thread(target=self._on_quit, daemon=True).start()
