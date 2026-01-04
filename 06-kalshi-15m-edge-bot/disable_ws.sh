#!/bin/bash
# Disable Kalshi WebSocket — restores pre-WS REST-only behavior
# No code changes needed; all WS paths are guarded by kalshi_ws.enabled
set -e
cd "$(dirname "$0")"

sed -i 's/^\(\s*enabled:\s*\)true/\1false/' config_15m.yaml
echo "✅ Kalshi WS disabled (REST-only mode). Restart the bot to apply."
grep -A3 'kalshi_ws:' config_15m.yaml
