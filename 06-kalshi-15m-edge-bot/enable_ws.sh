#!/bin/bash
# Re-enable Kalshi WebSocket after disable_ws.sh
set -e
cd "$(dirname "$0")"

sed -i 's/^\(\s*enabled:\s*\)false/\1true/' config_15m.yaml
echo "✅ Kalshi WS enabled. Restart the bot to apply."
grep -A3 'kalshi_ws:' config_15m.yaml
