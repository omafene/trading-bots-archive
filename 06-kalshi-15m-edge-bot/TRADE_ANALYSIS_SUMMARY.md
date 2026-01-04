# Trade Analysis Summary

**Analysis Date:** 2026-02-02
**Data Period:** Jan 21 - Feb 2, 2026
**Total Signals:** 1,179
**Total Executions:** 398 (33.8% execution rate)

---

## 🎯 Key Findings

### 1. Your Filters Are Working, But May Be Too Loose

**Current Settings:**
- `min_edge_percent: 30%`
- `min_expected_probability: 80%`
- `min_signal_strength: 50`

**Reality Check:**
- Only **56.9%** of signals pass your 30% edge + 50 strength filters
- Your 30% edge requirement is actually at the **50th percentile** (median)
- Your 50 strength requirement is **below median** (median = 64.2)

**Problem:** You set high thresholds (30% edge, 80% probability) but they're not as restrictive as you might think because the bot generates many high-quality signals.

---

## 💰 Critical Insight: Entry Price = Edge Predictor

**Lower entry prices correlate with MUCH higher edges:**

| Entry Price | Avg Edge | Avg ROI | Signal Count |
|-------------|----------|---------|--------------|
| 0-15¢       | 53.0%    | 799%    | 64           |
| 15-30¢      | 41.7%    | 254%    | 323          |
| 30-50¢      | 29.8%    | 107%    | 655          |
| 50-75¢      | 18.1%    | 55%     | 136          |

**What This Means:**
- The bot is finding mispriced longshots (low probability outcomes priced too cheap)
- 65% of signals are in the 25-50¢ range (moderate edge opportunities)
- Only 5.4% of signals are cheap lottery tickets (<15¢)

**Question for You:** Are you comfortable betting on low-probability outcomes? Your 80% min probability filter is already screening most of these out.

---

## 📊 Symbol Performance

All three symbols show similar edge characteristics:

| Symbol | Signals | Avg Edge | Avg Strength | YES Bias |
|--------|---------|----------|--------------|----------|
| ETH    | 574     | 33.4%    | 63.9         | 75%      |
| BTC    | 343     | 32.6%    | 62.5         | 76%      |
| SOL    | 262     | 32.4%    | 62.2         | 51%      |

**Observations:**
- ETH generates the most signals (48.7%)
- All symbols have similar edge quality
- Strong YES bias (69.6% overall) suggests momentum strategies favor directional bets
- SOL is more balanced (51% YES) - possibly different market dynamics

---

## 🔍 Edge vs Strength: They Measure Different Things

Higher edge ≠ Higher signal strength:

| Edge Range | Avg Strength | Std Dev |
|------------|--------------|---------|
| 10-20%     | 60.3         | 6.1     |
| 20-30%     | 63.6         | 4.4     |
| 30-40%     | 63.9         | 4.5     |
| 40-50%     | 64.3         | 5.3     |
| 50%+       | 66.0         | 4.2     |

**What This Tells Us:**
- Signal strength increases slightly with edge, but NOT proportionally
- A 50% edge signal might have 66 strength vs 64 strength for 30% edge
- **Strength captures risk-adjusted quality**, not just raw edge size
- Both metrics matter - use them together, not separately

---

## ⚙️ Recommended Settings

### Conservative Approach (Quality over Quantity)
```yaml
min_edge_percent: 35          # Top 38% of signals
min_signal_strength: 60        # Top 45% of signals
min_expected_probability: 0.70 # Relax from 0.80
```
**Expected:** ~450 signals would pass (38% of historical)

### Balanced Approach (Current-ish)
```yaml
min_edge_percent: 30          # Keep current
min_signal_strength: 60        # Raise from 50
min_expected_probability: 0.70 # Lower from 0.80
```
**Expected:** ~640 signals would pass (54% of historical)

### Aggressive Approach (More Opportunities)
```yaml
min_edge_percent: 25          # Lower threshold
min_signal_strength: 55        # Moderate filter
min_expected_probability: 0.65 # More permissive
```
**Expected:** ~825 signals would pass (70% of historical)

---

## 🚨 Addressing Your Drawdown

**Current Status:**
- Peak: $300
- Current: $202.63
- Drawdown: 32.5%

**This is significant.** Before changing settings, you need to understand:

### Questions to Investigate:

1. **Were losing trades on weak or strong signals?**
   - If losses came from 50-60 strength signals → raise min_strength to 60+
   - If losses came from 60+ signals → the model may have issues

2. **Were losses on cheap entries (<25¢) or expensive ones?**
   - Cheap entries have higher theoretical edge but more variance
   - Consider adding `min_entry_price: 0.25` to avoid lottery tickets

3. **What was the win rate by edge bucket?**
   - Were 30-40% edge signals actually profitable?
   - You need actual P&L data to validate the edge calculations

4. **Position sizing issues?**
   - Kelly with 20% multiplier on 80% probability = large bets
   - Consider lowering `kelly_multiplier` to 0.15 or 0.10

---

## 🎯 Direct Answer to Your Original Question

> "Should I not bother about the up or down momentum % as a setting for trading?"

**Answer: NO, don't add explicit momentum filters.**

**Why:**
1. Momentum direction is already factored into signal strength (0-15 points)
2. Flat momentum signals lose 10 points automatically
3. Your 50+ strength requirement already filters weak momentum
4. The multi-factor approach is DESIGNED to find non-momentum edges

**Evidence from your data:**
- 69.6% of signals are YES (directional/momentum biased)
- But the bot still finds 30.4% NO signals (counter-momentum)
- NO signals likely rely more on stat arb and microstructure

**The few flat signals that pass your filters are probably:**
- Market inefficiencies (lagging prices)
- Orderbook imbalances (informed flow)
- Statistical arbitrage opportunities

These are EXACTLY the types of edges you want to trade.

---

## 📋 Next Steps

1. **Get actual P&L data** from Kalshi API to validate edge calculations
2. **Analyze win rate by signal strength** to find optimal threshold
3. **Consider position sizing** - your drawdown suggests oversized bets
4. **Monitor execution rate** - only 33.8% of signals execute (why?)
5. **Review failed executions** - are you missing the best opportunities?

---

## 🛠️ Analysis Tools Created

Two scripts are now available:

1. **`trade_analyzer.py`** - Comprehensive signal analysis
2. **`trade_insights.py`** - Detailed insights and recommendations

Run anytime with:
```bash
python3 trade_analyzer.py
python3 trade_insights.py
```

Export data for Excel/Sheets:
```bash
python3 trade_analyzer.py  # Creates data/signal_analysis.csv
```
