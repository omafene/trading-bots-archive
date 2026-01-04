# Edge Calculation Fix - Root Cause Analysis & Roadmap

**Created:** Feb 12, 2026
**Status:** 🔴 Known Issue - Workaround Implemented
**Priority:** High (P1) - Affects core strategy logic

---

## 🔍 Problem Summary

The bot's edge calculation is **systematically wrong** when multi-factor adjustments (volatility, orderbook, stat arb) contradict the primary momentum signal.

### The Symptom
Bot generates "contrarian bets" where:
- **Momentum says:** DOWN (-0.5%)
- **Bot wants to bet:** YES (price will go UP)
- **Result:** Loses 88.4% of the time

### The Root Cause
When secondary factors (vol, orderbook, stat arb) add up to override the momentum signal, they're adding **noise, not signal**. The edge calculation trusts these noisy adjustments equally with the primary momentum signal.

---

## 📊 Evidence (Feb 12, 2026)

### Contrarian Bet Performance
```
Time Period: 4.5 hours (2:51 PM - 7:25 PM)
Markets: 73 unique, 69 verified outcomes

Contrarian Bets (as calculated):
  Win Rate: 11.6% (8/69)
  Expected Loss: -$38.40 per bet

Faded Contrarian (opposite side):
  Win Rate: 84.3% (43/51)
  Expected Profit: +$34.31 per bet
  Average Edge: -22.6% (NEGATIVE!)
```

### Key Finding
**The opposite of the bot's edge calculation wins 84% of the time, even with -22.6% calculated edge!**

This proves the edge calculation is not just wrong, but **inversely correlated** with actual outcomes in contrarian scenarios.

---

## 🩹 Current Workaround (Implemented)

### What We Did
Added "fade contrarian bets" feature:
- Detect when edge calc contradicts momentum
- Take the **opposite** side (aligned with momentum)
- Bypass edge requirements (allow negative edge)

### Files Modified
1. `config_15m.yaml` - Added `fade_contrarian_bets` config
2. `edge_detector_advanced.py` - Added fade logic (lines 346-411)
3. `FADE_CONTRARIAN_GUIDE.md` - Documentation

### Why This is a Workaround
- ✅ **Works:** 84% win rate
- ❌ **Not a fix:** Doesn't address root cause
- ❌ **Fragile:** Relies on edge calc staying broken in the same way
- ❌ **Incomplete:** Only catches extreme cases, may miss subtle miscalculations

---

## 🎯 Root Cause Fix - What Needs to Change

### Current Edge Calculation Logic
```python
# Phase 1: Momentum → base_prob (e.g., 95% DOWN)
base_prob = calculate_from_momentum(...)

# Phase 2-5: Apply adjustments
vol_adjustment = +3%
micro_adjustment = +5%
stat_arb_adjustment = +2%
time_adjustment = +4%

# PROBLEM: These can sum to +14% and flip the signal!
adjusted_prob = base_prob + vol_adj + micro_adj + stat_arb + time_adj
# Result: 95% DOWN → 81% UP (FLIPPED!)

# Phase 6: Calculate edge for BOTH sides
edge_yes = (adjusted_prob - market_price) * 100
edge_no = ((1 - adjusted_prob) - market_price) * 100

# Phase 7: Pick side with HIGHER edge (even if contrarian!)
if edge_yes > edge_no:
    bet_yes()  # CONTRARIAN - loses 88% of time!
```

### The Problem
1. **Additive adjustments** can overwhelm the base signal
2. **No weighting hierarchy** - momentum treated same as orderbook noise
3. **No direction locking** - adjustments can flip the direction
4. **Blind optimization** - picks highest edge regardless of signal coherence

---

## 🔧 Proposed Fixes (Priority Order)

### Option 1: Directional Adjustments Only (RECOMMENDED)
**Concept:** Adjustments strengthen/weaken confidence, but never flip direction

