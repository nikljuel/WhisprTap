import select
import threading
from typing import Callable

import evdev


def _key_to_code(name: str) -> int | None:
    code = getattr(evdev.ecodes, "KEY_" + name.upper(), None)
    return code


def _code_to_key(code: int) -> str:
    name = evdev.ecodes.KEY.get(code, "")
    if isinstance(name, list):
        name = name[0]
    if isinstance(name, str) and name.startswith("KEY_"):
        return name[4:].lower()
    return ""


def _find_keyboards() -> list:
    devices = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
            keys = d.capabilities().get(evdev.ecodes.EV_KEY, [])
            if evdev.ecodes.KEY_A in keys:
                devices.append(d)
        except Exception:
            pass
    return devices


class HotkeyManager:
    def __init__(self, hotkey: str, on_press: Callable[[], None]):
        self._hotkey = hotkey
        self._on_press = on_press
        self._stop_event = threading.Event()
        self._stop_event.set()  # kein start() noch aufgerufen
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        stop_event = threading.Event()
        self._stop_event = stop_event
        for device in _find_keyboards():
            t = threading.Thread(target=self._listen, args=(device, stop_event), daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop_event.set()
        self._threads.clear()

    def update_hotkey(self, hotkey: str) -> None:
        self.stop()
        self._hotkey = hotkey
        self.start()

    def _listen(self, device: evdev.InputDevice, stop_event: threading.Event) -> None:
        target = _key_to_code(self._hotkey)
        if target is None:
            return
        try:
            while not stop_event.is_set():
                r, _, _ = select.select([device.fd], [], [], 0.1)
                if r:
                    for event in device.read():
                        if (event.type == evdev.ecodes.EV_KEY
                                and event.code == target
                                and event.value == 1):
                            self._on_press()
        except Exception:
            pass


def record_hotkey(timeout: float = 5.0) -> str | None:
    """Wartet auf einen einzelnen Tastendruck und gibt den Hotkey-Namen zurück."""
    result: list[str] = []
    done = threading.Event()

    def listen_device(device: evdev.InputDevice) -> None:
        try:
            while not done.is_set():
                r, _, _ = select.select([device.fd], [], [], 0.1)
                if r:
                    for event in device.read():
                        if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                            name = _code_to_key(event.code)
                            if name and not result:
                                result.append(name)
                                done.set()
        except Exception:
            pass

    threads = [
        threading.Thread(target=listen_device, args=(d,), daemon=True)
        for d in _find_keyboards()
    ]
    for t in threads:
        t.start()

    done.wait(timeout=timeout)
    done.set()

    return result[0] if result else None
