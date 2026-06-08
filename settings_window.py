from __future__ import annotations

import shutil
import sys
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import objc
from Foundation import NSURL
from PyObjCTools import AppHelper

import AppKit
import autostart
import config
from audio_devices import (
    InputDevice,
    coerce_input_devices,
    find_input_device_by_index,
    input_device_config_ref,
    normalized_input_device_config,
    resolve_input_device_index,
    safe_get_input_devices,
)
from hotkey_manager import record_hotkey


SIDEBAR_WIDTH = 178
ACTION_BAR_HEIGHT = 58
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 520
CONTENT_WIDTH = WINDOW_WIDTH - SIDEBAR_WIDTH


MODEL_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("tiny", "Tiny", "About 75 MB. Fastest option, lowest accuracy."),
    ("base", "Base", "About 145 MB. Fast and suitable for short notes."),
    ("small", "Small", "About 465 MB. Good balance for everyday dictation."),
    ("medium", "Medium", "About 1.5 GB. Recommended default."),
    ("large-v1", "Large v1", "About 3 GB. Higher accuracy, slower loading."),
    ("large-v2", "Large v2", "About 3 GB. Higher accuracy, improved model."),
    ("large-v3", "Large v3", "About 3 GB. Latest large multilingual model."),
    ("distil-small.en", "Distil Small English", "About 335 MB. Fast, English only."),
    ("distil-medium.en", "Distil Medium English", "About 790 MB. Fast, English only."),
    ("distil-large-v2", "Distil Large v2", "About 1.5 GB. Faster large model."),
    ("distil-large-v3", "Distil Large v3", "About 1.5 GB. Faster large v3 model."),
)

LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "Automatic"),
    ("de", "German"),
    ("en", "English"),
)


@dataclass(frozen=True)
class SelectOption:
    value: object
    label: str
    detail: str = ""


@dataclass(frozen=True)
class SettingsViewState:
    hotkey: str
    model_size: str
    language: str
    auto_paste: bool
    model_dir: str
    input_device: int | None
    input_device_ref: dict[str, object] | None
    autostart: bool
    model_options: tuple[SelectOption, ...]
    language_options: tuple[SelectOption, ...]
    device_options: tuple[SelectOption, ...]
    input_devices: tuple[InputDevice, ...]
    selected_model_index: int
    selected_language_index: int
    selected_device_index: int
    device_error: str | None = None


def _scan_downloaded_models(model_dir: str) -> list[tuple[str, Path, int]]:
    """Return (model name, path, byte size) for downloaded faster-whisper models."""
    base = Path(model_dir)
    if not base.exists():
        return []
    results = []
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("models--"):
            continue
        name = directory.name.removeprefix("models--Systran--faster-whisper-")
        name = name.removeprefix("models--Systran--faster-distil-whisper-")
        if name.startswith("models--"):
            continue
        blobs = directory / "blobs"
        size = sum(f.stat().st_size for f in blobs.iterdir() if f.is_file()) if blobs.exists() else 0
        results.append((name, directory, size))
    return results


