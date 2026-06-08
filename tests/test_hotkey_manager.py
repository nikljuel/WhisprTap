import unittest

from hotkey_manager import normalize_hotkey


class NormalizeHotkeyTests(unittest.TestCase):
    def test_normalizes_function_keys(self) -> None:
        self.assertEqual(normalize_hotkey("F9"), "f9")
        self.assertEqual(normalize_hotkey("Key.f9"), "f9")
        self.assertEqual(normalize_hotkey("<Key.f9>"), "f9")

    def test_normalizes_character_keys(self) -> None:
        self.assertEqual(normalize_hotkey("'a'"), "a")
        self.assertEqual(normalize_hotkey(" A "), "a")

    def test_normalizes_common_macos_aliases(self) -> None:
        self.assertEqual(normalize_hotkey("cmd"), "command")
        self.assertEqual(normalize_hotkey("cmd_l"), "command")
        self.assertEqual(normalize_hotkey("esc"), "escape")
        self.assertEqual(normalize_hotkey("return"), "enter")


if __name__ == "__main__":
    unittest.main()
