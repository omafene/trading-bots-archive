# Edge Calculation Fix - UP Trades Overconfidence Problem

## The Problem

The bot's probability model is **severely miscalibrated** for UP momentum trades:

| Model Says | Actual Outcome | Calibration Error |
|-----------|----------------|-------------------|
| 80-100% confident (YES wins) | **33.3%** actually win | **-55.3%** error |
| 60-70% confident | **20.0%** actually win | **-44.2%** error |
| 0-50% low confidence | **56.8%** actually win | **+16.9%** error |

**Inverse relationship**: Higher model confidence = Lower actual win rate!

## Root Cause Analysis

### Current Logic (`momentum_analyzer.py` lines 209-216)

```python
if market_type == 'up':
    # If already above threshold, YES is likely
    if active_price >= threshold:
        expected_prob = 0.80  # ❌ TOO OPTIMISTIC - actual: 33%
    else:
        # Below threshold - how far away are we?
        expected_prob = 0.50 - (distance_pct * 0.05)
        if momentum['direction'] == 'up':
            expected_prob += 0.15  # ❌ TOO MUCH BONUS
```

### Why It Fails for UP Trades

**3 Fundamental Issues:**

1. **Mean Reversion Ignored**
   - UP momentum = temporary bounce in downtrend market (Feb 4-10)
   - Model assumes momentum continues → overconfident
   - DOWN momentum = real trend → model conservative (underestimates) → negative edge paradox

2. **Fixed 80% for "already above threshold"**
   - If BTC is $100 above threshold with 5 min left, model says 80% certain
   - Reality: Crypto is volatile, $100 gap can reverse quickly
   - Actual outcome: Only 33% win rate when model says 80%+

3. **Momentum Bonus Too Large (+15%)**
   - UP momentum gets +15% bonus
   - But UP momentum is weak (78% have signal=0, avg signal 5.2 vs 40.8 for DOWN)
   - Weak momentum shouldn't get same bonus as strong momentum

## The Paradox: Negative Edge = Best Trades

**DOWN trades with "negative edge" have 99.5% WR!**

Why?
- Model is too conservative (expected prob too low)
- Market prices in fear premium (NO side expensive)
- When model says 70% but market prices at 85¢, that's "negative edge"
- But model is underestimating → actually a great trade!

**UP trades with "positive edge" have 0-40% WR**

Why?
- Model is too aggressive (expected prob too high)
- When model says 90% but market prices at 60¢, that's "positive edge"
- But model is overestimating → actually a terrible trade!

## Proposed Fixes

### Fix #1: Recalibrate UP Trade Probabilities (Conservative)

**Before:**
```python
if active_price >= threshold:
    expected_prob = 0.80  # ❌ WAY too high
```

**After:**
```python
if active_price >= threshold:
    # Reduce confidence based on distance and time remaining
    distance_pct = ((active_price - threshold) / threshold) * 100
    time_factor = min(minutes_remaining / 15, 1.0)  # More confident if more time

    # Base: 50% (neutral), add distance bonus capped at 20%
    expected_prob = 0.50 + min(distance_pct * 0.02, 0.20) * time_factor

    # Only add momentum bonus if strong signal
    if momentum['signal_strength'] >= 25:
        expected_prob += 0.10  # Reduced from 0.15

    # Cap at 70% (model overconfident above this)
    expected_prob = min(expected_prob, 0.70)
```

### Fix #2: Signal-Strength-Weighted Probability

**Current:** All UP trades get same momentum bonus regardless of signal quality

**Proposed:**
```python
# Calculate base probability from distance
base_prob = 0.50 + (distance_pct * 0.05)

# Scale momentum bonus by signal strength
signal_factor = min(signal_strength / 50, 1.0)  # 0-1 scale
momentum_bonus = 0.15 * signal_factor  # 0 if signal=0, 15% if signal=50+

expected_prob = base_prob + momentum_bonus

# Different caps for UP vs DOWN
if market_type == 'up':
    expected_prob = min(expected_prob, 0.70)  # UP capped at 70% (calibration data)
else:  # down
    expected_prob = min(expected_prob, 0.85)  # DOWN can go higher (better calibration)
```

### Fix #3: Market-Regime-Aware Calibration (Advanced)

**Hypothesis:** UP trades fail because Feb 4-10 was a DOWN market regime

**Solution:** Detect regime and adjust probabilities

```python
def detect_market_regime(self, symbol: str, lookback_hours: int = 24) -> str:
    """Detect if we're in up/down/sideways regime over last N hours"""
    # Get 24h price history
    long_momentum = self.calculate_momentum(symbol, minutes=lookback_hours * 60)

    if long_momentum['percent_change'] > 2.0:
        return 'uptrend'
    elif long_momentum['percent_change'] < -2.0:
        return 'downtrend'
    else:
        return 'sideways'

# In calculate_expected_probability:
regime = self.detect_market_regime(symbol, lookback_hours=24)

if market_type == 'up':
    if regime == 'downtrend':
        # Counter-trend trade in downtrend = very risky
        expected_prob *= 0.7  # Reduce by 30%
    elif regime == 'uptrend':
        # With-trend trade = more reliable
        expected_prob *= 1.1  # Slight boost
```

## Recommended Implementation

### Phase 1: Quick Win (Today)
**Just disable UP trades** (already in your config ✅)
```yaml
allowed_trends: ["down"]  # You already have this!
```

### Phase 2: Enable SOL UP Only (Week 1)
SOL UP has 84.6% WR - use per-symbol filter:
```yaml
symbol_configs:
  SOL:
    allowed_trends: ["up", "down"]
```

### Phase 3: Recalibrate Model (Week 2-3)
Implement Fix #1 + Fix #2 in `momentum_analyzer.py`:
- Cap UP probabilities at 70%
- Weight momentum bonus by signal strength
- Test on paper trading for 1 week

### Phase 4: Advanced (Month 2)
If you want to trade UP on BTC/ETH later:
- Implement market regime detection
- Collect more data during up-market regime
- Recalibrate with larger dataset

## Why Not Fix It Now?

**You don't need to!** The data shows:
1. SOL UP works (84.6% WR) - just enable it with per-symbol filter
2. BTC/ETH UP is fundamentally weak (31-40% WR) - not worth fixing
3. DOWN trades already work perfectly (98% WR with current model)

**Recommendation:** Don't fix what isn't broken. Just add per-symbol filters and trade SOL both ways, BTC/ETH down only.

## Testing the Fix (If You Implement It)

1. **Backtest on existing data:**
   ```python
   # Apply recalibrated model to Feb 4-10 UP trades
   # Check if calibration error reduces from -55% to < -10%
   ```

2. **Paper trade for 1 week:**
   - Log predicted vs actual for UP trades
   - Target: Calibration error < ±15%

3. **Monitor by expected probability bucket:**
   ```
   Model 60-70% → Actual should be 55-75% (not 20% like now)
   Model 80%+ → Actual should be 70-90% (not 33% like now)
   ```

## Summary

**Problem:** Model overconfident on UP trades (says 88%, actual 33%)

**Why:** Fixed 80% for "above threshold" + large momentum bonus + mean reversion ignored

**Quick Fix:** Use per-symbol filters (SOL only for UP trades)

**Long-term Fix:** Recalibrate model with signal-weighted bonuses and 70% cap

**Current Action:** You're already doing the right thing (DOWN only) ✅
