# Probability Model v2 (Calibrated) - Implementation Guide

## ✅ Changes Applied

### Kalshi Bot:
1. **momentum_analyzer.py** - Added `calculate_expected_probability_calibrated()` method
2. **momentum_analyzer.py** - Added DYNAMIC CALIBRATION (self-improving curves)
3. **edge_detector_advanced.py** - Added model selection logic in `_get_expected_prob()`
4. **config_15m.yaml** - Added `probability_model` config option (line 29)
5. **config_15m.yaml** - Added dynamic calibration settings (lines 216-228)

### Polymarket Bot:
1. **momentum_analyzer.py** - Added `calculate_expected_probability_calibrated()` method
2. **momentum_analyzer.py** - Added DYNAMIC CALIBRATION (self-improving curves)
3. **edge_detector_advanced.py** - Added model selection logic in `_get_expected_prob()`
4. **config_polymarket.yaml** - Added `probability_model` config option (line 52)
5. **config_polymarket.yaml** - Added dynamic calibration settings (lines 227-239)

---

## 🎯 What Was Fixed

### The Overconfidence Problem:
Bot's v1 model calculated probabilities >1.0 (impossible!) which were then capped at 0.95.

**Calibration Data:**
```
Bot Said    | Actual WR | Error
------------|-----------|--------
60-70%      | 33.3%     | -29%  ❌
70-80%      | 46.7%     | -28%  ❌
80-90%      | 55.6%     | -31%  ❌
90-95%      | 60.0%     | -33%  ❌
>100%       | 80.9%     | -36%  ❌
```

Bot was **consistently overconfident by 28-36%**.

### v2 Calibrated Model Changes:

1. **Reduced Base Confidence:**
   - At threshold: 0.80 → 0.60 (25% reduction)
   - Away from threshold: 0.50 → 0.45 (10% reduction)

2. **Reduced Distance Bonus:**
   - Multiplier: 0.05 → 0.03 (40% reduction)

3. **Reduced Momentum Bonus:**
   - Bonus: 0.15 → 0.10 (33% reduction)

4. **Reduced Trend Strength Bonus:**
   - Multiplier: 0.15 → 0.10 (33% reduction)

5. **Added Calibration Curve:**
   - Maps bot's raw probability to actual expected win rate
   - Uses piecewise linear interpolation
   - Ensures final probabilities match historical performance

---

## 📋 Configuration

Add to your `config_15m.yaml` or `config_polymarket.yaml`:

```yaml
strategy:
  # Choose probability model
  probability_model: "v1"  # Start with v1 (baseline)
```

**Options:**
- `"v1"` - Legacy model (current, overconfident)
- `"v2_calibrated"` - New calibrated model

---

## 🧪 Testing Strategy

### Phase 1: Baseline (Days 1-7)
```yaml
probability_model: "v1"  # Keep current model
```
- Run for 7 days
- Record performance metrics
- Baseline: ~85% DOWN WR, ~54% UP WR

### Phase 2: Calibrated Model (Days 8-14)
```yaml
probability_model: "v2_calibrated"  # Switch to new model
```
- Run for 7 days
- Compare performance to baseline
- Monitor: Win rate, trade volume, profitability

### Phase 3: Analysis & Decision (Day 15)
Compare metrics:
```python
python3 << 'ENDSCRIPT'
import pandas as pd

df = pd.read_csv('data/negative_edges/skipped_trades.csv')

# v1 performance (Days 1-7)
v1_data = df[(df['timestamp'] >= '2026-02-11') & (df['timestamp'] < '2026-02-18')]

# v2 performance (Days 8-14)
v2_data = df[(df['timestamp'] >= '2026-02-18') & (df['timestamp'] < '2026-02-25')]

for model, data in [('v1', v1_data), ('v2', v2_data)]:
    data['won'] = data['would_have_won'].astype(str).str.lower() == 'true'
    print(f"\n{model.upper()} MODEL:")
    print(f"  Total trades: {len(data)}")
    print(f"  Win rate: {data['won'].mean()*100:.1f}%")
    
    for trend in ['up', 'down']:
        t = data[data['momentum_direction'] == trend]
        if len(t) > 0:
            wr = t['won'].mean() * 100
            print(f"  {trend.upper()}: {wr:.1f}% WR ({len(t)} trades)")
ENDSCRIPT
```

**Decision Matrix:**
| Metric | v1 Better | v2 Better | Decision |
|--------|-----------|-----------|----------|
| UP WR | <70% | >70% | Use v2 |
| DOWN WR | >85% | >85% | Doesn't matter |
| Total trades | >300/week | <200/week | Consider v1 if volume important |
| Profitability | $X/week | >$X/week | Use v2 |

---

## 📊 Expected Impact

### With v1 (Legacy):
```
UP trends:   54% WR (overconfident, crowd pulls down)
DOWN trends: 85% WR (overconfident but crowd corrects)
Trade volume: High (aggressive)
Crowd blending: Required (to fix overconfidence)
```

### With v2 (Calibrated):
```
UP trends:   Expected 65-75% WR (more accurate)
DOWN trends: Expected 85-90% WR (same or better)
Trade volume: Medium (more selective)
Crowd blending: Optional (model already calibrated)
```

---

## 🔧 Advanced: Model Combinations

You can combine model selection with crowd blending settings:

### Option A: v2 + No Crowd Blending
```yaml
strategy:
  probability_model: "v2_calibrated"

calibration:
  crowd_confidence:
    enabled: false  # Disable - model is already calibrated
```
**Best for:** Trust in bot's calibration, want pure model-driven decisions

### Option B: v2 + UP-only Crowd Blending
```yaml
strategy:
  probability_model: "v2_calibrated"

calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: ["up"]  # Blend DOWN only
```
**Best for:** Hedge your bets, still help DOWN trends with crowd wisdom

