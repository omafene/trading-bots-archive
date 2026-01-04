#!/usr/bin/env python3
"""
Final accurate analysis of today's trades
"""

from kalshi_client import KalshiClient
from config_loader import load_config_with_env


def main():
    config = load_config_with_env()
    client = KalshiClient(config)

    balance = client.get_balance()

    print("="*90)
    print("✅ ACTUAL TRADING ACTIVITY - FEBRUARY 2, 2026")
    print("="*90)
    print(f"\n💰 Current Balance: ${balance:.2f}\n")

    orders = client.get_orders()

    # Filter today's executed orders
    today_executed = [o for o in orders
                      if '2026-02-02' in o.get('created_time', '')
                      and o.get('status') == 'executed']

    today_cancelled = [o for o in orders
                       if '2026-02-02' in o.get('created_time', '')
                       and o.get('status') == 'canceled']

    print(f"📊 Summary:")
    print(f"   ✅ Executed: {len(today_executed)} trades")
    print(f"   ❌ Cancelled: {len(today_cancelled)} orders")
    print(f"   📈 Fill Rate: {len(today_executed)/(len(today_executed)+len(today_cancelled))*100:.1f}%")

    if not today_executed:
        print("\n   No executed trades today")
        return

    print(f"\n{'='*90}")
    print(f"💸 ALL EXECUTED TRADES TODAY")
    print(f"{'='*90}\n")

    total_buy_cost = 0
    total_sell_revenue = 0
    total_fees = 0

    for i, order in enumerate(sorted(today_executed, key=lambda x: x.get('created_time')), 1):
        ticker = order.get('ticker', 'N/A')
        side = order.get('side', 'N/A').upper()
        action = order.get('action', 'N/A').upper()
        fill_count = order.get('fill_count', 0)

        # Price
        price_cents = order.get('yes_price' if side == 'YES' else 'no_price', 0)
        price_dollars = price_cents / 100

        # Costs
        taker_cost = order.get('taker_fill_cost', 0) / 100
        maker_cost = order.get('maker_fill_cost', 0) / 100
        total_cost = taker_cost + maker_cost

        # Fees
        taker_fees = order.get('taker_fees', 0) / 100
        maker_fees = order.get('maker_fees', 0) / 100
        fees = taker_fees + maker_fees

        time = order.get('created_time', '')[11:19]

        # Track totals
        if action == 'BUY':
            total_buy_cost += (total_cost + fees)
        else:
            total_sell_revenue += total_cost

        total_fees += fees

        # Extract symbol
        if 'BTC' in ticker:
            symbol = 'BTC'
        elif 'ETH' in ticker:
            symbol = 'ETH'
        elif 'SOL' in ticker:
            symbol = 'SOL'
        else:
            symbol = '???'

        # Market time
        import re
        match = re.search(r'-(\d{2})(\d{2})-', ticker)
        if match:
            market_time = f"{match.group(1)}:{match.group(2)}"
        else:
            market_time = '??:??'

        print(f"{i}. {time} | {symbol} {market_time} Market")
        print(f"   {action} {fill_count} {side} @ {price_cents}¢ = ${total_cost:.2f}")
        if fees > 0:
            print(f"   Fees: ${fees:.2f} | Total: ${total_cost + fees:.2f}")
        print()

    print(f"{'='*90}")
    print(f"💰 FINANCIAL SUMMARY")
    print(f"{'='*90}\n")
    print(f"   Total Deployed (BUYs): ${total_buy_cost:.2f}")
    print(f"   Total Received (SELLs): ${total_sell_revenue:.2f}")
    print(f"   Total Fees Paid: ${total_fees:.2f}")
    print(f"   Net Cash Flow: ${total_sell_revenue - total_buy_cost:+.2f}")

    # Estimate P&L from sells
    buy_count = sum(1 for o in today_executed if o.get('action') == 'buy')
    sell_count = sum(1 for o in today_executed if o.get('action') == 'sell')

    print(f"\n   Positions Opened: {buy_count}")
    print(f"   Positions Closed: {sell_count}")

    if sell_count > 0:
        print(f"\n   💡 Estimated profit from {sell_count} closed positions: ${total_sell_revenue - total_fees:.2f}")

    print(f"\n{'='*90}\n")


if __name__ == '__main__':
    main()
