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
                ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text],
                timeout=10,
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

        # Versuch 1: ydotool type (braucht /dev/uinput-Gruppenrechte, siehe scripts/setup_uinput.sh)
        if shutil.which("ydotool"):
            result = subprocess.run(
                ["ydotool", "type", "--", text],
                timeout=10,
                capture_output=True,
            )
            if result.returncode == 0:
                return

        # Versuch 2: wtype (native Wayland, keine Root-Rechte nötig)
        if shutil.which("wtype"):
            try:
                subprocess.run(["wtype", "--", text], timeout=10, capture_output=True)
                return
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Versuch 3: xdotool type via XWayland
        if shutil.which("xdotool") and os.environ.get("DISPLAY"):
            try:
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text],
                    timeout=10,
                    capture_output=True,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass


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
