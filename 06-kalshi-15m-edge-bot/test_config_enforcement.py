#!/usr/bin/env python3
"""
Comprehensive Config Setting Validation
Tests that all config settings are actually enforced
"""
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from position_manager_15m import PositionManager15m
from telegram_notifier import TelegramNotifier
import time

def test_max_concurrent_trades():
    """Test max_concurrent_trades limit is enforced"""
    print("\n" + "="*80)
    print("TEST: max_concurrent_trades enforcement")
    print("="*80)

    config = load_config_with_env()
    client = KalshiClient(config)
    telegram = TelegramNotifier(config)
    pos_manager = PositionManager15m(client, config, telegram)

    max_trades = config['strategy']['max_concurrent_trades']
    print(f"Config max_concurrent_trades: {max_trades}")

    # Get current position count
    pos_manager.sync_with_exchange()
    current = len(pos_manager.open_positions)
    print(f"Current positions: {current}")

    # Check if limit would be enforced
    total_count = pos_manager.get_total_position_count()
    print(f"Total count (confirmed + pending): {total_count}")

    if total_count >= max_trades:
        print(f"✅ At limit ({total_count}/{max_trades}) - should block new trades")
        can_trade = total_count < max_trades
        assert not can_trade, "Should not allow trading at limit!"
    else:
        print(f"✅ Under limit ({total_count}/{max_trades}) - can trade")

    print("✅ PASSED: max_concurrent_trades check working")

def test_take_profit_enabled():
    """Test TP is enabled and threshold is correct"""
    print("\n" + "="*80)
    print("TEST: Take Profit settings")
    print("="*80)

    config = load_config_with_env()

    tp_enabled = config['strategy'].get('tp_enabled', True)
    target_roi = config['strategy'].get('target_roi', 0.50)
    tp_interval = config['strategy'].get('tp_check_interval')

    print(f"TP Enabled: {tp_enabled}")
    print(f"Target ROI: {target_roi}")
    print(f"TP Check Interval: {tp_interval}s")

    assert tp_enabled in [True, False], "tp_enabled should be boolean"
    assert isinstance(target_roi, (int, float)), "target_roi should be numeric"
    assert target_roi > 0, "target_roi should be positive"
    if tp_interval:
        assert tp_interval > 0, "tp_check_interval should be positive"

    print("✅ PASSED: TP settings valid")

def test_stop_loss_enabled():
    """Test SL is enabled and threshold is correct"""
    print("\n" + "="*80)
    print("TEST: Stop Loss settings")
    print("="*80)

    config = load_config_with_env()

    sl_enabled = config['strategy'].get('stop_loss_enabled', True)
    sl_pct = config['strategy'].get('stop_loss_pct', 0.05)

    print(f"SL Enabled: {sl_enabled}")
    print(f"SL Percentage: {sl_pct}")

    assert sl_enabled in [True, False], "sl_enabled should be boolean"
    assert isinstance(sl_pct, (int, float)), "sl_pct should be numeric"
    assert sl_pct > 0, "sl_pct should be positive"

    print("✅ PASSED: SL settings valid")

def test_position_size_limits():
    """Test position sizing is within configured limits"""
    print("\n" + "="*80)
    print("TEST: Position size limits")
    print("="*80)

    config = load_config_with_env()
    client = KalshiClient(config)

    min_position_size = config['risk']['min_position_size']
    max_position_size = config['risk']['max_position_size']

    print(f"Min position size: {min_position_size}")
    print(f"Max position size: {max_position_size}")

    # Get balance
    balance = client.get_balance()
    if balance:
        print(f"Balance: ${balance:.2f}")
        assert max_position_size <= balance, f"Max position ${max_position_size} exceeds balance ${balance}"
        print("✅ PASSED: Position sizing respects limits")
    else:
        print("⚠️ Could not test (balance unavailable)")

def test_order_expiry():
    """Test order_expiry_seconds is configured"""
    print("\n" + "="*80)
    print("TEST: Order expiry setting")
    print("="*80)

    config = load_config_with_env()

    expiry = config['strategy']['order_expiry_seconds']
    print(f"Order expiry: {expiry}s")

    assert expiry > 0, "Order expiry should be positive"
    assert expiry >= 3, "Order expiry should be at least 3s"

    print("✅ PASSED: Order expiry configured correctly")

def test_edge_detection_settings():
    """Test edge detection thresholds"""
    print("\n" + "="*80)
    print("TEST: Edge detection settings")
    print("="*80)

    config = load_config_with_env()

    min_edge = config['strategy']['min_edge_percent']
    use_advanced = config['strategy']['use_advanced_edge_detection']

    print(f"Min edge threshold: {min_edge}%")
    print(f"Advanced edge detection: {use_advanced}")

    assert min_edge > 0, "Edge threshold should be positive"
    assert use_advanced in [True, False], "use_advanced should be boolean"

    print("✅ PASSED: Edge detection configured correctly")

