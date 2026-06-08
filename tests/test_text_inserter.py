import unittest

from text_inserter import COMMAND_V_KEYCODE, MacOSTextInserter, QuartzCommandVEventSender


class FakePasteboard:
    def __init__(self, *, should_copy: bool = True):
        self.should_copy = should_copy
        self.cleared = False
        self.value = None

    def clearContents(self):
        self.cleared = True

    def setString_forType_(self, text, pasteboard_type):
        self.value = (text, pasteboard_type)
        return self.should_copy


class FakeEventSender:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls = 0

    def send_command_v(self):
        self.calls += 1
        if self.error is not None:
            raise self.error


class TextInserterTests(unittest.TestCase):
    def test_auto_paste_false_copies_without_paste_attempt(self) -> None:
        pasteboard = FakePasteboard()
        event_sender = FakeEventSender()
        inserter = MacOSTextInserter(
            pasteboard=pasteboard,
            accessibility_check=lambda: self.fail("accessibility should not be checked"),
            event_sender=event_sender,
            paste_delay=0,
        )

        result = inserter.insert("hello", auto_paste=False)

        self.assertTrue(result.copied)
        self.assertFalse(result.paste_attempted)
        self.assertFalse(result.pasted)
        self.assertIsNone(result.error)
        self.assertTrue(pasteboard.cleared)
        self.assertEqual(pasteboard.value[0], "hello")
        self.assertEqual(event_sender.calls, 0)

    def test_missing_accessibility_reports_error_without_typing_v(self) -> None:
        event_sender = FakeEventSender()
        inserter = MacOSTextInserter(
            pasteboard=FakePasteboard(),
            accessibility_check=lambda: False,
            event_sender=event_sender,
            paste_delay=0,
        )

        result = inserter.insert("hello", auto_paste=True)

        self.assertTrue(result.copied)
        self.assertTrue(result.paste_attempted)
        self.assertFalse(result.pasted)
        self.assertIn("Accessibility", result.error)
        self.assertEqual(event_sender.calls, 0)

    def test_quartz_event_error_reports_error_and_keeps_clipboard(self) -> None:
        pasteboard = FakePasteboard()
        inserter = MacOSTextInserter(
            pasteboard=pasteboard,
            accessibility_check=lambda: True,
            event_sender=FakeEventSender(error=RuntimeError("boom")),
            paste_delay=0,
        )

        result = inserter.insert("hello", auto_paste=True)

        self.assertTrue(result.copied)
        self.assertTrue(result.paste_attempted)
        self.assertFalse(result.pasted)
        self.assertIn("boom", result.error)
        self.assertEqual(pasteboard.value[0], "hello")

    def test_successful_auto_paste_reports_pasted(self) -> None:
        event_sender = FakeEventSender()
        inserter = MacOSTextInserter(
            pasteboard=FakePasteboard(),
            accessibility_check=lambda: True,
            event_sender=event_sender,
            paste_delay=0,
        )

        result = inserter.insert("hello", auto_paste=True)

        self.assertTrue(result.copied)
        self.assertTrue(result.paste_attempted)
        self.assertTrue(result.pasted)
        self.assertIsNone(result.error)
        self.assertEqual(event_sender.calls, 1)


class QuartzCommandVEventSenderTests(unittest.TestCase):
    def test_sends_command_v_with_command_flag(self) -> None:
        class FakeQuartz:
            kCGEventFlagMaskCommand = 123
            kCGHIDEventTap = 456

            def __init__(self):
                self.created = []
                self.posts = []

            def CGEventCreateKeyboardEvent(self, source, keycode, is_down):
                event = {"source": source, "keycode": keycode, "is_down": is_down}
                self.created.append(event)
                return event

            def CGEventSetFlags(self, event, flags):
                event["flags"] = flags

            def CGEventPost(self, tap, event):
                self.posts.append((tap, event))

        quartz = FakeQuartz()
        sender = QuartzCommandVEventSender(quartz=quartz)

        sender.send_command_v()

        self.assertEqual(
            [(event["keycode"], event["is_down"]) for event in quartz.created],
            [(COMMAND_V_KEYCODE, True), (COMMAND_V_KEYCODE, False)],
        )
        self.assertEqual([event["flags"] for event in quartz.created], [123, 123])
        self.assertEqual(
            [(tap, event["keycode"]) for tap, event in quartz.posts],
            [(456, COMMAND_V_KEYCODE), (456, COMMAND_V_KEYCODE)],
        )


if __name__ == "__main__":
    unittest.main()
