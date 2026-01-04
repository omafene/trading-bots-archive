#!/usr/bin/env python3
"""
Strategy Validation Script
Tracks detected edges and verifies if they actually win
"""

import yaml
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from kalshi_client import KalshiClient

def parse_edge_from_logs(log_file):
    """
    Extract all detected edges from logs
    Returns list of: {ticker, timestamp, side, entry_price, edge_percent, expected_prob}
    """
    detected_edges = []
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
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
                
                # Extract edge percentage (look for "EDGE: X.X%")
                if 'EDGE:' in detail_line:
                    edge_match = re.search(r'EDGE: ([\d.]+)%', detail_line)
                    if edge_match:
                        edge_data['edge_percent'] = float(edge_match.group(1))
                
                # Extract probabilities (Expected: X% | Market: Y%)
                if 'Expected:' in detail_line:
                    exp_match = re.search(r'Expected.*?: ([\d.]+)%', detail_line)
                    if exp_match:
                        edge_data['expected_prob'] = float(exp_match.group(1)) / 100
                
                if 'Market:' in detail_line or 'Market Probability:' in detail_line:
                    market_match = re.search(r'Market.*?: ([\d.]+)%', detail_line)
                    if market_match:
                        edge_data['market_prob'] = float(market_match.group(1)) / 100
                
                # Extract recommended side and entry
                if 'Recommended Side:' in detail_line:
                    side_match = re.search(r'Recommended Side: (\w+)', detail_line)
                    if side_match:
                        edge_data['side'] = side_match.group(1).lower()
                
                if 'Entry Price:' in detail_line:
                    entry_match = re.search(r'Entry Price: ([\d.]+)%', detail_line)
                    if entry_match:
                        edge_data['entry_price'] = float(entry_match.group(1)) / 100
                
                # Extract signal strength
                if 'Signal Strength:' in detail_line:
                    signal_match = re.search(r'Signal Strength: ([\d.]+)', detail_line)
                    if signal_match:
                        edge_data['signal'] = float(signal_match.group(1))
            
            # If we got minimum required data, add it
            if 'edge_percent' in edge_data and ('side' in edge_data or 'entry_price' in edge_data):
                detected_edges.append(edge_data)
                print(f"  Found edge: {edge_data['ticker']} - Edge: {edge_data.get('edge_percent', 0):.1f}%")
            
            i += 30  # Skip ahead
        else:
            i += 1
    
    return detected_edges

def check_market_outcome(client, ticker):
    """
    Check if a market has settled and what the outcome was
    Returns: {'settled': True/False, 'outcome': 'yes'/'no'/None}
    """
    try:
        # Get market info
        response = client._make_request("GET", f"/markets/{ticker}")
        
        if not response:
            return {'settled': False, 'outcome': None}
        
        market = response.get('market', {})
        status = market.get('status', '')
        result = market.get('result', '')
        
        if status == 'settled' or status == 'closed':
            settled = True
            outcome = result.lower() if result else None
        else:
            settled = False
            outcome = None
        
        return {
            'settled': settled,
            'outcome': outcome,
            'status': status,
            'result': result
        }
        
    except Exception as e:
        print(f"Error checking {ticker}: {e}")
        return {'settled': False, 'outcome': None}