def _fmt_size(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    return f"{n / 1_000_000:.0f} MB"


def _model_options(current_model: str) -> tuple[SelectOption, ...]:
    options = [SelectOption(value=value, label=label, detail=detail) for value, label, detail in MODEL_OPTIONS]
    if current_model and current_model not in {str(option.value) for option in options}:
        options.insert(0, SelectOption(value=current_model, label=f"Custom: {current_model}", detail="Custom model name."))
    return tuple(options)


def _language_options(current_language: str) -> tuple[SelectOption, ...]:
    options = [SelectOption(value=value, label=label) for value, label in LANGUAGE_OPTIONS]
    if current_language and current_language not in {str(option.value) for option in options}:
        options.insert(0, SelectOption(value=current_language, label=f"Custom: {current_language}"))
    return tuple(options)


def _device_options(input_devices: list[InputDevice]) -> tuple[SelectOption, ...]:
    name_counts: dict[str, int] = {}
    for device in input_devices:
        name_counts[device.name] = name_counts.get(device.name, 0) + 1

    def label_for(device: InputDevice) -> str:
        label = device.name
        if name_counts[device.name] > 1 and device.host_api:
            label = f"{label} - {device.host_api}"
        if device.is_default:
            label = f"{label} (Default)"
        return label

    return (
        SelectOption(value=None, label="System Default"),
        *(SelectOption(value=device.index, label=label_for(device)) for device in input_devices),
    )


def _selected_index(options: tuple[SelectOption, ...], value: object) -> int:
    for index, option in enumerate(options):
        if option.value == value:
            return index
    return 0


def build_settings_view_state(
    cfg: dict,
    *,
    input_devices: list[InputDevice | tuple[int, str]] | None = None,
    device_error: str | None = None,
    autostart_enabled: bool | None = None,
) -> SettingsViewState:
    if input_devices is None:
        input_devices, detected_error = safe_get_input_devices()
        device_error = device_error or detected_error
    else:
        input_devices = coerce_input_devices(input_devices)

    model_options = _model_options(str(cfg.get("model_size", config.DEFAULTS["model_size"])))
    language_options = _language_options(str(cfg.get("language", config.DEFAULTS["language"])))
    device_options = _device_options(input_devices)
    model_size = str(cfg.get("model_size", config.DEFAULTS["model_size"]))
    language = str(cfg.get("language", config.DEFAULTS["language"]))
    normalized_cfg = normalized_input_device_config(cfg, input_devices)
    input_device = normalized_cfg.get("input_device")
    input_device_ref = normalized_cfg.get("input_device_ref")
    autostart_value = autostart.is_enabled() if autostart_enabled is None else autostart_enabled

    return SettingsViewState(
        hotkey=str(cfg.get("hotkey", config.DEFAULTS["hotkey"])),
        model_size=model_size,
        language=language,
        auto_paste=bool(cfg.get("auto_paste", config.DEFAULTS["auto_paste"])),
        model_dir=str(cfg.get("model_dir", config.DEFAULTS["model_dir"])),
        input_device=input_device,
        input_device_ref=input_device_ref,
        autostart=bool(autostart_value),
        model_options=model_options,
        language_options=language_options,
        device_options=device_options,
        input_devices=tuple(input_devices),
        selected_model_index=_selected_index(model_options, model_size),
        selected_language_index=_selected_index(language_options, language),
        selected_device_index=_selected_index(device_options, input_device),
        device_error=device_error,
    )


def _font(size: float = 13, weight: float = AppKit.NSFontWeightRegular):
    return AppKit.NSFont.systemFontOfSize_weight_(size, weight)


def _label(text: str, frame, *, size: float = 13, weight: float = AppKit.NSFontWeightRegular, color=None):
    field = AppKit.NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setFont_(_font(size, weight))
    field.setTextColor_(color or AppKit.NSColor.labelColor())
    try:
        field.cell().setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
        field.cell().setWraps_(True)
    except Exception:
        pass
    return field


def _button(title: str, frame, target, action: str):
    button = AppKit.NSButton.alloc().initWithFrame_(frame)
    button.setTitle_(title)
    button.setBezelStyle_(AppKit.NSBezelStyleRounded)
    button.setControlSize_(AppKit.NSControlSizeRegular)
    button.setFont_(_font())
    button.setTarget_(target)
    button.setAction_(action)
    return button


def _checkbox(title: str, frame, value: bool):
    checkbox = AppKit.NSButton.alloc().initWithFrame_(frame)
    checkbox.setButtonType_(AppKit.NSButtonTypeSwitch)
    checkbox.setTitle_(title)
    checkbox.setFont_(_font())
    checkbox.setState_(AppKit.NSControlStateValueOn if value else AppKit.NSControlStateValueOff)
    return checkbox


def _popup(frame, options: tuple[SelectOption, ...], selected_index: int):
    popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(frame, False)
    popup.setFont_(_font())
    for option in options:
        popup.addItemWithTitle_(option.label)
    popup.selectItemAtIndex_(selected_index)
    return popup


def _system_image(name: str, description: str):
    try:
        return AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, description)
    except Exception:
        return None


