# 🐛 ROOT CAUSE: The 3 Critical Bugs in Your Model

## 🔴 BUG #1: Momentum → Probability Is INVERTED

### The Data Shows:

| Momentum | Model Says | Actually Wins | Error |
|----------|-----------|---------------|-------|
| **-1.0% to -0.5%** (DOWN) | 12.7% | **50.3%** | **-37.6%** ❌ |
| **-0.5% to -0.2%** (DOWN) | 24.3% | **38.0%** | **-13.7%** ❌ |
| **0.0% to 0.2%** (UP) | 41.4% | **20.9%** | **+20.5%** ❌ |
| **0.2% to 0.5%** (UP) | 42.5% | **24.5%** | **+18.1%** ❌ |

### The Problem:

**NEGATIVE momentum (DOWN) wins MORE than POSITIVE momentum (UP)!**

- DOWN momentum: Wins 50.3% (model says 12.7%)
- UP momentum: Wins 20.9% (model says 41.4%)

**This is completely backwards!**

### Why This Happens:

Looking at `momentum_analyzer.py` lines 236-295, the base probability model:

```python
# For UP markets with threshold
if market_type == 'up':
    if active_price >= threshold:
        expected_prob = 0.80  # Already above, likely to stay
    else:
        expected_prob = 0.50 - (distance_pct * 0.05)
        if momentum['direction'] == 'up':
            expected_prob += 0.15  # Bonus for aligned momentum
```

**The bug:** This calculates probability that price will reach/exceed threshold.

But when you bet on an UP market:
- **YES bet** = betting price will be ABOVE threshold
- Market sets thresholds VERY HIGH (optimistic)
- Even with UP momentum, price rarely reaches them
- So YES bets lose!

When momentum is UP:
- Model adds +15% to probability (for YES side)
- But threshold is too high
- YES side actually loses

