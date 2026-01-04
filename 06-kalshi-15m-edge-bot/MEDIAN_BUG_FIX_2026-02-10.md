# Median Aggregation Bug Fix - 2026-02-10

## Summary

Fixed critical bug in spot price feed median calculation that was causing BTC to show +$29.95 bias (+4.29 bps) vs Kalshi's floor strike. After fix, BTC bias reduced to **+$7.88 (+1.12 bps)** - a **73% improvement**.

## The Bug

**File:** `spot_price_feed.py` lines 91-92

**Old (incorrect) code:**
```python
prices.sort()
median_price = prices[len(prices) // 2]  # ❌ Wrong for even-length lists
```

**Problem:** With an even number of prices (e.g., when Kraken missing), this returns the **higher value** instead of the **average of the two middle values**.

**Example:**
- Prices: [70000, 70100]
- Buggy result: 70100 (just picks the second value)
- Correct result: 70050 (average of both)

## Root Cause Analysis

The BTC +$29.95 bias was caused by **TWO bugs working together**:

### Bug #1: Kraken Data Missing
- Kraken BTC data was missing 89% of the time (68 out of 76 markets)
- This forced a 2-price scenario: Coinbase + Binance only

### Bug #2: Incorrect Median Calculation
- With 2 prices, the buggy code returned `prices[1]` (the higher value)
- Since Binance trades ~$45 higher than Coinbase for BTC
- System was systematically picking Binance instead of averaging

### Combined Impact
- When Kraken missing + buggy median: +$33.72 bias
- When Kraken present: -$2.10 bias (correct median of 3 values worked)

## The Fix

**New (correct) code:**
```python
prices.sort()
n = len(prices)
if n % 2 == 1:
    # Odd number: take middle value
    median_price = prices[n // 2]
else:
    # Even number: average the two middle values (proper median)
    median_price = (prices[n // 2 - 1] + prices[n // 2]) / 2
```

## Impact Analysis (Historical Data Recalculation)

### BTC (76 markets)
| Metric | Before Fix | After Fix | Improvement |
|--------|-----------|-----------|-------------|
| Average bias | +$29.95 (+4.29 bps) | +$7.88 (+1.12 bps) | 73% reduction |
| Typical error | ±$57.47 | ±$44.21 | $13.26 better |
| Status | ⚠️ Acceptable | ✅ Excellent | - |

### ETH (178 markets)
| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| Average bias | -$0.01 (-0.04 bps) | -$0.01 (-0.05 bps) | Negligible |
| Status | ✨ Perfect | ✨ Perfect | No change |

### SOL (168 markets)
| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| Average bias | -$0.00 (-0.15 bps) | -$0.00 (-0.19 bps) | Negligible |
| Status | ✨ Perfect | ✨ Perfect | No change |

**Note:** ETH and SOL were unaffected because they had all 3 exchanges available 100% of the time, so the median calculation was correct (odd number of values).

## Final Calibration Results

After median bug fix, all three assets show excellent to perfect calibration:

- **BTC:** +1.12 bps (excellent, < 5 bps threshold)
- **ETH:** -0.05 bps (perfect, < 1 bps threshold)
- **SOL:** -0.19 bps (perfect, < 1 bps threshold)

## Conclusion

✅ **Median bug fixed** - proper averaging for even-length price lists
✅ **BTC calibration improved 73%** - from +4.29 bps to +1.12 bps
✅ **All assets now excellent** - no further adjustments needed

The Coinbase/Binance/Kraken median aggregation method is working correctly and matches Kalshi's CF Benchmarks methodology well.

## Files Modified

1. `spot_price_feed.py` (lines 86-94) - Fixed median calculation logic

## Testing

Verified fix with test cases:
- ✅ 3 prices (odd): [70000, 70050, 70100] → 70050
- ✅ 2 prices (even): [70000, 70100] → 70050 (was 70100)
- ✅ 2 prices (even): [70000, 70010] → 70005 (was 70010)
- ✅ 1 price: [70000] → 70000
- ✅ 4 prices (even): [2000, 2010, 2020, 2030] → 2015

## Next Steps

1. Monitor BTC performance with fixed median calculation
2. Continue tracking feed calibration data to verify improvement
3. If Kraken availability improves (bug fixed separately), expect BTC to reach -0.31 bps (nearly perfect)
