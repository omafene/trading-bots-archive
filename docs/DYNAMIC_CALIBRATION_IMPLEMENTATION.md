# Dynamic Calibration Implementation Summary

**Date:** 2026-02-11
**Status:** ✅ Complete and ready for testing
**Applies to:** v2_calibrated model ONLY (v1 remains unchanged)

---

## 🎯 What Was Built

The v2_calibrated probability model now **self-improves over time** by learning from actual trading performance.

### Key Features:

1. **Auto-Updating Calibration Curves**
   - Analyzes recent performance from `skipped_trades.csv`
   - Recalculates calibration curves every 7 days
   - Maps bot probabilities to actual win rates

2. **Separate UP/DOWN Calibration**
   - UP trends get their own calibration curve
   - DOWN trends get their own calibration curve
   - Handles performance asymmetry (UP 54% WR vs DOWN 91% WR)

3. **Safe Fallback System**
   - Requires minimum 100 trades before updating
   - Falls back to static curve if insufficient data
   - Logs all calibration changes for transparency

4. **On-Startup Calibration**
   - Bot loads and applies latest calibration on startup
   - Uses last 30 days of performance data
   - No manual intervention required

---

## 📁 Files Modified

### Kalshi Bot:
- `/root/kalshi_15m_bot/momentum_analyzer.py`
  - Added: Dynamic calibration initialization in `__init__()` (lines 44-58)
  - Modified: `_apply_calibration_curve()` to use direction-specific curves (lines 377-432)
  - Added: `_default_calibration_curve()` - Static fallback (lines 434-446)
  - Added: `_maybe_recalibrate()` - Checks if recalibration needed (lines 448-457)
  - Added: `_recalibrate_from_data()` - Main recalibration logic (lines 459-533)
  - Added: `_calculate_curve_from_bucket_data()` - Build curve from data (lines 535-571)
  - Added: `_log_curve_comparison()` - Log curve changes (lines 573-584)
  - Added: `_interpolate_curve()` - Helper for curve interpolation (lines 586-596)

- `/root/kalshi_15m_bot/config_15m.yaml`
  - Added: Dynamic calibration config section (lines 216-228)

### Polymarket Bot:
- `/root/polymarket_15m_bot/momentum_analyzer.py`
  - Same changes as Kalshi bot

- `/root/polymarket_15m_bot/config_polymarket.yaml`
  - Added: Dynamic calibration config section (lines 227-239)

---

## ⚙️ Configuration Options

Add to `config_15m.yaml` or `config_polymarket.yaml` under `calibration:` section:

```yaml
calibration:
  # === DYNAMIC CALIBRATION (v2 model only) ===
  dynamic_recalibration_enabled: true  # Toggle on/off
  recalibration_interval_days: 7       # How often to recalibrate
  recalibration_lookback_days: 30      # How much history to use
  min_samples_for_recalibration: 100   # Minimum trades before updating
  separate_curves_by_direction: true   # Separate UP/DOWN curves
```

**Current settings:** Both bots have dynamic calibration ENABLED by default.

---

## 🔬 How It Works

### 1. On Bot Startup:
```python
# In momentum_analyzer.__init__()
if self.dynamic_recalibration_enabled:
    self._maybe_recalibrate()  # Load latest calibration from data
```

### 2. Recalibration Process:
```
Load skipped_trades.csv
  ↓
Filter to last 30 days
  ↓
Group by bot probability buckets (50-60%, 60-70%, etc.)
  ↓
Calculate actual win rate per bucket
  ↓
Build new calibration curve: [(bot_prob, actual_wr), ...]
  ↓
Update calibration_curve_up and calibration_curve_down
  ↓
Log comparison: "Bot 65%: 45.0% → 51.8% (+6.8%)"
```

### 3. Probability Calculation:
```python
# v2 model uses direction-specific calibration
def calculate_expected_probability_calibrated(...):
    # ... calculate raw probability ...

    # Apply direction-specific calibration
    direction = momentum.get('direction', 'unknown')
    calibrated_prob = self._apply_calibration_curve(raw_prob, direction)

    return calibrated_prob
```

### 4. Curve Selection:
```python
def _apply_calibration_curve(self, raw_prob, direction):
    # Use UP curve for UP trends, DOWN curve for DOWN trends
    if direction == 'up':
        curve = self.calibration_curve_up
    else:
        curve = self.calibration_curve_down

    # Interpolate between calibration points
    return self._interpolate_curve(curve, raw_prob)
```

---

## 📊 Expected Log Output

### On Startup (Sufficient Data):
```
✅ Momentum analyzer initialized (interval: 1s, buffer: 1200 samples = 20 min, R² window: 5min rolling)
🔄 Recalibration triggered (7 days since last)
✅ UP calibration curve UPDATED from 143 trades
📊 UP Calibration Curve Comparison:
   Bot 55%: 35.0% → 42.3% (+7.3%)
   Bot 65%: 45.0% → 51.8% (+6.8%)
   Bot 75%: 55.0% → 62.1% (+7.1%)
   Bot 85%: 65.0% → 71.4% (+6.4%)

✅ DOWN calibration curve UPDATED from 287 trades
📊 DOWN Calibration Curve Comparison:
   Bot 55%: 35.0% → 38.2% (+3.2%)
   Bot 65%: 45.0% → 48.9% (+3.9%)
   Bot 75%: 55.0% → 79.4% (+24.4%)
   Bot 85%: 65.0% → 88.1% (+23.1%)

📊 Dynamic calibration ENABLED (recal every 7d, lookback 30d)
```

