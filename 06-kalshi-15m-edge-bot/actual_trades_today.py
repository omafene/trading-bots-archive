#!/usr/bin/env python3
"""
Get actual trade history from Kalshi
"""

from kalshi_client import KalshiClient
from config_loader import load_config_with_env
from datetime import datetime


def main():
    print("="*80)
    print("📊 ACTUAL TRADING ACTIVITY - FEB 2, 2026")
    print("="*80)

    config = load_config_with_env()
    client = KalshiClient(config)

    # Current balance
    balance = client.get_balance()
    print(f"\n💰 Current Balance: ${balance:.2f}")

    # Get order history
    print(f"\n📜 Order History:")

    try:
        # Get all orders (filled and unfilled)
        all_orders = client.get_orders()

        if not all_orders:
            print("   No orders found")
        else:
            print(f"   Total orders: {len(all_orders)}")

            # Filter for today
            today = '2026-02-02'
            today_orders = [o for o in all_orders
                           if today in o.get('created_time', '')]

            if not today_orders:
                print(f"\n   No orders today ({today})")
            else:
                print(f"\n   Orders today: {len(today_orders)}")

                # Group by status
                by_status = {}
                for order in today_orders:
                    status = order.get('status', 'unknown')
                    by_status.setdefault(status, []).append(order)

                print(f"\n   By Status:")
                for status, orders in sorted(by_status.items()):
                    print(f"      {status}: {len(orders)}")

                # Show executed orders
                executed = by_status.get('executed', [])
                if executed:
                    print(f"\n   ✅ EXECUTED TRADES TODAY: {len(executed)}")

                    total_buy_cost = 0
                    total_sell_revenue = 0

                    for order in executed:
                        ticker = order.get('ticker', 'N/A')
                        side = order.get('side', 'N/A')
                        action = order.get('action', 'N/A')
                        quantity = order.get('quantity', 0)
                        price = order.get('yes_price' if side == 'yes' else 'no_price', 0)
                        time = order.get('created_time', '')[:19]

                        cost = (quantity * price) / 100
                        if action == 'buy':
                            total_buy_cost += cost
                        else:
                            total_sell_revenue += cost

                        print(f"\n      • {time}")
                        print(f"        {ticker[:40]}")
                        print(f"        {action.upper()} {quantity} {side.upper()} @ {price}¢ = ${cost:.2f}")

                    print(f"\n   💰 Summary:")
                    print(f"      Total Bought: ${total_buy_cost:.2f}")
                    print(f"      Total Sold: ${total_sell_revenue:.2f}")
                    print(f"      Net: ${total_sell_revenue - total_buy_cost:+.2f}")

                # Show cancelled/failed
                failed = by_status.get('canceled', []) + by_status.get('expired', [])
                if failed:
                    print(f"\n   ❌ Cancelled/Expired: {len(failed)} orders")

    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)


if __name__ == '__main__':
    main()
