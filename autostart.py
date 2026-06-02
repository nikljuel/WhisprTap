import sys
from pathlib import Path

DESKTOP_FILE = Path.home() / ".config" / "autostart" / "whisprtap.desktop"

TEMPLATE = """\
[Desktop Entry]
Type=Application
Name=WhisprTap
Comment=Push-to-Talk Transkriptor
Exec={python} {main}
Path={workdir}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""


def enable() -> None:
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    main = Path(__file__).resolve().parent / "main.py"
    content = TEMPLATE.format(
        python=sys.executable,
        main=main,
        workdir=main.parent,
    )
    DESKTOP_FILE.write_text(content, encoding="utf-8")


def disable() -> None:
    DESKTOP_FILE.unlink(missing_ok=True)


def is_enabled() -> bool:
    return DESKTOP_FILE.exists()


def apply(enabled: bool) -> None:
    if enabled:
        enable()
    else:
        disable()
