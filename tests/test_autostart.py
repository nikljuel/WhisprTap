import plistlib
import unittest
from pathlib import Path

import autostart


class LaunchAgentTests(unittest.TestCase):
    def test_build_launch_agent_uses_expected_paths(self) -> None:
        plist = autostart.build_launch_agent(
            python="/tmp/venv/bin/python",
            main="/tmp/whisprtap/main.py",
            workdir="/tmp/whisprtap",
        )

        self.assertEqual(plist["Label"], "com.whisprtap")
        self.assertEqual(
            plist["ProgramArguments"],
            ["/tmp/venv/bin/python", "/tmp/whisprtap/main.py"],
        )
        self.assertEqual(plist["WorkingDirectory"], "/tmp/whisprtap")
        self.assertTrue(plist["RunAtLoad"])
        self.assertFalse(plist["KeepAlive"])

    def test_launch_agent_is_plist_serializable(self) -> None:
        plist = autostart.build_launch_agent(
            python=Path("/tmp/venv/bin/python"),
            main=Path("/tmp/whisprtap/main.py"),
            workdir=Path("/tmp/whisprtap"),
        )

        encoded = plistlib.dumps(plist)
        self.assertEqual(plistlib.loads(encoded), plist)


if __name__ == "__main__":
    unittest.main()
