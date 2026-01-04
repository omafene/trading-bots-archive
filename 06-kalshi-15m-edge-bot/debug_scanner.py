#!/usr/bin/env python3
"""
Debug: What markets is Kalshi actually returning?
"""

import yaml
from datetime import datetime, timezone
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

# Get all open markets
print("Fetching all open markets...")
response = client._make_request("GET", "/markets", params={
    "status": "open",
    "limit": 1000
})

if not response or not isinstance(response, dict):
    print("❌ No response from API")
    exit(1)

markets = response.get('markets', [])
print(f"Total markets returned: {len(markets)}\n")

# Look for 15m markets
print("="*60)
print("SEARCHING FOR KXBTC15M AND KXETH15M:")
print("="*60)

btc15m_count = 0
eth15m_count = 0
now = datetime.now(timezone.utc)

for market in markets:
    ticker = market.get('ticker', '')
    
    # Check for 15m markets
    if 'KXBTC15M' in ticker or 'KXETH15M' in ticker:
        symbol = 'BTC' if 'KXBTC15M' in ticker else 'ETH'
        
        if 'KXBTC15M' in ticker:
            btc15m_count += 1
        else:
            eth15m_count += 1
        
        close_time_str = market.get('close_time', '')
        title = market.get('title', '')
        
        # Calculate minutes to close
        minutes_to_close = "N/A"
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                minutes_to_close = (close_time - now).total_seconds() / 60
                minutes_to_close = f"{minutes_to_close:.1f} min"
            except:
                pass
        
        print(f"\n{symbol}: {ticker}")
        print(f"   Title: {title}")
        print(f"   Closes in: {minutes_to_close}")
        print(f"   Close time: {close_time_str}")

print(f"\n{'='*60}")
print(f"SUMMARY:")
print(f"{'='*60}")
print(f"KXBTC15M markets: {btc15m_count}")
print(f"KXETH15M markets: {eth15m_count}")
print(f"Total 15m markets: {btc15m_count + eth15m_count}")

if btc15m_count == 0 and eth15m_count == 0:
    print("\n❌ NO 15-MIN MARKETS FOUND!")
    print("\nPossible reasons:")
    print("1. Markets might not be available at this time")
    print("2. Kalshi might have changed ticker format")
    print("3. Markets might be under different tickers")
    
    # Show some sample tickers to help debug
    print("\nSample tickers from response (first 20):")
    for i, market in enumerate(markets[:20]):
        ticker = market.get('ticker', '')
        if 'BTC' in ticker or 'ETH' in ticker:
            print(f"  {ticker}")
else:
    print(f"\n✅ Found {btc15m_count + eth15m_count} 15-minute markets")
