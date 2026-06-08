import plistlib
import sys
from pathlib import Path

LABEL = "com.whisprtap"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / ".whisprtap"


def build_launch_agent(
    python: str | Path | None = None,
    main: str | Path | None = None,
    workdir: str | Path | None = None,
) -> dict:
    main_path = Path(main) if main is not None else Path(__file__).resolve().parent / "main.py"
    python_path = Path(python) if python is not None else Path(sys.executable)
    workdir_path = Path(workdir) if workdir is not None else main_path.parent

    return {
        "Label": LABEL,
        "ProgramArguments": [str(python_path), str(main_path)],
        "WorkingDirectory": str(workdir_path),
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(LOG_DIR / "whisprtap.out.log"),
        "StandardErrorPath": str(LOG_DIR / "whisprtap.err.log"),
    }


def enable() -> None:
    LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LAUNCH_AGENT_PATH.open("wb") as f:
        plistlib.dump(build_launch_agent(), f)


def disable() -> None:
    LAUNCH_AGENT_PATH.unlink(missing_ok=True)


def is_enabled() -> bool:
    return LAUNCH_AGENT_PATH.exists()


def apply(enabled: bool) -> None:
    if enabled:
        enable()
    else:
        disable()
