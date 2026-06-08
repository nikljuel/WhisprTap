import threading
from typing import Callable

from pynput import keyboard

_ALIASES = {
    "cmd": "command",
    "cmd_l": "command",
    "cmd_r": "command",
    "command_l": "command",
    "command_r": "command",
    "ctrl": "control",
    "ctrl_l": "control",
    "ctrl_r": "control",
    "control_l": "control",
    "control_r": "control",
    "alt_l": "alt",
    "alt_r": "alt",
    "option": "alt",
    "option_l": "alt",
    "option_r": "alt",
    "esc": "escape",
    "return": "enter",
}


def normalize_hotkey(value: object) -> str | None:
    """Return the stable config name for a pynput key or user-entered key name."""
    if value is None:
        return None

    name = getattr(value, "name", None)
    if not name:
        char = getattr(value, "char", None)
        if char:
            name = char
        else:
            name = str(value)

    key = str(name).strip().lower()
    if key.startswith("<") and key.endswith(">"):
        key = key[1:-1]
    if key.startswith("key."):
        key = key[4:]
    if key.startswith("'") and key.endswith("'") and len(key) >= 2:
        key = key[1:-1]

    key = key.replace(" ", "")
    if not key:
        return None
    return _ALIASES.get(key, key)


class HotkeyManager:
    def __init__(self, hotkey: str, on_press: Callable[[], None]):
        self._hotkey = normalize_hotkey(hotkey)
        self._on_press = on_press
        self._listener: keyboard.Listener | None = None
        self._pressed: set[str] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        self.stop()
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        with self._lock:
            self._pressed.clear()
        if listener:
            listener.stop()

    def update_hotkey(self, hotkey: str) -> None:
        self.stop()
        self._hotkey = normalize_hotkey(hotkey)
        self.start()

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        pressed = normalize_hotkey(key)
        if pressed != self._hotkey:
            return

        with self._lock:
            if pressed in self._pressed:
                return
            self._pressed.add(pressed)

        self._on_press()

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        released = normalize_hotkey(key)
        if released:
            with self._lock:
                self._pressed.discard(released)


def record_hotkey(timeout: float = 5.0) -> str | None:
    """Wait for one key press and return its normalized config name."""
    result: list[str] = []
    done = threading.Event()

    def on_press(key: keyboard.Key | keyboard.KeyCode) -> bool:
        name = normalize_hotkey(key)
        if name:
            result.append(name)
            done.set()
            return False
        return True

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    done.wait(timeout=timeout)
    listener.stop()

    return result[0] if result else None
