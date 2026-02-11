# Drift-Based Recalibration Implementation

**Date:** 2026-02-11
**Status:** ✅ Complete and ready for testing
**Applies to:** v2_calibrated model ONLY (v1 remains unchanged)

---

## 🎯 What Was Built

The v2_calibrated model now supports **adaptive recalibration** triggered by performance drift, not just fixed schedules.

### Key Innovation:

Instead of "recalibrate every 7 days," the bot now recalibrates when **model performance deviates from expectations**.

**Traditional Approach (Schedule-Based):**
```
Day 1 → Calibrate
Day 7 → Recalibrate (even if performance is perfect)
Day 14 → Recalibrate (even if market hasn't changed)
```

**New Approach (Drift-Based):**
```
Day 1 → Calibrate
Day 2 → Performance drifts 13% → RECALIBRATE ✅
Day 5 → Performance stable (5% drift) → No recalibration
Day 8 → Market regime shift, 11% drift → RECALIBRATE ✅
```

---

## 📊 How Drift Detection Works

### The Concept:

```
Every time _maybe_recalibrate() is called:
  ├─ Load last 100 trades from skipped_trades.csv
  ├─ For UP trends:
  │   ├─ What did calibration curve predict? → Expected WR
  │   ├─ What actually happened? → Actual WR
  │   └─ Drift = |Actual WR - Expected WR|
  │
  ├─ For DOWN trends:
  │   └─ Same calculation
  │
  └─ If drift > 10% → TRIGGER RECALIBRATION
```

### Example:

**Calibration Curve Says:**
- Bot probability 70% → Expect 55% actual WR

**Recent Performance (Last 100 trades at ~70% bot prob):**
- Actual WR: 68%

**Drift Calculation:**
- Drift = |68% - 55%| = **13%**
- Threshold = 10%
- **13% > 10%** → 🔄 **RECALIBRATE NOW!**

---

## ⚙️ Three Recalibration Modes

### **Mode 1: Schedule** (Fixed Interval)

```yaml
recalibration_mode: "schedule"
recalibration_interval_days: 7
```

**Behavior:**
- Recalibrates every 7 days, regardless of performance
- Simple, predictable
- Misses market regime changes between intervals

**Use when:**
- You prefer predictable, fixed schedules
- Testing baseline behavior

---

### **Mode 2: Drift** (Pure Adaptive)

```yaml
recalibration_mode: "drift"
drift_threshold_percent: 10.0  # 10% drift threshold
```

**Behavior:**
- Only recalibrates when performance drifts >10%
- Responsive to market changes
- Could recalibrate daily in volatile markets, or not for weeks in stable markets

**Use when:**
- You want maximum responsiveness
- Markets are highly volatile
- You trust drift detection

---

### **Mode 3: Hybrid** (Recommended) ⭐

```yaml
recalibration_mode: "hybrid"
drift_threshold_percent: 10.0
max_recalibration_interval_days: 7
min_recalibration_interval_hours: 12
```

**Behavior:**
- Triggers on **EITHER** drift OR schedule
- Respects min/max intervals (prevents over/under-fitting)
- Best of both worlds

**Trigger Logic:**
```
Recalibrate IF:
  (Drift > 10%)  OR  (7 days passed)

BUT RESPECT:
  - Don't recalibrate if <12 hours since last (cooldown)
  - Force recalibrate if >7 days passed (max staleness)
```

**Use when:**
- Trading crypto (volatile markets)
- Want responsiveness + stability
- Production use (RECOMMENDED)

---

## 📐 Configuration Options

### Full Config (Both Bots):

