#!/usr/bin/env python3
"""
Find 15-minute BTC/ETH markets on Kalshi
"""

import yaml
from kalshi_client import KalshiClient

# Load config
with open('config_15m.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Connect
client = KalshiClient(config)
if not client.authenticate():
    print("❌ Auth failed")
    exit(1)

print("✅ Connected to Kalshi\n")

# Get markets using pagination (like main bot does)
print("Fetching ALL markets (this may take a moment)...")
all_markets = []
cursor = None

for page in range(10):  # Get up to 10 pages
    try:
        params = {
            "status": "open",
            "limit": 200
        }
        if cursor:
            params['cursor'] = cursor
        
        result = client._make_request("GET", "/markets", params=params)
        
        if not result or 'markets' not in result:
            break
        
        markets = result.get('markets', [])
        all_markets.extend(markets)
        
        cursor = result.get('cursor')
        if not cursor:
            break
        
        print(f"  Page {page + 1}: {len(markets)} markets (total: {len(all_markets)})")
    
    except Exception as e:
        print(f"Error: {e}")
        break

print(f"\n✅ Total markets fetched: {len(all_markets)}\n")

# Look for 15-minute crypto markets
print("="*60)
print("15-MINUTE CRYPTO MARKETS:")
print("="*60)

btc_15m = []
eth_15m = []

for market in all_markets:
    ticker = market.get('ticker', '')
    title = market.get('title', '')
    
    # Check for pattern: KXBTC15M or KXETH15M
    if 'KXBTC15M' in ticker.upper():
        btc_15m.append(market)
    elif 'KXETH15M' in ticker.upper():
        eth_15m.append(market)

print(f"\n🪙 BTC 15-min markets: {len(btc_15m)}")
print(f"🪙 ETH 15-min markets: {len(eth_15m)}")
print(f"📊 Total 15-min markets: {len(btc_15m) + len(eth_15m)}\n")

# Show first 5 of each
if btc_15m:
    print("="*60)
    print("BTC 15-MIN MARKETS (showing first 5):")
    print("="*60)
    for i, market in enumerate(btc_15m[:5], 1):
        print(f"\n{i}. {market.get('ticker')}")
        print(f"   Title: {market.get('title')}")
        print(f"   Close: {market.get('close_time')}")
        print(f"   Volume: ${market.get('volume', 0):,.0f}")

if eth_15m:
    print("\n" + "="*60)
    print("ETH 15-MIN MARKETS (showing first 5):")
    print("="*60)
    for i, market in enumerate(eth_15m[:5], 1):
        print(f"\n{i}. {market.get('ticker')}")
        print(f"   Title: {market.get('title')}")
        print(f"   Close: {market.get('close_time')}")
        print(f"   Volume: ${market.get('volume', 0):,.0f}")

if not btc_15m and not eth_15m:
    print("❌ NO 15-MINUTE MARKETS FOUND")
    print("\nLet me check for other crypto patterns...")
    
    # Check what crypto markets exist
    all_crypto = []
    for market in all_markets:
        ticker = market.get('ticker', '')
        if 'KXBTC' in ticker.upper() or 'KXETH' in ticker.upper():
            all_crypto.append(market)
    
    print(f"\n📊 Total crypto markets: {len(all_crypto)}")
    
    if all_crypto:
        print("\nSample crypto tickers:")
        for market in all_crypto[:10]:
            print(f"  {market.get('ticker')}")
