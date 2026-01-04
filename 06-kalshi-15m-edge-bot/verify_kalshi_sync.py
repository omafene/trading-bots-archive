#!/usr/bin/env python3
"""
Kalshi Sync Verification Script
Tests that bot state matches Kalshi reality
"""

import yaml
from kalshi_client import KalshiClient
from position_manager_15m import PositionManager15m
from config_loader import load_config_with_env
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 80)
    print("KALSHI SYNCHRONIZATION VERIFICATION")
    print("=" * 80)

    # Load config with environment variables
    config = load_config_with_env('config_15m.yaml')

    # Initialize client
    client = KalshiClient(config)
    if not client.authenticate():
        print("❌ Authentication failed")
        return

    print("\n✅ Authenticated successfully")

    # Get current state from Kalshi
    print("\n📊 FETCHING KALSHI STATE...")
    print("-" * 80)

    balance = client.get_balance()
    if balance is not None:
        print(f"Balance: ${balance:.2f}")
    else:
        print("Balance: ❌ Failed to retrieve (API error)")

    positions = client.get_positions()
    if hasattr(positions, 'market_positions'):
        pos_list = positions.market_positions
    elif isinstance(positions, dict):
        pos_list = positions.get('market_positions', [])
    else:
        pos_list = []

    print(f"Active Positions: {len(pos_list)}")

    if pos_list:
        print("\nPosition Details:")
        for i, pos in enumerate(pos_list, 1):
            if isinstance(pos, dict):
                ticker = pos.get('ticker', 'N/A')
                position = pos.get('position', 0)
                print(f"  {i}. {ticker}: {position} contracts")
            else:
                ticker = getattr(pos, 'ticker', 'N/A')
                position = getattr(pos, 'position', 0)
                print(f"  {i}. {ticker}: {position} contracts")

    # Get recent orders
    orders = client.get_orders(status="resting")
    print(f"\nResting Orders: {len(orders) if orders else 0}")

    if orders:
        print("\nOrder Details:")
        for i, order in enumerate(orders[:5], 1):
            ticker = order.get('ticker', 'N/A')
            side = order.get('side', 'N/A')
            status = order.get('status', 'N/A')
            print(f"  {i}. {ticker} ({side.upper()}) - {status}")

    # Test position manager sync
    print("\n\n🔄 TESTING POSITION MANAGER SYNC...")
    print("-" * 80)

    from telegram_notifier import TelegramNotifier
    telegram = TelegramNotifier(config)
    pos_manager = PositionManager15m(client, config, telegram)

    pos_manager.sync_with_exchange()

    print(f"Bot's Position Count: {len(pos_manager.open_positions)}")
    print(f"Bot's Pending Orders: {len(pos_manager.pending_orders)}")

    if pos_manager.open_positions:
        print("\nBot's Tracked Positions:")
        for i, pos in enumerate(pos_manager.open_positions, 1):
            ticker = pos.get('ticker', 'N/A')
            side = pos.get('side', 'N/A')
            print(f"  {i}. {ticker} ({side.upper()})")

    # Verification
    print("\n\n✅ VERIFICATION:")
    print("-" * 80)

    kalshi_count = len(pos_list)
    bot_count = len(pos_manager.open_positions)

    if kalshi_count == bot_count:
        print(f"✅ SYNC SUCCESSFUL: Bot matches Kalshi ({bot_count} positions)")
    else:
        print(f"⚠️ SYNC MISMATCH:")
        print(f"   Kalshi shows: {kalshi_count} positions")
        print(f"   Bot tracking: {bot_count} positions")
        print(f"   Difference: {abs(kalshi_count - bot_count)}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
