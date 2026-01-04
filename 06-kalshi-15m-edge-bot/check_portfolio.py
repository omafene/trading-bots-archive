"""
Get actual portfolio state from Kalshi
"""

from config_loader import load_config_with_env
from kalshi_client import KalshiClient
import json

config = load_config_with_env('config_15m.yaml')
client = KalshiClient(config)

if not client.authenticate():
    print("❌ Authentication failed")
    exit(1)

print("=" * 80)
print("KALSHI PORTFOLIO STATE")
print("=" * 80)
print()

# Get balance
balance = client.get_balance()
print(f"💰 Available Balance: ${balance / 100:.2f}")
print()

# Get all positions
positions = client.get_positions()

if positions:
    print(f"📊 Open Positions: {len(positions)}")
    print()

    total_value = 0
    total_cost = 0

    for pos in positions[:20]:  # Show first 20
        ticker = pos.get('ticker', 'Unknown')
        position = pos.get('position', 0)

        # Get market info
        try:
            market = client.get_market(ticker)
            if market:
                yes_price = market.get('yes_bid', 0) / 100
                no_price = market.get('no_bid', 0) / 100

                # Estimate value
                if position > 0:  # Long YES
                    value = position * yes_price
                elif position < 0:  # Short YES (= Long NO)
                    value = abs(position) * no_price
                else:
                    value = 0

                total_value += value

                print(f"{ticker[:45]:45s} | Contracts: {position:6d} | Est Value: ${value:.2f}")
        except:
            print(f"{ticker[:45]:45s} | Contracts: {position:6d} | Value: ???")

    print()
    print(f"Estimated Portfolio Value: ${total_value:.2f}")
    print(f"Total Account Value: ${balance/100 + total_value:.2f}")
    print()
else:
    print("No open positions found")
    print()

# Get portfolio summary if available
print("=" * 80)
print("ACCOUNT SUMMARY")
print("=" * 80)

try:
    # Check if there's a portfolio summary endpoint
    result = client._make_request("GET", "/portfolio")
    if result:
        print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Could not get portfolio summary: {e}")