```yaml
calibration:
  # === DYNAMIC CALIBRATION (v2 model only) ===
  dynamic_recalibration_enabled: true

  # === RECALIBRATION MODE ===
  recalibration_mode: "hybrid"  # Options: "schedule", "drift", "hybrid"

  # SCHEDULE-BASED SETTINGS
  recalibration_interval_days: 7  # For schedule mode

  # DRIFT-BASED SETTINGS (adaptive to market changes)
  drift_threshold_percent: 10.0  # Recalibrate if >10% drift
  drift_check_interval_trades: 50  # (Currently unused - checked on startup/periodic calls)
  min_drift_samples: 50  # Need 50+ samples to calculate reliable drift
  drift_lookback_trades: 100  # Use last 100 trades for drift calculation

  # HYBRID MODE LIMITS
  max_recalibration_interval_days: 7  # Force recal after 7 days max
  min_recalibration_interval_hours: 12  # Don't recal more than every 12h

  # DATA REQUIREMENTS
  recalibration_lookback_days: 30  # Use last 30 days for recalibration
  min_samples_for_recalibration: 100  # Need 100+ trades to recalibrate
  separate_curves_by_direction: true  # Separate UP/DOWN curves
```

---

## 🎚️ Recommended Thresholds for Crypto

Based on crypto market volatility characteristics:

| Setting | Conservative | Balanced | Aggressive |
|---------|-------------|----------|------------|
| **Drift Threshold** | 15% | 10% ⭐ | 8% |
| **Min Samples** | 100 | 50 ⭐ | 30 |
| **Cooldown** | 24h | 12h ⭐ | 6h |
| **Max Interval** | 14d | 7d ⭐ | 3d |

**Why 10% for crypto?**
- Below 8%: Could be statistical noise
- 10-12%: Meaningful market regime shift
- Above 15%: Model is seriously degraded (too late)

**Comparison to Traditional Finance:**
- TradFi: 3-5% drift (stable markets)
- Crypto: 8-15% drift (volatile markets) ✅

---

## 📋 Files Modified

### Kalshi Bot:
- `/root/kalshi_15m_bot/momentum_analyzer.py`
  - Added drift configuration loading (lines 47-68)
  - Updated `_maybe_recalibrate()` with mode logic (lines 471-506)
  - Added `_should_recalibrate_schedule()` (lines 508-519)
  - Added `_should_recalibrate_drift()` (lines 521-540)
  - Added `_calculate_calibration_drift()` (lines 542-607)

- `/root/kalshi_15m_bot/config_15m.yaml`
  - Added drift-based recalibration config (lines 216-242)

### Polymarket Bot:
- `/root/polymarket_15m_bot/momentum_analyzer.py`
  - Same changes as Kalshi bot

- `/root/polymarket_15m_bot/config_polymarket.yaml`
  - Added drift-based recalibration config (lines 227-253)

**Syntax check:** ✅ Both files compile successfully

---

## 📊 Expected Log Output

### On Startup (Drift Check):

```
✅ Momentum analyzer initialized (interval: 1s, buffer: 1200 samples = 20 min)
📊 Dynamic calibration ENABLED (hybrid mode, drift 10.0% OR 7d)

📊 UP Drift Check (last 43 trades):
   Expected WR (from curve): 45.2%
   Actual WR: 51.6%
   Drift: 6.4% ✓ OK

📊 DOWN Drift Check (last 78 trades):
   Expected WR (from curve): 65.8%
   Actual WR: 79.2%
   Drift: 13.4% ⚠️ THRESHOLD EXCEEDED

🔄 Recalibration triggered: DOWN drift 13.4% > 10.0%
✅ DOWN calibration curve UPDATED from 287 trades
📊 DOWN Calibration Curve Comparison:
   Bot 55%: 38.2% → 42.1% (+3.9%)
   Bot 65%: 48.9% → 54.3% (+5.4%)
   Bot 75%: 79.4% → 82.7% (+3.3%)
   Bot 85%: 88.1% → 90.5% (+2.4%)
```

### Drift Detected During Runtime:

```
📊 UP Drift Check (last 95 trades):
   Expected WR (from curve): 52.3%
   Actual WR: 63.8%
   Drift: 11.5% ⚠️ THRESHOLD EXCEEDED

🔄 Recalibration triggered: UP drift 11.5% > 10.0%
✅ UP calibration curve UPDATED from 143 trades
```