### On Startup (Insufficient Data):
```
⚠️ Recalibration skipped: Only 23 samples (need 100)
📊 Dynamic calibration ENABLED (recal every 7d, lookback 30d)
```

### If CSV Not Found:
```
⚠️ Recalibration skipped: data/negative_edges/skipped_trades.csv not found
📊 Dynamic calibration ENABLED (recal every 7d, lookback 30d)
```

---

## 🧪 Testing Plan

### Phase 1: Baseline (Days 1-7)
```yaml
probability_model: "v1"  # Static model
```
- Collect 100+ trades in skipped_trades.csv
- Establish baseline performance

### Phase 2: Static v2 (Days 8-14)
```yaml
probability_model: "v2_calibrated"  # v2 with static calibration
dynamic_recalibration_enabled: false
```
- Test v2 with fixed calibration curve
- Compare to v1 baseline

### Phase 3: Dynamic v2 (Days 15+)
```yaml
probability_model: "v2_calibrated"  # v2 with dynamic calibration
dynamic_recalibration_enabled: true
```
- Enable self-improving calibration
- Bot adapts to your specific performance
- Curves update every 7 days automatically

---

## 🎚️ Control Options

### Disable Dynamic Calibration (Use Static Curves Only):
```yaml
dynamic_recalibration_enabled: false
```
v2 model will use the hardcoded static calibration curve.

### Use Same Curve for UP and DOWN:
```yaml
separate_curves_by_direction: false
```
Both directions use the same calibration (not recommended).

### Recalibrate More/Less Frequently:
```yaml
recalibration_interval_days: 3   # Every 3 days (aggressive)
recalibration_interval_days: 14  # Every 2 weeks (conservative)
```

### Use More/Less Historical Data:
```yaml
recalibration_lookback_days: 14  # Last 2 weeks only
recalibration_lookback_days: 60  # Last 2 months
```

### Adjust Sample Size Requirement:
```yaml
min_samples_for_recalibration: 50   # Lower threshold (less stable)
min_samples_for_recalibration: 200  # Higher threshold (more stable)
```

---

## ⚠️ Important Notes

1. **v1 Model Unchanged:**
   - v1 always uses static probabilities (no calibration curve)
   - This is intentional for A/B testing

2. **Data Requirements:**
   - Need 100+ trades before first recalibration
   - Preferably 50+ trades per direction (UP/DOWN)
   - Falls back to static curve if insufficient data

3. **Automatic Recalibration:**
   - Happens on bot startup (if interval elapsed)
   - Can be triggered manually by restarting bot
   - Currently no runtime recalibration (would need separate thread)

4. **Curve Stability:**
   - Uses 30 days lookback by default (balanced)
   - Requires 10+ trades per bucket (50-60%, 60-70%, etc.)
   - Minimum 4 buckets needed for valid curve

5. **Transparency:**
   - All curve updates logged with before/after comparison
   - Can see exactly how calibration changed
   - No "black box" - all changes visible in logs

---

## 🚀 Next Steps

1. **Keep current config** (v1 model) for 7 days baseline
2. **After 7 days, switch to v2_calibrated:**
   ```bash
   # Edit config_15m.yaml
   probability_model: "v2_calibrated"

   # Restart bot
   pkill -f edge_bot.py
   python3 edge_bot.py
   ```
3. **Check logs for dynamic calibration:**
   - Look for "✅ UP/DOWN calibration curve UPDATED"
   - Review curve comparison to see adjustments
4. **Monitor performance over 7+ days**
5. **Compare v1 vs v2 results**

---

## 📈 Expected Benefits

- **Improved UP trend accuracy:** v2 learns your UP performance, adjusts calibration accordingly
- **Optimized DOWN trends:** Already good (91% WR), but fine-tunes further
- **Market adaptation:** Automatically adjusts to bull/bear market shifts
- **No manual tuning:** Bot learns and improves itself
- **Transparent learning:** All adjustments logged and visible

---

**Status:** ✅ Implementation complete, tested (syntax check passed), ready for production testing.

---

## 🆕 UPDATE: Drift-Based Recalibration Added!

**New Feature:** Adaptive recalibration triggered by performance drift, not just schedules.

See `/root/DRIFT_BASED_RECALIBRATION.md` for full details.

**Quick Summary:**
- **3 Modes:** Schedule, Drift, or Hybrid (recommended)
- **Drift Detection:** Recalibrates when performance deviates >10% from calibration curve
- **Hybrid Mode:** Triggers on EITHER drift OR schedule (best for crypto)
- **Cooldown Protection:** Won't recalibrate more than every 12 hours
- **Separate UP/DOWN:** Tracks drift for each direction independently

**Config:**
```yaml
recalibration_mode: "hybrid"  # Drift + schedule
drift_threshold_percent: 10.0  # 10% drift threshold (optimal for crypto)
```

**Status:** ✅ Implemented and ready for testing