def validate_edges(edges, client):
    """
    Check outcomes for all detected edges
    Calculate win rate and actual performance
    """
    
    print("="*60)
    print("VALIDATING DETECTED EDGES")
    print("="*60)
    print()
    
    results = {
        'total': 0,
        'settled': 0,
        'wins': 0,
        'losses': 0,
        'pending': 0,
        'total_edge': 0,
        'total_signal': 0,
        'outcomes': []
    }
    
    for edge in edges:
        ticker = edge.get('ticker')
        side = edge.get('side')
        entry = edge.get('entry_price', 0)
        expected = edge.get('expected_prob', 0)
        edge_pct = edge.get('edge_percent', 0)
        signal = edge.get('signal', 0)
        
        print(f"Checking: {ticker}")
        print(f"  Predicted: {side.upper()} @ {entry:.0%}")
        print(f"  Expected prob: {expected:.0%}")
        print(f"  Edge: {edge_pct:.1f}%")
        
        # Check outcome
        outcome = check_market_outcome(client, ticker)
        
        results['total'] += 1
        results['total_edge'] += edge_pct
        results['total_signal'] += signal
        
        if outcome['settled']:
            results['settled'] += 1
            actual_outcome = outcome['outcome']
            
            # Did we win?
            if actual_outcome == side:
                results['wins'] += 1
                won = True
                print(f"  Outcome: {actual_outcome.upper()} ✅ WIN")
                
                # Calculate actual profit
                profit = (1 - entry) if entry > 0 else 0
                roi = (profit / entry * 100) if entry > 0 else 0
                
            else:
                results['losses'] += 1
                won = False
                print(f"  Outcome: {actual_outcome.upper()} ❌ LOSS")
                
                profit = -entry
                roi = -100
            
            results['outcomes'].append({
                'ticker': ticker,
                'predicted_side': side,
                'actual_outcome': actual_outcome,
                'won': won,
                'entry_price': entry,
                'profit': profit,
                'roi': roi,
                'edge_percent': edge_pct,
                'signal': signal
            })
            
        else:
            results['pending'] += 1
            print(f"  Status: {outcome.get('status', 'unknown')} ⏳ PENDING")
        
        print()
    
    return results