### Schedule-Based Recalibration (Hybrid Mode):

```
🔄 Recalibration triggered: Max interval reached (7 days)
📊 UP Drift Check (last 132 trades):
   Expected WR (from curve): 48.1%
   Actual WR: 52.3%
   Drift: 4.2% ✓ OK

📊 DOWN Drift Check (last 245 trades):
   Expected WR (from curve): 71.2%
   Actual WR: 68.9%
   Drift: 2.3% ✓ OK

✅ UP calibration curve UPDATED from 132 trades
✅ DOWN calibration curve UPDATED from 245 trades
```

### Cooldown Prevents Excessive Recalibration:

```
📊 UP Drift Check (last 87 trades):
   Drift: 12.1% ⚠️ THRESHOLD EXCEEDED

⏸️ Recalibration skipped: Within 12h cooldown (8.3h since last)
```

---

## 🧪 Testing Scenarios

### Scenario 1: Stable Market (No Drift)

**Setup:**
- Mode: Hybrid
- Drift threshold: 10%
- Max interval: 7 days

**Expected Behavior:**
```
Day 1: Initial calibration on startup
Day 2-6: Drift <10%, no recalibration
Day 7: Force recalibration (max interval)
```

**What to monitor:**
- Drift should stay <10%
- Only recalibrates on Day 7 (schedule)

---

### Scenario 2: Market Regime Change (High Drift)

**Setup:**
- Mode: Hybrid
- Market shifts from bull → bear on Day 3

**Expected Behavior:**
```
Day 1: Initial calibration
Day 2: Drift 5% (normal variance)
Day 3: Market regime shift → Drift 14% → RECALIBRATE ✅
Day 4: Drift 6% (stable after recal)
Day 5: Another shift → Drift 11% → RECALIBRATE ✅
```

**What to monitor:**
- Recalibration happens quickly after regime shift
- Performance improves after recalibration

---

### Scenario 3: Volatile/Noisy Period (Cooldown Protection)

**Setup:**
- Mode: Hybrid
- High volatility, erratic performance

**Expected Behavior:**
```
Day 1, 6am: Drift 12% → RECALIBRATE ✅
Day 1, 10am: Drift 11% → SKIP (within 12h cooldown)
Day 1, 6pm: Drift 13% → SKIP (within 12h cooldown)
Day 2, 7am: Drift 10.5% → RECALIBRATE ✅ (13h passed)
```

**What to monitor:**
- Cooldown prevents over-fitting to noise
- Only recalibrates when enough time has passed

---

## 🚀 How to Use (Step by Step)

### **Step 1: Current State (Baseline)**

Keep current config for 1-7 days:
```yaml
probability_model: "v1"
```

Collect baseline data in `skipped_trades.csv`.

---

### **Step 2: Enable v2 with Hybrid Recalibration**

Update config:
```yaml
strategy:
  probability_model: "v2_calibrated"

calibration:
  dynamic_recalibration_enabled: true
  recalibration_mode: "hybrid"  # Drift + schedule
  drift_threshold_percent: 10.0
  max_recalibration_interval_days: 7
  min_recalibration_interval_hours: 12

  crowd_confidence:
    enabled: false  # Test pure v2 first
```

Restart bot:
```bash
pkill -f edge_bot.py
python3 edge_bot.py
```

---

### **Step 3: Monitor Drift Logs**

Check logs for:
- ✅ Initial calibration on startup
- 📊 Drift checks (shows expected vs actual WR)
- 🔄 Recalibration triggers (drift or schedule)
- ⚠️ Drift threshold exceeded warnings

**Example grep:**
```bash
tail -f logs/edge_bot.log | grep -E "Drift Check|Recalibration triggered|THRESHOLD EXCEEDED"
```

---

