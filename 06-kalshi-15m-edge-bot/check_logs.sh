#!/bin/bash
# Log monitoring commands for Kalshi 15m Bot

echo "════════════════════════════════════════════════════════════════════════════════"
echo "KALSHI BOT LOG MONITOR"
echo "════════════════════════════════════════════════════════════════════════════════"
echo

# Get today's date
TODAY=$(date +"%Y-%m-%d")

# === FADING ACTIVITY ===
echo "1️⃣  FADING EVENTS (Last 12 hours):"
echo "─────────────────────────────────────────────────────────────────────────────────"
FADE_COUNT=$(grep -a "FADING" logs/edge_bot.log | grep "$TODAY" | wc -l)
echo "   Total: $FADE_COUNT"
echo "   Recent fades:"
grep -a "FADING" logs/edge_bot.log | grep "$TODAY" | tail -5 | sed 's/.*INFO - //'
echo

# === ORDER BOOK BLOCKS ===
echo "2️⃣  ORDER BOOK FILTER BLOCKS:"
echo "─────────────────────────────────────────────────────────────────────────────────"
OB_BLOCKS=$(grep -a -E "Stale Order Book|No Order Book|Weak Order Book" logs/edge_bot.log | grep "$TODAY" | wc -l)
echo "   Total blocked by order book: $OB_BLOCKS"
if [ $OB_BLOCKS -gt 0 ]; then
    grep -a -E "Stale Order Book|No Order Book|Weak Order Book" logs/edge_bot.log | grep "$TODAY" | tail -10
fi
echo

# === SKIP REASONS ===
echo "3️⃣  TOP SKIP REASONS (Last 12 hours):"
echo "─────────────────────────────────────────────────────────────────────────────────"
grep -a "skip:" logs/edge_bot.log | grep "$TODAY" | \
  sed 's/.*skip: //' | cut -d'(' -f1 | sort | uniq -c | sort -rn | head -10
echo

# === EDGE SIGNALS ===
echo "4️⃣  EDGE SIGNALS GENERATED:"
echo "─────────────────────────────────────────────────────────────────────────────────"
SIGNALS=$(grep -a "🎯.*Edge:" logs/edge_bot.log | grep "$TODAY" | wc -l)
echo "   Total signals: $SIGNALS"
if [ $SIGNALS -gt 0 ]; then
    echo "   Recent signals:"
    grep -a "🎯.*Edge:" logs/edge_bot.log | grep "$TODAY" | tail -5
fi
echo

# === LATE WINDOW TRADES ===
echo "5️⃣  LATE WINDOW TRADES (<3 mins to close):"
echo "─────────────────────────────────────────────────────────────────────────────────"
LATE_TRADES=$(grep -a "Closes in [0-2] min" logs/edge_bot.log | grep "$TODAY" | wc -l)
echo "   Total late trades: $LATE_TRADES"
if [ $LATE_TRADES -gt 0 ]; then
    grep -a "Closes in [0-2] min" logs/edge_bot.log | grep "$TODAY" | tail -5
fi
echo

echo "════════════════════════════════════════════════════════════════════════════════"
echo "Quick Commands:"
echo "  • Watch fading live:    tail -f logs/edge_bot.log | grep FADING"
echo "  • Watch order book:     tail -f logs/edge_bot.log | grep 'Order Book'"
echo "  • Watch signals:        tail -f logs/edge_bot.log | grep '🎯'"
echo "════════════════════════════════════════════════════════════════════════════════"
