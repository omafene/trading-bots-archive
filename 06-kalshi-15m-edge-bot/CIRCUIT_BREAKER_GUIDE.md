# Circuit Breaker (Max Drawdown Protection)

## What It Does

The **circuit breaker** automatically **halts trading** when your account balance drops below a threshold from your peak balance. This prevents catastrophic losses from strategy failure, technical bugs, or extreme market events.

---

## How It Works

### 1. **Tracks Peak Balance**
```
Day 1: Start with $500 → Peak: $500
Day 2: Profit to $540 → Peak: $540 ✅ New high!
Day 3: Profit to $580 → Peak: $580 ✅ New high!
Day 4: Loss to $550 → Peak: $580 (unchanged)
```

The bot remembers your **highest account balance** (peak) and saves it to disk (`data/risk_state.json`).

### 2. **Calculates Drawdown**
```
Drawdown = (Peak Balance - Current Balance) / Peak Balance

Example:
  Peak: $580
  Current: $493
  Drawdown: ($580 - $493) / $580 = 15%
```

### 3. **Triggers at Threshold**
```yaml
# config_15m.yaml
risk:
  max_drawdown_pct: 0.15  # 15% threshold
```

When drawdown reaches 15% (or your configured threshold):
1. **🛑 Trading automatically halted** - Bot sets `paused: true`
2. **📱 Telegram alert sent** - Immediate notification with details
3. **📊 State saved to disk** - Circuit breaker remains active after restart
4. **⚠️ Manual review required** - You must investigate and manually resume

---

## Example Scenario

### Without Circuit Breaker (Catastrophic Loss):
```
Day 1: $500 → Strategy working
Day 2: $480 (-4%) → Small loss, keep trading
Day 3: $450 (-10%) → Moderate loss, keep trading
Day 4: $380 (-24%) → Large loss, keep trading 😰
Day 5: $290 (-42%) → Massive loss, keep trading 😱
Day 6: $150 (-70%) → Ruin territory 💀
```

**Result:** Lost 70% of capital. Need 233% return to recover!

### With 15% Circuit Breaker (Protected):
```
Day 1: $500 (Peak: $500) → Strategy working
Day 2: $480 (Peak: $500) → Down 4%, still trading
Day 3: $450 (Peak: $500) → Down 10%, still trading
Day 4: $425 (Peak: $500) → Down 15%

🛑 CIRCUIT BREAKER TRIGGERED
📱 Telegram: "Trading halted - Review strategy"
⏸️ Bot paused automatically

Day 5: Manual review
       → Check logs, identify issue
       → Fix strategy or stop trading
       → Prevent further losses
```

**Result:** Limited loss to 15%. Only need 17.6% return to recover.

---

## Configuration

### Enable/Disable Circuit Breaker
```yaml
# config_15m.yaml
risk:
  circuit_breaker_enabled: true  # Set to false to disable
  max_drawdown_pct: 0.15         # 15% max drawdown
```

### Recommended Thresholds:

| Risk Tolerance | Max Drawdown | Use Case |
|----------------|--------------|----------|
| **Conservative** | 10% | New strategies, small capital |
| **Moderate** | 15% | Tested strategies, medium capital |
| **Aggressive** | 20% | Proven strategies, large capital |
| **Extreme** | 25%+ | High volatility tolerance (NOT recommended) |

⚠️ **Never set above 25%** - Losses become psychologically and mathematically difficult to recover from.

---

## What Triggers the Circuit Breaker

### 1. **Strategy Failure**
Your edge model stops working (market efficiency increased, edge compressed)

**Example:**
```
Week 1: 65% win rate → Profitable
Week 2: 62% win rate → Profitable
Week 3: 58% win rate → Breakeven
Week 4: 52% win rate → Losing money
→ Drawdown hits 15% → Circuit breaker triggers
```

**Action:** Review recent trades, check if edge still exists