def analyze_results(results):
    """
    Generate comprehensive analysis of results
    """
    
    print("="*60)
    print("VALIDATION RESULTS")
    print("="*60)
    print()
    
    total = results['total']
    settled = results['settled']
    wins = results['wins']
    losses = results['losses']
    pending = results['pending']
    
    print(f"📊 OVERVIEW:")
    print(f"   Total edges detected: {total}")
    print(f"   Settled: {settled}")
    print(f"   Pending: {pending}")
    print()
    
    if settled == 0:
        print("⚠️ No settled markets yet - need to wait longer")
        print()
        
        if total > 0:
            avg_edge = results['total_edge'] / total
            avg_signal = results['total_signal'] / total
            
            print(f"📈 DETECTED EDGES STATS:")
            print(f"   Average edge: {avg_edge:.2f}%")
            print(f"   Average signal: {avg_signal:.1f}/100")
        
        return
    
    # Calculate performance metrics
    win_rate = (wins / settled * 100) if settled > 0 else 0
    
    print(f"🎯 PERFORMANCE:")
    print(f"   Wins: {wins}")
    print(f"   Losses: {losses}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print()
    
    # Calculate profitability
    outcomes = results['outcomes']
    
    if outcomes:
        total_profit = sum(o['profit'] for o in outcomes)
        total_invested = sum(o['entry_price'] for o in outcomes)
        avg_roi = (total_profit / total_invested * 100) if total_invested > 0 else 0
        
        print(f"💰 PROFITABILITY:")
        print(f"   Total profit: ${total_profit:.2f}")
        print(f"   Total invested: ${total_invested:.2f}")
        print(f"   Average ROI: {avg_roi:.1f}%")
        print()
        
        # Edge vs actual
        avg_edge = sum(o['edge_percent'] for o in outcomes) / len(outcomes)
        avg_signal = sum(o['signal'] for o in outcomes) / len(outcomes)
        
        print(f"📊 EDGE ACCURACY:")
        print(f"   Average edge detected: {avg_edge:.2f}%")
        print(f"   Average signal: {avg_signal:.1f}/100")
        print()
    
    # Break down by edge size
    if outcomes:
        print(f"📈 WIN RATE BY EDGE SIZE:")
        
        edge_buckets = {
            '15%+': [],
            '10-15%': [],
            '7-10%': [],
            '5-7%': [],
            '3-5%': [],
            '<3%': []
        }
        
        for o in outcomes:
            edge = o['edge_percent']
            if edge >= 15:
                edge_buckets['15%+'].append(o)
            elif edge >= 10:
                edge_buckets['10-15%'].append(o)
            elif edge >= 7:
                edge_buckets['7-10%'].append(o)
            elif edge >= 5:
                edge_buckets['5-7%'].append(o)
            elif edge >= 3:
                edge_buckets['3-5%'].append(o)
            else:
                edge_buckets['<3%'].append(o)
        
        for bucket, trades in edge_buckets.items():
            if trades:
                bucket_wins = sum(1 for t in trades if t['won'])
                bucket_rate = bucket_wins / len(trades) * 100
                print(f"   {bucket}: {bucket_wins}/{len(trades)} = {bucket_rate:.1f}% win rate")
    
    print()
    
    # Strategy assessment
    print("="*60)
    print("🎯 STRATEGY ASSESSMENT:")
    print("="*60)
    print()
    
    if settled < 10:
        print(f"⚠️ Sample size too small ({settled} trades)")
        print(f"   Need at least 20 settled trades for reliable assessment")
        print(f"   Let bot run longer...")
    
    elif win_rate < 52:
        print(f"❌ STRATEGY DOES NOT WORK")
        print(f"   Win rate {win_rate:.1f}% is below break-even")
        print(f"   → Momentum does not predict outcomes")
        print(f"   → Pivot to different strategy")
    
    elif win_rate < 58:
        print(f"⚠️ MARGINAL STRATEGY")
        print(f"   Win rate {win_rate:.1f}% is barely profitable")
        print(f"   → Implement spread checking")
        print(f"   → Optimize execution")
        print(f"   → Test with more data")
    
    elif win_rate < 65:
        print(f"✅ STRATEGY WORKS!")
        print(f"   Win rate {win_rate:.1f}% is profitable")
        print(f"   → Implement all optimizations")
        print(f"   → Start small live trading")
        print(f"   → Continue validation")
    
    else:
        print(f"✅✅ EXCELLENT STRATEGY!")
        print(f"   Win rate {win_rate:.1f}% is very profitable")
        print(f"   → Implement Kelly sizing")
        print(f"   → Scale up capital")
        print(f"   → Monitor for regression")
    
    print()


def main():
    print("="*60)
    print("🧪 STRATEGY VALIDATION TOOL")
    print("="*60)
    print()
    
    # Load config
    with open('config_15m.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Connect
    client = KalshiClient(config)
    if not client.authenticate():
        print("❌ Auth failed")
        return
    
    print("✅ Connected to Kalshi")
    print()
    
    # Parse logs
    print("Parsing logs for detected edges...")
    edges = parse_edge_from_logs('logs/edge_bot.log')
    
    print(f"Found {len(edges)} detected edges in logs")
    print()
    
    if not edges:
        print("❌ No edges found in logs yet")
        print()
        print("Possible reasons:")
        print("1. Bot hasn't run long enough")
        print("2. No edges meeting criteria")
        print("3. Markets too efficient")
        print()
        print("Let bot run for at least a few hours and try again")
        return
    
    # Validate edges
    results = validate_edges(edges, client)
    
    # Analyze results
    analyze_results(results)
    
    # Show top wins and losses
    if results['outcomes']:
        print("="*60)
        print("📊 TOP TRADES:")
        print("="*60)
        print()
        
        sorted_outcomes = sorted(results['outcomes'], key=lambda x: x['profit'], reverse=True)
        
        print("Best Wins:")
        for o in sorted_outcomes[:3]:
            if o['won']:
                print(f"  {o['ticker']}: {o['predicted_side'].upper()} @ {o['entry_price']:.0%} → ${o['profit']:.2f} profit")
        
        print()
        print("Worst Losses:")
        for o in sorted_outcomes[-3:]:
            if not o['won']:
                print(f"  {o['ticker']}: {o['predicted_side'].upper()} @ {o['entry_price']:.0%} → ${o['profit']:.2f} loss")
        
        print()


if __name__ == "__main__":
    main()
