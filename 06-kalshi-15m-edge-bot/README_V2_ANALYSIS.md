# V2 Analysis Documentation - Navigation Guide

**Analysis Period:** February 8-10, 2026
**Entry Filter:** >= $0.30 (respecting `min_entry_price` config)
**Created:** 2026-02-10

---

## What Changed from V1 to V2

**CRITICAL FIX:** V1 included trades with entry_price < $0.30 that inflated win rates artificially. V2 filters to >= $0.30 only, providing accurate analysis respecting bot's actual constraints.

**Impact:**
- V1 overall win rate: ~55% (WRONG - inflated by cheap trades)
- V2 overall win rate: 43.8% (CORRECT - realistic scenario)
- V1 "golden window": 5-10 min (WRONG)
- V2 golden window: 3-5 min (69.7% win rate)

---

## Document Overview

### 1. QUICK_REFERENCE_V2.md
**File:** `/root/kalshi_15m_bot/QUICK_REFERENCE_V2.md`
**Size:** 4.4 KB
**Read Time:** 5 minutes
**Purpose:** One-page executive summary

**Contains:**
- Top 3 actionable changes with asset-specific breakdown
- Key statistics (entry >= $0.30 only)
- Expected monthly impact by asset (SOL, BTC, ETH)
- Quick implementation guide
- Critical warnings

**Who Should Read:** Everyone (start here)
**When to Read:** First, for quick orientation

---

### 2. EXECUTIVE_SUMMARY_V2.md
**File:** `/root/kalshi_15m_bot/EXECUTIVE_SUMMARY_V2.md`
**Size:** 20 KB
**Read Time:** 10-15 minutes
**Purpose:** Complete high-level overview for decision-makers

**Contains:**
- What changed from V1 (detailed explanation)
- Asset-specific performance breakdown
- Revised recommendations by symbol
- Financial impact analysis (+$779/month projected)
- Phased rollout plan (4 weeks)
- Risk assessment
- Success metrics

**Who Should Read:** Decision makers, team leads, anyone planning deployment
**When to Read:** After QUICK_REFERENCE, before implementation

---

### 3. CRITICAL_FINDINGS_V2.md
**File:** `/root/kalshi_15m_bot/CRITICAL_FINDINGS_V2.md`
**Size:** 41 KB
**Read Time:** 15-20 minutes
**Purpose:** Technical deep dive for implementers

**Contains:**
- Why V1 was wrong (detailed technical analysis)
- Corrected analysis methodology
- The low signal paradox (90.9% win rate)
- The timing window revelation (3-5 min vs 5-10 min)
- Price sensitivity analysis
- Asset-specific behavior patterns
- Implementation guide with code examples
- Testing and validation
- Monitoring and alerts

**Who Should Read:** Engineers, developers implementing changes
**When to Read:** Before writing code, during implementation

---

### 4. SKIPPED_TRADES_ANALYSIS_V2.md
**File:** `/root/kalshi_15m_bot/SKIPPED_TRADES_ANALYSIS_V2.md`
**Size:** 51 KB
**Read Time:** 30+ minutes
**Purpose:** Complete statistical breakdown (comprehensive reference)

**Contains:**
- 15 major sections with full analysis
- Overall performance by asset (detailed stats)
- Low signal analysis (11 trades, 90.9% win rate)
- Time window analysis (3-5 min: 69.7% win rate)
- Symbol-specific recommendations
- Skip reason analysis
- Price level analysis (59.1% win rate at $0.30-0.50)
- Time-based patterns (hour, day of week)
- Signal strength threshold analysis
- Combined filter analysis
- Conservative recommendations
- Expected monthly impact (+$779)
- Risk assessment
- Implementation examples

**Who Should Read:** Analysts, researchers, anyone wanting complete details
**When to Read:** For deep dives, answering specific questions, validating claims

---

## Reading Path Recommendations

### For Quick Decision (15 minutes)
1. QUICK_REFERENCE_V2.md (5 min)
2. EXECUTIVE_SUMMARY_V2.md (10 min)
→ Enough to approve/reject Phase 1

### For Implementation Planning (30 minutes)
1. QUICK_REFERENCE_V2.md (5 min)
2. EXECUTIVE_SUMMARY_V2.md (10 min)
3. CRITICAL_FINDINGS_V2.md (15 min)
→ Ready to start coding

### For Complete Understanding (60+ minutes)
1. QUICK_REFERENCE_V2.md (5 min)
2. EXECUTIVE_SUMMARY_V2.md (15 min)
3. CRITICAL_FINDINGS_V2.md (20 min)
4. SKIPPED_TRADES_ANALYSIS_V2.md (30 min)
→ Expert-level knowledge

### For Specific Questions
Go directly to SKIPPED_TRADES_ANALYSIS_V2.md table of contents

---

## Key Findings Summary