### **Step 4: Tune Thresholds (Optional)**

If recalibrating too often:
```yaml
drift_threshold_percent: 12.0  # Increase threshold
min_recalibration_interval_hours: 24  # Longer cooldown
```

If not responsive enough:
```yaml
drift_threshold_percent: 8.0  # Lower threshold
min_recalibration_interval_hours: 6  # Shorter cooldown
```

---

## 💡 Pro Tips

### 1. **Start with Hybrid Mode**
- Gives you both drift responsiveness AND scheduled updates
- Prevents staleness even if drift is low

### 2. **Monitor Drift Patterns**
- Track drift logs for 7+ days
- Identify typical drift ranges (UP vs DOWN)
- Adjust thresholds based on your data

### 3. **Use Cooldown Wisely**
- 12h cooldown prevents noise-driven recalibration
- But allows 2x/day if truly needed

### 4. **Separate UP/DOWN Thresholds** (Future Enhancement)
```yaml
drift_threshold_up: 12.0  # UP needs higher threshold (more variance)
drift_threshold_down: 8.0  # DOWN more stable
```

### 5. **Drift Dashboard** (Future Enhancement)
- Track drift over time
- Visualize when recalibrations happen
- Correlate with market volatility

---

## 🎯 Expected Benefits

### **Responsiveness:**
- ✅ Catches market regime changes within 50-100 trades
- ✅ No waiting for fixed 7-day interval
- ✅ Recalibrates when needed, not on schedule

### **Stability:**
- ✅ Cooldown prevents over-fitting to noise
- ✅ Max interval prevents staleness
- ✅ Separate UP/DOWN drift tracking

### **Performance:**
- ✅ Better calibration during volatile markets
- ✅ Stable calibration during calm markets
- ✅ Adaptive to your specific trading data

### **Transparency:**
- ✅ Every drift check logged
- ✅ Clear reason for each recalibration
- ✅ No "black box" - all decisions visible

---

## ⚠️ Important Notes

1. **Requires Historical Data:**
   - Need 100+ trades in `skipped_trades.csv`
   - UP and DOWN each need 50+ trades for drift calculation
   - Falls back to static curve if insufficient data

2. **Cooldown is Critical:**
   - Prevents recalibrating on every market blip
   - Default 12h is good for crypto
   - Adjust based on your trading frequency

3. **Drift Calculation is Periodic:**
   - Currently checks on bot startup and when `_maybe_recalibrate()` is called
   - Future: Could add continuous drift monitoring thread
   - For now, restart bot daily to check drift

4. **v1 Model Unaffected:**
   - v1 always uses static probabilities (no calibration curve)
   - Drift detection only affects v2_calibrated

5. **Per-Direction Drift:**
   - UP and DOWN checked separately
   - If EITHER exceeds threshold → recalibrate BOTH
   - Future: Could recalibrate only drifted direction

---

## 🔮 Future Enhancements

### **1. Continuous Drift Monitoring**
- Background thread checking drift every N trades
- Don't wait for startup/periodic calls

### **2. Per-Direction Recalibration**
- If only UP drifts → only recalibrate UP curve
- More granular, less disruption

### **3. Separate UP/DOWN Thresholds**
- UP trends: 12% threshold (more volatile)
- DOWN trends: 8% threshold (more stable)

### **4. Drift Dashboard**
- Web UI showing drift over time
- Visualize recalibration events
- Correlate with market conditions

### **5. Drift Prediction**
- ML model to predict when drift will occur
- Proactive recalibration

---

## ✅ Status

**Implementation:** ✅ Complete
**Testing:** ⏳ Ready for production testing
**Documentation:** ✅ Complete
**Syntax Check:** ✅ Passed

**Recommendation:** Switch to v2_calibrated with hybrid mode and monitor drift logs for 7+ days. Compare to v1 baseline.

---

**Created:** 2026-02-11
**Author:** Claude + User collaboration
**Version:** 1.0

