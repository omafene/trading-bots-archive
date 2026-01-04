# Conservative Lock Fix - Over-Leverage Protection

**Date**: 2026-02-06
**Approach**: Lock ALL trade attempts permanently (before execution)

---

## The Problem

**Over-leverage incident**: $500.93 spent on 7 duplicate orders in 7 minutes

**Root causes**:
1. ❌ Markets close in <10 minutes → positions settle instantly
2. ❌ API lag (1-3 seconds) → trade succeeds but bot thinks it failed
3. ❌ Time-based locks (30-60s) expire while position already closed
4. ❌ Janitor unlocks tickers when: `time_expired AND no_position_on_kalshi`
5. ❌ Next scan → places DUPLICATE order

---

## The Conservative Solution

**Lock EVERY ticker IMMEDIATELY before attempting trade** (regardless of outcome)

### Timeline
```
09:51:05.000 - Edge detected on KXBTC15M-26FEB061000-00
09:51:05.001 - 🔒 PREVENTIVE LOCK (BEFORE trade attempt)
09:51:05.002 - Add to successfully_traded_tickers (permanent)
09:51:05.003 - Attempt trade → API call sent
09:51:06.000 - API slow/timeout → no response
09:51:06.100 - position_manager returns (False, None)
09:51:06.200 - Log: "Order creation failed"
09:51:06.300 - BUT ticker stays in successfully_traded_tickers ✓
09:51:08.000 - Order appears on Kalshi (2s API lag)
09:52:00.000 - Next scan → ticker locked → SKIPS ✓
10:00:00.000 - Forever more → ticker locked → SKIPS ✓
```

**Result**: Zero chance of duplicates (even if API lags 60+ seconds)

---

## Implementation

### 1. Preventive Lock (edge_bot.py:440-450)
```python
# BEFORE trade attempt:
if ticker not in self.edge_detector.traded_tickers:
    self.edge_detector.traded_tickers.add(ticker)
    # IMMEDIATELY add to permanent locks (preventive)
    self.edge_detector.successfully_traded_tickers.add(ticker)
    self.logger.info(f"🔒 PREVENTIVE LOCK: {ticker} (attempting trade)")
```

### 2. No Unlock on "Failure" (edge_bot.py:517-520)
```python
else:
    self.logger.error(f"❌ Order creation failed for {opp['ticker']}")
    # Ticker already in permanent locks (preventive lock at start)
    # Will stay locked - janitor can verify later if needed
    self.logger.warning(f"⚠️ {ticker} remains locked (preventive)")
```

### 3. Janitor Keeps All Locks (edge_bot.py:345-360)
```python
# HIGHEST PRIORITY: Keep all preventively locked tickers
new_locks.update(self.edge_detector.successfully_traded_tickers)

# Keep locks that have Kalshi positions/orders
new_locks.update(kalshi_tickers)

# Note: With conservative locking, we don't unlock on time expiry
# All trade attempts stay locked permanently
```

---

## What You'll See

### Successful Trade
```
🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00 (attempting trade)
✅ TRADE EXECUTED: KXBTC15M-26FEB061000-00 | NO @ 61% | Expected ROI: 33.1%
🔓 Ticker locks: 0 → 1 (1 positions + 0 pending + 1 preventive)
   🔒 Preventively locked: KXBTC15M-26FEB061000-00
```

### Failed Trade (or API Lag)
```
🔒 PREVENTIVE LOCK: KXSOL15M-26FEB061000-00 (attempting trade)
❌ Order creation failed for KXSOL15M-26FEB061000-00
⚠️ KXSOL15M-26FEB061000-00 remains locked (preventive - verify manually if real failure)
🔓 Ticker locks: 0 → 1 (0 positions + 0 pending + 1 preventive)
   🔒 Preventively locked: KXSOL15M-26FEB061000-00
```

### Next Scan (ticker blocked)
```
⏭️ KXBTC15M-26FEB061000-00 skip: Permanently Locked (Already Traded)
```

---

## Trade-offs

### ✅ Pros
- **Bulletproof**: Zero duplicates even with 60+ second API lag
- **Simple**: No complex verification or retry logic
- **Safe**: Can't over-leverage under any circumstances
- **Fast**: No waiting for multi-second verification

