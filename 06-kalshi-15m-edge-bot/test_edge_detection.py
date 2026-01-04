#!/usr/bin/env python3
"""
Test if edge detection is working
Compare detected edges vs actual market outcomes
"""

import yaml
import time
from datetime import datetime, timezone
from kalshi_client import KalshiClient
from spot_price_feed import CFBenchmarksRTI
from momentum_analyzer import MomentumAnalyzer
from market_scanner_15m import Market15mScanner
from edge_detector import EdgeDetector

# Load config
with open('config_15m.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Override to see ALL edges (even small ones)
config['strategy']['min_edge_percent'] = 1.0  # Show edges >1%
config['strategy']['min_expected_probability'] = 0.50  # Accept any

print("="*60)
print("EDGE DETECTION TEST")
print("="*60)
print()

# Connect
client = KalshiClient(config)
if not client.authenticate():
    print("❌ Auth failed")
    exit(1)

# Initialize components
spot_feed = CFBenchmarksRTI(config)
momentum = MomentumAnalyzer(spot_feed)
scanner = Market15mScanner(client, config)
edge_detector = EdgeDetector(spot_feed, momentum, config)

print("✅ Connected and initialized\n")

# Update price history first
print("Building price history (collecting 10 samples over 50 seconds)...")
for i in range(10):
    btc_price = spot_feed.get_btc_price()
    eth_price = spot_feed.get_eth_price()
    
    if btc_price:
        momentum.update_price_history('BTC')
        print(f"  Sample {i+1}: BTC ${btc_price:,.2f}")
    if eth_price:
        momentum.update_price_history('ETH')
        print(f"  Sample {i+1}: ETH ${eth_price:,.2f}")
    
    if i < 9:
        time.sleep(5)

print("\n" + "="*60)
print("SCANNING FOR MARKETS")
print("="*60)

# Scan for markets
markets = scanner.scan_opportunities()
print(f"\n✅ Found {len(markets)} markets\n")

if not markets:
    print("❌ No markets found. Try again when markets are active.")
    exit(0)

# Analyze each market
print("="*60)
print("EDGE ANALYSIS")
print("="*60)

for market in markets:
    print(f"\n📊 {market['ticker']}")
    print(f"   Title: {market['title']}")
    print(f"   Symbol: {market['symbol']}")
    print(f"   Type: {market['market_type']}")
    print(f"   Closes in: {market['minutes_to_close']:.1f} min")
    print(f"   YES bid: {market['yes_bid']:.0%} | YES ask: {market['yes_ask']:.0%}")
    print(f"   NO bid: {market['no_bid']:.0%} | NO ask: {market['no_ask']:.0%}")
    
    # Get current momentum
    mom = momentum.calculate_momentum(market['symbol'], minutes=15)
    
    if mom:
        print(f"\n   💨 MOMENTUM:")
        print(f"      Direction: {mom['direction'].upper()}")
        print(f"      Change: {mom['percent_change']:+.3f}%")
        print(f"      Trend strength: {mom['trend_strength']:.1%}")
        print(f"      Samples: {mom['num_samples']}")
    else:
        print(f"\n   ⚠️ No momentum data")
    
    # Try to detect edge
    edge = edge_detector.analyze_market(market)
    
    if edge:
        print(f"\n   🎯 EDGE DETECTED!")
        print(f"      Expected prob: {edge['expected_probability']:.1%}")
        print(f"      Market prob: {edge['market_probability']:.1%}")
        print(f"      Edge: {edge['edge_percent']:.2f}%")
        print(f"      Side: {edge['recommended_side'].upper()}")
        print(f"      Entry: {edge['entry_price']:.0%}")
        print(f"      Signal: {edge['signal_strength']:.0f}/100")
    else:
        print(f"\n   ❌ No edge detected")
        
        # Show why
        if mom:
            # Manually calculate what edge detector does
            expected_prob = momentum.calculate_expected_probability(
                market['symbol'], 
                market['market_type'],
                market.get('threshold'),
                15
            )
            
            if expected_prob:
                market_prob = market['yes_ask']
                edge_pct = (expected_prob - market_prob) * 100
                
                print(f"      Expected prob: {expected_prob:.1%}")
                print(f"      Market ask: {market_prob:.1%}")
                print(f"      Edge: {edge_pct:.2f}%")
                print(f"      → Edge too small (< threshold)")
            else:
                print(f"      → Could not calculate expected probability")
        else:
            print(f"      → No momentum data")

print("\n" + "="*60)
print("INTERPRETATION")
print("="*60)

if not any(edge_detector.analyze_market(m) for m in markets):
    print("\n⚠️ NO EDGES FOUND\n")
    print("Possible reasons:")
    print("1. Markets are EFFICIENT - odds already reflect momentum")
    print("2. Momentum model is WRONG - doesn't predict actual outcomes")
    print("3. Sample size too small - need more price history")
    print("4. Threshold too high - lower min_edge_percent in config")
    print("\nRecommendation:")
    print("→ Run this script several times over different hours")
    print("→ Lower min_edge_percent to 1% to see smaller edges")
    print("→ Consider that 15-min markets might be too efficient for momentum strategy")
else:
    print("\n✅ EDGES FOUND - Edge detection is working!")
    print("\nNext steps:")
    print("→ Observe if detected edges actually win")
    print("→ Track win rate over 20+ detected edges")
    print("→ If win rate > 60%, strategy works!")