### Option C: v1 + UP-disabled Crowd Blending (CURRENT)
```yaml
strategy:
  probability_model: "v1"

calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: ["up"]  # Current setting
```
**Best for:** Maintaining current baseline while testing v2

### Option D: v2 + Reduced Crowd Blending
```yaml
strategy:
  probability_model: "v2_calibrated"

calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: []  # Blend all directions
    max_market_weight: 0.4  # But trust bot more (60%)
    min_market_weight: 0.3
```
**Best for:** Want both model calibration AND crowd wisdom, balanced approach

---

## ⚠️ Important Notes

1. **Start with v1 as baseline** - Don't change everything at once
2. **Test one model at a time** - Clear A/B test
3. **Give it 7 days minimum** - Need enough trades for statistical significance
4. **Monitor both UP and DOWN trends** - Performance may differ by direction
5. **Check trade volume** - v2 might take fewer trades (more selective)

---

## 📝 Files Modified

### Kalshi Bot:
- `/root/kalshi_15m_bot/momentum_analyzer.py`
  - Added `calculate_expected_probability_calibrated()` (lines 254-371)
  - Added `_apply_calibration_curve()` (lines 373-400)

- `/root/kalshi_15m_bot/edge_detector_advanced.py`
  - Updated `_get_expected_prob()` (lines 492-521)
  - Added model selection logic

- `/root/kalshi_15m_bot/config_15m.yaml`
  - Added `probability_model` option (lines 28-42)

### Polymarket Bot:
- `/root/polymarket_15m_bot/momentum_analyzer.py`
- `/root/polymarket_15m_bot/edge_detector_advanced.py`
- `/root/polymarket_15m_bot/config_polymarket.yaml`
  - Same changes as Kalshi bot

---

## 🚀 Quick Start

1. **Keep current config** (v1 model) for 7 days:
```yaml
probability_model: "v1"
```

2. **After 7 days, switch to v2**:
```yaml
probability_model: "v2_calibrated"
```

3. **Restart bot:**
```bash
cd /root/kalshi_15m_bot
pkill -f edge_bot.py
python3 edge_bot.py
```

4. **Monitor logs for:**
```
📊 ... | Base Prob (bot model): 65.0%  (v2 should be lower than v1)
```

5. **Compare results after another 7 days**

---

## ❓ FAQ

**Q: Will v2 take fewer trades?**
A: Possibly. It's more conservative, so might skip marginal opportunities.

**Q: Should I disable crowd blending with v2?**
A: Test both. v2 is calibrated so crowd blending may not be needed, but it could still help.

**Q: Can I switch back to v1?**
A: Yes! Just change config back to `probability_model: "v1"` and restart.

**Q: Which is better?**
A: Test both for 7 days each and compare. Expected: v2 better for UP trends, v1 similar for DOWN.

**Q: What if neither works well?**
A: Check if crowd blending settings also need adjustment.

---

---

## 🔄 NEW: Dynamic Calibration (Self-Improving v2)

**What it does:** v2_calibrated model now auto-updates its calibration curves from your actual performance data!

### How It Works:

1. **On Bot Startup:**
   - Loads recent `skipped_trades.csv` data (last 30 days)
   - Analyzes: "When bot said 65%, what was the actual win rate?"
   - Updates calibration curves to match real performance

2. **Every 7 Days:**
   - Automatically recalibrates from recent data
   - Logs curve changes to show improvement
   - Falls back to static curve if insufficient data

3. **Separate UP/DOWN Curves:**
   - UP trends get their own calibration curve
   - DOWN trends get their own calibration curve
   - Handles UP/DOWN performance asymmetry

### Configuration:

```yaml
calibration:
  # Dynamic calibration (v2 model only)
  dynamic_recalibration_enabled: true  # Set to false to use static curves only
  recalibration_interval_days: 7       # How often to recalibrate
  recalibration_lookback_days: 30      # How much history to use
  min_samples_for_recalibration: 100   # Minimum trades before updating
  separate_curves_by_direction: true   # UP and DOWN get separate curves
```

### What You'll See in Logs:

**On bot startup (if enough data):**
```
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
   Bot 75%: 55.0% → 79.4% (+24.4%)  ← Big improvement!
   Bot 85%: 65.0% → 88.1% (+23.1%)
```

**On startup (if not enough data yet):**
```
⚠️ Recalibration skipped: Only 23 samples (need 100)
📊 Dynamic calibration ENABLED (recal every 7d, lookback 30d)
   Using static calibration curves until sufficient data
```

### Benefits:

✅ **Adapts to market changes** - Bull vs bear markets
✅ **Learns from real performance** - Not just historical assumptions
✅ **Handles UP/DOWN asymmetry** - Separate curves for each direction
✅ **Safe fallback** - Uses static curve if insufficient data
✅ **Transparent** - Logs all curve updates

### Testing Impact:

- **First 7 days:** Static calibration curve (same for all trades)
- **After 100+ trades:** Dynamic curves kick in, customized to YOUR data
- **After 30+ days:** Mature calibration with high confidence

### Control Options:

**Disable dynamic calibration (use only static curves):**
```yaml
dynamic_recalibration_enabled: false
```

**Use same curve for UP and DOWN:**
```yaml
separate_curves_by_direction: false
```

**Recalibrate more frequently:**
```yaml
recalibration_interval_days: 3  # Every 3 days instead of 7
```

---

**Created:** 2026-02-11
**Updated:** 2026-02-11 (Added dynamic calibration)
**Status:** Ready for testing
**Recommendation:** Run v1 baseline for 7 days, then test v2 for 7 days, compare results. v2 will self-improve over time!
