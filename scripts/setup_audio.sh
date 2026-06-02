#!/bin/bash
# Audio-Einstellungen für WhisprTap setzen (Mic-Eingang aktivieren)
# Automatisch beim Start ausführen oder manuell: bash scripts/setup_audio.sh

amixer -c 0 sset Mic 80% unmute 2>/dev/null
amixer -c 0 sset Capture 100% cap 2>/dev/null
echo "[WhisprTap] Audio-Mixer konfiguriert: Mic 80%, Capture 100%"
