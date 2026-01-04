#!/usr/bin/env python3
"""
Strategy Validation Script
Tracks detected edges from logs and verifies them against actual Kalshi outcomes.
"""

import yaml
import re
import logging
from datetime import datetime, timezone
from kalshi_client import KalshiClient

# Setup basic logging for the script itself
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Validator")

def parse_edge_from_logs(log_file):
    """
    Extract all detected edges from logs using improved pattern matching.
    Returns list of: {ticker, timestamp, side, entry_price, edge_percent, expected_prob}
    """
    detected_edges = []
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for opportunity ticker (🎯 KXBTC15M-...)
        ticker_match = re.search(r'🎯 (KXBTC15M-\S+|KXETH15M-\S+)', line)
        
        if ticker_match:
            edge_data = {}
            edge_data['ticker'] = ticker_match.group(1)
            
            # Extract timestamp from this line
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                edge_data['timestamp'] = timestamp_match.group(1)
            
            # Look ahead for details (next 30 lines)
            for j in range(i, min(i+30, len(lines))):
                detail_line = lines[j]
                
                # Extract edge percentage
                if 'EDGE:' in detail_line:
                    edge_match = re.search(r'EDGE: ([\d.]+)%', detail_line)
                    if edge_match:
                        edge_data['edge_percent'] = float(edge_match.group(1))
                
                # Extract probabilities
                if 'Expected:' in detail_line:
                    exp_match = re.search(r'Expected.*?: ([\d.]+)%', detail_line)
                    if exp_match:
                        edge_data['expected_prob'] = float(exp_match.group(1)) / 100
                
                if 'Market:' in detail_line or 'Market Probability:' in detail_line:
                    market_match = re.search(r'Market.*?: ([\d.]+)%', detail_line)
                    if market_match:
                        edge_data['market_prob'] = float(market_match.group(1)) / 100
                
                # Extract recommended side
                if 'Recommended Side:' in detail_line:
                    side_match = re.search(r'Recommended Side: (\w+)', detail_line)
                    if side_match:
                        edge_data['side'] = side_match.group(1).lower()
                
                # Extract entry price
                if 'Entry Price:' in detail_line:
                    entry_match = re.search(r'Entry Price: ([\d.]+)%', detail_line)
                    if entry_match:
                        edge_data['entry_price'] = float(entry_match.group(1)) / 100
                
                # Extract signal strength
                if 'Signal Strength:' in detail_line:
                    signal_match = re.search(r'Signal Strength: ([\d.]+)', detail_line)
                    if signal_match:
                        edge_data['signal'] = float(signal_match.group(1))
            
            # Minimum required data to validate a trade
            if 'edge_percent' in edge_data and ('side' in edge_data or 'entry_price' in edge_data):
                detected_edges.append(edge_data)
            
            i += 30  # Skip block to avoid redundant parsing
        else:
            i += 1
    
    return detected_edges

def check_market_outcome(client, ticker):
    """
    Check Kalshi v2 API for the finalized outcome of a market.
    """
    try:
        # Standard Kalshi v2 Market Endpoint
        response = client._make_request("GET", f"/markets/{ticker}")
        
        if not response or 'market' not in response:
            return {'settled': False, 'outcome': None}
        
        market = response['market']
        # 'finalized' is the standard status for a settled market with a result
        status = market.get('status', '').lower()
        is_done = status in ['settled', 'finalized', 'closed']
        
        # 'result' typically contains "yes" or "no"
        result = market.get('result', '').lower()
        
        return {
            'settled': is_done and bool(result),
            'outcome': result if result in ['yes', 'no'] else None,
            'status': status
        }
    except Exception as e:
        logger.error(f"Error checking {ticker}: {e}")
        return {'settled': False, 'outcome': None}

def validate_edges(edges, client):
    """Iterate through parsed edges and tally wins/losses."""
    print("="*60)
    print(f"VALIDATING {len(edges)} DETECTED EDGES")
    print("="*60)
    
    results = {
        'total': 0, 'settled': 0, 'wins': 0, 'losses': 0,
        'pending': 0, 'total_edge': 0, 'total_signal': 0, 'outcomes': []
    }
    
    for edge in edges:
        ticker = edge.get('ticker')
        side = edge.get('side', 'unknown')
        entry = edge.get('entry_price', 0)
        
        outcome_data = check_market_outcome(client, ticker)
        results['total'] += 1
        results['total_edge'] += edge.get('edge_percent', 0)
        results['total_signal'] += edge.get('signal', 0)
        
        if outcome_data['settled']:
            results['settled'] += 1
            actual = outcome_data['outcome']
            won = (actual == side)
            
            if won:
                results['wins'] += 1
                status_str = "✅ WIN"
                profit = (1.0 - entry) if entry > 0 else 0
            else:
                results['losses'] += 1
                status_str = "❌ LOSS"
                profit = -entry
                
            print(f"{ticker}: Predicted {side.upper()} @ {entry:.0%} | Outcome: {actual.upper()} {status_str}")
            
            results['outcomes'].append({
                'ticker': ticker, 'won': won, 'profit': profit,
                'edge_percent': edge.get('edge_percent', 0),
                'entry_price': entry
            })
        else:
            results['pending'] += 1
            print(f"{ticker}: ⏳ PENDING (Status: {outcome_data['status']})")
            
    return results

def analyze_results(results):
    """Print the final strategy assessment."""
    settled = results['settled']
    if settled == 0:
        print("\n⚠️ No markets have settled yet. Run the bot longer.")
        return

    win_rate = (results['wins'] / settled) * 100
    total_profit = sum(o['profit'] for o in results['outcomes'])
    
    print("\n" + "="*60)
    print("FINAL PERFORMANCE REPORT")
    print("="*60)
    print(f"Win Rate: {win_rate:.1f}% ({results['wins']}/{settled})")
    print(f"Total Theoretical Profit: ${total_profit:.2f} per contract")
    print(f"Avg Edge Detected: {results['total_edge']/results['total']:.2f}%")
    
    if win_rate >= 60:
        print("Assessment: 🔥 EXCELLENT - Strategy has a strong edge.")
    elif win_rate >= 54:
        print("Assessment: ✅ PROFITABLE - Strategy is working but watch spreads.")
    else:
        print("Assessment: ❌ UNPROFITABLE - Revisit Volatility/Momentum logic.")

def main():
    # Load your existing config
    try:
        with open('config_15m.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ config_15m.yaml not found.")
        return

    client = KalshiClient(config)
    if not client.authenticate():
        print("❌ Authentication failed.")
        return

    # Assuming your bot logs to this file
    log_path = 'logs/edge_bot.log'
    edges = parse_edge_from_logs(log_path)
    
    if not edges:
        print("No edges found in logs. Check if '🎯' emoji and 'EDGE:' lines exist.")
        return

    final_results = validate_edges(edges, client)
    analyze_results(final_results)

if __name__ == "__main__":
    main()
