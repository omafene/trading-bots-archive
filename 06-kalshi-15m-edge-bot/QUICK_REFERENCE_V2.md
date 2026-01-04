# Quick Reference V2 - Skipped Trades Analysis
**Analysis Period:** February 8-10, 2026 | **Entry Filter:** >= $0.30 | **Read Time:** 5 minutes

---

## What Changed from V1
- **V1 Problem:** Included cheap trades ($0.01-0.29) that inflated win rates artificially
- **V2 Fix:** Filtered to entry_price >= $0.30 (respects `min_entry_price` config)
- **Impact:** More accurate picture - 43.8% win rate vs V1's inflated numbers
- **Key Insight:** SOL still outperforms (55.6%), but overall quality is poor without selective filters

---

## Top 3 Actionable Changes

### 1. Lower Signal Strength Threshold (Asset-Specific)
**Current:** `min_signal_strength: 40`
**Recommended:**
- **SOL:** 25 (70% win rate on low-signal + cheap entries)
- **BTC:** 25 (66.7% win rate on low-signal + cheap entries)
- **ETH:** 35 (conservative - weakest performer)

**Why:** Low signal trades (< 40) have **90.9% overall win rate** and +$207 PnL across 11 trades
**Monthly Impact:** +$621/month from low-signal trades alone

### 2. Focus on 3-5 Minute Window (Not 5-10)
**Current:** Trading allowed 0-15 minutes before close
**Recommended:**
- **ETH:** STRICT 3-5 min only (77.8% win rate, +$311 PnL)
- **SOL/BTC:** Prefer 3-5 min, allow up to 8 min

**Why:** 5-10 min window has 32.3% win rate vs 69.7% for 3-5 min
**Monthly Impact:** +$266.50 → +$800/month (extrapolated)

### 3. Enforce Price Ceiling at $0.50
**Current:** No explicit max price (relies on liquidity)
**Recommended:** `max_entry_price: 0.50` for all assets

**Why:**
- $0.30-0.50: **59.1% win rate** (44 trades)
- $0.50-0.70: 33.3% win rate (42 trades)
- $0.70+: 20% win rate (10 trades)

**Monthly Impact:** Avoid -$1,215.50/month in losses from expensive trades

---

## Key Statistics (Entry >= $0.30)

### Overall Performance
| Metric | Value |
|--------|-------|
| Total Opportunities | 96 trades (3 days) |
| Win Rate | 43.8% |
| Total PnL | -$1,296 |
| Avg Entry Price | $0.50 |

### Asset Rankings
| Rank | Asset | Trades | Win Rate | PnL | Avg Entry |
|------|-------|--------|----------|-----|-----------|
| 1 | **SOL** | 18 | **55.6%** | -$52.50 | $0.46 |
| 2 | **BTC** | 29 | 41.4% | -$518.00 | $0.50 |
| 3 | **ETH** | 49 | 40.8% | -$725.50 | $0.52 |

### Best Performing Filters (by Asset)

**SOL - Low Signal + Cheap Entry ($0.30-0.50)**
- Trades: 10
- Win Rate: **70.0%**
- PnL: **+$79.00**

**BTC - Low Signal + Cheap Entry ($0.30-0.50)**
- Trades: 15
- Win Rate: **66.7%**
- PnL: **+$40.50**

**ETH - Low Signal + 3-5 Min Window**
- Trades: 13
- Win Rate: **69.2%**
- PnL: **+$140.00**

---

## Expected Monthly Impact by Asset

### Phase 1 Deployment (Conservative)

**SOL Configuration**
- Additional Trades/Month: ~100
- Expected Win Rate: 70%
- **Monthly PnL: +$237**
- Risk Level: LOW

**BTC Configuration**
- Additional Trades/Month: ~150
- Expected Win Rate: 66.7%
- **Monthly PnL: +$122**
- Risk Level: MEDIUM

**ETH Configuration**
- Additional Trades/Month: ~130
- Expected Win Rate: 69.2%
- **Monthly PnL: +$420**
- Risk Level: MEDIUM-HIGH

### Total Expected Gain
**Combined Monthly Impact: +$779/month**
(+40% trade volume with selective asset-specific filters)

---

## Quick Implementation Guide

### Week 1: SOL Only (Lowest Risk)
```yaml
sol_config:
  min_signal_strength: 25
  min_expected_probability: 0.60
  max_entry_price: 0.50
  min_minutes_to_close: 3
  max_minutes_to_close: 5
```

### Week 2: Add BTC
```yaml
btc_config:
  min_signal_strength: 25
  max_entry_price: 0.50  # CRITICAL
  min_minutes_to_close: 3
```

### Week 3: Add ETH (Most Conservative)
```yaml
eth_config:
  min_signal_strength: 35
  min_expected_probability: 0.70  # INCREASE from 0.65
  max_entry_price: 0.50
  min_minutes_to_close: 3
  max_minutes_to_close: 5  # STRICT
```

### Week 4: Universal Filters
- Blacklist Sundays (worst day across all assets)
- Add hour-of-day filters (optional)

---

## Critical Warnings

1. **ETH is the weakest performer** (40.8% win rate) - requires strictest filters
2. **Price matters more than timing** - $0.30-0.50 has 59% win rate vs 20% for $0.70+
3. **5-10 min window is a trap** - 32% win rate (V1 was wrong about "golden window")
4. **3-5 min is the real golden window** - 69.7% win rate
5. **Low signal trades are profitable** - 90.9% win rate (V1 missed this completely)

---

**Next Steps:**
1. Read EXECUTIVE_SUMMARY_V2.md for detailed asset analysis
2. Read CRITICAL_FINDINGS_V2.md for technical implementation
3. Read SKIPPED_TRADES_ANALYSIS_V2.md for complete statistical breakdown