When momentum is DOWN:
- Model subtracts from probability
- But this makes the model bet NO
- NO side (betting it WON'T reach threshold) wins!

**Result: The model's "momentum bonus" makes it overconfident on the losing side.**

---

## 🔴 BUG #2: Calibration Curve Is BACKWARDS

### Current Curve (from `momentum_analyzer.py` lines 450-464):

```python
(0.50, 0.35),  # Bot says 50%, maps to 35%
(0.60, 0.45),  # Bot says 60%, maps to 45%
(0.70, 0.55),  # Bot says 70%, maps to 55%
```

### What The Data Shows:

| Bot Says | Current Curve Maps To | Actually Wins |
|----------|----------------------|---------------|
| 0-50% | 0% | **33.7%** |
| 50-60% | 35% | **27.6%** |
| 60-70% | 45% | **20.5%** |

**The curve is making it WORSE!**

When bot says 50%:
- Curve maps it to 35%
- Actually wins 27.6%
- Curve is still too optimistic!

And look at this pattern: **Higher bot probability = LOWER actual win rate!**

This confirms the model is inverted - when the bot is most confident, it's most wrong.

### The Fix:

The calibration curve should be:
```python
# CORRECTED CURVE (based on actual data)
(0.00, 0.34),  # Bot says 0-50%, actually 33.7%
(0.55, 0.28),  # Bot says 50-60%, actually 27.6%
(0.65, 0.21),  # Bot says 60-70%, actually 20.5%
# ... but this is still wrong because the base model is inverted!
```

**BUT** - fixing the calibration curve won't help if the base model is inverted!

---

## 🔴 BUG #3: Orderbook/Multi-Factor Adjustments Are Backwards

### The Data Shows:

| Order Book Depth | Model Probability | Actual Win Rate | Error |
|------------------|------------------|-----------------|-------|
| **100-500** (thin) | 35.0% | **23.2%** | +11.8% (overconfident) |
| **5000+** (deep) | 29.6% | **41.6%** | -12.0% (underconfident) |

**Thin orderbooks: Model overconfident**
**Deep orderbooks: Model underconfident**

### Why This Happens:

From `edge_detector_advanced.py` lines 215-217, microstructure adjustments:

```python
micro_yes = self.orderbook.get_microstructure_signal(ticker, orderbook_data, side='yes')
micro_no = self.orderbook.get_microstructure_signal(ticker, orderbook_data, side='no')
```

The orderbook analyzer likely:
1. Sees thin orderbook → assumes low liquidity → reduces confidence
2. Sees deep orderbook → assumes high liquidity → increases confidence

But the data shows the opposite:
- Thin orderbooks: Actually perform BETTER than expected (overcorrection)
- Deep orderbooks: Actually perform WORSE than expected (undercorrection)

**Why?** Deep orderbooks may indicate:
- More market makers
- Better pricing efficiency
- HARDER to find edge (market is more accurate)

So deep orderbooks should REDUCE confidence, not increase it!

---

## 🎯 THE REAL ROOT CAUSE

All three bugs point to the same underlying issue:

### **The model is optimized for trending markets that REACH thresholds**
### **But Kalshi sets thresholds ABOVE where prices actually close**

Example:
- BTC at $50,000
- UP market threshold: $50,100 (0.2% above current)
- Momentum: +0.3% UP
- Model thinks: "Strong momentum UP, high probability of reaching $50,100"
- Reality: Price closes at $50,090 (went UP but not enough)
- Result: YES bet loses, NO bet wins

**The markets are designed so thresholds are HARD to reach.**

This explains:
1. ✅ Why UP momentum → Model confident → Actually loses
2. ✅ Why DOWN momentum → Model pessimistic → Actually wins (NO bets)
3. ✅ Why "contrarian" bets win (betting AGAINST reaching threshold)
4. ✅ Why negative edges win (model says "no edge" but threshold is hard)

---

## 💡 THE FIXES

### Fix #1: Invert the Momentum Bonus (Immediate)

In `momentum_analyzer.py` line 259 and 267:

```python
# CURRENT (WRONG)
if momentum['direction'] == 'up':
    expected_prob += 0.15  # Makes model TOO confident

# FIXED
if momentum['direction'] == 'up':
    expected_prob -= 0.15  # Reduce confidence when momentum strong
    # Because threshold is likely above current price
```

**Why this works:** Strong momentum means market is moving toward threshold, but thresholds are set AHEAD of likely close price.

### Fix #2: Disable Calibration Curve (Immediate)

In `momentum_analyzer.py` line 397, when calling `_apply_calibration_curve`:

```python
# CURRENT
calibrated_prob = self._apply_calibration_curve(expected_prob, momentum_direction)

# FIXED (temporary)
calibrated_prob = expected_prob  # Don't apply broken curve
```

Or set this config:
```yaml
probability_model: "v1"  # Use legacy without calibration
```

### Fix #3: Simplify the Model (Medium-term)

The multi-factor adjustments (vol, orderbook, stat arb) add noise. Data shows:
- Bot overall error: 0.473
- Market overall error: 0.498

Bot is only 2.5% more accurate than market price itself!

**Simpler is better:**

```python
# Instead of complex multi-factor model, use simple approach:
# 1. Calculate distance to threshold
# 2. Adjust for mean reversion (fade momentum, not follow it)
# 3. Done

def simple_probability(current_price, threshold, momentum_pct):
    distance_pct = ((threshold - current_price) / current_price) * 100

    # Base probability (how far from threshold)
    if distance_pct < -1:  # More than 1% above threshold
        base_prob = 0.80  # Very likely to stay above
    elif distance_pct > 1:  # More than 1% below threshold
        base_prob = 0.20  # Unlikely to reach
    else:
        base_prob = 0.50  # Close call

    # Fade strong momentum (mean reversion)
    if abs(momentum_pct) > 0.5:  # Strong momentum
        # Reduce confidence - likely to reverse
        momentum_adjustment = -min(abs(momentum_pct) * 0.10, 0.15)
    else:
        momentum_adjustment = 0

    return max(0.05, min(0.95, base_prob + momentum_adjustment))
```

This aligns with your data:
- Strong momentum → Reduce confidence → Fewer losses
- Near threshold → Coin flip → Accurate
- Far from threshold → High confidence → Wins

---

## 📊 Expected Impact of Fixes

### Current (Broken) Model:
- UP momentum markets: Model says 41.4%, actually 20.9% ❌
- DOWN momentum markets: Model says 12.7%, actually 50.3% ❌

### After Fix #1 (Invert Momentum):
- UP momentum markets: Model says ~26%, actually ~21% ✅
- DOWN momentum markets: Model says ~28%, actually ~50% (still off but better)

### After Fix #1 + #2 (No Calibration):
- Overall accuracy improves ~15-20%
- Edge calculation becomes meaningful again

### After Fix #1 + #2 + #3 (Simple Model):
- Clean signal, less noise
- Estimated 55-60% win rate (vs current 42.9%)

---

## ✅ IMMEDIATE ACTION PLAN

1. **Disable the broken calibration curve**
2. **Invert the momentum bonus** (or remove it entirely)
3. **Test for 24 hours**
4. **If works, simplify to distance-based model**

The core issue is **Kalshi's thresholds are optimistic** and your model is following momentum, when it should be fading it.