### 2. **Technical Bug**
Code error causing bad trades

**Example:**
```
Bug: Position sizing calculates wrong (10x too large)
Trade 1: Risk $500 instead of $50 → Lose $500
→ 15% drawdown → Circuit breaker triggers
```

**Action:** Review logs, fix bug, resume after testing

### 3. **Black Swan Event**
Extreme unexpected market move

**Example:**
```
BTC flash crash: -20% in 5 minutes
Your 4 open positions: All stop out
→ 18% drawdown → Circuit breaker triggers
```

**Action:** Wait for market stabilization, assess if model still valid

### 4. **Market Regime Change**
Underlying market dynamics changed

**Example:**
```
Before: 15-min markets had 10-60s lag (your edge)
After: Kalshi adds faster market makers (lag down to 5s)
Your stat arb trades start failing
→ Drawdown builds to 15% → Circuit breaker triggers
```

**Action:** Adapt strategy or stop trading until edge returns

---

## Bot Behavior When Triggered

### Automatic Actions:
1. ✅ **Bot paused** - Sets `paused: true` (thread-safe)
2. ✅ **State saved** - Writes to `data/risk_state.json`
3. ✅ **Critical logs** - Logs details to console and log file
4. ✅ **Telegram alert** - Sends detailed notification

### Log Output:
```
============================================================
🛑 CIRCUIT BREAKER TRIGGERED
============================================================
Current Drawdown: 15.5%
Max Allowed: 15.0%
Peak Balance: $580.00
Current Balance: $490.00
Loss: $90.00
============================================================
🛑 TRADING HALTED - MANUAL REVIEW REQUIRED
============================================================
✅ Bot automatically paused
📱 Telegram alert sent
```

### Telegram Alert:
```
🛑 CIRCUIT BREAKER TRIGGERED
──────────────────
Drawdown: 15.5%
Max Allowed: 15.0%

Peak Balance: $580.00
Current Balance: $490.00
Loss: $90.00

🛑 TRADING HALTED
⚠️ ACTION REQUIRED:
1. Review recent trades
2. Check for strategy failure
3. Analyze market conditions
4. Manual resume required
```

---

## How to Resume Trading

### Step 1: Investigate the Cause
```bash
# Check recent trades in logs
grep "FILL CONFIRMED" logs/edge_bot.log | tail -20

# Check for errors
grep "ERROR\|CRITICAL" logs/edge_bot.log | tail -30

# Review drawdown progression
grep "DRAWDOWN STATUS" logs/edge_bot.log | tail -50
```

### Step 2: Identify the Issue
- **Strategy failure?** → Win rate dropped, edge compressed
- **Technical bug?** → Code errors in logs
- **Bad luck?** → Random variance (happens, but rare to hit 15%)
- **Market change?** → Liquidity dried up, lag decreased, etc.

### Step 3: Fix or Stop
- **If fixable:** Fix the bug, adjust thresholds, wait for better conditions
- **If not fixable:** Stop trading, strategy no longer profitable

### Step 4: Resume Trading (Manual)

**Option A: Via Telegram**
```
/resume
```

**Option B: Via Config**
```yaml
# config_15m.yaml
bot:
  paused: false  # Change from true to false
```

Then restart the bot.

---

## Resetting the Circuit Breaker

### Automatic Reset (Recommended):
The circuit breaker **automatically resets** when your balance recovers above the peak:

```
Peak: $580
Drawdown to $490 → Circuit breaker triggers → Trading halted
Manual trading or market recovery → Balance rises to $585
→ New peak: $585 → Circuit breaker resets ✅
```

### Manual Reset (Advanced):
⚠️ **Use with extreme caution!**

If you want to force-reset the circuit breaker without recovering:

```python
# In Python console or debug script
from edge_bot import EdgeDetectionBot
bot = EdgeDetectionBot()
bot.risk_manager.reset_circuit_breaker(manual_override=True)
```

