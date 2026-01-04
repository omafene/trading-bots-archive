#!/usr/bin/env python3
"""
Strategy Validation Script v3.1 - Signal Aware
Updated to match the new Signal-based log format and PM2 log structures.
"""

import yaml
import re
import logging
from kalshi_client import KalshiClient

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Validator")

def parse_edge_from_logs(log_file):
    """Extract all detected edges from logs, supporting both old and new formats."""
    detected_edges = []
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return []

    for i in range(len(lines)):
        line = lines[i]
        
        # 1. Flexible Ticker Match (handles "🎯 EDGE: Ticker" or just "🎯 Ticker")
        ticker_match = re.search(r'🎯 (?:EDGE: )?(KX\S+)', line)
        
        if ticker_match:
            ticker = ticker_match.group(1)
            edge_data = {'ticker': ticker}
            
            # 2. Extract Side and Entry Price (e.g., "YES @ 45%")
            side_price_match = re.search(r'(\w+) @ (\d+)%', line)
            if side_price_match:
                edge_data['side'] = side_price_match.group(1).lower()
                edge_data['entry_price'] = float(side_price_match.group(2)) / 100
                
                # 3. Extract Edge Percent (e.g., "Edge: 15.5%")
                edge_val_match = re.search(r'Edge: ([\d.]+)%', line)
                edge_data['edge_percent'] = float(edge_val_match.group(1)) if edge_val_match else 0.0
                
                # 4. Extract Depth Score if available (default to 0)
                depth_match = re.search(r'Depth: (\d+)', line)
                edge_data['depth'] = int(depth_match.group(1)) if depth_match else 0
                
                # 5. Extract Signal Strength if available
                signal_match = re.search(r'Signal: ([\d.]+)', line)
                edge_data['signal_strength'] = float(signal_match.group(1)) if signal_match else 0.0

                detected_edges.append(edge_data)
            
    return detected_edges

def check_market_outcome(client, ticker):
    """Check Kalshi v2 API for the finalized outcome."""
    try:
        response = client._make_request("GET", f"/markets/{ticker}")
        if not response or 'market' not in response:
            return {'settled': False, 'outcome': None, 'status': 'unknown'}
        
        market = response['market']
        status = market.get('status', '').lower()
        result = market.get('result', '').lower()
        is_done = status in ['settled', 'finalized', 'closed']
        
        return {
            'settled': is_done and bool(result),
            'outcome': result if result in ['yes', 'no'] else None,
            'status': status
        }
    except Exception:
        return {'settled': False, 'outcome': None, 'status': 'error'}

def validate_edges(edges, client):
    """Iterate through edges and tally results."""
    print("="*95)
    print(f"{'TICKER':<30} | {'SIDE':<4} @ {'PRICE':<4} | {'SIGNAL':<6} | {'EDGE':<7} | {'RESULT'}")
    print("="*95)
    
    results = {'total': 0, 'settled': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'outcomes': []}
    
    # Use a set to avoid double-checking the same ticker in the same log session
    seen_tickers = set()
    
    for edge in edges:
        ticker = edge['ticker']
        if ticker in seen_tickers: continue
        seen_tickers.add(ticker)
        
        side = edge['side']
        entry = edge['entry_price']
        edge_val = edge['edge_percent']
        signal = edge.get('signal_strength', 0)
        
        outcome_data = check_market_outcome(client, ticker)
        results['total'] += 1
        
        if outcome_data['settled']:
            results['settled'] += 1
            actual = outcome_data['outcome']
            won = (actual == side)
            
            status_str = "✅ WIN" if won else "❌ LOSS"
            profit = (1.0 - entry) if won else -entry
            
            print(f"{ticker:<30} | {side.upper():<4} @ {entry:>4.0%} | {signal:>6.1f} | {edge_val:>6.2f}% | {status_str}")
            
            if won: results['wins'] += 1
            else: results['losses'] += 1
            results['outcomes'].append({'won': won, 'edge': edge_val, 'profit': profit})
        else:
            results['pending'] += 1
            print(f"{ticker:<30} | ⏳ PENDING ({outcome_data['status']})")
            
    return results

def analyze_results(results):
    if results['settled'] == 0:
        print("\n⚠️ No markets settled yet.")
        return

    win_rate = (results['wins'] / results['settled']) * 100
    total_profit = sum(o['profit'] for o in results['outcomes'])
    
    print("\n" + "="*70)
    print(f"FINAL PERFORMANCE REPORT - Win Rate: {win_rate:.1f}%")
    print("="*70)
    print(f"Settled Trades: {results['settled']} | Wins: {results['wins']} | Losses: {results['losses']}")
    print(f"Theoretical PnL: ${total_profit:.2f} (per contract)")
    print("="*70)

def main():
    try:
        with open('config_15m.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception:
        print("❌ config_15m.yaml missing.")
        return

    client = KalshiClient(config)
    if not client.authenticate(): return

    # Check the actual PM2 log or your local log file
    edges = parse_edge_from_logs('logs/edge_bot.log')
    if not edges:
        print("No edges found in logs. Check if logs/edge_bot.log exists and contains '🎯' lines.")
        return

    final_results = validate_edges(edges, client)
    analyze_results(final_results)

if __name__ == "__main__":
    main()
