from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import sounddevice as sd


@dataclass(frozen=True)
class InputDeviceRef:
    name: str
    host_api: str
    input_channels: int

    def to_config(self) -> dict[str, object]:
        return {
            "name": self.name,
            "host_api": self.host_api,
            "input_channels": self.input_channels,
        }


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    host_api: str
    input_channels: int
    is_default: bool = False

    @property
    def ref(self) -> InputDeviceRef:
        return InputDeviceRef(
            name=self.name,
            host_api=self.host_api,
            input_channels=self.input_channels,
        )


def get_input_devices() -> list[InputDevice]:
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    default_index = _default_input_index()

    results: list[InputDevice] = []
    for index, device in enumerate(devices):
        channels = int(device.get("max_input_channels", 0))
        if channels <= 0:
            continue
        results.append(
            InputDevice(
                index=index,
                name=str(device.get("name", f"Input Device {index}")),
                host_api=_host_api_name(host_apis, device.get("hostapi")),
                input_channels=channels,
                is_default=index == default_index,
            )
        )
    return results


def safe_get_input_devices() -> tuple[list[InputDevice], str | None]:
    try:
        return get_input_devices(), None
    except Exception as exc:
        return [], f"Microphones could not be loaded: {exc}"


def coerce_input_devices(devices: Iterable[InputDevice | tuple[int, str]]) -> list[InputDevice]:
    coerced: list[InputDevice] = []
    for device in devices:
        if isinstance(device, InputDevice):
            coerced.append(device)
        else:
            index, name = device
            coerced.append(
                InputDevice(
                    index=index,
                    name=name,
                    host_api="",
                    input_channels=1,
                )
            )
    return coerced


def input_device_ref_from_config(value: Any) -> InputDeviceRef | None:
    if not isinstance(value, dict):
        return None

    name = value.get("name")
    host_api = value.get("host_api")
    channels = value.get("input_channels", value.get("channels"))
    if not isinstance(name, str) or not isinstance(host_api, str):
        return None

    try:
        input_channels = int(channels)
    except (TypeError, ValueError):
        return None

    if input_channels <= 0:
        return None
    return InputDeviceRef(name=name, host_api=host_api, input_channels=input_channels)


def input_device_config_ref(device: InputDevice | None) -> dict[str, object] | None:
    return device.ref.to_config() if device is not None else None


def find_input_device_by_index(index: int | None, devices: Sequence[InputDevice]) -> InputDevice | None:
    if index is None:
        return None
    for device in devices:
        if device.index == index:
            return device
    return None


def resolve_input_device(
    cfg: dict[str, object],
    devices: Sequence[InputDevice] | None = None,
) -> InputDevice | None:
    if devices is None:
        devices, _error = safe_get_input_devices()

    ref = input_device_ref_from_config(cfg.get("input_device_ref"))
    if ref is not None:
        return find_input_device_by_ref(ref, devices)

    legacy_index = _coerce_index(cfg.get("input_device"))
    return find_input_device_by_index(legacy_index, devices)


def resolve_input_device_index(
    cfg: dict[str, object],
    devices: Sequence[InputDevice] | None = None,
) -> int | None:
    device = resolve_input_device(cfg, devices)
    return device.index if device is not None else None


def normalized_input_device_config(
    cfg: dict[str, object],
    devices: Sequence[InputDevice] | None = None,
) -> dict[str, object]:
    if devices is None:
        devices, _error = safe_get_input_devices()

    normalized = dict(cfg)
    device = resolve_input_device(cfg, devices)
    if device is None:
        normalized["input_device"] = None
        normalized["input_device_ref"] = None
    else:
        normalized["input_device"] = device.index
        normalized["input_device_ref"] = input_device_config_ref(device)
    return normalized


def find_input_device_by_ref(ref: InputDeviceRef, devices: Sequence[InputDevice]) -> InputDevice | None:
    for device in devices:
        if device.ref == ref:
            return device
    return None


def _coerce_index(value: object) -> int | None:
    if value is None:
        return None
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


def _default_input_index() -> int | None:
    default_device = sd.default.device
    if isinstance(default_device, (list, tuple)) and default_device:
        return _coerce_index(default_device[0])
    return _coerce_index(default_device)


def _host_api_name(host_apis: Sequence[dict], host_api_index: object) -> str:
    try:
        return str(host_apis[int(host_api_index)].get("name", host_api_index))
    except Exception:
        return str(host_api_index)