**When to use:**
- After depositing new capital
- After fixing a known bug and you're confident
- After testing in paper trading confirms fix

**DO NOT use if:**
- You don't understand why drawdown happened
- Strategy is genuinely failing
- Just trying to "push through" losses

---

## Adjusting After Capital Changes

### After Depositing Capital:
```python
# Option 1: Reset peak to new total
bot.risk_manager.reset_peak_balance(new_peak=1000)  # If you deposit $500 to reach $1000

# Option 2: Let it adjust naturally
# Just deposit and continue - peak will update as you profit
```

### After Withdrawing Capital:
```python
# Reset peak to new total
bot.risk_manager.reset_peak_balance(new_peak=500)  # If you withdraw $500
```

---

## Monitoring Drawdown

### In Portfolio Status Logs:
```
💼 PORTFOLIO STATUS:
   Cash: $525.00
   Active Positions: 2
   Real Exposure: $45.00

📊 DRAWDOWN STATUS:
   Peak Balance: $580.00
   Current Drawdown: 9.5%
   Max Allowed: 15.0%
   Distance to Breaker: 5.5%
```

### Warning Levels:
- **0-8% drawdown:** 🟢 Normal variance
- **8-12% drawdown:** 🟡 Warning - Monitor closely
- **12-15% drawdown:** 🟠 Alert - Approaching threshold
- **15%+ drawdown:** 🔴 Circuit breaker triggered

---

## Best Practices

### 1. **Don't Disable It**
The circuit breaker exists for a reason. If you think 15% is too strict, increase the threshold rather than disabling:

```yaml
risk:
  circuit_breaker_enabled: true  # Keep enabled!
  max_drawdown_pct: 0.20         # Increase threshold if needed
```

### 2. **Take It Seriously**
If the circuit breaker triggers, **something is wrong**. Don't just resume and hope for the best.

### 3. **Track Your Peak**
Check `data/risk_state.json` periodically to see your peak balance and circuit breaker status.

### 4. **Test in Paper Trading**
Before going live, test that the circuit breaker works by simulating losses (or temporarily lowering the threshold to 5%).

### 5. **Set and Forget**
Once configured correctly, don't touch it. The circuit breaker should be your **last line of defense**, not something you frequently adjust.

---

## FAQ

### Q: What if I hit the circuit breaker due to bad luck?
**A:** Statistically unlikely. A 15% drawdown with a 60% win rate would require ~8-10 consecutive losses, which has <1% probability. More likely a strategy issue.

### Q: Can I disable it temporarily?
**A:** Yes, but **strongly discouraged**. Set `circuit_breaker_enabled: false` in config. Only do this if you understand the risks.

### Q: What if I'm testing a new strategy?
**A:** **Lower the threshold** to 10% while testing, not disable it entirely.

### Q: Does it work across bot restarts?
**A:** Yes! Peak balance and circuit breaker state persist in `data/risk_state.json`.

### Q: What if I delete the state file?
**A:** Peak resets to `total_capital` from config. Circuit breaker starts fresh.

### Q: Can I set different thresholds for different strategies?
**A:** Currently no (single threshold per bot). Run separate bot instances if needed.

---

## Summary

✅ **What it protects against:**
- Strategy failure (edge disappears)
- Technical bugs (code errors)
- Black swan events (extreme moves)
- Market regime changes (edge erosion)

✅ **How it protects you:**
- Limits losses to 15% (or your threshold)
- Forces manual review before continuing
- Prevents "revenge trading" psychology
- Saves capital for future opportunities

✅ **Configuration:**
```yaml
risk:
  circuit_breaker_enabled: true
  max_drawdown_pct: 0.15  # 15% max loss from peak
```

✅ **Recovery:**
- Investigate cause
- Fix issue
- Resume manually via Telegram or config
- Circuit breaker resets when balance exceeds peak

**The circuit breaker is your safety net. Don't disable it!** 🛡️