class _SettingsWindowDelegate(AppKit.NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_SettingsWindowDelegate, self).init()
        if self is None:
            return None
        self.owner = owner
        return self

    def windowShouldClose_(self, _sender):
        self.owner._close()
        return False


class _SettingsActionHandler(AppKit.NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_SettingsActionHandler, self).init()
        if self is None:
            return None
        self.owner = owner
        return self

    def selectPage_(self, sender):
        self.owner._select_page_by_index(sender.tag())

    def save_(self, _sender):
        self.owner._save()

    def cancel_(self, _sender):
        self.owner._close()

    def recordHotkey_(self, _sender):
        self.owner._record_hotkey()

    def modelChanged_(self, _sender):
        self.owner._update_model_detail()

    def languageChanged_(self, _sender):
        self.owner._update_language_warning()

    def manageModels_(self, _sender):
        self.owner._open_model_manager()

    def openMicrophoneSettings_(self, _sender):
        self.owner._open_privacy_pane("Privacy_Microphone")

    def refreshMicrophones_(self, _sender):
        self.owner._refresh_microphones()

    def openAccessibilitySettings_(self, _sender):
        self.owner._open_privacy_pane("Privacy_Accessibility")


class _ModelTableDataSource(AppKit.NSObject):
    def initWithRows_(self, rows):
        self = objc.super(_ModelTableDataSource, self).init()
        if self is None:
            return None
        self.rows = rows
        return self

    def numberOfRowsInTableView_(self, _table_view):
        return len(self.rows)

    def tableView_objectValueForTableColumn_row_(self, _table_view, table_column, row):
        model_name, path, size = self.rows[row]
        identifier = str(table_column.identifier())
        if identifier == "name":
            return model_name
        if identifier == "size":
            return _fmt_size(size)
        if identifier == "path":
            return str(path)
        return ""


class _ModelManagerHandler(AppKit.NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(_ModelManagerHandler, self).init()
        if self is None:
            return None
        self.owner = owner
        return self

    def deleteSelected_(self, _sender):
        self.owner.delete_selected()

    def close_(self, _sender):
        self.owner.close()


class _ModelManagerController:
    def __init__(self, parent_window, cfg: dict):
        self._parent_window = parent_window
        self._model_dir = cfg.get("model_dir", str(Path.home() / ".whisprtap" / "models"))
        self._window = None
        self._table = None
        self._placeholder = None
        self._rows: list[tuple[str, Path, int]] = []
        self._data_source = None
        self._handler = _ModelManagerHandler.alloc().initWithOwner_(self)

    def open(self) -> None:
        if self._window is not None:
            self._window.makeKeyAndOrderFront_(None)
            return

        style = AppKit.NSWindowStyleMaskTitled
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, 620, 380),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("Downloaded Models")
        self._window = window

        content = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 620, 380))
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(AppKit.NSColor.windowBackgroundColor().CGColor())
        window.setContentView_(content)

        title = _label(
            "Downloaded Models",
            AppKit.NSMakeRect(24, 330, 260, 24),
            size=17,
            weight=AppKit.NSFontWeightSemibold,
        )
        content.addSubview_(title)

        table = AppKit.NSTableView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 560, 230))
        table.setUsesAlternatingRowBackgroundColors_(True)
        table.setAllowsMultipleSelection_(False)
        table.setRowHeight_(26)
        for identifier, title_text, width in (
            ("name", "Model", 150),
            ("size", "Size", 85),
            ("path", "Location", 325),
        ):
            column = AppKit.NSTableColumn.alloc().initWithIdentifier_(identifier)
            column.setTitle_(title_text)
            column.setWidth_(width)
            table.addTableColumn_(column)
        self._table = table

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(AppKit.NSMakeRect(24, 86, 572, 230))
        scroll.setBorderType_(AppKit.NSNoBorder)
        scroll.setHasVerticalScroller_(True)
        scroll.setDocumentView_(table)
        content.addSubview_(scroll)

        placeholder = _label(
            "No downloaded models were found.",
            AppKit.NSMakeRect(26, 190, 360, 24),
            color=AppKit.NSColor.secondaryLabelColor(),
        )
        self._placeholder = placeholder
        content.addSubview_(placeholder)

        delete_button = _button("Delete...", AppKit.NSMakeRect(388, 24, 96, 30), self._handler, "deleteSelected:")
        close_button = _button("Close", AppKit.NSMakeRect(496, 24, 100, 30), self._handler, "close:")
        content.addSubview_(delete_button)
        content.addSubview_(close_button)

        self.refresh()
        self._parent_window.beginSheet_completionHandler_(window, None)

    def refresh(self) -> None:
        self._rows = _scan_downloaded_models(self._model_dir)
        self._data_source = _ModelTableDataSource.alloc().initWithRows_(self._rows)
        self._table.setDataSource_(self._data_source)
        self._table.reloadData()
        self._placeholder.setHidden_(bool(self._rows))

    def delete_selected(self) -> None:
        selected = self._table.selectedRow()
        if selected < 0 or selected >= len(self._rows):
            return

        name, path, _size = self._rows[selected]
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(f'Delete model "{name}"?')
        alert.setInformativeText_("This removes the downloaded model files from disk. They can be downloaded again later.")
        alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        response = alert.runModal()
        if response != AppKit.NSAlertFirstButtonReturn:
            return

        shutil.rmtree(path, ignore_errors=True)
        locks = Path(self._model_dir) / ".locks" / path.name
        if locks.exists():
            shutil.rmtree(locks, ignore_errors=True)
        self.refresh()

    def close(self) -> None:
        if self._window is None:
            return
        self._parent_window.endSheet_(self._window)
        self._window.orderOut_(None)
        self._window = None


