#!/usr/bin/env python3
"""
Signal Performance Histogram
Analyzes logs to find the win rate and PnL for specific Signal Strength brackets.
"""

import yaml
import re
import collections
from kalshi_client import KalshiClient

def parse_signal_data(log_file):
    """Extracts signal and ticker data from logs."""
    trades = []
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return []

    for line in lines:
        # Match the Ticker, Side, Price, Signal, and Edge from the 🎯 EDGE line
        match = re.search(r'🎯 (?:EDGE: )?(KX\S+) \| (\w+) @ (\d+)% \| .*?Signal: ([\d.]+)', line)
        if match:
            trades.append({
                'ticker': match.group(1),
                'side': match.group(2).lower(),
                'entry_price': float(match.group(3)) / 100,
                'signal': float(match.group(4))
            })
    return trades

def check_outcome(client, ticker):
    """Fetches the final market result from Kalshi."""
    try:
        response = client._make_request("GET", f"/markets/{ticker}")
        market = response.get('market', {})
        if market.get('status') in ['settled', 'finalized', 'closed']:
            return market.get('result', '').lower()
    except:
        pass
    return None

def run_histogram():
    # 1. Load Config & Client
    try:
        with open('config_15m.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except:
        print("❌ config_15m.yaml not found.")
        return

    client = KalshiClient(config)
    client.authenticate()

    # 2. Parse Logs
    print("🔍 Analyzing logs...")
    trades = parse_signal_data('logs/edge_bot.log')
    if not trades:
        print("No trades found in logs.")
        return

    # 3. Process Outcomes and Bin by Signal
    # Bins: 50-60, 60-70, 70-80, 80-90, 90-100
    bins = collections.defaultdict(lambda: {'total': 0, 'wins': 0, 'pnl': 0.0})
    
    print(f"📊 Processing {len(trades)} potential trades...")
    seen = set()
    
    for trade in trades:
        if trade['ticker'] in seen: continue
        seen.add(trade['ticker'])
        
        outcome = check_outcome(client, trade['ticker'])
        if outcome:
            # Determine bin (e.g., 74.5 becomes 70)
            signal_bin = int(trade['signal'] // 10) * 10
            bins[signal_bin]['total'] += 1
            
            won = (outcome == trade['side'])
            if won:
                bins[signal_bin]['wins'] += 1
                bins[signal_bin]['pnl'] += (1.0 - trade['entry_price'])
            else:
                bins[signal_bin]['pnl'] -= trade['entry_price']

    # 4. Print Histogram Table
    print("\n" + "="*75)
    print(f"{'SIGNAL RANGE':<15} | {'TRADES':<8} | {'WIN RATE':<10} | {'NET PNL (per contract)':<20}")
    print("-"*75)
    
    for s_range in sorted(bins.keys()):
        data = bins[s_range]
        win_rate = (data['wins'] / data['total']) * 100
        pnl_str = f"${data['pnl']:+,.2f}"
        
        # Simple text bar for visual "histogram" effect
        bar = "█" * int(win_rate / 5)
        
        print(f"{s_range:>3}-{s_range+9:<3} Signal   | {data['total']:<8} | {win_rate:>7.1f}%  | {pnl_str:<20} {bar}")

    print("="*75)
    print("💡 ACTION: Target the signal ranges with the highest Win Rate and Net PnL.")

if __name__ == "__main__":
    run_histogram()
