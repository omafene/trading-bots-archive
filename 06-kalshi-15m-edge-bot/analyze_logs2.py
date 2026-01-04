#!/usr/bin/env python3
"""
Analyze 15m Edge Bot Logs (v4.0)
Updated: Added 'Time Remaining' Distribution & Window-Specific Advice.
"""

import re
import logging
import statistics
from datetime import datetime
from collections import defaultdict

def parse_logs(log_file):
    """Parse log file and extract edge opportunities and timing data."""
    opportunities = []
    current_opp = None

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return []

    for line in lines:
        # Detect the primary summary line
        match = re.search(r'🎯 (?:EDGE: )?(KX\S+) \| (\w+) @ (\d+)% \| Edge: ([\d.]+)% \| Signal: ([\d.]+)', line)

        if match:
            current_opp = {
                'ticker': match.group(1),
                'symbol': match.group(1).split('-')[0],
                'side': match.group(2).lower(),
                'entry_price': float(match.group(3)),
                'edge': float(match.group(4)),
                'signal': float(match.group(5)),
                'minutes_left': None
            }

            ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if ts_match:
                current_opp['timestamp'] = ts_match.group(1)

            opportunities.append(current_opp)
            continue

        # NEW: Capture the timing data from the 'Closes in' lines
        time_match = re.search(r'(?:⏰ )?Closes in (\d+) min', line)
        if time_match and current_opp:
            current_opp['minutes_left'] = int(time_match.group(1))

    return opportunities

def analyze_opportunities(opportunities):
    """Generate comprehensive statistics including timing analysis."""
    if not opportunities:
        print("❌ No opportunities found in logs! Verify the bot is logging properly.")
        return

    print("="*60)
    print("📊 BOT LOG ANALYSIS - PERFORMANCE INSIGHTS (v4.0)")
    print("="*60)

    # 1. OVERVIEW
    print(f"📈 OVERVIEW:")
    print(f"    Total Opportunities: {len(opportunities)}")

    # 2. TRADING WINDOW DISTRIBUTION (NEW)
    print(f"\n⏰ OPPORTUNITIES BY MINUTES REMAINING:")
    time_counts = defaultdict(int)
    for o in opportunities:
        if o['minutes_left'] is not None:
            time_counts[o['minutes_left']] += 1
    
    if time_counts:
        for mins in sorted(time_counts.keys(), reverse=True):
            bar = "█" * time_counts[mins]
            print(f"    {mins:2d} min left: {time_counts[mins]:3d} {bar}")
    else:
        print("    No timing data found. Ensure 'Closes in X min' is in logs.")

    # 3. EDGE STATS
    edges = [o['edge'] for o in opportunities]
    print(f"\n💎 EDGE DISTRIBUTION:")
    print(f"    Average Edge: {statistics.mean(edges):.2f}%")
    print(f"    Elite (15%+): {sum(1 for e in edges if e >= 15)} trades")
    print(f"    Standard (3-15%): {sum(1 for e in edges if 3 <= e < 15)} trades")

    # 4. SIGNAL STRENGTH
    signals = [o['signal'] for o in opportunities]
    print(f"\n💪 SIGNAL STRENGTH:")
    print(f"    Average: {statistics.mean(signals):.1f}/100")
    print(f"    High Conviction (80+): {sum(1 for s in signals if s >= 80)}")
    print(f"    Medium (65-80): {sum(1 for s in signals if 65 <= s < 80)}")
    print(f"    Low (<65): {sum(1 for s in signals if s < 65)}")

    # 5. SYMBOL DISTRIBUTION
    symbols = [o['symbol'] for o in opportunities]
    print(f"\n🪙 SYMBOL DISTRIBUTION:")
    symbol_counts = defaultdict(int)
    for s in symbols: symbol_counts[s] += 1
    for s, count in sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {s}: {count} ({count/len(symbols)*100:.1f}%)")

    # 6. TOP 5
    print(f"\n🏆 TOP 5 HIGH-CONVICTION SIGNALS:")
    top_signals = sorted(opportunities, key=lambda x: x['signal'], reverse=True)[:5]
    for i, opp in enumerate(top_signals, 1):
        print(f"    {i}. {opp['ticker']} | Signal: {opp['signal']:.1f} | Edge: {opp['edge']:.1f}%")

    print("\n" + "="*60)

    # 7. STRATEGY ADVICE (IMPROVED)
    avg_s = statistics.mean(signals)
    avg_e = statistics.mean(edges)
    
    print(f"\n💡 STRATEGY ADVICE:")

    # Time Window Advice
    if time_counts.get(1) or time_counts.get(2):
        print("    🛑 WINDOW WARNING: Trades detected with < 3 mins left. High risk of expiry whipsaws.")
    elif all(3 <= m <= 9 for m in time_counts.keys() if m is not None):
        print("    ✅ OPTIMAL TIMING: All trades are inside your 3-9 min 'Golden Window'.")

    # Signal Quality Advice
    if avg_s < 70:
        print(f"    ❌ SELECTIVITY CRITICAL: Raise 'min_signal_strength' to 75+ immediately.")
    elif avg_s >= 80:
        print(f"    🔥 HIGH ALPHA: Your setups are elite. Ensure Trend Protector is ON.")

    # Edge vs. Fee Advice
    if avg_e > 20:
        print(f"    ✅ PROFIT BUFFER: {avg_e:.1f}% edge comfortably covers fees.")
    elif avg_e < 10:
        print(f"    🛑 FEE WARNING: Gains will likely be erased by spread and fees.")

if __name__ == "__main__":
    import sys
    log_file = "logs/edge_bot.log"
    if len(sys.argv) > 1:
        log_file = sys.argv[1]

    print(f"Analyzing: {log_file}\n")
    data = parse_logs(log_file)
    analyze_opportunities(data)