class SettingsWindow:
    def __init__(
        self,
        root=None,
        on_save: Callable[[dict], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ):
        self._root = root
        self._on_save = on_save
        self._on_close = on_close
        self._window = None
        self._delegate = None
        self._handler = _SettingsActionHandler.alloc().initWithOwner_(self)
        self._page_names = ["General", "Dictation", "Models", "Permissions"]
        self._page_views = {}
        self._sidebar_buttons = []
        self._state: SettingsViewState | None = None
        self._hotkey_field = None
        self._record_button = None
        self._save_button = None
        self._model_popup = None
        self._model_detail_label = None
        self._language_popup = None
        self._language_warning = None
        self._auto_paste_checkbox = None
        self._device_popup = None
        self._device_help_label = None
        self._refresh_device_button = None
        self._autostart_checkbox = None
        self._model_manager = None
        self._lock = threading.Lock()

    def open(self) -> None:
        if threading.current_thread() is threading.main_thread():
            self._open_on_main_thread()
        else:
            AppHelper.callAfter(self._open_on_main_thread)

    def close(self) -> None:
        if threading.current_thread() is threading.main_thread():
            self._close()
        else:
            AppHelper.callAfter(self._close)

    def _open_on_main_thread(self) -> None:
        with self._lock:
            if self._window is not None:
                self._window.makeKeyAndOrderFront_(None)
                AppKit.NSApp.activateIgnoringOtherApps_(True)
                return
            self._build()
        self._window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def _build(self) -> None:
        cfg = config.load()
        self._state = build_settings_view_state(cfg)

        style = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskResizable
            | AppKit.NSWindowStyleMaskMiniaturizable
        )
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("WhisprTap Settings")
        window.setMinSize_(AppKit.NSMakeSize(680, 460))
        window.center()
        self._delegate = _SettingsWindowDelegate.alloc().initWithOwner_(self)
        window.setDelegate_(self._delegate)
        self._window = window

        root = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))
        root.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        root.setWantsLayer_(True)
        root.layer().setBackgroundColor_(AppKit.NSColor.windowBackgroundColor().CGColor())
        window.setContentView_(root)

        self._build_sidebar(root)
        self._build_action_bar(root)
        self._build_pages(root)
        self._select_page_by_index(0)

    def _build_sidebar(self, root) -> None:
        sidebar = AppKit.NSVisualEffectView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT))
        sidebar.setAutoresizingMask_(AppKit.NSViewHeightSizable)
        sidebar.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)
        sidebar.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        sidebar.setState_(AppKit.NSVisualEffectStateActive)
        root.addSubview_(sidebar)

        title = _label(
            "WhisprTap",
            AppKit.NSMakeRect(20, WINDOW_HEIGHT - 58, SIDEBAR_WIDTH - 36, 24),
            size=15,
            weight=AppKit.NSFontWeightSemibold,
        )
        title.setAutoresizingMask_(AppKit.NSViewMinYMargin)
        sidebar.addSubview_(title)

        items = [
            ("General", "gearshape"),
            ("Dictation", "waveform"),
            ("Models", "square.stack.3d.up"),
            ("Permissions", "lock.shield"),
        ]
        y = WINDOW_HEIGHT - 102
        for index, (label, symbol) in enumerate(items):
            button = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(12, y, SIDEBAR_WIDTH - 24, 30))
            button.setTitle_(label)
            button.setTag_(index)
            button.setBordered_(False)
            button.setAlignment_(AppKit.NSLeftTextAlignment)
            button.setFont_(_font(13, AppKit.NSFontWeightRegular))
            image = _system_image(symbol, label)
            if image is not None:
                button.setImage_(image)
                button.setImagePosition_(AppKit.NSImageLeft)
            button.setTarget_(self._handler)
            button.setAction_("selectPage:")
            button.setAutoresizingMask_(AppKit.NSViewMinYMargin)
            sidebar.addSubview_(button)
            self._sidebar_buttons.append(button)
            y -= 36

    def _build_action_bar(self, root) -> None:
        bar = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(SIDEBAR_WIDTH, 0, CONTENT_WIDTH, ACTION_BAR_HEIGHT)
        )
        bar.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMaxYMargin)
        bar.setMaterial_(AppKit.NSVisualEffectMaterialHeaderView)
        bar.setBlendingMode_(AppKit.NSVisualEffectBlendingModeWithinWindow)
        root.addSubview_(bar)

        separator = AppKit.NSBox.alloc().initWithFrame_(AppKit.NSMakeRect(0, ACTION_BAR_HEIGHT - 1, CONTENT_WIDTH, 1))
        separator.setBoxType_(AppKit.NSBoxSeparator)
        separator.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMinYMargin)
        bar.addSubview_(separator)

        cancel = _button("Cancel", AppKit.NSMakeRect(CONTENT_WIDTH - 218, 14, 92, 30), self._handler, "cancel:")
        cancel.setAutoresizingMask_(AppKit.NSViewMinXMargin | AppKit.NSViewMaxYMargin)
        save = _button("Save Changes", AppKit.NSMakeRect(CONTENT_WIDTH - 118, 14, 104, 30), self._handler, "save:")
        save.setKeyEquivalent_("\r")
        save.setAutoresizingMask_(AppKit.NSViewMinXMargin | AppKit.NSViewMaxYMargin)
        self._save_button = save

        bar.addSubview_(cancel)
        bar.addSubview_(save)

    def _build_pages(self, root) -> None:
        host = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(SIDEBAR_WIDTH, ACTION_BAR_HEIGHT, CONTENT_WIDTH, WINDOW_HEIGHT - ACTION_BAR_HEIGHT)
        )
        host.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        root.addSubview_(host)

        self._page_views["General"] = self._build_general_page(host)
        self._page_views["Dictation"] = self._build_dictation_page(host)
        self._page_views["Models"] = self._build_models_page(host)
        self._page_views["Permissions"] = self._build_permissions_page(host)

    def _scroll_page(self, host, document_height: int):
        frame = AppKit.NSMakeRect(0, 0, CONTENT_WIDTH, WINDOW_HEIGHT - ACTION_BAR_HEIGHT)
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(frame)
        scroll.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        scroll.setBorderType_(AppKit.NSNoBorder)
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)

        doc = AppKit.NSView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, CONTENT_WIDTH, document_height))
        doc.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        scroll.setDocumentView_(doc)
        host.addSubview_(scroll)
        return scroll, doc

    def _heading(self, doc, text: str, y: int) -> int:
        heading = _label(text, AppKit.NSMakeRect(28, y, CONTENT_WIDTH - 56, 28), size=18, weight=AppKit.NSFontWeightSemibold)
        heading.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        doc.addSubview_(heading)
        return y - 42

    def _row_label(self, doc, text: str, y: int):
        label = _label(text, AppKit.NSMakeRect(28, y + 2, 142, 22), weight=AppKit.NSFontWeightSemibold)
        doc.addSubview_(label)
        return label

    def _help_label(self, doc, text: str, x: int, y: int, width: int):
        label = _label(text, AppKit.NSMakeRect(x, y, width, 36), size=12, color=AppKit.NSColor.secondaryLabelColor())
        label.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        doc.addSubview_(label)
        return label

    def _build_general_page(self, host):
        assert self._state is not None
        scroll, doc = self._scroll_page(host, 430)
        y = self._heading(doc, "General", 374)

        self._row_label(doc, "Hotkey", y)
        hotkey = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(178, y, 124, 26))
        hotkey.setEditable_(False)
        hotkey.setSelectable_(False)
        hotkey.setStringValue_(self._state.hotkey)
        hotkey.setFont_(_font())
        self._hotkey_field = hotkey
        doc.addSubview_(hotkey)

        record = _button("Record...", AppKit.NSMakeRect(314, y - 1, 94, 28), self._handler, "recordHotkey:")
        self._record_button = record
        doc.addSubview_(record)
        self._help_label(doc, "Use one key to start and stop dictation.", 178, y - 38, CONTENT_WIDTH - 220)
        y -= 86

        self._row_label(doc, "Auto-Paste", y)
        self._auto_paste_checkbox = _checkbox("Paste transcribed text into the active app", AppKit.NSMakeRect(174, y, 330, 24), self._state.auto_paste)
        doc.addSubview_(self._auto_paste_checkbox)
        y -= 58

        self._row_label(doc, "Launch at Login", y)
        self._autostart_checkbox = _checkbox("Start WhisprTap when you sign in", AppKit.NSMakeRect(174, y, 300, 24), self._state.autostart)
        doc.addSubview_(self._autostart_checkbox)
        return scroll

    def _build_dictation_page(self, host):
        assert self._state is not None
        scroll, doc = self._scroll_page(host, 430)
        y = self._heading(doc, "Dictation", 374)

        self._row_label(doc, "Language", y)
        self._language_popup = _popup(
            AppKit.NSMakeRect(178, y - 2, 230, 28),
            self._state.language_options,
            self._state.selected_language_index,
        )
        self._language_popup.setTarget_(self._handler)
        self._language_popup.setAction_("languageChanged:")
        doc.addSubview_(self._language_popup)
        self._help_label(doc, "Automatic lets Whisper detect the spoken language.", 178, y - 38, CONTENT_WIDTH - 220)
        self._language_warning = _label(
            "",
            AppKit.NSMakeRect(178, y - 62, CONTENT_WIDTH - 220, 20),
            size=12,
            color=AppKit.NSColor.systemOrangeColor(),
        )
        self._language_warning.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        doc.addSubview_(self._language_warning)
        y -= 86

        self._row_label(doc, "Microphone", y)
        self._device_popup = _popup(
            AppKit.NSMakeRect(178, y - 2, 306, 28),
            self._state.device_options,
            self._state.selected_device_index,
        )
        doc.addSubview_(self._device_popup)
        refresh = _button("Refresh", AppKit.NSMakeRect(496, y - 2, 82, 28), self._handler, "refreshMicrophones:")
        refresh.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        self._refresh_device_button = refresh
        doc.addSubview_(refresh)
        message = self._state.device_error or "Use System Default unless you want a specific input device."
        self._device_help_label = self._help_label(doc, message, 178, y - 38, CONTENT_WIDTH - 220)
        return scroll

    def _build_models_page(self, host):
        assert self._state is not None
        scroll, doc = self._scroll_page(host, 450)
        y = self._heading(doc, "Models", 394)

        self._row_label(doc, "Model", y)
        self._model_popup = _popup(
            AppKit.NSMakeRect(178, y - 2, 270, 28),
            self._state.model_options,
            self._state.selected_model_index,
        )
        self._model_popup.setTarget_(self._handler)
        self._model_popup.setAction_("modelChanged:")
        doc.addSubview_(self._model_popup)
        self._model_detail_label = self._help_label(doc, "", 178, y - 40, CONTENT_WIDTH - 220)
        y -= 92

        self._row_label(doc, "Storage", y)
        storage = _label(self._state.model_dir, AppKit.NSMakeRect(178, y + 2, CONTENT_WIDTH - 230, 24), color=AppKit.NSColor.secondaryLabelColor())
        storage.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        doc.addSubview_(storage)
        y -= 58

        self._row_label(doc, "Downloads", y)
        manage = _button("Manage Models...", AppKit.NSMakeRect(178, y - 2, 144, 28), self._handler, "manageModels:")
        doc.addSubview_(manage)
        self._update_model_detail()
        return scroll

    def _build_permissions_page(self, host):
        scroll, doc = self._scroll_page(host, 450)
        y = self._heading(doc, "Permissions", 394)

        self._row_label(doc, "Microphone", y)
        open_microphone = _button("Open Microphone Settings", AppKit.NSMakeRect(178, y - 2, 190, 28), self._handler, "openMicrophoneSettings:")
        doc.addSubview_(open_microphone)
        self._help_label(doc, "Required for recording audio.", 178, y - 38, CONTENT_WIDTH - 220)
        y -= 92

        self._row_label(doc, "Accessibility", y)
        open_accessibility = _button("Open Accessibility Settings", AppKit.NSMakeRect(178, y - 2, 202, 28), self._handler, "openAccessibilitySettings:")
        doc.addSubview_(open_accessibility)
        self._help_label(doc, "Required for the global hotkey and Auto-Paste.", 178, y - 38, CONTENT_WIDTH - 220)
        return scroll

    def _select_page_by_index(self, index: int) -> None:
        if index < 0 or index >= len(self._page_names):
            return
        selected_name = self._page_names[index]
        for name, view in self._page_views.items():
            view.setHidden_(name != selected_name)
        for button in self._sidebar_buttons:
            is_selected = button.tag() == index
            button.setState_(AppKit.NSControlStateValueOn if is_selected else AppKit.NSControlStateValueOff)
            button.setContentTintColor_(AppKit.NSColor.controlAccentColor() if is_selected else AppKit.NSColor.labelColor())

    def _selected_option(self, popup, options: tuple[SelectOption, ...]) -> SelectOption:
        index = popup.indexOfSelectedItem()
        if index < 0 or index >= len(options):
            return options[0]
        return options[index]

    def _update_model_detail(self) -> None:
        if self._state is None or self._model_popup is None or self._model_detail_label is None:
            return
        selected = self._selected_option(self._model_popup, self._state.model_options)
        self._model_detail_label.setStringValue_(selected.detail)
        self._update_language_warning()

    def _update_language_warning(self) -> None:
        if self._state is None or self._language_warning is None or self._model_popup is None or self._language_popup is None:
            return
        selected_model = self._selected_option(self._model_popup, self._state.model_options).value
        selected_language = self._selected_option(self._language_popup, self._state.language_options).value
        if str(selected_model).endswith(".en") and selected_language != "en":
            self._language_warning.setStringValue_("The selected Distil English model only supports English.")
        else:
            self._language_warning.setStringValue_("")

    def _record_hotkey(self) -> None:
        previous = self._hotkey_field.stringValue()
        self._hotkey_field.setStringValue_("Press a key...")
        self._record_button.setEnabled_(False)
        self._record_button.setTitle_("Listening...")
        self._save_button.setEnabled_(False)

        def worker() -> None:
            key = record_hotkey(timeout=5.0)

            def finish() -> None:
                self._hotkey_field.setStringValue_(key or previous)
                self._record_button.setEnabled_(True)
                self._record_button.setTitle_("Record...")
                self._save_button.setEnabled_(True)

            AppHelper.callAfter(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _open_model_manager(self) -> None:
        cfg = config.load()
        self._model_manager = _ModelManagerController(self._window, cfg)
        self._model_manager.open()

    def _open_privacy_pane(self, pane: str) -> None:
        url = NSURL.URLWithString_(f"x-apple.systempreferences:com.apple.preference.security?{pane}")
        AppKit.NSWorkspace.sharedWorkspace().openURL_(url)

    def _refresh_microphones(self) -> None:
        if self._state is None or self._device_popup is None:
            return

        selected_value = self._selected_option(self._device_popup, self._state.device_options).value
        selected_index = selected_value if isinstance(selected_value, int) else None
        selected_device = find_input_device_by_index(selected_index, self._state.input_devices)
        current_cfg = {
            "input_device": selected_index,
            "input_device_ref": input_device_config_ref(selected_device),
        }

        devices, device_error = safe_get_input_devices()
        resolved_index = resolve_input_device_index(current_cfg, devices)
        resolved_device = find_input_device_by_index(resolved_index, devices)
        device_options = _device_options(devices)
        selected_device_index = _selected_index(device_options, resolved_index)
        self._state = replace(
            self._state,
            input_device=resolved_index,
            input_device_ref=input_device_config_ref(resolved_device),
            input_devices=tuple(devices),
            device_options=device_options,
            selected_device_index=selected_device_index,
            device_error=device_error,
        )

        self._device_popup.removeAllItems()
        for option in device_options:
            self._device_popup.addItemWithTitle_(option.label)
        self._device_popup.selectItemAtIndex_(selected_device_index)
        if self._device_help_label is not None:
            message = device_error or "Use System Default unless you want a specific input device."
            self._device_help_label.setStringValue_(message)

    def _save(self) -> None:
        assert self._state is not None
        new_cfg = config.load()
        new_cfg["hotkey"] = self._hotkey_field.stringValue()
        new_cfg["model_size"] = self._selected_option(self._model_popup, self._state.model_options).value
        new_cfg["language"] = self._selected_option(self._language_popup, self._state.language_options).value
        new_cfg["auto_paste"] = self._auto_paste_checkbox.state() == AppKit.NSControlStateValueOn
        selected_value = self._selected_option(self._device_popup, self._state.device_options).value
        selected_index = selected_value if isinstance(selected_value, int) else None
        selected_device = find_input_device_by_index(selected_index, self._state.input_devices)
        if selected_device is None:
            resolved_device = None
        else:
            live_devices, _device_error = safe_get_input_devices()
            resolved_index = resolve_input_device_index(
                {
                    "input_device": selected_index,
                    "input_device_ref": input_device_config_ref(selected_device),
                },
                live_devices,
            )
            resolved_device = find_input_device_by_index(resolved_index, live_devices)
        new_cfg["input_device"] = resolved_device.index if resolved_device is not None else None
        new_cfg["input_device_ref"] = input_device_config_ref(resolved_device)
        new_cfg["autostart"] = self._autostart_checkbox.state() == AppKit.NSControlStateValueOn
        autostart.apply(new_cfg["autostart"])
        config.save(new_cfg)
        if self._on_save:
            self._on_save(new_cfg)
        self._close()

    def _close(self) -> None:
        window = self._window
        if window is None:
            return
        if self._model_manager is not None:
            self._model_manager.close()
            self._model_manager = None
        self._window = None
        window.setDelegate_(None)
        window.orderOut_(None)
        if self._on_close:
            self._on_close()


def run_standalone() -> None:
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    window = SettingsWindow(on_close=AppHelper.stopEventLoop)
    window.open()
    app.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    if "--standalone" not in sys.argv:
        print("settings_window.py can only be started with --standalone.", file=sys.stderr)
        raise SystemExit(2)
    run_standalone()
