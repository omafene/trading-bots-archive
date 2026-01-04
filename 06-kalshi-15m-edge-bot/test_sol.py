import requests
import json

def test_sol_price():
    symbol = "SOL"
    prices = []

    print(f"--- Testing {symbol} Spot Price Fetching ---")

    # 1. Test Coinbase
    try:
        url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            price = float(data['data']['amount'])
            prices.append(price)
            print(f"✅ Coinbase: ${price:,.2f}")
        else:
            print(f"❌ Coinbase Error: {resp.status_code}")
    except Exception as e:
        print(f"❌ Coinbase Exception: {e}")

    # 2. Test Kraken (Note: SOLUSD is standard on Kraken)
    try:
        # Kraken naming check
        pair = "SOLUSD" 
        url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Kraken returns results inside a key that matches the pair name
            # We iterate through keys to find the one containing 'SOL'
            found = False
            for key in data.get('result', {}):
                if 'SOL' in key or 'XSOL' in key:
                    price = float(data['result'][key]['c'][0])
                    prices.append(price)
                    print(f"✅ Kraken:   ${price:,.2f} (Key: {key})")
                    found = True
                    break
            if not found:
                print(f"❌ Kraken Error: SOL pair not found in result {data.get('result', {}).keys()}")
        else:
            print(f"❌ Kraken Error: {resp.status_code}")
    except Exception as e:
        print(f"❌ Kraken Exception: {e}")

    # 3. Final Aggregation (Median Logic)
    if prices:
        prices.sort()
        median = prices[len(prices) // 2]
        print(f"\n📊 AGGREGATED MEDIAN: ${median:,.2f}")
        print(f"Successfully pulled from {len(prices)} sources.")
    else:
        print("\n🚨 CRITICAL: No prices retrieved. Check your internet connection or API status.")

if __name__ == "__main__":
    test_sol_price()
