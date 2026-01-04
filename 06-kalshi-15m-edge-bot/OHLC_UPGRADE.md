# OHLC Aggregation Upgrade - Noise Reduction for R²

**Date**: 2026-02-06
**Reason**: User experienced erratic R² correlation before today's fixes
**Solution**: Implement Gemini's recommendation to use 1-minute OHLC candles for R²

---

## The Problem

You had **erratic R² correlation** before today. Today we fixed:

1. ✅ **Rolling window** (timing issue) - R² now looks at recent 4 mins, not full candle
2. ✅ **Trend strength filter** - R² combined with momentum
3. ✅ **Higher momentum threshold** - avoid weak trends

BUT we **didn't** fix:
4. ❌ **1-second tick noise** - R² still calculated on high-frequency data

---

## Gemini's Insight

> "At 1-second frequency, price movements are dominated by 'noise' (bid-ask spread bouncing). Calculating R² on this noise will yield erratic results."

**Solution**: Aggregate 1-second ticks into 1-minute OHLC candles for R² calculation.

---

## What We Implemented

### New File: `ohlc_aggregator.py`

Aggregates high-frequency price ticks into 1-minute candles:
- Takes 60 price points per minute
- Outputs 1 OHLC candle per minute
- Uses **Close** price for R² calculation

### Updated: `momentum_analyzer.py`

Added hybrid approach:
- **For R² calculation**: Use 1-minute OHLC Close prices (smooth)
- **For momentum/slope**: Use raw 1-second data (responsive)
- **For execution**: Keep 1-second price updates (fast)

### Config Changes

```yaml
strategy:
  # Existing settings
  r_squared_lookback_minutes: 4  # Rolling window (recent data)

  # NEW: OHLC aggregation
  use_ohlc_for_r_squared: true   # Aggregate to 1-min candles
  ohlc_interval_seconds: 60      # 1-minute candles
```

---

## How It Works

### Before (Noisy):
```
4-minute lookback × 60 ticks/min = ~240 data points
R² calculated on 240 noisy ticks
→ Erratic R² values
```

### After (Smooth):
```
4-minute lookback → 4 complete 1-min candles
R² calculated on 4 OHLC Close prices
→ Clean R² values that reflect true trend
```

### Example

**Market**: BTC at minute 12 of 15-min candle (3 mins left)

**Raw ticks** (last 4 minutes):
```
Min 8: 95000, 95001, 94999, 95002, 95001... (60 ticks)
Min 9: 95010, 95012, 95009, 95011, 95013... (60 ticks)
Min 10: 95025, 95024, 95026, 95023, 95027... (60 ticks)
Min 11: 95040, 95039, 95041, 95038, 95042... (60 ticks)
```

**OHLC candles**:
```
Min 8:  Open=95000, High=95005, Low=94998, Close=95003
Min 9:  Open=95003, High=95015, Low=95008, Close=95012
Min 10: Open=95012, High=95028, Low=95020, Close=95026
Min 11: Open=95026, High=95043, Low=95035, Close=95041
```

**R² calculation**:
- Before: Fit line through 240 noisy points → R² = 0.65 (mediocre due to noise)
- After: Fit line through 4 clean closes → R² = 0.92 (strong trend detected!)

---

## Why This Matters

Your erratic R² before was likely due to:
1. ❌ **Full candle lookback** (FIXED: rolling window)
2. ❌ **1-second tick noise** (FIXED: OHLC aggregation)

Now you have BOTH fixes:
- ✅ Right DATA (recent 4 minutes)
- ✅ Right FREQUENCY (1-minute candles)

---

## Expected Improvement

### Before Today
- R² had mixed correlation with wins
- High R² ≠ good trade

### After Today (Rolling Window Only)
- R² better correlated (recent data)
- But still potentially noisy

### After OHLC Addition
- R² cleanly measures trend quality
- High R² = genuine linear trend (not noise)
- Should see strong correlation between R² >0.3 and wins

---

## Monitoring

Watch for these improvements:

### R² Values Should Be More Stable
```
# Before (noisy):
10:00 - R²=0.45
10:05 - R²=0.72  ← Jump!
10:10 - R²=0.38  ← Drop!

# After (stable):
10:00 - R²=0.48
10:05 - R²=0.52  ← Gradual change
10:10 - R²=0.47  ← Consistent
```

### Better Win Rate Correlation
```
High R² (>0.5) trades: Should win >45%
Low R² (<0.3) trades: Should win <35%
Clear separation = filter working!
```

---

## Rollback

If OHLC causes issues, disable it:

```yaml
strategy:
  use_ohlc_for_r_squared: false  # Back to smoothed ticks
```

Bot will fall back to 12-second smoothed ticks (previous behavior).

---

## Trade-Off: Responsiveness vs Stability

| Aspect | 1-Sec Smoothed Ticks | 1-Min OHLC Candles |
|--------|---------------------|-------------------|
| **R² Stability** | Lower (noisy) | Higher (clean) ✅ |
| **Responsiveness** | Higher (instant) | Lower (1-min lag) |
| **Trend Detection** | Noisier | Cleaner ✅ |
| **Best For** | Execution speed | R² calculation ✅ |

**Our hybrid approach**: Use OHLC for R² (stability), keep 1-sec for execution (speed).

---

## The Bottom Line

Given your **historical R² issues**, implementing OHLC is **proactive risk management**.

You now have:
1. ✅ Rolling window (right timing)
2. ✅ Trend strength filter (R² + momentum)
3. ✅ OHLC aggregation (right frequency)
4. ✅ Crowd confidence blending (market wisdom)

**All bases covered!** 🎯
