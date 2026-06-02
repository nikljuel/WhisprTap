import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod


class TextInserter(ABC):
    @abstractmethod
    def insert(self, text: str, auto_paste: bool = True) -> None:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


def create_inserter() -> "TextInserter":
    """Wählt automatisch den richtigen Inserter basierend auf der Session."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        return WaylandTextInserter()
    return XdotoolTextInserter()


class XdotoolTextInserter(TextInserter):
    """X11: Zwischenablage via xclip + Auto-Paste via xdotool."""

    def is_available(self) -> bool:
        return shutil.which("xdotool") is not None

    def insert(self, text: str, auto_paste: bool = True) -> None:
        _copy_xclip(text)

        if not auto_paste or not self.is_available():
            return

        try:
            time.sleep(0.1)
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                timeout=2,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


class WaylandTextInserter(TextInserter):
    """Wayland: Zwischenablage via wl-copy + Auto-Paste via ydotool."""

    def is_available(self) -> bool:
        return shutil.which("wl-copy") is not None

    def insert(self, text: str, auto_paste: bool = True) -> None:
        _copy_wl(text)

        if not auto_paste:
            return

        time.sleep(0.1)

        # Versuch 1: ydotool type — tippt zeichenweise ein (funktioniert in Terminal + Editoren)
        # ydotool 0.1.8 ignoriert das Tastaturlayout und nutzt QWERTY-Keycodes. Auf QWERTZ
        # werden Z und Y vertauscht → wir kompensieren durch Vorkorrektur im Text.
        if shutil.which("ydotool"):
            result = subprocess.run(
                ["ydotool", "type", "--", _qwertz_fix(text)],
                timeout=30,
                capture_output=True,
            )
            if result.returncode == 0:
                return

        # Versuch 2: xdotool type via XWayland (layout-aware, kein Z/Y-Problem)
        if shutil.which("xdotool") and os.environ.get("DISPLAY"):
            try:
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text],
                    timeout=30,
                    capture_output=True,
                )
                return
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Fallback: Ctrl+V aus Zwischenablage (Text liegt bereits dort via wl-copy)
        if shutil.which("ydotool"):
            subprocess.run(["ydotool", "key", "ctrl+v"], timeout=2, capture_output=True)


def _qwertz_fix(text: str) -> str:
    """Kompensiert ydotool's QWERTY-Keycode-Mapping auf QWERTZ-Tastaturen.
    ydotool sendet für 'z' → KEY_Z, was auf QWERTZ 'y' produziert. Vorher tauschen
    damit der Compositor das richtige Zeichen ausgibt."""
    result = []
    for ch in text:
        if ch == 'z':
            result.append('y')
        elif ch == 'y':
            result.append('z')
        elif ch == 'Z':
            result.append('Y')
        elif ch == 'Y':
            result.append('Z')
        else:
            result.append(ch)
    return ''.join(result)


def _copy_xclip(text: str) -> None:
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode("utf-8"),
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass


def _copy_wl(text: str) -> None:
    try:
        subprocess.run(
            ["wl-copy"],
            input=text.encode("utf-8"),
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass
