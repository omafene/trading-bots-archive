# Fade Contrarian Bets - Implementation Guide

## Overview

The bot can now **fade** (take the opposite of) contrarian bets based on evidence that shows an 84.3% win rate when betting against the bot's own contrarian signals.

## Configuration

```yaml
# In config_15m.yaml

# Step 1: Disable contrarian bets (REQUIRED for fading to work)
disable_contrarian_bets: true

# Step 2: Enable fading (EXPERIMENTAL)
fade_contrarian_bets: false      # true = fade, false = skip
min_fade_edge: -50.0             # Safety: reject if edge < -50%
```

## How It Works

### Scenario 1: Contrarian Bets ALLOWED
```yaml
disable_contrarian_bets: false
fade_contrarian_bets: true     # Has NO EFFECT
```

**Behavior:** Bot takes contrarian bets normally (high risk, 11.6% win rate)

---

### Scenario 2: Contrarian Bets DISABLED (Current Default)
```yaml
disable_contrarian_bets: true
fade_contrarian_bets: false
```

**Behavior:** Bot skips contrarian bets entirely

**Example:**
- Momentum: DOWN -0.5%
- Bot calculates: YES edge = 58%, NO edge = 25%
- Bot wants to bet: YES (contrarian to DOWN momentum)
- **Action: SKIP** ⏭️

---

### Scenario 3: FADE Contrarian Bets (NEW!)
```yaml
disable_contrarian_bets: true
fade_contrarian_bets: true
min_fade_edge: -50.0
```

**Behavior:** Bot takes the OPPOSITE side of contrarian signals

**Example:**
- Momentum: DOWN -0.5%
- Bot calculates: YES edge = 58%, NO edge = -22%
- Bot wants to bet: YES (contrarian to DOWN momentum)
- **Fade detected:** Flip to NO side
- Check: NO edge (-22%) > min_fade_edge (-50%) ✅
- **Action: BET NO** 🔄 (aligned with momentum)

---

## Evidence (Feb 12, 2026)

### Data Collection
- **Time period:** 4.5 hours (2:51 PM - 7:25 PM)
- **Markets analyzed:** 73 unique contrarian opportunities
- **Markets verified:** 51 with confirmed outcomes

### Contrarian Bet Performance (Original Signal)
```
Win Rate: 11.6% (8 wins / 61 losses)
Expected Value: -$38.40 per bet
```

### Faded Contrarian Performance (Opposite Side)
```
Win Rate: 84.3% (43 wins / 8 losses)
Expected Value: +$34.31 per bet
Total Profit: +$1,750 over 51 bets
Average Edge: -22.6% (NEGATIVE!)
```

### Key Insight
**36 out of 43 winning faded trades had NEGATIVE calculated edge!**

This proves that when the bot's multi-factor model contradicts momentum so badly that it creates a contrarian signal, the edge calculation itself is systematically wrong.

---

## Theory

### The Meta-Signal

When the bot detects a contrarian opportunity, it's actually detecting:

> **"My momentum signal and my edge calculation are in extreme conflict"**

**In these situations:**
1. ✅ Momentum is correct (84% of the time)
2. ❌ Edge calculation is corrupted by multi-factor adjustments
3. 💡 The conflict itself is a signal to **trust momentum, ignore edge**

### Why It Works

The contrarian signal is a **red flag** that secondary factors (volatility, orderbook, stat arb) have added so much noise that they've overwhelmed the primary signal (momentum).

**Fading = Betting with momentum = High win rate**

---

## Safety Features

### 1. Minimum Fade Edge
```yaml
min_fade_edge: -50.0
```
Prevents taking faded trades with extremely negative edge (< -50%).

While evidence shows even -22% edge fades win 84%, this safety valve prevents catastrophic edge scenarios.

### 2. All Normal Filters Still Apply

Faded trades must still pass:
- ✅ Price floor check
- ✅ Price ceiling check
- ✅ Spread check
- ✅ Win probability check
- ✅ Depth requirements

Only the edge requirement is bypassed (since we have empirical evidence).

---

## Recommendations

### Phase 1: Data Collection (Now)
```yaml
disable_contrarian_bets: true
fade_contrarian_bets: false    # Keep disabled
```

**Action:** Continue collecting contrarian bet data for 1 week

### Phase 2: Observation Mode (After 1 week)
```yaml
disable_contrarian_bets: true
fade_contrarian_bets: true
min_fade_edge: -50.0
```

**BUT:** Set position sizing to $0 or use paper trading mode to verify performance

### Phase 3: Live Trading (If Pattern Holds)
Enable live trading with faded contrarians after confirming 70%+ win rate over 100+ trades

---

## Risks & Caveats

### ⚠️ Sample Size
- Only 51 verified markets from 4.5 hours of trading
- Single day of data (Feb 12, 2026)
- May not represent all market conditions

### ⚠️ Market Regime Dependency
- Works in current market conditions
- May fail in different volatility regimes
- Could be overfitting to today's specific patterns

### ⚠️ Edge Calculation Issues
- If the underlying edge calculation bug is fixed, fading may stop working
- This is a workaround, not a permanent solution

### ⚠️ Position Sizing
- 84% win rate ≠ 100% win rate
- Still need proper bankroll management
- Circuit breakers still apply

---

## Monitoring

### What to Watch
1. **Win rate:** Should stay > 70% for strategy to be viable
2. **Average edge:** Should stabilize around -20% to -30%
3. **Frequency:** How often are fades triggering?
4. **Market conditions:** Does it work in all regimes?

### When to Disable
- Win rate drops below 60%
- Fades trigger too frequently (> 50% of opportunities)
- Edge calculation gets fixed (contrarian signals disappear)

---

## Implementation Status

✅ **Completed:**
- Config options added
- Edge detector logic updated
- Safety checks implemented
- Documentation created

⏸️ **Current Status:**
- `fade_contrarian_bets: false` (disabled by default)
- Collecting more data before enabling

🔬 **Next Steps:**
1. Run for 1 week with fading disabled
2. Analyze outcomes of contrarian signals
3. If 70%+ win rate confirmed, enable fading in observation mode
4. After 100+ faded trades, enable live trading

---

## Code Locations

- **Config:** `config_15m.yaml` lines 78-103
- **Logic:** `edge_detector_advanced.py` lines 346-407
- **Analysis:** `check_contrarian_outcomes.py`

---

*Last Updated: Feb 12, 2026*
*Evidence Period: 4.5 hours (51 markets)*
*Status: EXPERIMENTAL - USE WITH CAUTION*