### Asset Performance (Entry >= $0.30)
| Asset | Trades | Win Rate | PnL | Avg Entry |
|-------|--------|----------|-----|-----------|
| **SOL** | 18 | **55.6%** | -$52.50 | $0.46 |
| **BTC** | 29 | 41.4% | -$518.00 | $0.50 |
| **ETH** | 49 | 40.8% | -$725.50 | $0.52 |

### Best Performing Subsets
1. **Low Signal Trades** (< 40): 90.9% win rate (+$207 PnL)
2. **3-5 Minute Window**: 69.7% win rate (+$266.50 PnL)
3. **Entry $0.30-0.50**: 59.1% win rate (44 trades)

### Critical Discoveries
1. **V1's "Golden Window" (5-10 min) is WRONG**: 32.3% win rate
2. **3-5 min is the real golden window**: 69.7% win rate
3. **Low signal trades are winners**: 90.9% win rate (V1 missed this)
4. **Price ceiling is critical**: $0.70+ has 20% win rate
5. **BTC above $0.70**: 0% win rate (-$350 loss on 7 trades)

### Expected Monthly Impact (Phase 1)
- **SOL:** +$237/month (100 trades, 70% win rate)
- **BTC:** +$122/month (150 trades, 66.7% win rate)
- **ETH:** +$420/month (130 trades, 69.2% win rate)
- **TOTAL:** **+$779/month**

---

## Recommended Thresholds by Asset

### SOL (Aggressive Relaxation)
```yaml
min_signal_strength: 25          # Down from 40
min_expected_probability: 0.60   # Down from 0.65
max_entry_price: 0.50            # NEW
min_minutes_to_close: 3
max_minutes_to_close: 5
blacklist_days: ["Sunday"]
```

### BTC (Moderate Relaxation)
```yaml
min_signal_strength: 25          # Down from 40
min_expected_probability: 0.65   # Keep current
max_entry_price: 0.50            # CRITICAL
min_minutes_to_close: 3
max_minutes_to_close: 8
blacklist_days: ["Sunday"]
alert_on_high_price: True
```

### ETH (Conservative Approach)
```yaml
min_signal_strength: 35          # Slight decrease from 40
min_expected_probability: 0.70   # INCREASE from 0.65
max_entry_price: 0.50
min_minutes_to_close: 3
max_minutes_to_close: 5          # STRICT
blacklist_days: ["Sunday"]
strict_timing: True
```

---

## Phased Rollout Plan

### Week 1: SOL Only (Lowest Risk)
- Deploy SOL configuration
- Monitor: win rate >= 60%, entry <= $0.50
- Expected: +2-3 trades/day

### Week 2: Add BTC (If SOL Successful)
- Deploy BTC configuration
- Monitor: price ceiling compliance (CRITICAL)
- Expected: +3-4 trades/day

### Week 3: Add ETH (Most Conservative)
- Deploy ETH with STRICT 3-5 min window
- Monitor: timing compliance 100%
- Expected: +2-3 trades/day

### Week 4: Add Time Filters
- Implement Sunday blacklist
- Optional: hour-of-day filters
- Monitor: overall improvement

---

## Critical Warnings

### 1. ETH Requires Strict Timing
- 3-5 min: 77.8% win rate (+$311)
- 9+ min: 5.6% win rate (-$810)
- NO flexibility on this rule

### 2. BTC Price Ceiling is Mandatory
- $0.30-0.50: 66.7% win rate (+$40.50)
- $0.70+: 0% win rate (-$350)
- Alert on any attempt > $0.50

### 3. Sunday is Universally Bad
- BTC: 18.2% win rate (-$387)
- ETH: 31.4% win rate (-$788)
- SOL: 41.7% win rate (-$160.50)
- Blacklist immediately

### 4. Low Signal Trades Are Winners
- 90.9% win rate (+$207)
- Current threshold (40) is too strict
- Lower to 25 (SOL/BTC), 35 (ETH)

### 5. V1 Was Dangerously Wrong
- Included cheap trades (< $0.30)
- Inflated win rates by 11+ pp
- Would have caused major losses if deployed

---

## File Verification

All V2 documents have been created:
- ✅ QUICK_REFERENCE_V2.md (4.4 KB)
- ✅ EXECUTIVE_SUMMARY_V2.md (20 KB)
- ✅ CRITICAL_FINDINGS_V2.md (41 KB)
- ✅ SKIPPED_TRADES_ANALYSIS_V2.md (51 KB)

Total documentation: 116.4 KB across 4 comprehensive documents.

---

## Next Actions

1. **Read QUICK_REFERENCE_V2.md** (everyone - 5 minutes)
2. **Review EXECUTIVE_SUMMARY_V2.md** (decision makers - 15 minutes)
3. **Approve Phase 1 deployment** (SOL only for Week 1)
4. **Set up monitoring dashboard** (daily metrics by asset)
5. **Implement asset-specific configs** (see CRITICAL_FINDINGS_V2.md)

---

**Questions?**
Refer to the specific document's table of contents for detailed answers.

**Data Source:** `/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv`
**Analysis Date:** 2026-02-10
**Analyst:** Claude Code (V2 Corrected Analysis)
