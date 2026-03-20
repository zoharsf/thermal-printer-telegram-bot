#!/bin/bash
set -e

# Pre-scan BLE to populate adapter cache so Bleak can find the printer on first connect
echo "Pre-scanning BLE devices..."
bluetoothctl scan on &
SCAN_PID=$!
sleep 6
kill "$SCAN_PID" 2>/dev/null || true
echo "BLE pre-scan complete."

exec uv run python -m catprint_bot.main
