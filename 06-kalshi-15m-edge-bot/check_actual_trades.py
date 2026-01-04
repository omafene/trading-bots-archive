#!/usr/bin/env python3
"""
Check actual trade executions via Kalshi API
"""

import os
import sys
from kalshi_client import KalshiClient
from config_loader import load_config_with_env


def main():
    print("="*70)
    print("🔍 CHECKING ACTUAL KALSHI ACCOUNT ACTIVITY")
    print("="*70)

    # Load config
    config = load_config_with_env()

    # Initialize client
    client = KalshiClient(config)

    # Get current balance
    balance = client.get_balance()
    print(f"\n💰 Current Balance: ${balance:.2f}")

    # Get current positions
    print(f"\n📊 Current Positions:")
    try:
        positions = client.get_positions()

        if not positions:
            print("   No open positions")
        else:
            print(f"   Found {len(positions)} positions:")
            for pos in positions:
                ticker = pos.get('ticker', 'N/A')
                side = pos.get('side', 'N/A')
                count = pos.get('position', 0)
                market_exposure = pos.get('market_exposure', 0)

                print(f"\n   • {ticker}")
                print(f"     Side: {side.upper()}")
                print(f"     Contracts: {count}")
                print(f"     Exposure: ${abs(market_exposure)/100:.2f}")

    except Exception as e:
        print(f"   Error getting positions: {e}")

    # Get fills (recent trades)
    print(f"\n📜 Recent Fills (Today):")
    try:
        fills = client.get_fills()

        if not fills:
            print("   No fills found")
        else:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')

            today_fills = [f for f in fills if today in f.get('created_time', '')]

            if not today_fills:
                print(f"   No fills today ({today})")
            else:
                print(f"   Found {len(today_fills)} fills today:")

                for fill in today_fills:
                    ticker = fill.get('ticker', 'N/A')
                    side = fill.get('side', 'N/A')
                    count = fill.get('count', 0)
                    price = fill.get('yes_price' if side == 'yes' else 'no_price', 0)
                    action = fill.get('action', 'N/A')
                    time = fill.get('created_time', '')[:19]

                    print(f"\n   • {time}")
                    print(f"     {ticker}")
                    print(f"     {action.upper()} {count} {side.upper()} @ ${price/100:.2f}")

    except Exception as e:
        print(f"   Error getting fills: {e}")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