### ⚠️ Cons
- **Failed trades stay locked**: Real failures require manual unlock
- **No auto-retry**: Can't retry same ticker in same session
- **Manual intervention**: Use `/reset` command or restart bot to unlock

---

## Unlocking Failed Trades

If a trade genuinely fails and you want to retry:

### Option 1: Reset All Locks
```python
# In Python console or add as command:
bot.edge_detector.reset_locks()
```

### Option 2: Restart Bot
```bash
# Locks reset on bot restart
systemctl restart edge_bot
```

### Option 3: Manual Removal (Advanced)
```python
# Remove specific ticker:
bot.edge_detector.successfully_traded_tickers.remove('KXBTC15M-26FEB061000-00')
bot.edge_detector.traded_tickers.remove('KXBTC15M-26FEB061000-00')
```

---

## Verification

After deploying, check logs for:

1. **Preventive locks appear BEFORE trade attempts**:
   ```
   🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00 (attempting trade)
   ```

2. **Failed trades stay locked**:
   ```
   ❌ Order creation failed for KXSOL15M-26FEB061000-00
   ⚠️ KXSOL15M-26FEB061000-00 remains locked (preventive)
   ```

3. **No duplicate trade attempts**:
   ```
   # Should NEVER see same ticker attempted twice in logs:
   🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00 (attempting trade)
   ... later ...
   🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00 (attempting trade)  ← SHOULD NOT HAPPEN
   ```

---

## Files Modified

1. **edge_detector_advanced.py** (lines 26-33)
   - Added `successfully_traded_tickers` set
   - Updated `reset_locks()` method

2. **edge_bot.py** (lines 440-520, 345-370)
   - Preventive lock before trade attempt
   - Simplified janitor (no time-based unlocking)
   - Updated logging

---

## Recovery Plan

If this causes issues (e.g., too many false failures getting locked):

### Rollback
```bash
cd /root/kalshi_15m_bot
git diff edge_detector_advanced.py edge_bot.py
# Revert changes manually or restore from backup
```

### Alternative: Add Janitor Cleanup
Add a verification function that runs hourly:
```python
def verify_locked_tickers(self):
    """Check if preventively locked tickers have no position on Kalshi"""
    for ticker in list(self.edge_detector.successfully_traded_tickers):
        # Check Kalshi for any position/order history
        if self._confirmed_no_trade_on_kalshi(ticker):
            # Safe to unlock after 5 minutes
            self.edge_detector.successfully_traded_tickers.remove(ticker)
            self.logger.info(f"🔓 Verified no trade: {ticker} (unlocked)")
```

---

## Why This Works

**The golden rule**: Lock BEFORE attempting, not after confirming

**Old approach**:
```
Attempt → Wait for response → If success, lock → If API lag, duplicate!
```

**New approach**:
```
Lock → Attempt → Don't care about response → Can't duplicate ✓
```

Even if:
- ✅ API takes 60 seconds to respond
- ✅ Response gets lost entirely
- ✅ Order appears on Kalshi 10 seconds later
- ✅ Position closes before next janitor run

**The ticker is ALREADY locked. Cannot retry.**

---

## Monitoring

Watch for these patterns in logs:

### Good Pattern (Working Correctly)
```
10:05:00 - 🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00
10:05:01 - ✅ TRADE EXECUTED: KXBTC15M-26FEB061000-00
10:05:05 - ⏭️ KXBTC15M-26FEB061000-00 skip: Permanently Locked
10:05:10 - ⏭️ KXBTC15M-26FEB061000-00 skip: Permanently Locked
```

### Bad Pattern (BUG - should not happen)
```
10:05:00 - 🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00
10:05:01 - ✅ TRADE EXECUTED: KXBTC15M-26FEB061000-00
10:05:35 - 🔒 PREVENTIVE LOCK: KXBTC15M-26FEB061000-00  ← DUPLICATE!
```

If you see the bad pattern, the preventive lock is not working correctly.

---

## Summary

**Conservative locking = Zero duplicates, zero exceptions, zero excuses**

Trade once → Locked forever → Safe.
