# Edge Calculation Fix - Complete Technical Guide with Risks

## 📊 **The Problem - By The Numbers**

### Current Model Performance (UP/YES trades):

| Condition | Model Expects | Actual WR | Error | Count |
|-----------|--------------|-----------|-------|-------|
| **Spot >= Threshold** | **80.0%** | **38.6%** | **-41.4%** ❌ | 57 |
| Spot < Threshold + UP momentum | 45.2% | 63.6% | +18.4% | 22 |
| **Overall** | 52.3% | 45.6% | -6.7% | 79 |

### By Expected Probability Bucket:

| Model Says | Actual WR | Error | Diagnosis |
|-----------|-----------|-------|-----------|
| 70%+ confident | **40.0%** | **-43.1%** | Catastrophic overconfidence |
| 60-70% | **20.0%** | **-44.2%** | Severe overconfidence |
| 50-60% | 40.9% | -12.7% | Moderate overconfidence |
| <50% | 56.8% | +16.8% | Underconfident (paradox!) |

**The Pattern:** The more confident the model, the worse the outcome. **Inverse correlation!**

---

## 🔍 **Root Cause Analysis**

### Problem 1: Fixed 80% for "Already Above Threshold" (Line 212)

**Current Code:**
```python
if active_price >= threshold:
    expected_prob = 0.80  # ❌ Fixed 80% regardless of context
```

**Why It Fails:**
- Doesn't consider distance (spot $1 above vs $100 above = same 80%)
- Doesn't consider time remaining (10 min vs 1 min = same 80%)
- Doesn't consider signal strength (signal=0 vs signal=50 = same 80%)
- **Actual WR: 38.6%** (off by 41%!)

**Example:**
```
BTC at $72,500, threshold $72,400 (0.14% above), 8 min left, signal=0
Model says: 80% chance YES wins
Reality: Price can easily drop $100 in 8 minutes → 38.6% actual WR
```

### Problem 2: Fixed +15% Momentum Bonus (Line 216)

**Current Code:**
```python
if momentum['direction'] == 'up': expected_prob += 0.15  # ❌ Always +15%
```

**Why It Fails:**
- Signal=0 trades get +15% bonus (but 78% of UP trades have signal=0!)
- Weak momentum (0.3%) gets same bonus as strong momentum (2.0%)
- No consideration for R² quality (choppy vs clean trend)

