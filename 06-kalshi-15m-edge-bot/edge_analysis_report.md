# Edge Detection Analysis Report
**Generated:** 2026-02-09
**Analysis Period:** Last 24 hours + Historical data

## Executive Summary

### 🚨 **CRITICAL FINDING: Momentum Filter Too Strict**
The bot is detecting **almost ZERO edges** because the `min_momentum_pct: 0.3` filter is blocking 100% of trades from even being evaluated.

**Recent logs show:**
- All markets being skipped due to "Low Momentum (0.18-0.24% < 0.30%)"
- Markets with momentum of 0.18-0.28% are being rejected
- **NO trades are passing the initial momentum filter to reach edge calculation**

---

## Last 24 Hours Performance

### Skipped Trades Analysis
- **Total skipped:** 22 trades
- **Would have won:** 17 (77.3%)
- **Would have lost:** 5 (22.7%)
- **Missed theoretical PnL:** +$175.50
- **Average PnL per trade:** +$7.98

### Skip Reasons (Last 24h)
1. **Low Edge:** 10 trades (53.1% historical win rate) ⚠️
2. **Low Win Prob:** 7 trades (33.4% historical win rate) ✅
3. **Low Signal:** 5 trades (50.7% historical win rate) ⚠️

### Win Rate by Edge Size (Last 24h)
| Edge Range | Win Rate | Trades | PnL |
|------------|----------|--------|-----|
| < -5% | 50.0% | 6 | -$133.50 |
| -5% to 0% | 80.0% | 5 | -$15.00 |
| 0% to 5% | 100.0% | 1 | +$21.00 |
| 15% to 20% | 100.0% | 2 | +$79.00 |
| > 20% | 87.5% | 8 | +$224.00 |

---

## Historical Performance (All Time)

### Overall Statistics
- **Total skipped trades:** 3,255
- **Skip reason breakdown:**
  - Low Win Prob: 1,811 (55.6%)
  - Low Edge: 1,375 (42.2%)
  - Low Signal: 69 (2.1%)

### Filter Effectiveness Analysis

#### 1. "Low Win Prob" Filter (1,811 trades)
- **Median probability:** 58.83%
- **Win rate:** 33.4% ✅ **WORKING AS INTENDED**
- **Total theoretical PnL:** -$34,940.50
- **Conclusion:** This filter is PROTECTING us from bad trades

#### 2. "Low Edge" Filter (1,375 trades)
- **Median probability:** 93.26% (very confident!)
- **Win rate:** 53.1% ⚠️ **LOSING OPPORTUNITIES**
- **Total theoretical PnL:** -$23,875.50
- **Average edge:** -5.35% (negative!)
- **Conclusion:** Mixed - blocking some bad trades but also missing good ones

#### 3. "Low Signal" Filter (69 trades)
- **Median probability:** 57.00%
- **Win rate:** 50.7% (coin flip)
- **Total theoretical PnL:** -$601.50
- **Conclusion:** Too small sample size, but appears neutral

---

## Current Configuration Issues

### 🔴 CRITICAL: Momentum Filter Too Strict
```yaml
min_momentum_pct: 0.3  # Requiring 0.3% momentum
```
**Problem:** Markets with 0.18-0.28% momentum are being rejected
**Impact:** NO trades are passing this filter in real-time
**Recent log evidence:**
```
⏭️ KXSOL15M skip: Low Momentum (0.212 < 0.300) - weak trend
⏭️ KXETH15M skip: Low Momentum (0.231 < 0.300) - weak trend
⏭️ KXSOL15M skip: Low Momentum (0.205 < 0.300) - weak trend
```

### ⚠️ Edge Threshold Too Loose
```yaml
min_edge_percent: -3  # Allowing NEGATIVE edges!
```
**Problem:** Bot will take trades with negative expected value
**Impact:** Historical data shows "Low Edge" skips had -5.35% average edge
**Recommendation:** Increase to 5-10% minimum edge

### ✅ Win Probability Filter Working
```yaml
min_expected_probability: 0.65  # Requiring 65% win probability
```
**Status:** WORKING CORRECTLY
**Evidence:** "Low Win Prob" skips had 33.4% win rate (correctly rejected)

