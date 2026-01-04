# 🎯 Contrarian-Only Trading Mode

## Quick Start

To trade **ONLY** faded contrarian bets:

```yaml
# In config_15m.yaml, set:
contrarian_only_mode: true  # Enable contrarian-only mode
fade_contrarian_bets: true  # Must be enabled for fading to work
min_fade_edge: -70.0        # Allow faded edges down to -70%
```

Then restart your bot:
```bash
python3 edge_bot.py
```

---

## What This Does

### ✅ **When Enabled (`contrarian_only_mode: true`):**

**TAKES:**
- Faded contrarian bets only (momentum-aligned trades)
- Example: Momentum UP, bot wanted NO → FLIPS to YES ✅

**SKIPS:**
- All non-contrarian trades
- Regular high-edge momentum trades
- Everything else

**Log message:** `⏭️ skip: Contrarian-Only Mode (non-contrarian trade)`

### ❌ **When Disabled (`contrarian_only_mode: false`):**

**Normal mode** - takes ALL trades that pass filters:
- Regular momentum trades
- Faded contrarian trades
- Everything with sufficient edge

---

## Expected Performance (Based on 24h Analysis)

| Metric | Value |
|--------|-------|
| **Daily Volume** | ~5,000 trades |
| **Win Rate** | **66.5%** |
| **Daily Profit** | **~$109K** (theoretical) |
| **Avg per Trade** | **+$21.44** |
| **Best Symbol** | XRP (73.6% WR) |

---

## Config Settings Explained

```yaml
fade_contrarian_bets: true
# Must be TRUE - enables the fade logic

min_fade_edge: -70.0
# Faded trades often have negative calculated edge
# -70% allows most profitable fades through
# Historical avg: -37% with 0.05 slippage

contrarian_only_mode: true
# NEW: When TRUE, ONLY trades faded contrarians
# Skips all regular momentum trades

disable_contrarian_bets: true
# Should be TRUE - blocks unfaded contrarian bets
# (Only relevant when fade_contrarian_bets: false)
```

---

## Monitoring

### Watch for successful fades:
```bash
tail -f logs/edge_bot.log | grep "🔄 FADING"
```

### Watch for skipped non-contrarian trades:
```bash
tail -f logs/edge_bot.log | grep "Contrarian-Only Mode"
```

### Count today's faded trades:
```bash
grep "🔄 FADING" logs/edge_bot.log | grep "$(date +%Y-%m-%d)" | wc -l
```

---

## Use Cases

### **Scenario 1: Test Fade Strategy Isolated**
```yaml
contrarian_only_mode: true   # Only fades
fade_contrarian_bets: true
```
**Result:** Pure fade performance, no other trades

### **Scenario 2: Normal Trading (Fades + Regular)**
```yaml
contrarian_only_mode: false  # All trades
fade_contrarian_bets: true
```
**Result:** Faded contrarians + regular momentum trades

### **Scenario 3: No Contrarian Trading**
```yaml
contrarian_only_mode: false
fade_contrarian_bets: false
disable_contrarian_bets: true
```
**Result:** Regular momentum only, all contrarians skipped

---

## Safety Notes

1. **Start with paper trading** to verify performance matches historical
2. **Monitor first 100 faded trades** closely
3. **Expected win rate: 66.5%** - if significantly lower, investigate
4. **XRP performs best** (73.6% WR) in contrarian fades
5. **BTC is weakest** (54.5% WR) but still profitable

---

## Troubleshooting

**Not seeing any trades?**
- Check: `contrarian_only_mode: true` AND `fade_contrarian_bets: true`
- Check: `min_fade_edge` is not too strict (try -100.0 temporarily)
- Check logs for: "🔄 FADING" messages

**Too many skips?**
- Faded edges might be below your `min_fade_edge` threshold
- Try lowering to -100.0 temporarily to see if trades appear
- Check: `slippage_buffer` setting (should be 0.05)

**All contrarians skipped?**
- Check: `fade_contrarian_bets` is TRUE
- If FALSE, contrarians will be skipped (not faded)

---

**Created:** 2026-02-13
**Based on:** 5,095 contrarian trades analyzed over 24 hours
