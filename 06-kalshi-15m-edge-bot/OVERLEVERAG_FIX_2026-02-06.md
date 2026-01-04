# Over-Leverage Bug Fix - 2026-02-06

## The Incident
- **Date**: 2026-02-06, 9:50-9:57 AM
- **Damage**: $500.93 spent across 7 orders in 7 minutes
- **Expected**: 1 trade per ticker
- **Actual**: Multiple duplicate orders on same 3 tickers (BTC, ETH, SOL)

## Root Cause

### The Fatal Flaw
The janitor unlocked tickers when **BOTH** conditions were met:
1. Time lock expired (> `min_ticker_lock_seconds`)
2. No position exists on Kalshi

**The problem**: Markets closing in <10 minutes would:
- Fill instantly → order removed from `pending_orders`
- Close within minutes → position settles/removed from Kalshi
- By the time time-lock expired (30-60s), position was already gone
- Janitor saw "no position + time expired" → unlocked ticker
- Next scan → placed duplicate order

### Timeline Example
```
09:51:05 - Trade KXBTC → fills instantly
09:51:07 - Order removed from pending_orders (filled)
10:00:00 - Market closes → position settles
09:51:55 - Time lock (50s) still active ✓
09:52:05 - Time lock (60s) EXPIRED + NO position = UNLOCKS ✗
09:52:10 - Places ANOTHER order on same ticker!
```

### Why ALL Lock Mechanisms Failed

1. **ticker_lock** - Unlocked after time + no position
2. **api_lag_protection** (30-60s time locks) - Not long enough for fast-closing markets
3. **max_concurrent_trades=3** - Orders filled instantly, freeing slots every scan
4. **correlation_filter** - Should only take 1 best signal, but locks kept expiring

## The Fix

### New Tracking System
Added permanent vs temporary lock tracking:

**Before**:
- `traded_tickers` - all locked tickers (cleared when time + no position)

**After**:
- `successfully_traded_tickers` - **PERMANENT LOCKS** (never unlock)
- `failed_trade_attempts` - temporary locks (unlock after `min_ticker_lock_seconds`)
- `ticker_trade_timestamps` - existing time-based tracking

### Logic Changes

#### 1. On Successful Trade (edge_bot.py:475-489)
```python
if success:
    # CRITICAL FIX: Mark as permanently traded (NEVER unlock)
    self.edge_detector.successfully_traded_tickers.add(ticker)
    self.logger.info(f"🔒 PERMANENT LOCK: {ticker} (successfully traded)")
```

#### 2. On Failed Trade (edge_bot.py:490-498)
```python
else:
    # Mark as failed attempt (will unlock after min_ticker_lock_seconds)
    self.edge_detector.failed_trade_attempts[ticker] = time.time()
    self.logger.warning(f"⚠️ {ticker} trade attempt failed, temporary lock for {min_duration}s")
```

#### 3. Janitor Priority (edge_bot.py:345-396)
```python
# HIGHEST PRIORITY: Keep all successfully traded tickers locked PERMANENTLY
new_locks.update(self.edge_detector.successfully_traded_tickers)

# Keep locks that have Kalshi positions/orders
new_locks.update(kalshi_tickers)

# Handle failed trade attempts (temporary locks)
for ticker, fail_time in list(self.edge_detector.failed_trade_attempts.items()):
    time_since_fail = now - fail_time
    if time_since_fail < min_duration:
        new_locks.add(ticker)  # Keep locked
    else:
        self.edge_detector.failed_trade_attempts.pop(ticker, None)  # Can retry
```

### Files Modified
1. `edge_detector_advanced.py` - Added permanent tracking (lines 29-33, 47-52, 74-80)
2. `edge_bot.py` - Permanent lock on success, temp lock on failure (lines 345-414, 475-498)

## Expected Behavior

### Scenario 1: Successful Trade
```
09:51:05 - Trade KXBTC → SUCCESS
09:51:05 - Add to successfully_traded_tickers (PERMANENT)
09:52:10 - Janitor: Ticker in permanent locks → STAYS LOCKED ✓
09:55:00 - Janitor: Still in permanent locks → STAYS LOCKED ✓
10:00:00 - Market closes, position settles
10:05:00 - Janitor: Still in permanent locks → STAYS LOCKED ✓
```

**Result**: Can NEVER trade KXBTC15M-26FEB061000-00 again (even if position closes)

### Scenario 2: Failed Trade
```
09:51:05 - Trade KXSOL → FAILS
09:51:05 - Add to failed_trade_attempts with timestamp
09:51:10 - Janitor: time_since_fail = 5s < 30s → STAYS LOCKED ✓
09:51:40 - Janitor: time_since_fail = 35s > 30s → UNLOCKS (can retry)
09:51:45 - Can attempt KXSOL again ✓
```

**Result**: Failed attempts can retry after `min_ticker_lock_seconds` (30-60s)

## Testing

Run the bot and verify logs show:
```
🔒 PERMANENT LOCK: KXBTC15M-26FEB061000-00 (successfully traded)
🔓 Ticker locks: 0 → 1 (0 positions + 0 pending + 0 time-locked + 1 permanent)
   🔒 Permanently locked: KXBTC15M-26FEB061000-00
```

Later scans should skip with:
```
⏭️ KXBTC15M-26FEB061000-00 skip: Permanently Locked (Already Traded)
```

## Notes
- Permanent locks persist until bot restart or manual `reset_locks()` call
- This prevents over-leverage even if positions close instantly
- Failed trades still get `min_ticker_lock_seconds` cooldown before retry
- `max_concurrent_trades` now has real protection (can't duplicate tickers)
- No config changes needed - fix is automatic

## Rollback
If issues arise, revert commits to these files:
1. `edge_detector_advanced.py`
2. `edge_bot.py`

Look for changes around lines 29-33, 345-414, 475-498.
