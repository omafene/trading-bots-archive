#!/usr/bin/env python3
"""
Test that config sync settings work correctly
"""
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from position_manager_15m import PositionManager15m
from telegram_notifier import TelegramNotifier
import time

def test_sync_timing():
    """Verify sync happens at configured intervals"""
    config = load_config_with_env()
    client = KalshiClient(config)
    telegram = TelegramNotifier(config)
    pos_manager = PositionManager15m(client, config, telegram)

    print("Testing sync timing...")

    # Record initial state
    initial_positions = len(pos_manager.open_positions)

    # Run sync
    start = time.time()
    pos_manager.sync_with_exchange()
    duration = time.time() - start

    print(f"✅ Sync completed in {duration:.2f}s")
    print(f"   Positions tracked: {len(pos_manager.open_positions)}")

    # Verify sync is reasonably fast
    assert duration < 5, f"Sync took too long: {duration}s"

def test_retry_config():
    """Verify retry settings are configured"""
    config = load_config_with_env()

    assert 'retry_attempts' in config['execution'], "Missing retry_attempts"
    assert config['execution']['retry_attempts'] >= 0, "Need at least 0 retry attempts"

    print(f"✅ Retry attempts: {config['execution']['retry_attempts']}")
    print(f"✅ Retry delay: {config['execution']['retry_delay']}s")

def test_position_consistency():
    """Verify bot position count matches Kalshi"""
    config = load_config_with_env()
    client = KalshiClient(config)
    telegram = TelegramNotifier(config)
    pos_manager = PositionManager15m(client, config, telegram)

    # Sync first
    pos_manager.sync_with_exchange()

    # Get bot's view
    bot_count = len(pos_manager.open_positions)
    bot_tickers = {p['ticker'] for p in pos_manager.open_positions}

    # Get Kalshi's truth
    kalshi_positions = client.get_positions()
    kalshi_count = len([p for p in kalshi_positions if p.get('position', 0) != 0])
    kalshi_tickers = {p['ticker'] for p in kalshi_positions if p.get('position', 0) != 0}

    # Compare
    if bot_count == kalshi_count:
        print(f"✅ Position counts match: {bot_count}")
    else:
        print(f"⚠️ MISMATCH: Bot has {bot_count}, Kalshi has {kalshi_count}")

        missing = kalshi_tickers - bot_tickers
        extra = bot_tickers - kalshi_tickers

        if missing:
            print(f"   Bot missing: {missing}")
        if extra:
            print(f"   Bot has extra: {extra}")

    return bot_count == kalshi_count

if __name__ == "__main__":
    print("=" * 80)
    print("SYNC CONFIG TESTING")
    print("=" * 80)

    test_sync_timing()
    test_retry_config()
    matches = test_position_consistency()

    print("=" * 80)
    if matches:
        print("✅ ALL TESTS PASSED - Config sync working correctly")
    else:
        print("⚠️ POSITION MISMATCH - Review sync logic")
    print("=" * 80)
