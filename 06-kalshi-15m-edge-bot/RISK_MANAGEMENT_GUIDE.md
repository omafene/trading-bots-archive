# Risk Management System

Your bot now has **3 layers of risk protection**:

1. **Kelly Criterion Position Sizing** - Optimize bet sizes for maximum growth
2. **Real Stop-Loss** - Auto-exit on adverse spot price moves
3. **Max Drawdown Circuit Breaker** - Halt trading on excessive losses

---

## 1. Kelly Criterion Position Sizing

### What It Does

Automatically calculates the **optimal position size** for each trade based on:
- Your edge (expected probability vs market price)
- Your win probability
- Your current balance

### The Formula

```
Kelly Fraction = (b × p - q) / b

Where:
  b = odds (profit/stake)
  p = win probability
  q = loss probability (1-p)

Then: Position Size = Balance × Kelly Fraction × 0.25 (Quarter-Kelly)
```

### Example

```
Market: "BTC Above 96K" = 40 cents
Your model: 70% win probability
Balance: $500

Calculation:
  Odds (b) = (1.00 - 0.40) / 0.40 = 1.5
  p = 0.70, q = 0.30
  Kelly = (1.5 × 0.70 - 0.30) / 1.5 = 0.50 (50% of balance!)

Quarter-Kelly = 0.50 × 0.25 = 0.125 (12.5%)
Position Size = $500 × 0.125 = $62.50
```

### Why Quarter-Kelly?

**Full Kelly (1.0x):**
- Maximum growth rate
- High variance (big swings)
- Risk of ruin if edge miscalculated

**Half Kelly (0.5x):**
- 75% of full Kelly growth
- 50% of full Kelly variance
- More stable

**Quarter-Kelly (0.25x):** ✅ **Recommended**
- 50% of full Kelly growth
- 25% of full Kelly variance
- Very stable, low risk of ruin
- Protects against edge estimation errors

### Configuration

```yaml
# config_15m.yaml
risk:
  kelly_multiplier: 0.25  # Quarter-Kelly (recommended)
  min_position_size: 1.0  # Minimum $1 per trade

strategy:
  max_position_percent: 0.10  # Cap at 10% per trade (safety limit)
```

### Position Sizing Hierarchy

```
1. Calculate Kelly size
2. Apply Quarter-Kelly multiplier (0.25x)
3. Cap at max_position_percent (10%)
4. Floor at min_position_size ($1)
```

**Example Flow:**
```
Kelly says: Bet $200 (40% of $500)
× 0.25 Quarter-Kelly = $50
Check cap: $500 × 10% = $50 (OK)
Check floor: $50 > $1 (OK)
Final: Bet $50
```

### When Kelly Returns 0

If `kelly_fraction ≤ 0`, the bet has **negative expected value**:
```
Position size = $0 → Trade skipped

Log: "⚠️ Insufficient balance or negative Kelly for KXBTC..."
```

This is a **safety feature** - Kelly won't let you bet on negative-EV trades.

---

## 2. Real Stop-Loss (Auto-Exit)

### What It Does

**Automatically exits positions** when spot price moves significantly against your bet.

This is a **REAL stop-loss**, not just an alert. The bot will:
1. Monitor spot price every 2 seconds
2. Calculate stop-loss trigger levels
3. Auto-exit via market order when triggered
4. Send Telegram notification

### How It Works

#### For "ABOVE" Markets:

**YES Position (betting price goes above threshold):**
```
Strike: 95K
Stop-loss: 5%
Trigger: 95K × (1 - 0.05) = 90.25K

If spot drops to 90.25K → Exit immediately
```

**NO Position (betting price stays below threshold):**
```
Strike: 95K
Stop-loss: 5%
Trigger: 95K × (1 + 0.05) = 99.75K

If spot rises to 99.75K → Exit immediately
```

#### For "BELOW" Markets:

**YES Position (betting price goes below threshold):**
```
Strike: 90K
Stop-loss: 5%
Trigger: 90K × (1 + 0.05) = 94.5K

If spot rises to 94.5K → Exit immediately
```

**NO Position (betting price stays above threshold):**
```
Strike: 90K
Stop-loss: 5%
Trigger: 90K × (1 - 0.05) = 85.5K

If spot drops to 85.5K → Exit immediately
```

### Configuration