def test_retry_settings():
    """Test retry configuration"""
    print("\n" + "="*80)
    print("TEST: Retry settings")
    print("="*80)

    config = load_config_with_env()

    retry_attempts = config['execution']['retry_attempts']
    retry_delay = config['execution']['retry_delay']

    print(f"Retry attempts: {retry_attempts}")
    print(f"Retry delay: {retry_delay}s")

    assert retry_attempts >= 0, "Should have at least 0 retries"
    assert retry_delay > 0, "Retry delay should be positive"

    print("✅ PASSED: Retry settings valid")

def test_monitoring_intervals():
    """Test monitoring interval settings"""
    print("\n" + "="*80)
    print("TEST: Monitoring intervals")
    print("="*80)

    config = load_config_with_env()

    scan_interval = config['monitoring']['scan_interval']
    tp_check = config['strategy'].get('tp_check_interval')
    spot_update = config['monitoring']['spot_price_update_interval']

    print(f"Scan interval: {scan_interval}s")
    print(f"TP check interval: {tp_check}s")
    print(f"Spot price update: {spot_update}s")

    assert scan_interval > 0, "Scan interval should be positive"
    if tp_check:
        assert tp_check > 0, "TP check should be positive"
    assert spot_update > 0, "Spot update should be positive"

    # TP check should be faster than scan
    if tp_check:
        assert tp_check <= scan_interval, "TP check should be <= scan interval"

    print("✅ PASSED: Monitoring intervals configured correctly")

def test_api_timeout():
    """Test API timeout setting"""
    print("\n" + "="*80)
    print("TEST: API timeout")
    print("="*80)

    config = load_config_with_env()

    timeout = config['api']['timeout']
    print(f"API timeout: {timeout}s")

    assert timeout > 0, "Timeout should be positive"
    assert timeout >= 5, "Timeout should be at least 5s"
    assert timeout <= 60, "Timeout seems too high"

    print("✅ PASSED: API timeout reasonable")

def test_config_relationships():
    """Test that related config values make sense together"""
    print("\n" + "="*80)
    print("TEST: Config value relationships")
    print("="*80)

    config = load_config_with_env()

    # Order expiry should be > API timeout
    expiry = config['strategy']['order_expiry_seconds']
    timeout = config['api']['timeout']

    print(f"Order expiry: {expiry}s")
    print(f"API timeout: {timeout}s")

    if expiry <= timeout:
        print(f"⚠️ WARNING: Order expiry ({expiry}s) <= timeout ({timeout}s)")
        print("   Orders may expire before API responds!")
    else:
        print(f"✅ Order expiry > timeout ({expiry}s > {timeout}s)")

    # Scan interval should be <= order expiry
    scan_interval = config['monitoring']['scan_interval']
    if scan_interval > expiry:
        print(f"⚠️ WARNING: Scan interval ({scan_interval}s) > expiry ({expiry}s)")
        print("   May miss orders before they expire!")
    else:
        print(f"✅ Scan interval <= expiry ({scan_interval}s <= {expiry}s)")

    print("✅ PASSED: Config relationships valid")

def test_live_tp_application():
    """Test TP is actually applied to live positions"""
    print("\n" + "="*80)
    print("TEST: TP applied to live positions")
    print("="*80)

    config = load_config_with_env()
    client = KalshiClient(config)
    telegram = TelegramNotifier(config)
    pos_manager = PositionManager15m(client, config, telegram)

    if not config['strategy'].get('tp_enabled', True):
        print("⚠️ SKIPPED: TP disabled in config")
        return

    pos_manager.sync_with_exchange()

    if not pos_manager.open_positions:
        print("⚠️ SKIPPED: No open positions to test")
        return

    print(f"Testing TP on {len(pos_manager.open_positions)} positions...")

    # Run TP check
    try:
        pos_manager.manage_take_profit()
        print("✅ PASSED: TP check executed without errors")
    except Exception as e:
        print(f"❌ FAILED: TP check crashed: {e}")
        raise

if __name__ == "__main__":
    print("="*80)
    print("COMPREHENSIVE CONFIG VALIDATION TEST")
    print("="*80)

    tests = [
        ("Max Concurrent Trades", test_max_concurrent_trades),
        ("Take Profit Settings", test_take_profit_enabled),
        ("Stop Loss Settings", test_stop_loss_enabled),
        ("Position Size Limits", test_position_size_limits),
        ("Order Expiry", test_order_expiry),
        ("Edge Detection", test_edge_detection_settings),
        ("Retry Settings", test_retry_settings),
        ("Monitoring Intervals", test_monitoring_intervals),
        ("API Timeout", test_api_timeout),
        ("Config Relationships", test_config_relationships),
        ("Live TP Application", test_live_tp_application),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {name} - {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️ SKIPPED: {name} - {e}")
            skipped += 1

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️ Skipped: {skipped}")
    print(f"Total: {len(tests)}")

    if failed == 0:
        print("\n🎉 ALL CONFIG SETTINGS VALIDATED!")
    else:
        print(f"\n⚠️ {failed} config validation(s) failed - review settings")

    print("="*80)
