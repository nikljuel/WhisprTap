import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULTS = {
    "hotkey": "f9",
    "model_size": "medium",
    "language": "de",
    "auto_paste": True,
    "model_dir": str(Path.home() / ".whisprtap" / "models"),
}


def load() -> dict:
    if not CONFIG_PATH.exists():
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {**DEFAULTS, **data}


def save(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
