#!/bin/bash
# Gibt der input-Gruppe Zugriff auf /dev/uinput, damit ydotool ohne Daemon läuft.
# Einmalig mit sudo ausführen: bash scripts/setup_uinput.sh

set -e

RULE='KERNEL=="uinput", GROUP="input", MODE="0660"'
RULES_FILE="/etc/udev/rules.d/99-uinput.rules"

echo "$RULE" | sudo tee "$RULES_FILE" > /dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger /dev/uinput

echo "Fertig. Bitte WhisprTap neu starten."
echo "Aktuelle Rechte: $(ls -la /dev/uinput)"
