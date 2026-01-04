#!/bin/bash
# Script to add XRP support to the Kalshi 15m bot

echo "🚀 Adding XRP support to Kalshi 15m bot..."

# Backup files first
echo "📦 Creating backups..."
cp negative_edge_tracker.py negative_edge_tracker.py.pre_xrp
cp position_manager_15m.py position_manager_15m.py.pre_xrp
cp spot_price_feed.py spot_price_feed.py.pre_xrp
cp edge_bot.py edge_bot.py.pre_xrp
cp market_scanner_15m.py market_scanner_15m.py.pre_xrp

echo "✅ Backups created with .pre_xrp extension"

echo ""
echo "⚠️  MANUAL STEPS REQUIRED:"
echo ""
echo "1. negative_edge_tracker.py (line 315-323)"
echo "   Add:    elif 'XRP' in ticker.upper():"
echo "           return 'XRP'"
echo ""
echo "2. position_manager_15m.py (line 419-427)"
echo "   Add:    elif 'XRP' in ticker.upper():"
echo "           return 'XRP'"
echo ""
echo "3. spot_price_feed.py (line 66-68)"
echo "   Add:    elif symbol == 'XRP': k_pair = 'XXRPZUSD'"
echo ""
echo "4. config_15m.yaml"
echo "   Add 'XRP' to symbols list: [\"SOL\", \"BTC\", \"ETH\", \"XRP\"]"
echo "   Add XRP config:"
echo "     XRP:"
echo "       allowed_trends: [\"down\"]"
echo ""
echo "5. OPTIONAL: edge_bot.py & market_scanner_15m.py"
echo "   Update default fallback to include 'XRP'"
echo ""
echo "Run this command to verify changes:"
echo "  grep -n \"XRP\" negative_edge_tracker.py position_manager_15m.py spot_price_feed.py config_15m.yaml"
echo ""
