# WhisprTap

System-weiter Push-to-Talk-Transkriptor für Linux. Drücke einen Hotkey, sprich, drücke nochmal — der Text wird automatisch in das fokussierte Fenster eingefügt oder in die Zwischenablage kopiert.

## Voraussetzungen

- Linux mit Wayland
- Python 3.9+
- ~2 GB freier Speicher für das Whisper-Modell
- 16 GB RAM empfohlen

## Installation

### 1. System-Pakete installieren

```bash
sudo apt update
sudo apt install xdotool xclip python3-tk libportaudio2
```

### 2. Python-Umgebung erstellen

```bash
python3 -m venv ~/.whisprtap/venv
source ~/.whisprtap/venv/bin/activate
pip install -r requirements.txt
```

### 3. App starten

```bash
source ~/.whisprtap/venv/bin/activate
python3 main.py
```

Beim **ersten Start** lädt `faster-whisper` das Whisper-Medium-Modell automatisch von Hugging Face herunter (~1,5 GB). Danach läuft alles vollständig offline.

## Bedienung

- **Hotkey drücken** (Standard: `F9`) → Aufnahme startet (rotes Icon im Tray)
- **Hotkey nochmal drücken** → Aufnahme endet, Transkription beginnt
- **Cursor in Textfeld** → Text wird automatisch eingefügt
- **Kein Textfeld fokussiert** → Text landet in der Zwischenablage

## Einstellungen

Rechtsklick auf das Tray-Icon → "Einstellungen..." öffnet den Dialog:
- Hotkey ändern
- Modellgröße wählen (tiny/small/medium/large)
- Sprache wählen
- Auto-Paste aktivieren/deaktivieren

## X11 vs. Wayland prüfen

```bash
echo $XDG_SESSION_TYPE
```

- `x11` → Auto-Paste funktioniert
- `wayland` → nur Zwischenablage (xdotool nicht verfügbar)

## Mac (Apple Silicon) — spätere Portierung

Tausche folgende Adapter aus:

| Komponente | Linux | macOS |
|---|---|---|
| Whisper | `faster-whisper` | `mlx-whisper` |
| Tray | `pystray` | `rumps` |
| Text einfügen | `xdotool` | `pyautogui` |

Kernlogik (`recorder.py`, `hotkey_manager.py`, `config.py`, `main.py`) bleibt unverändert.

## Konfigurationsdatei

`config.json` wird beim ersten Start automatisch erstellt:

```json
{
  "hotkey": "f9",
  "model_size": "medium",
  "language": "de",
  "auto_paste": true,
  "model_dir": "~/.whisprtap/models/"
}
```
