import tempfile
import unittest
from pathlib import Path

import config
from audio_devices import InputDevice
from settings_window import _fmt_size, _scan_downloaded_models, build_settings_view_state


class SettingsWindowHelperTests(unittest.TestCase):
    def test_formats_model_sizes(self) -> None:
        self.assertEqual(_fmt_size(0), "0 MB")
        self.assertEqual(_fmt_size(42_000_000), "42 MB")
        self.assertEqual(_fmt_size(1_500_000_000), "1.5 GB")

    def test_scans_downloaded_faster_whisper_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            medium = base / "models--Systran--faster-whisper-medium" / "blobs"
            medium.mkdir(parents=True)
            (medium / "model.bin").write_bytes(b"a" * 12)

            distil = base / "models--Systran--faster-distil-whisper-large-v3" / "blobs"
            distil.mkdir(parents=True)
            (distil / "model.bin").write_bytes(b"b" * 7)

            ignored = base / "models--Other--not-whisper" / "blobs"
            ignored.mkdir(parents=True)
            (ignored / "model.bin").write_bytes(b"c" * 100)

            models = _scan_downloaded_models(tmp)

        by_name = {name: size for name, _path, size in models}
        self.assertEqual(by_name, {"medium": 12, "large-v3": 7})

    def test_maps_config_to_view_state(self) -> None:
        cfg = {
            **config.DEFAULTS,
            "hotkey": "f10",
            "model_size": "distil-small.en",
            "language": "en",
            "auto_paste": False,
            "input_device": 2,
            "input_device_ref": None,
            "autostart": False,
        }

        state = build_settings_view_state(
            cfg,
            input_devices=[
                InputDevice(1, "Built-in Microphone", "Core Audio", 1, is_default=True),
                InputDevice(2, "USB Microphone", "Core Audio", 2),
            ],
            autostart_enabled=True,
        )

        self.assertEqual(state.hotkey, "f10")
        self.assertEqual(state.model_options[state.selected_model_index].value, "distil-small.en")
        self.assertEqual(state.language_options[state.selected_language_index].label, "English")
        self.assertEqual(state.device_options[state.selected_device_index].label, "USB Microphone")
        self.assertEqual(
            state.input_device_ref,
            {"name": "USB Microphone", "host_api": "Core Audio", "input_channels": 2},
        )
        self.assertFalse(state.auto_paste)
        self.assertTrue(state.autostart)

    def test_marks_default_device_in_label(self) -> None:
        state = build_settings_view_state(
            {**config.DEFAULTS, "input_device": 1},
            input_devices=[
                InputDevice(1, "MacBook Air-Mikrofon", "Core Audio", 1, is_default=True),
                InputDevice(2, "USB Microphone", "Core Audio", 2),
            ],
            autostart_enabled=False,
        )

        self.assertEqual(state.device_options[state.selected_device_index].label, "MacBook Air-Mikrofon (Default)")

    def test_resolves_saved_device_reference_after_index_changes(self) -> None:
        cfg = {
            **config.DEFAULTS,
            "input_device": 2,
            "input_device_ref": {
                "name": "USB Microphone",
                "host_api": "Core Audio",
                "input_channels": 2,
            },
        }

        state = build_settings_view_state(
            cfg,
            input_devices=[
                InputDevice(1, "Built-in Microphone", "Core Audio", 1, is_default=True),
                InputDevice(7, "USB Microphone", "Core Audio", 2),
            ],
            autostart_enabled=False,
        )

        self.assertEqual(state.input_device, 7)
        self.assertEqual(state.device_options[state.selected_device_index].label, "USB Microphone")

    def test_falls_back_to_system_default_for_missing_device(self) -> None:
        cfg = {
            **config.DEFAULTS,
            "input_device": 99,
            "input_device_ref": {
                "name": "Missing Microphone",
                "host_api": "Core Audio",
                "input_channels": 1,
            },
        }

        state = build_settings_view_state(
            cfg,
            input_devices=[InputDevice(1, "Built-in Microphone", "Core Audio", 1, is_default=True)],
            device_error="Microphones could not be loaded",
            autostart_enabled=False,
        )

        self.assertEqual(state.device_options[state.selected_device_index].label, "System Default")
        self.assertIsNone(state.input_device)
        self.assertIsNone(state.input_device_ref)
        self.assertEqual(state.device_error, "Microphones could not be loaded")


if __name__ == "__main__":
    unittest.main()
