from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

import AppKit
import ApplicationServices
import Quartz


COMMAND_V_KEYCODE = 9


@dataclass(frozen=True)
class InsertionResult:
    copied: bool
    paste_attempted: bool
    pasted: bool
    error: str | None = None


class TextInserter(ABC):
    @abstractmethod
    def insert(self, text: str, auto_paste: bool = True) -> InsertionResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


def create_inserter() -> "TextInserter":
    return MacOSTextInserter()


class QuartzCommandVEventSender:
    def __init__(self, quartz=Quartz):
        self._quartz = quartz

    def send_command_v(self) -> None:
        down = self._quartz.CGEventCreateKeyboardEvent(None, COMMAND_V_KEYCODE, True)
        up = self._quartz.CGEventCreateKeyboardEvent(None, COMMAND_V_KEYCODE, False)
        if down is None or up is None:
            raise RuntimeError("Could not create Command-V keyboard event.")

        for event in (down, up):
            self._quartz.CGEventSetFlags(event, self._quartz.kCGEventFlagMaskCommand)
            self._quartz.CGEventPost(self._quartz.kCGHIDEventTap, event)


class MacOSTextInserter(TextInserter):
    """macOS insertion through the clipboard and an optional Command-V paste."""

    def __init__(
        self,
        *,
        pasteboard=None,
        accessibility_check: Callable[[], bool] | None = None,
        event_sender: QuartzCommandVEventSender | None = None,
        paste_delay: float = 0.1,
    ):
        self._pasteboard = pasteboard or AppKit.NSPasteboard.generalPasteboard()
        self._accessibility_check = accessibility_check or ApplicationServices.AXIsProcessTrusted
        self._event_sender = event_sender or QuartzCommandVEventSender()
        self._paste_delay = paste_delay

    def is_available(self) -> bool:
        return True

    def insert(self, text: str, auto_paste: bool = True) -> InsertionResult:
        try:
            self._copy_to_clipboard(text)
        except Exception as exc:
            return InsertionResult(
                copied=False,
                paste_attempted=False,
                pasted=False,
                error=f"Clipboard copy failed: {exc}",
            )

        if not auto_paste:
            return InsertionResult(copied=True, paste_attempted=False, pasted=False)

        if not self._accessibility_check():
            return InsertionResult(
                copied=True,
                paste_attempted=True,
                pasted=False,
                error="Accessibility permission is required for Auto-Paste.",
            )

        try:
            if self._paste_delay > 0:
                time.sleep(self._paste_delay)
            self._event_sender.send_command_v()
        except Exception as exc:
            return InsertionResult(
                copied=True,
                paste_attempted=True,
                pasted=False,
                error=f"Command-V paste failed: {exc}",
            )

        return InsertionResult(copied=True, paste_attempted=True, pasted=True)

    def _copy_to_clipboard(self, text: str) -> None:
        self._pasteboard.clearContents()
        copied = self._pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)
        if not copied:
            raise RuntimeError("NSPasteboard rejected plain text content.")