```python
# Base momentum signal
if momentum_direction == 'down':
    base_prob = 0.95  # 95% chance DOWN
else:
    base_prob = 0.05  # 5% chance DOWN

# Adjustments scale the CONFIDENCE, not flip the direction
confidence_multiplier = 1.0
confidence_multiplier += vol_signal * 0.05      # ±5% confidence
confidence_multiplier += micro_signal * 0.03    # ±3% confidence
confidence_multiplier += stat_arb_signal * 0.02 # ±2% confidence

# Apply multiplier (bounded to prevent >100% or <0%)
if momentum_direction == 'down':
    adjusted_prob = min(0.99, max(0.60, base_prob * confidence_multiplier))
    # Examples:
    # 95% * 1.10 = 99% (very confident DOWN)
    # 95% * 0.90 = 85% (less confident DOWN)
    # NEVER flips to UP!
else:
    adjusted_prob = max(0.01, min(0.40, base_prob * confidence_multiplier))

# Only calculate edge for momentum-aligned side
if momentum_direction == 'down':
    edge_no = calculate_edge(adjusted_prob, market['no_ask'])
    bet_no_if_edge_positive()
else:
    edge_yes = calculate_edge(adjusted_prob, market['yes_ask'])
    bet_yes_if_edge_positive()
```

**Pros:**
- ✅ Momentum always wins (as evidence shows it should)
- ✅ Secondary factors still contribute (adjust confidence)
- ✅ No contrarian bets possible
- ✅ Simpler logic

**Cons:**
- ❌ Can't catch genuine reversals (but evidence shows this is rare)
- ❌ Requires refactoring adjustment calculations

---

### Option 2: Weighted Factor Hierarchy
**Concept:** Give momentum much higher weight than secondary factors

```python
# Weighted combination
final_prob = (
    0.70 * momentum_prob +      # 70% weight to momentum
    0.10 * vol_adjusted_prob +   # 10% weight to volatility
    0.10 * micro_prob +          # 10% weight to orderbook
    0.05 * stat_arb_prob +       # 5% weight to stat arb
    0.05 * time_decay_prob       # 5% weight to time decay
)

# Now secondary factors can't overwhelm momentum
# Max they can shift: 30% vs momentum's 70%
```

**Pros:**
- ✅ Preserves current structure
- ✅ Can still catch reversals (if all factors agree)
- ✅ Easier to implement

**Cons:**
- ❌ Doesn't fully solve the problem
- ❌ Still possible to generate contrarian bets
- ❌ Requires tuning weights

---

### Option 3: Two-Stage Filtering
**Concept:** Momentum filters first, then edge calculation

```python
# Stage 1: Momentum Filter
if momentum_direction == 'down':
    allowed_sides = ['no']
else:
    allowed_sides = ['yes']

# Stage 2: Calculate edge ONLY for allowed sides
edge_dict = {}
for side in allowed_sides:
    edge_dict[side] = calculate_full_edge(market, side)

# Stage 3: Take best allowed edge
if max(edge_dict.values()) > min_edge_threshold:
    best_side = max(edge_dict, key=edge_dict.get)
    bet(best_side)
```

**Pros:**
- ✅ Simple to implement
- ✅ Guarantees no contrarian bets
- ✅ Keeps all existing edge logic

**Cons:**
- ❌ Wastes computation (calculates both sides, uses one)
- ❌ Doesn't fix the underlying edge calc issue

---

### Option 4: Fix Secondary Factor Calculations
**Concept:** Investigate why vol/micro/stat-arb are so noisy

**Tasks:**
1. **Analyze each factor in isolation:**
   - Does volatility signal actually predict better than momentum?
   - Does orderbook pressure work on 15min markets?
   - Is stat arb even relevant for 15min timeframes?

2. **Disable problematic factors:**
   - Run backtest with only momentum
   - Add back one factor at a time
   - Keep only factors that improve win rate

3. **Recalibrate adjustments:**
   - Current adjustments may be too large (±5%)
   - Test smaller adjustments (±1-2%)

**Pros:**
- ✅ Fixes root cause scientifically
- ✅ Improves overall model quality

**Cons:**
- ❌ Time consuming
- ❌ Requires extensive backtesting
- ❌ May find factors don't help at all

---

## 🗺️ Implementation Roadmap

### Phase 1: Data Collection (Current - Week 1)
**Status:** ✅ In Progress
- Run with fade enabled on both bots
- Collect contrarian bet data
- Track which secondary factors cause most contrarian signals