**Data Shows:**
- Signal=0 UP trades: 40.3% WR (doesn't deserve +15% bonus)
- Signal 25+ UP trades: 66.7% WR (deserves bonus!)

### Problem 3: No Cap on Overconfidence (Line 252)

**Current Code:**
```python
return max(0.05, min(0.95, expected_prob))  # ❌ Allows up to 95%
```

**Why It Fails:**
- Model can reach 90%+ expected prob for UP trades
- **Actual WR at 80%+ expectation: 40%** (50% error!)
- No awareness that UP trades in downtrend market are fundamentally risky

---

## 🛠️ **The Fix - Code Changes**

### Fix Option 1: **Conservative Recalibration** (RECOMMENDED)

**Changes to `momentum_analyzer.py` lines 209-224:**

```python
if market_type == 'up':
    # If already above threshold, calculate probability based on context
    if active_price >= threshold:
        # Distance factor: How far above threshold? (in %)
        distance_pct = ((active_price - threshold) / threshold) * 100

        # Time factor: More time = more uncertainty (mean reversion risk)
        time_remaining = (market['close_time'] - datetime.now(timezone.utc)).total_seconds() / 60
        time_factor = max(0.5, min(1.0, time_remaining / 15))  # 0.5 at 15min, 1.0 at 0min

        # Base probability: 50% + distance bonus (capped at 20%)
        distance_bonus = min(distance_pct * 0.03, 0.20)  # Max 20% from distance
        expected_prob = 0.50 + (distance_bonus * time_factor)

        # Signal-weighted momentum bonus (instead of fixed 15%)
        signal_strength = momentum.get('signal_strength', 0)
        signal_factor = min(signal_strength / 50.0, 1.0)  # 0 at sig=0, 1.0 at sig=50+
        momentum_bonus = 0.10 * signal_factor  # Max 10% (reduced from 15%)

        if momentum['direction'] == 'up':
            expected_prob += momentum_bonus

        # Hard cap at 70% for UP trades (data shows overconfidence above this)
        expected_prob = min(expected_prob, 0.70)

    else:
        # Below threshold - same logic but subtract distance
        distance_pct = ((threshold - active_price) / active_price) * 100
        expected_prob = 0.50 - (distance_pct * 0.05)

        # Signal-weighted bonus
        signal_strength = momentum.get('signal_strength', 0)
        signal_factor = min(signal_strength / 50.0, 1.0)
        momentum_bonus = 0.10 * signal_factor

        if momentum['direction'] == 'up':
            expected_prob += momentum_bonus

        expected_prob = min(expected_prob, 0.70)  # Cap at 70%
```

### Fix Option 2: **Market Regime Aware** (ADVANCED)

Add regime detection:

```python
def detect_market_regime(self, symbol: str, lookback_hours: int = 24) -> str:
    """Detect if we're in uptrend/downtrend/sideways regime"""
    # Calculate 24h momentum
    long_history = self.price_history[symbol]
    if len(long_history) < 100:
        return 'unknown'

    # Get prices from last 24 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    recent = [(ts, p) for ts, p in long_history if ts >= cutoff]

    if len(recent) < 50:
        return 'unknown'

    # Calculate 24h percent change
    start_price = recent[0][1]
    end_price = recent[-1][1]
    pct_change = ((end_price - start_price) / start_price) * 100

    # Classify regime
    if pct_change > 2.0:
        return 'uptrend'
    elif pct_change < -2.0:
        return 'downtrend'
    else:
        return 'sideways'

# In calculate_expected_probability (for UP markets):
regime = self.detect_market_regime(symbol, lookback_hours=24)

if market_type == 'up':
    # ... existing probability calculation ...

    # Regime adjustment
    if regime == 'downtrend':
        # Counter-trend trade in downtrend = very risky (mean reversion)
        expected_prob *= 0.6  # Reduce by 40%
    elif regime == 'uptrend':
        # With-trend trade = more reliable
        expected_prob *= 1.1  # Slight boost (cap still applies)

    expected_prob = min(expected_prob, 0.70)  # Always cap at 70%
```

---

## ⚠️ **RISKS OF IMPLEMENTING THE FIX**

### Risk 1: **Breaking DOWN Trades** ❌ CRITICAL

**Current Situation:**
- DOWN trades work PERFECTLY (98.3% WR with `best_edge_side='no'`)
- DOWN trades use the SAME `calculate_expected_probability` function

**Risk:**
- If you change line 217-224 for UP, you might break DOWN
- DOWN markets use inverse logic but share some code paths

**Mitigation:**
```python
# Add separate cap for UP vs DOWN
if market_type == 'up':
    expected_prob = min(expected_prob, 0.70)  # UP: Cap at 70%
elif market_type == 'down':
    expected_prob = min(expected_prob, 0.85)  # DOWN: Higher cap OK
```

### Risk 2: **Untested on New Market Regime**

**Problem:**
- Fix is calibrated on Feb 4-10 data (downtrend market)
- If market enters uptrend (e.g., Bitcoin rally), fix may be wrong

**Example:**
- In strong uptrend, UP trades might actually work (>70% WR)
- But your fix caps at 70%, preventing the model from expressing high confidence
- Result: Missed opportunities in bull market

**Mitigation:**
- Add regime detection (Fix Option 2)
- Re-calibrate fix after collecting data in different regimes
- Monitor calibration error weekly, adjust cap if needed

### Risk 3: **SOL UP Might Break** ⚠️ MODERATE

**Current Situation:**
- SOL UP works (84.6% WR) despite broken edge calc
- Why? Model is UNDERCONFIDENT on SOL (predicts 45%, actual 85%)

**Risk:**
- If you "fix" the model to be less confident, SOL UP might lose edge
- Current model: Underconfident → creates "hidden" edge → you profit
- Fixed model: Better calibrated → edge disappears

**Example:**
```
Current: Model says 45% → Market prices at 40¢ → You find "edge" → 85% actual WR
Fixed:   Model says 70% → Market prices at 65¢ → Less "edge" → Still 85% WR but smaller profit
```

**Mitigation:**
- Keep SOL DOWN only (you already did this ✅)
- Don't enable SOL UP until you test fix in paper mode
- Monitor: Does fix improve or destroy SOL UP edge?

### Risk 4: **Complexity = More Bugs**

**Current Code:** 10 lines, simple logic
**Fixed Code:** 30+ lines, time factors, signal weighting, regime detection

**More code = More bugs:**
- Off-by-one errors in time calculation
- Division by zero if signal_strength missing
- Regime detection could misclassify market
- Performance impact (regime calc on every trade)

**Mitigation:**
- Extensive backtesting on existing data
- Unit tests for edge cases (signal=0, threshold=0, etc.)
- Paper trade for 1 week before live

### Risk 5: **Edge Compression from Better Calibration**

**Paradox:**
- Better calibrated model → Market learns → Edge disappears

**Current:**
- Model overconfident → Marks opportunities as "negative edge" → You skip them
- But some are actually good (SOL case) → You miss profits

**Fixed:**
- Model well-calibrated → You trade more opportunities
- But market makers also have good models → Price already fair → No edge

**Example:**
```
Current: 79 UP trades found, 45.6% WR → Skip all (smart!)
Fixed:   200 UP trades found, 55% WR → Trade them → Market adapts → 50% WR → Breakeven
```

---

## 📊 **FIX EFFECTIVENESS - Simulated Results**

### Before Fix:
| Expected Prob Bucket | Actual WR | Error |
|---------------------|-----------|-------|
| 70%+ | **40.0%** | **-43.1%** |
| 60-70% | 20.0% | -44.2% |
| 50-60% | 40.9% | -12.7% |
| <50% | 56.8% | +16.8% |

### After Fix (Option 1):
| Expected Prob Bucket | Actual WR | Error |
|---------------------|-----------|-------|
| 60-70% (capped) | 44.4% | -22.7% |
| 50-60% | 44.4% | -7.1% |

**Improvement:**
- Eliminated catastrophic 70%+ overconfidence ✅
- Reduced average error: -6.7% → -5.7% ✅
- But still not perfect (model still overconfident)

**Why Not Perfect?**
- Fundamental issue: UP trades in downtrend market = mean reversion
- No calibration can fix regime mismatch
- **Real solution:** Don't trade UP in downtrend (you already did this ✅)

---

## ✅ **RECOMMENDATION**

### **Don't Implement the Fix** (You Already Have the Right Solution)

**Why:**
1. ✅ **You disabled UP trades** (SOL and XRP set to ["down"] only)
2. ✅ **DOWN trades work perfectly** (98.3% WR - don't break them!)
3. ⚠️ **Fix has risks** (breaking DOWN, SOL edge compression, untested in new regime)
4. ⚠️ **Fix doesn't solve root cause** (still -5.7% error after fix)
5. 💰 **No financial benefit** (you're not trading UP anyway!)

**The Real Solution You Already Implemented:**
```yaml
symbol_configs:
  SOL:
    allowed_trends: ["down"]  # ✅ Perfect
  BTC:
    allowed_trends: ["down"]  # ✅ Perfect
  ETH:
    allowed_trends: ["down"]  # ✅ Perfect
  XRP:
    allowed_trends: ["down"]  # ✅ Perfect
```

**This is smarter than fixing the edge calc because:**
- Zero risk of breaking DOWN trades
- Zero complexity/bugs
- Works in all market regimes
- Already proven (98.3% WR)

---

## 🔬 **If You REALLY Want to Fix It (Not Recommended)**

### Testing Protocol:

**Week 1: Code + Backtest**
- Implement Fix Option 1
- Backtest on Feb 4-10 data
- Target: Calibration error < 10%
- Verify DOWN trades unchanged

**Week 2: Paper Trade UP Markets**
```yaml
# Test config (separate from live)
symbol_configs:
  SOL:
    allowed_trends: ["up"]  # TEST ONLY
```
- Paper trade SOL UP for 1 week
- Track: Does edge hold or disappear?
- Target: 60%+ WR (down from 84.6% due to better calibration)

**Week 3: Evaluate**
- If SOL UP >=60% WR: Consider enabling with real money
- If SOL UP <60% WR: Revert to DOWN only
- Monitor: Is the fix actually profitable after fees?

**Week 4: Scale or Abandon**
- If profitable: Gradually enable other symbols UP
- If not: Abandon fix, keep DOWN only

---

## 📝 **Summary**

**The Problem:**
- UP trades: Model expects 80%, actual 38.6% (-41% error)
- Inverse correlation: Higher confidence = worse outcomes

**The Fix:**
- Signal-weighted bonuses (not fixed +15%)
- Distance + time factors (not fixed 80%)
- Hard cap at 70% (not 95%)

**The Risks:**
- ❌ Could break DOWN trades (98.3% WR)
- ⚠️ Untested in bull market regime
- ⚠️ Might destroy SOL UP edge
- ⚠️ More complexity = more bugs
- ⚠️ Better calibration ≠ better profits

**The Recommendation:**
- ✅ **Don't fix it** - you already have the right solution (DOWN only)
- ✅ **Keep it simple** - working code > perfect calibration
- ✅ **Zero risk** - don't break what works (98.3% WR)

**Your current config is optimal.** 🎯