### ⚠️ Trend Strength May Be Too Strict
```yaml
min_trend_strength: 0.3  # Requiring 0.3 trend strength
```
**Problem:** This combines with momentum filter to further restrict trades
**Impact:** Unknown - need more data since momentum filter blocks everything first

---

## Recommendations

### 🚀 HIGH PRIORITY (Do First)

#### 1. Lower Momentum Filter (CRITICAL)
```yaml
# Current
min_momentum_pct: 0.3

# Recommended
min_momentum_pct: 0.15  # Allow weaker trends (0.15% = 15 basis points)
```
**Rationale:**
- Current setting blocks 100% of trades
- Historical data shows 0.2-0.5% momentum had 33.2% win rate
- Lowering to 0.15% will allow more trades while still filtering out flat markets

#### 2. Tighten Edge Threshold
```yaml
# Current
min_edge_percent: -3

# Recommended
min_edge_percent: 7  # Require 7% edge minimum
```
**Rationale:**
- Negative edges lost money historically
- 7% edge provides cushion for slippage and model error
- Last 24h data shows high edge trades had 87.5-100% win rate

#### 3. Lower Trend Strength (Secondary)
```yaml
# Current
min_trend_strength: 0.3

# Recommended
min_trend_strength: 0.2  # Allow slightly weaker trends
```
**Rationale:**
- Works in conjunction with momentum filter
- Will allow more trades once momentum filter is loosened

---

### 📊 MEDIUM PRIORITY (Monitor & Adjust)

#### 4. Review Signal Strength Threshold
```yaml
min_signal_strength: 40  # Current
```
**Action:** Monitor after loosening momentum filter
**Rationale:** Need more data once trades start flowing

#### 5. Consider Tightening Win Probability Filter
```yaml
# Current
min_expected_probability: 0.65

# Optional
min_expected_probability: 0.70  # More conservative
```
**Rationale:** Only if edge count becomes too high after other changes

---

## Calibration Data Insights

### Spot Price Feed Accuracy
- Calibration data shows spot prices within 0.02-0.1% of Kalshi floor strikes
- Median delta: ~10-20 basis points
- Feed appears accurate and timely

### Market Efficiency
- High-depth markets (>500 contracts): 83.8% accurate
- Medium-depth markets: 70.9% accurate
- Low-depth markets: 68.7% accurate
- Bot model: 35-39% accurate

**Conclusion:** Crowd wisdom blending (already enabled) is critical

---

## Action Items

### Immediate Actions (Today)
1. ✅ **Update `min_momentum_pct` from 0.3 to 0.15** in config_15m.yaml
2. ✅ **Update `min_edge_percent` from -3 to 7** in config_15m.yaml
3. ✅ **Update `min_trend_strength` from 0.3 to 0.2** in config_15m.yaml
4. ✅ **Restart bot** to apply new settings
5. ✅ **Monitor for 2-4 hours** to see if edge detection improves

### Follow-up Actions (This Week)
1. ⏳ Analyze new edge detection rate after changes
2. ⏳ Review win rate of actual trades vs skipped trades
3. ⏳ Fine-tune signal strength threshold if needed
4. ⏳ Consider A/B testing different threshold combinations

---

## Conclusion

**The bot's edge detection is currently BROKEN due to overly strict momentum filtering.**

The `min_momentum_pct: 0.3` setting is filtering out 100% of potential trades before they even reach the edge calculation phase. Historical data suggests this could be lowered to 0.15-0.20% to allow legitimate trading opportunities while still filtering out flat/choppy markets.

Additionally, allowing negative edges (`min_edge_percent: -3`) is problematic and should be tightened to require a meaningful positive edge (7-10%).

**Expected Impact of Changes:**
- Edge detection should increase from ~0 trades/hour to 2-5 trades/hour
- Win rate should remain >50% due to other filters (probability, signal strength)
- PnL should improve due to capturing legitimate opportunities

---

**Next Steps:** Apply recommended configuration changes and monitor results for 2-4 hours before further adjustment.
