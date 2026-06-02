# WhisprTap

System-weiter Push-to-Talk-Transkriptor für Linux. Drücke einen Hotkey, sprich, drücke nochmal — der Text wird automatisch an der Cursorposition eingefügt oder in die Zwischenablage kopiert.

## Voraussetzungen

- Linux (X11 oder Wayland/GNOME)
- Python 3.9+
- ~1,5 GB freier Speicher für das Whisper-Modell
- 8 GB RAM (16 GB empfohlen für flüssige Transkription)

---

## Installation

### 1. System-Pakete

**X11:**
```bash
sudo apt install xdotool xclip python3-tk libportaudio2
```

**Wayland (GNOME):**
```bash
sudo apt install wl-clipboard ydotool python3-tk libportaudio2
```

### 2. uinput-Rechte einrichten (nur Wayland)

Damit `ydotool` Text ohne Root-Rechte eintippen kann, muss die `input`-Gruppe Zugriff auf `/dev/uinput` bekommen. Einmalig ausführen:

```bash
sudo bash scripts/setup_uinput.sh
```

Das Skript legt eine Udev-Regel an und lädt sie sofort. Kein Neustart oder Neuanmeldung nötig, solange du bereits in der `input`-Gruppe bist (prüfen mit `groups`). Falls nicht:

```bash
sudo usermod -a -G input $USER
# danach neu anmelden
```

Testen ob alles klappt (Cursor in ein Textfeld setzen, dann):
```bash
ydotool type -- "Hallo Welt"
```

### 3. Python-Umgebung erstellen

```bash
python3 -m venv ~/.whisprtap/venv
source ~/.whisprtap/venv/bin/activate
pip install -r requirements.txt
```

### 4. App starten

```bash
source ~/.whisprtap/venv/bin/activate
python3 main.py
```

Beim **ersten Start** lädt faster-whisper das Whisper-Medium-Modell automatisch (~1,5 GB). Danach läuft alles vollständig offline.

---

## Bedienung

| Aktion | Ergebnis |
|---|---|
| Hotkey drücken | Aufnahme startet (rotes Icon im Tray) |
| Hotkey nochmal drücken | Aufnahme endet, Transkription beginnt |
| Text fertig → Cursor in Textfeld | Text wird direkt eingefügt |
| Text fertig → kein Textfeld fokussiert | Text landet in der Zwischenablage |

Standard-Hotkey: `F9`

---

## Einstellungen

Rechtsklick auf das Tray-Icon → **Einstellungen...**

| Option | Beschreibung |
|---|---|
| Hotkey | Taste zum Starten/Stoppen der Aufnahme |
| Modellgröße | `tiny` (schnell) bis `large` (genau) |
| Sprache | `de`, `en`, `auto`, … |
| Auto-Paste | Text direkt eintippen oder nur in Zwischenablage |
| Mikrofon | Eingabegerät wählen oder System-Standard |

---

## Session-Typ prüfen

```bash
echo $XDG_SESSION_TYPE   # "x11" oder "wayland"
```

### X11

Text-Eingabe läuft via `xdotool type`. Keine Sonderrechte nötig.

### Wayland (GNOME)

GNOME unterstützt kein virtuelles Keyboard-Protokoll (`zwp_virtual_keyboard_v1`). Deshalb wird `ydotool` mit direktem `/dev/uinput`-Zugriff verwendet. Voraussetzung: Schritt **2** der Installation oben.

---

## Konfigurationsdatei

`config.json` wird beim ersten Start automatisch angelegt:

```json
{
  "hotkey": "f9",
  "model_size": "medium",
  "language": "de",
  "auto_paste": true,
  "model_dir": "~/.whisprtap/models/",
  "input_device": null
}
```

`input_device: null` bedeutet System-Standard. Einen bestimmten Index setzen entspricht dem Gerät aus `python3 -c "import sounddevice; print(sounddevice.query_devices())"`.

---

## Fehlerbehebung

**„ydotoold backend unavailable / failed to open uinput device"**
→ Udev-Regel fehlt oder Nutzer nicht in `input`-Gruppe. Schritt 2 der Installation ausführen.

**„Aufnahme zu kurz"**
→ Hotkey wurde zu kurz gehalten (< 0,5 Sekunden). Einfach nochmal versuchen.

**„Kein Text erkannt"**
→ Whisper hat nur Stille oder Hintergrundgeräusche aufgenommen. VAD-Filter aktiv — kurze Geräusche werden herausgefiltert.

**Text landet in Zwischenablage statt direkt eingefügt zu werden**
→ Auto-Paste in den Einstellungen aktivieren, oder auf Wayland: Schritt 2 der Installation ausführen.

---

## Mac (Apple Silicon) — spätere Portierung

| Komponente | Linux | macOS |
|---|---|---|
| Whisper | `faster-whisper` | `mlx-whisper` |
| Tray | `pystray` | `rumps` |
| Text einfügen | `xdotool` / `ydotool` | `pyautogui` |
| Hotkey | `evdev` | `pynput` |

Kernlogik (`recorder.py`, `transcriber.py`, `config.py`, `main.py`) bleibt unverändert.