```yaml
# config_15m.yaml
strategy:
  stop_loss_enabled: true  # Enable auto-exit
  stop_loss_pct: 0.05      # 5% threshold
```

**Recommended Thresholds:**

| Market Volatility | Stop-Loss % | When to Use |
|-------------------|-------------|-------------|
| **Low vol** | 3-4% | Stable market, tight stops |
| **Normal vol** | 5% | **Default (recommended)** |
| **High vol** | 7-8% | Crypto during volatility spike |
| **Extreme vol** | 10%+ | Black swan events (not recommended) |

### Example Trade

```
12:00:00 - Enter YES on "BTC Above 95K" @ 40 cents
           Stop-loss trigger: 90.25K

12:02:15 - BTC spot: 94.5K (still above stop)
12:04:30 - BTC spot: 92.0K (still above stop)
12:06:45 - BTC spot: 90.0K (BELOW stop!)

🛑 STOP-LOSS TRIGGERED
   Exit @ 15 cents (current bid)
   Loss: 62.5% on position

12:07:00 - BTC spot: 88.5K (would have been total loss)
           ✅ Stop-loss saved you from 100% loss!
```

### What Happens When Triggered

1. **Log Entry:**
```
🛑 STOP-LOSS TRIGGERED: KXBTC15M-05FEB-1430-A95000
   Reason: Spot $90000 < Stop $90250
   Side: YES | Market: ABOVE 95000
```

2. **Auto-Exit:**
- Fetches current orderbook
- Gets bid price
- Submits market order (IOC)
- Position closed

3. **Telegram Alert:**
```
🛑 STOP-LOSS EXECUTED
──────────────────
Market: KXBTC15M-05FEB-1430-A95000
Side: YES
Entry: $0.40
Exit: $0.15
Loss: 62.5%

Trigger: Spot $90000 < Stop $90250
Spot: $90,000
```

### Monitoring

Stop-loss checks run **every 2 seconds** (same as take-profit checks).

In logs:
```
💼 PORTFOLIO STATUS:
   Cash: $450.00
   Active Positions: 2

Position 1: KXBTC15M... (YES)
  Entry: $0.40 | Current: $0.35 | ROI: -12.5%
  Stop-loss: $90,250 | Current Spot: $92,500 ✅ Safe

Position 2: KXETH15M... (NO)
  Entry: $0.60 | Current: $0.55 | ROI: -8.3%
  Stop-loss: $3,150 | Current Spot: $3,080 ✅ Safe
```

---

## 3. Max Drawdown Circuit Breaker

(See CIRCUIT_BREAKER_GUIDE.md for full documentation)

**Quick Summary:**
- Tracks peak balance
- Calculates drawdown from peak
- Halts trading if drawdown > 15% (configurable)
- Requires manual resume after review

```yaml
risk:
  circuit_breaker_enabled: true
  max_drawdown_pct: 0.15  # 15% threshold
```

---

## How They Work Together

### Example Trading Session

```
Starting Balance: $500
Peak: $500

Trade 1: Kelly says bet $25
  - Enter: $25 position
  - Stop-loss: 5% threshold
  - Win: +$25 → Balance: $525 → New peak!

Trade 2: Kelly says bet $26 (based on $525)
  - Enter: $26 position
  - Spot moves against you
  - Stop-loss triggers → Exit at -$13
  - Balance: $512
  - Drawdown: ($525 - $512) / $525 = 2.5% ✅ OK

Trade 3: Kelly says bet $25
  - Enter: $25 position
  - Win: +$25 → Balance: $537 → New peak!

Trades 4-8: Series of losses
  - Stop-losses trigger, limiting each loss
  - Balance drops to $457
  - Drawdown: ($537 - $457) / $537 = 14.9% ⚠️ Close!

Trade 9: Another loss
  - Balance: $445
  - Drawdown: ($537 - $445) / $537 = 17.1%

🛑 CIRCUIT BREAKER TRIGGERED
   Trading halted
   Manual review required
```

**What Protected You:**
1. **Kelly sizing** - Never overbet, positions scaled down as balance dropped
2. **Stop-losses** - Each loss limited to ~5-8% of position (not 100%)
3. **Circuit breaker** - Stopped trading before catastrophic losses

