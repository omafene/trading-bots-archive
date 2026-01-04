# 🔍 Why Faded Edges Became More Negative

## 📊 Summary

**Feb 12:** Average faded edge = **-42.0%**
**Feb 13:** Average faded edge = **-110.0%**
**Difference:** **-68%** more negative

---

## 🎯 ROOT CAUSE: Slippage Buffer Increase

### Config Change (Feb 13, 06:02 AM)
```yaml
# OLD (Feb 12 and before)
slippage_buffer: 0.10  # $0.10 slippage

# NEW (Feb 13, 06:02 AM)
slippage_buffer: 0.50  # $0.50 slippage
```

### Impact on Edge Calculation

The edge formula in your code:
```python
edge = ((probability - market_price - slippage_dollars) * 100) - exchange_fee
```

**Example Calculation:**
- Bot probability: 0.15 (15% - typical contrarian side)
- Market price: $0.60 (60 cents)
- Exchange fee: 1.5%

| Setting | Calculation | Edge |
|---------|-------------|------|
| **Feb 12** (slippage 0.10) | ((0.15 - 0.60 - 0.10) × 100) - 1.5% | **-56.5%** |
| **Feb 13** (slippage 0.50) | ((0.15 - 0.60 - 0.50) × 100) - 1.5% | **-96.5%** |
| **Difference** | | **-40.0%** |

---

## 📈 Full Breakdown

### Feb 12 Data (2,027 contrarian bets)
- **Original Edge:** +53.77% avg (contrarian side bot wanted)
- **Faded Edge:** -42.01% avg (opposite side after flip)
- **Faded Win Rate:** 90.0%
- **Faded P&L:** +$84,810

### Why Feb 13 is -110% instead of -82%?
Expected impact: -42% + (-40%) = **-82%**
Actual observed: **-110%**
Extra -28% likely from:
1. **Market conditions:** Today's markets may be more extreme
2. **Sample variance:** Different set of markets being scanned
3. **Timing:** Different times of day have different spreads

---

## 🔧 The Fix Options

### Option 1: Revert Slippage (Recommended if Feb 12 was working well)
```yaml
slippage_buffer: 0.10  # Back to Feb 12 settings
min_fade_edge: -80.0   # Can keep original threshold
```
**Pros:** Return to proven settings
**Cons:** May not reflect actual slippage you're experiencing

### Option 2: Keep New Slippage + Lower Threshold (Current)
```yaml
slippage_buffer: 0.50   # Keep realistic slippage
min_fade_edge: -150.0   # Allow highly negative fades
```
**Pros:** More conservative/realistic slippage estimate
**Cons:** Taking trades with very negative calculated edges

### Option 3: Investigate Actual Slippage
- Check your actual fill prices vs quoted prices
- Measure real slippage from recent trades
- Set `slippage_buffer` to match reality

---

## 💡 Key Insight

The slippage buffer is being **subtracted from your expected value** before calculating edge. This means:

- **0.10 slippage** = -10% impact on edge (after × 100)
- **0.50 slippage** = -50% impact on edge (after × 100)
- **Difference** = -40% edge penalty

Since faded trades already have negative edges (you're betting against your model), the extra slippage makes them **much more negative**.

---

## ⚠️ Important Question

**Why was slippage increased from 0.10 to 0.50?**

Possible reasons:
1. You experienced worse slippage than 0.10 on actual trades
2. You wanted to be more conservative
3. Accidental config change

**Recommendation:** Check your actual trade fills to see what slippage you're really getting, then set the buffer accordingly.

---

## 📊 Historical Context

**Feb 12 Contrarian Bets (with 0.10 slippage):**
- Count: 2,027 trades
- Faded edge avg: -42.0%
- Faded win rate: 90.0%
- Faded P&L: +$84,810
- **Threshold:** -80% (would have allowed ~80% of these)

**Feb 13 Contrarian Bets (with 0.50 slippage):**
- Faded edge avg: -110.0%
- **Threshold:** -80% (blocks 100% of these)
- **New threshold:** -150% (allows most of these)

---

**Generated:** 2026-02-13 13:30 EST
