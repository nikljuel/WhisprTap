# WhisprTap

WhisprTap is a macOS-only menu bar app for local push-to-talk transcription. Press the hotkey, speak, press the hotkey again, and WhisprTap transcribes with `faster-whisper`, copies the text to the clipboard, and can paste it into the active app with Command-V.

## Requirements

- macOS on Intel or Apple Silicon. Other operating systems are not supported.
- Python 3.10+
- Microphone permission for Terminal or the Python app you use to launch WhisprTap
- Accessibility permission for Terminal or the Python app, required for the global hotkey and Auto-Paste
- About 1.5 GB of free disk space for the default `medium` model
- 8 GB RAM, 16 GB recommended

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

On first launch, `faster-whisper` downloads the configured model to `~/.whisprtap/models`. Transcription runs locally after the model is available.

## Start

```bash
.venv/bin/python main.py
```

WhisprTap appears in the macOS menu bar.

## macOS Permissions

Open **System Settings -> Privacy & Security** and allow Terminal or the Python app you use to launch WhisprTap:

| Area | Purpose |
|---|---|
| Microphone | Audio recording |
| Accessibility | Global hotkey and Auto-Paste |

WhisprTap usually needs to be restarted after permission changes.

## Usage

| Action | Result |
|---|---|
| Press the hotkey | Recording starts |
| Press the hotkey again | Recording stops and transcription starts |
| Auto-Paste enabled | Text is pasted with Command-V |
| Auto-Paste disabled | Text stays in the clipboard |

Default hotkey: `f9`

## Settings

Menu bar -> **WhisprTap** -> **Settings...**

| Option | Description |
|---|---|
| Hotkey | Key used to start and stop recording |
| Model | `tiny`, `base`, `small`, `medium`, `large-*`, or Distil models |
| Language | German, English, or automatic detection |
| Auto-Paste | Paste the transcript directly or only copy it |
| Microphone | Input device or System Default |
| Launch at Login | Create a LaunchAgent at `~/Library/LaunchAgents/com.whisprtap.plist` |

Settings are stored in `config.json` in the project directory. Models are stored in `~/.whisprtap/models` by default.

## Development

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q .
```

WhisprTap is intentionally macOS-only. Non-macOS launches exit in `main.py` with a clear error message.