**Without These Protections:**
- Fixed sizing → Would keep betting same amounts as balance dropped
- No stop-losses → Could lose 100% on bad positions
- No circuit breaker → Could blow entire account

---

## Configuration Summary

```yaml
# config_15m.yaml

capital:
  total_capital: 500  # Your starting capital

strategy:
  max_position_percent: 0.10  # Max 10% per trade (Kelly cap)
  max_concurrent_trades: 4    # Max 4 open positions

risk:
  # Kelly Sizing
  kelly_multiplier: 0.25      # Quarter-Kelly (recommended)
  min_position_size: 1.0      # Min $1 per trade

  # Stop-Loss
  stop_loss_enabled: true     # Enable auto-exit
  stop_loss_pct: 0.05         # 5% threshold

  # Circuit Breaker
  circuit_breaker_enabled: true
  max_drawdown_pct: 0.15      # 15% max drawdown
```

---

## Best Practices

### 1. Don't Touch Kelly Multiplier

0.25 (Quarter-Kelly) is optimal for most scenarios. Only increase if:
- ✅ You have 100+ trades of data proving your edge
- ✅ Win rate consistently > 65%
- ✅ You can tolerate higher variance

**Never use Full Kelly (1.0)** - High risk of ruin.

### 2. Adjust Stop-Loss Based on Market

```yaml
# Normal markets
stop_loss_pct: 0.05  # 5%

# High volatility (BTC +/- 5% daily)
stop_loss_pct: 0.07  # 7%

# Extreme volatility (black swan event)
stop_loss_pct: 0.10  # 10%
```

### 3. Circuit Breaker is Non-Negotiable

**Never disable it.** If 15% seems too strict:

```yaml
# Increase threshold instead
max_drawdown_pct: 0.20  # 20% (aggressive)
```

But **never go above 25%**.

### 4. Monitor Stop-Loss Frequency

If stop-losses trigger on >50% of trades:
- ❌ Your edge model is broken
- ❌ Volatility too high for your thresholds
- ❌ You're entering at bad times

**Action:** Fix edge model or increase stop-loss threshold.

### 5. Track Kelly vs Actual Sizes

```bash
# Check if Kelly sizing is working
grep "Position size for" logs/edge_bot.log | tail -20
```

Expected output:
```
💰 Position size for KXBTC...: $25.00 (Kelly-based, 5.0% of balance)
💰 Position size for KXETH...: $30.00 (Kelly-based, 6.0% of balance)
```

Sizes should vary based on:
- Edge strength (larger edge = larger bet)
- Win probability (higher prob = larger bet)
- Current balance (scales with account)

---

## FAQ

### Q: Can I use Full Kelly instead of Quarter-Kelly?
**A:** Technically yes, but **strongly discouraged**. Full Kelly has 4x the variance of Quarter-Kelly. You could lose 30-40% in a drawdown even with positive EV.

### Q: What if Kelly says bet $0?
**A:** Trade is skipped. This means the edge is negative or too small. This is a **good thing** - Kelly protects you from bad bets.

### Q: Can I disable stop-losses temporarily?
**A:** Yes: `stop_loss_enabled: false`. But **not recommended**. Only do this if:
- Testing in paper trading mode
- You have a very strong edge (>20%) and want to ride it out

### Q: Do stop-losses work on UP/DOWN markets?
**A:** Partially. Stop-losses work best on ABOVE/BELOW markets (threshold-based). For UP/DOWN markets, the bot falls back to simpler logic since there's no clear strike price.

### Q: What happens if stop-loss and take-profit both trigger?
**A:** Whichever checks first wins. Both run every 2 seconds, so realistically whichever condition is met first will execute.

### Q: Can I set different stop-losses per trade?
**A:** Currently no (global setting). You'd need to modify `position_manager_15m.py` to add per-position stop-loss overrides.

---

## Summary

✅ **Kelly Sizing:**
- Optimal bet sizes based on edge
- Scales with balance
- Protects against overbet
- Quarter-Kelly = safe default

✅ **Real Stop-Loss:**
- Auto-exit on adverse moves
- 5% threshold (default)
- Monitors every 2 seconds
- Limits losses per trade

✅ **Circuit Breaker:**
- Halts on 15% drawdown
- Protects from catastrophic loss
- Requires manual review
- Non-negotiable safety net

**Together, these form a robust risk management system that protects your capital while maximizing growth.** 🛡️
