#!/usr/bin/env python3
"""Check the actual outcomes of specific markets"""

import os
import sys
from dotenv import load_dotenv
from kalshi_client import KalshiClient
from config_loader import load_config_with_env

load_dotenv()

def main():
    # Initialize Kalshi client
    config = load_config_with_env()
    client = KalshiClient(config)

    # Markets to check
    markets = [
        "KXSOL15M-26FEB121130-30",
        "KXETH15M-26FEB121130-30",
        "KXXRP15M-26FEB121130-30",
        "KXBTC15M-26FEB121215-15",
        "KXSOL15M-26FEB121215-15",
        "KXXRP15M-26FEB121215-15",
        "KXETH15M-26FEB121215-15",
    ]

    print("Checking market outcomes...\n")

    for ticker in markets:
        try:
            market = client.get_market(ticker)
            status = market.get('status', 'unknown')
            result = market.get('result', 'unknown')

            # Get title info
            title = market.get('title', 'Unknown')
            yes_subtitle = market.get('yes_sub_title', '')

            print(f"📊 {ticker}")
            print(f"   Title: {title}")
            if yes_subtitle:
                print(f"   Threshold: {yes_subtitle}")
            print(f"   Status: {status}")
            print(f"   Result: {result}")

            # If it's settled, show which side won
            if result == 'yes':
                print(f"   ✅ YES won (price went UP/ABOVE threshold)")
            elif result == 'no':
                print(f"   ✅ NO won (price stayed DOWN/BELOW threshold)")

            print()

        except Exception as e:
            print(f"❌ Error checking {ticker}: {e}\n")

if __name__ == "__main__":
    main()
