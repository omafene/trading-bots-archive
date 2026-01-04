#!/usr/bin/env python3
"""
Test order placement and cancellation
"""
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
import time

def test_order_flow():
    print("=" * 80)
    print("ORDER FLOW TEST")
    print("=" * 80)

    config = load_config_with_env()
    client = KalshiClient(config)

    if not client.authenticate():
        print("❌ Authentication failed")
        return

    print("✅ Authenticated successfully\n")

    # 1. Find any open market with orderbook
    print("🔍 Searching for open markets...")
    markets = client.get_markets(status="open", limit=50)

    if not markets:
        print("❌ No open markets found")
        return

    print(f"✅ Found {len(markets)} open markets")
    print("\nSample markets:")
    for i, m in enumerate(markets[:5]):
        print(f"  {i+1}. {m.get('ticker', 'N/A')}")

    # Use the first available market
    market = markets[0]

    ticker = market['ticker']
    print(f"📊 Testing with market: {ticker}")
    print(f"   Title: {market.get('title', 'N/A')}\n")

    # 2. Get orderbook to find a safe price
    print("📖 Fetching orderbook...")
    orderbook = client.get_orderbook(ticker)

    if not orderbook:
        print("❌ Failed to get orderbook")
        return

    # Get best bid price
    yes_bids = orderbook.get('yes', [])
    if yes_bids and len(yes_bids) > 0:
        best_bid = yes_bids[0]['price']
    else:
        best_bid = 50  # Default to middle if no bids

    # Place order well below best bid (unlikely to fill)
    safe_price = max(1, best_bid - 10)

    print(f"💰 Best YES bid: {best_bid}¢")
    print(f"💰 Our test price: {safe_price}¢ (safely below market)\n")

    # 3. Create order
    print(f"📤 Placing TEST order: 1 YES contract @ {safe_price}¢...")
    order = client.create_order(
        ticker=ticker,
        side='yes',
        quantity=1,
        order_type='limit',
        yes_price=safe_price
    )

    if not order:
        print("❌ Order creation failed")
        return

    order_id = order['order']['order_id']
    print(f"✅ Order created successfully!")
    print(f"   Order ID: {order_id}")
    print(f"   Status: {order['order'].get('status', 'unknown')}\n")

    # 4. Wait and verify
    print("⏳ Waiting 2 seconds...")
    time.sleep(2)

    print("🔍 Checking order status...")
    order_status = client.get_order(order_id)
    if order_status:
        print(f"📋 Order status: {order_status.get('status', 'unknown')}")
        print(f"   Remaining quantity: {order_status.get('remaining_count', 'unknown')}\n")
    else:
        print("⚠️ Could not retrieve order status\n")

    # 5. Cancel order
    print(f"🔄 Cancelling order {order_id}...")
    if client.cancel_order(order_id):
        print("✅ Order cancelled successfully\n")
    else:
        print("❌ Cancellation failed\n")
        return

    # 6. Verify cancellation
    print("⏳ Waiting 1 second...")
    time.sleep(1)

    print("🔍 Verifying cancellation...")
    final_status = client.get_order(order_id)
    if final_status:
        print(f"📋 Final status: {final_status.get('status', 'unknown')}\n")

    print("=" * 80)
    print("✅ ORDER FLOW TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_order_flow()
