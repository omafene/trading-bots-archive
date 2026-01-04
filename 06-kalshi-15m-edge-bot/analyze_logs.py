#!/usr/bin/env python3
"""
Analyze 15m Edge Bot Logs (v3.1)
Updated to support Signal Strength and new Edge Summary formats.
"""

import re
import logging
import statistics
from datetime import datetime
from collections import defaultdict

def parse_logs(log_file):
    """Parse log file and extract edge opportunities from the new summary lines."""
    opportunities = []
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return []

    for line in lines:
        # Detect the primary summary line: 🎯 EDGE: TICKER | SIDE @ PRICE% | Edge: VALUE% | Signal: VALUE/100
        # This regex is flexible enough to handle PM2 prefixes as well.
        match = re.search(r'🎯 (?:EDGE: )?(KX\S+) \| (\w+) @ (\d+)% \| Edge: ([\d.]+)% \| Signal: ([\d.]+)', line)
        
        if match:
            opp = {
                'ticker': match.group(1),
                'symbol': match.group(1).split('-')[0], # Extracts BTC/ETH from ticker
                'side': match.group(2).lower(),
                'entry_price': float(match.group(3)),
                'edge': float(match.group(4)),
                'signal': float(match.group(5))
            }
            
            # Extract timestamp from the start of the line (common in bot logs)
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\\d{2}:\\d{2})', line)
            if ts_match:
                opp['timestamp'] = ts_match.group(1)
            
            opportunities.append(opp)
            
    return opportunities

def analyze_opportunities(opportunities):
    """Generate comprehensive statistics based on detected edges."""
    if not opportunities:
        print("❌ No opportunities found in logs! Verify the bot is logging '🎯 EDGE' lines.")
        return
    
    print("="*60)
    print("📊 BOT LOG ANALYSIS - PERFORMANCE INSIGHTS")
    print("="*60)
    
    # Overview
    print(f"📈 OVERVIEW:")
    print(f"   Total Opportunities: {len(opportunities)}")
    
    # Edge Stats
    edges = [o['edge'] for o in opportunities]
    print(f"\n💎 EDGE DISTRIBUTION:")
    print(f"   Average Edge: {statistics.mean(edges):.2f}%")
    print(f"   Elite (15%+): {sum(1 for e in edges if e >= 15)} trades")
    print(f"   Standard (3-15%): {sum(1 for e in edges if 3 <= e < 15)} trades")

    # Signal Strength Stats
    signals = [o['signal'] for o in opportunities]
    print(f"\n💪 SIGNAL STRENGTH:")
    print(f"   Average: {statistics.mean(signals):.1f}/100")
    print(f"   High Conviction (80+): {sum(1 for s in signals if s >= 80)}")
    print(f"   Medium (65-80): {sum(1 for s in signals if 65 <= s < 80)}")
    print(f"   Low (<65): {sum(1 for s in signals if s < 65)}")

    # Symbol distribution
    symbols = [o['symbol'] for o in opportunities]
    print(f"\n🪙 SYMBOL DISTRIBUTION:")
    symbol_counts = defaultdict(int)
    for s in symbols: symbol_counts[s] += 1
    for s, count in sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {s}: {count} ({count/len(symbols)*100:.1f}%)")

    # Top 5 Highest Conviction
    print(f"\n🏆 TOP 5 HIGH-CONVICTION SIGNALS:")
    top_signals = sorted(opportunities, key=lambda x: x['signal'], reverse=True)[:5]
    for i, opp in enumerate(top_signals, 1):
        print(f"   {i}. {opp['ticker']} | Signal: {opp['signal']:.1f} | Edge: {opp['edge']:.1f}%")

    print("\n" + "="*60)
    

    # IMPROVED: Logic-based Recommendations
    avg_s = statistics.mean(signals)
    avg_e = statistics.mean(edges)
    low_signals = sum(1 for s in signals if s < 70)
    
    print(f"\n💡 STRATEGY ADVICE:")
    
    # Signal Quality Advice
    if avg_s < 70:
        print(f"   ❌ SELECTIVITY CRITICAL: Your average signal is {avg_s:.1f}. Raise 'min_signal_strength' to 75+ immediately.")
    elif 70 <= avg_s < 80:
        print(f"   ⚠️ CAUTION: You are in the 'Mixed Zone'. {low_signals} trades are still low-quality. Consider tightening your filters.")
    elif avg_s >= 80:
        print(f"   🔥 HIGH ALPHA: Your setups are elite. Ensure 'trend_protection_enabled' is TRUE to avoid whipsaws.")

    # Edge vs. Fee Advice
    if avg_e > 20:
        print(f"   ✅ PROFIT BUFFER: Your {avg_e:.1f}% edge is high enough to easily cover Market Order fees and slippage.")
    elif avg_e < 10:
        print(f"   🛑 FEE WARNING: Small edges detected. High-frequency fees will likely erase your gains. Target >15% edge.")

    # Distribution Advice
    if len(opportunities) > 50:
        print(f"   📈 VOLUME CHECK: High trade frequency detected. Watch your 'max_concurrent_trades' to avoid locking up all capital.")
 


if __name__ == "__main__":
    import sys
    log_file = "logs/edge_bot.log"
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    print(f"Analyzing: {log_file}\n")
    data = parse_logs(log_file)
    analyze_opportunities(data)