**Success Criteria:**
- 100+ contrarian opportunities logged
- Win rate data for faded trades
- Factor attribution for each contrarian signal

---

### Phase 2: Factor Analysis (Week 2)
**Status:** ⏳ Not Started

**Tasks:**
1. Analyze which factors cause contrarian signals most often
   ```python
   # Count contrarian triggers by factor
   vol_contrarian_count = sum(abs(vol_adj) > 0.05)
   micro_contrarian_count = sum(abs(micro_adj) > 0.05)
   stat_arb_contrarian_count = sum(abs(stat_arb_adj) > 0.05)
   ```

2. Test each factor's predictive power independently
   ```python
   # Win rate when factor contradicts momentum
   vol_contradiction_win_rate = ...
   micro_contradiction_win_rate = ...
   ```

3. Identify the "worst offenders"

**Deliverable:** Analysis report showing which factors add noise vs signal

---

### Phase 3: Implement Fix (Week 3)
**Status:** ⏳ Not Started

**Approach:** Start with Option 1 (Directional Adjustments Only)

**Implementation Steps:**
1. Create `edge_detector_advanced_v2.py` (don't modify existing)
2. Implement directional-only adjustment logic
3. Add A/B testing flag in config
   ```yaml
   use_v2_edge_calculation: false  # A/B test flag
   ```
4. Run both versions in parallel (observation mode)

**Testing:**
- Compare v1 vs v2 edge calculations
- Track which generates more edges
- Monitor win rates for each version

**Success Criteria:**
- V2 generates no contrarian bets
- V2 win rate >= V1 win rate
- V2 finds similar number of edges as V1

---

### Phase 4: Validation (Week 4)
**Status:** ⏳ Not Started

**Tasks:**
1. Backtest v2 on historical data
2. Paper trade v2 for 3 days
3. Compare metrics:
   - Win rate
   - Edge per trade
   - Number of trades
   - Sharpe ratio

**Success Criteria:**
- Win rate > 60%
- No contrarian signals generated
- Trade frequency similar to v1
- Drawdowns < v1

---

### Phase 5: Migration (Week 5)
**Status:** ⏳ Not Started

**Tasks:**
1. Set `use_v2_edge_calculation: true` as default
2. Monitor for 1 week
3. If stable, remove v1 code
4. Remove fade contrarian workaround
5. Update documentation

**Success Criteria:**
- Bot runs stable with v2
- Win rate maintained
- No unexpected behavior

---

## 📝 Technical Debt Created

### Files with Workaround Code (TO BE REMOVED LATER)
```
/root/kalshi_15m_bot/
  ├── config_15m.yaml (lines 78-133)
  ├── edge_detector_advanced.py (lines 346-411)
  ├── FADE_CONTRARIAN_GUIDE.md
  └── FADE_CONTRARIAN_GUIDE.md

/root/polymarket_15m_bot/
  ├── config_polymarket.yaml (lines 99-133)
  ├── edge_detector_advanced.py (lines 346-411)
  └── FADE_CONTRARIAN_GUIDE.md
```

### When to Remove
After Phase 5 completion (v2 edge calc deployed and stable for 1 week)

---

## 🧪 Experiments to Run

### Experiment 1: Factor Ablation Study
**Goal:** Which factors cause contrarian signals?

```python
# Run bot with each factor disabled
configs = [
    {"vol": False, "micro": True, "stat_arb": True},
    {"vol": True, "micro": False, "stat_arb": True},
    {"vol": True, "micro": True, "stat_arb": False},
    {"vol": False, "micro": False, "stat_arb": False}  # momentum only
]

for config in configs:
    run_backtest(config)
    measure_contrarian_rate()
```

**Expected Result:** Find which factor is noisiest

---

### Experiment 2: Adjustment Magnitude Test
**Goal:** Are adjustments too large?

```python
# Test different scaling factors
scales = [0.25, 0.50, 0.75, 1.0, 1.5, 2.0]

for scale in scales:
    vol_adj *= scale
    micro_adj *= scale
    stat_arb_adj *= scale

    run_backtest()
    measure_contrarian_rate()
    measure_win_rate()
```

**Expected Result:** Find optimal adjustment magnitude

---

### Experiment 3: Momentum-Only Baseline
**Goal:** How well does pure momentum work?

```python
# Disable all adjustments
base_prob = momentum_probability
# Skip all other phases
edge = calculate_edge(base_prob, market_price)
```

**Expected Result:** Establish momentum-only baseline performance

---

## 📚 References

### Related Discussions
- **This conversation:** Edge calculation generating inverse predictions
- **Evidence file:** `/root/kalshi_15m_bot/check_contrarian_outcomes.py`
- **Analysis:** Showed 84.3% win rate for fading contrarian bets

### Key Data Files
```
/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv
  - Contains all contrarian bet opportunities
  - Fields: yes_edge, no_edge, momentum_direction, outcome
  - Use this for analysis
```

### Code Sections to Review
```python
# edge_detector_advanced.py

Lines 244-250: Probability calculation
  - Shows additive adjustment structure

Lines 258-259: Edge calculation
  - Calculates both sides independently

Lines 264-272: Side selection
  - Picks best edge (creates contrarian bets)

Lines 346-411: Fade logic (WORKAROUND)
  - Current hack to fix the issue
```

---

## ⚠️ Important Notes

### Don't Break These
While fixing the edge calculation, preserve:
- ✅ Momentum calculation logic (works well)
- ✅ Base probability from R² and distance
- ✅ Time decay adjustments (reasonable)
- ✅ Filter logic (price floor, ceiling, etc.)

### Can Modify/Remove
- ⚠️ Additive adjustment structure
- ⚠️ Volatility adjustment (may be too noisy)
- ⚠️ Orderbook microstructure on 15m (questionable)
- ⚠️ Stat arb on short timeframes (likely useless)

---

## 🎯 Success Metrics

### Edge Calculation v2 Goals
1. **Zero contrarian bets** - Direction always matches momentum
2. **Win rate ≥ 65%** - Better than current with fading
3. **Edge accuracy** - Calculated edge correlates with actual outcomes
4. **Simplicity** - Easier to understand and debug

### Definition of Done
- [ ] V2 edge calc implemented
- [ ] Backtested on 1 month of data
- [ ] Paper traded for 1 week
- [ ] Win rate > 60% verified
- [ ] No contrarian signals in 1000+ opportunities
- [ ] Deployed to production
- [ ] Workaround code removed
- [ ] Documentation updated

---

## 💬 Conversation Summary (Feb 12, 2026)

### What We Discovered
1. Contrarian bets lose 88.4% of the time
2. Fading them (taking opposite) wins 84.3% of the time
3. Even with -22.6% average edge, fades win
4. This proves edge calc is systematically wrong in these cases

### What We Built
1. Fade contrarian feature (workaround)
2. Safety threshold (min_fade_edge: -50%)
3. Comprehensive documentation
4. Both bots updated (Kalshi + Polymarket)

### What We Need to Fix
1. **Root cause:** Additive adjustments overwhelming momentum
2. **Solution:** Directional-only adjustments (Option 1)
3. **Timeline:** 5-week roadmap
4. **Next step:** Collect data for 1 week, then analyze factors

---

## 📞 Pickup Points for Next Session

When resuming this work, start with:

1. **Check fade performance:**
   ```bash
   cd /root/kalshi_15m_bot
   python3 check_contrarian_outcomes.py
   ```

2. **Run factor analysis:**
   ```bash
   python3 analyze_contrarian_factors.py  # TO BE CREATED
   ```

3. **Review skipped trades data:**
   ```bash
   head -100 data/negative_edges/skipped_trades.csv
   ```

4. **Implement v2 edge calc:**
   - Copy `edge_detector_advanced.py` to `edge_detector_advanced_v2.py`
   - Implement Option 1 (directional adjustments)
   - Add A/B testing config

5. **Test v2:**
   - Backtest on Feb 12 data
   - Compare v1 vs v2 contrarian rates
   - Measure win rates

---

**Status:** 🔴 Workaround Active, Root Cause Fix Pending
**Owner:** To be assigned
**Last Updated:** 2026-02-12
**Next Review:** 2026-02-19 (1 week data collection)
