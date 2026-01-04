"""
Check actual Kalshi account balance
"""

from config_loader import load_config_with_env
from kalshi_client import KalshiClient

config = load_config_with_env('config_15m.yaml')
client = KalshiClient(config)

if client.authenticate():
    print("✅ Authenticated\n")

    # Get balance
    balance = client.get_balance()

    if balance:
        print("=" * 60)
        print("KALSHI ACCOUNT BALANCE")
        print("=" * 60)
        print(f"Balance: ${balance / 100:.2f}")
        print()
        print("If this is ~$16,000, the $15,567 profit is REAL! 🎉")
        print("If this is ~$1,138, there may be unsettled positions.")
    else:
        print("❌ Could not fetch balance")
else:
    print("❌ Authentication failed")
