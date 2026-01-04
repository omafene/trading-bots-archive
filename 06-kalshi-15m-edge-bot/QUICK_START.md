# Quick Start: Advanced Edge Detection System

## 🚀 Get Running in 5 Minutes

### Step 1: Verify Installation (30 seconds)
```bash
# Test all modules load correctly
python3 -c "from edge_bot import EdgeDetectionBot; print('✅ Ready to run!')"
```

Expected output:
```
✅ Volatility analyzer initialized (window=15m)
✅ Orderbook analyzer initialized
✅ Basis monitor initialized
✅ Advanced multi-factor edge detection
✅ Ready to run!
```

---

### Step 2: Set Observation Mode (30 seconds)
```bash
# Edit config to watch without trading
nano config_15m.yaml
```

Change this line:
```yaml
bot:
  paused: true  # Set to true for observation mode
```

---

### Step 3: Run the Bot (1 minute)
```bash
python edge_bot.py
```

You should see:
```
🚀 Initializing ADVANCED multi-factor edge detection...
✅ Volatility analyzer initialized (window=15m)
✅ Orderbook analyzer initialized
✅ Basis monitor initialized
✅ Advanced multi-factor edge detection enabled
✅ Telegram alerts enabled
==========================================
🚀 15-MINUTE EDGE DETECTION BOT STARTED
==========================================
🚀 Starting high-frequency run loop...
```

---

### Step 4: Watch for Signals (2-4 hours)

Look for log output like this:

```
🔍 SCAN CYCLE #5
==========================================
📊 Found 14 active 15-min markets

🎯 KXBTC15M-24FEB05-2130-B96000 | YES @ 42% | Edge: 18.5% | ROI: 44.0%
Signal Strength: 74/100

Signal Breakdown:
  📊 Base Prob: 56.0%
  💨 Vol Signal: fade (1.52x) → -8.0%
  📈 Microstructure → YES: +12.0%, NO: -5.0%
  ⚡ Stat Arb → +15.0%
  ⏱️ Time Value → 0.0%

Momentum: up +1.8% | Trend: 0.62 | Volatility: 1.52x

⏸️ Bot is PAUSED - observation mode
```

**What to Check:**
- ✅ Are signals triggering? (vol, micro, stat arb)
- ✅ Do edge percentages look reasonable? (10-25%)
- ✅ Are signal strengths diverse? (50-85 range)
- ✅ Is the bot finding 3-8 opportunities per scan?

---

### Step 5: Enable Live Trading (when ready)
```bash
nano config_15m.yaml
```

Change:
```yaml
bot:
  paused: false  # Enable live trading

capital:
  total_capital: 500  # Increase from $10 to $500+
```

Restart bot:
```bash
python edge_bot.py
```

---

## 📊 What to Expect

### First Hour (Warm-up Period):
- Bot builds price history (needs 15+ minutes)
- Few or no signals initially
- Once history built → 3-8 signals per scan

### After 2-4 Hours (Steady State):
- 5-12 trades per hour (if unpaused)
- Average edge: 12-18%
- Signal strength: 55-75 typical, 80+ on great opportunities
- Win rate: Track this manually to validate model

---

## 🎯 Key Metrics to Monitor

### In the Logs:
```
🎯 Edge → YES: 18.5%, NO: 4.2%
Signal Strength: 74/100

Signal Breakdown:
  Vol adjustment: -8.0% (market underpricing volatility)
  Micro adjustment: +12.0% (strong order flow imbalance)
  Stat arb adjustment: +15.0% (lag opportunity detected)
```

### What Good Signals Look Like:
- ✅ **Edge: 12-25%** (sweet spot)
- ✅ **Signal Strength: 60-85** (high quality)
- ✅ **Multiple factors aligned** (vol + micro + stat arb)
- ✅ **Stat arb component present** (lag detection = best edge)

### What to Avoid:
- ❌ Edge < 8% (too thin after fees)
- ❌ Signal strength < 50 (weak signal)
- ❌ Only momentum contributing (no multi-factor edge)
- ❌ Extreme edges > 30% (likely data error)

---

## 🔧 Configuration Tweaks

### If Too Many Signals (>15 per scan):
```yaml
strategy:
  min_edge_percent: 12  # Increase from 10
  min_signal_strength: 60  # Increase from 50
```

### If Too Few Signals (<3 per scan):
```yaml
strategy:
  min_edge_percent: 8  # Decrease from 10
  min_signal_strength: 45  # Decrease from 50
```

### If Want More Aggressive:
```yaml
strategy:
  min_edge_percent: 8
  min_expected_probability: 0.55  # Lower from 0.60
  max_concurrent_trades: 4  # Up from 2
```

---

## 🐛 Troubleshooting

### Issue: "No Spot Price for BTC"
**Solution:** Wait 2-3 minutes for spot feed to initialize

### Issue: "Building History for BTC"
**Solution:** Normal! Needs 15 minutes of data before trading

### Issue: "No significant edges found"
**Possible causes:**
1. Markets are fairly priced (normal)
2. Too restrictive thresholds (lower min_edge)
3. Low volatility period (wait for market movement)

### Issue: Bot crashes on start
**Solution:**
```bash
# Check all imports work
python3 -c "from edge_bot import EdgeDetectionBot"

# If error, check:
pip3 install -r requirements.txt
```

---

## 📱 Telegram Commands

Once bot is running:
```
/status    - Check bot state, balance, positions
/pause     - Stop trading (observation mode)
/resume    - Start trading
/positions - List active trades
/balance   - Check account balance
/stop      - Shutdown bot
```

---

## 📈 Performance Tracking

### Manual Log Analysis:
```bash
# Count trades
grep "FILL CONFIRMED" logs/edge_bot.log | wc -l

# Check edges detected
grep "Edge:" logs/edge_bot.log | head -20

# See signal breakdowns
grep "Signal Breakdown" logs/edge_bot.log -A 5 | head -30
```

---

## 🎯 Success Criteria (After 1 Week)

### Good Performance:
- ✅ Win rate: 58-65%
- ✅ Average edge captured: 8-15%
- ✅ Sharpe ratio: 1.3-2.0
- ✅ Max drawdown: <15%
- ✅ Trades/day: 10-20

### Excellent Performance:
- ✅ Win rate: 65-70%
- ✅ Average edge captured: 12-20%
- ✅ Sharpe ratio: 2.0-2.5+
- ✅ Max drawdown: <10%
- ✅ Trades/day: 15-25

### Red Flags:
- ❌ Win rate: <55% (strategy not working)
- ❌ Max drawdown: >20% (risk management issue)
- ❌ Average edge: <5% (thresholds too loose)
- ❌ Trades/day: <5 (too conservative)

---

## 🚦 Traffic Light System

### 🟢 GREEN (Safe to Scale Up):
- Win rate >60%
- Sharpe >1.5
- 1 week profitable
- Drawdown <12%

### 🟡 YELLOW (Monitor Closely):
- Win rate 55-60%
- Sharpe 1.0-1.5
- Small profit/breakeven
- Drawdown 12-18%

### 🔴 RED (Stop Trading):
- Win rate <55%
- Sharpe <1.0
- Losing money
- Drawdown >20%

---

## 📞 Next Steps

1. **Today:** Run in observation mode for 2-4 hours
2. **Tomorrow:** Enable live trading with $50-100 (test capital)
3. **This Week:** Paper trade with full capital ($500+)
4. **Next Week:** Review performance, adjust thresholds
5. **Week 3+:** Scale up gradually if profitable

---

## 📚 Documentation

- `ADVANCED_EDGE_SYSTEM.md` - Complete technical explanation
- `IMPLEMENTATION_SUMMARY.md` - What was built and why
- `BUGFIXES.md` - Critical bugs that were fixed
- `FIXES_SUMMARY.md` - Security and bug fix overview

---

## ⚡ TL;DR

```bash
# 1. Test imports
python3 -c "from edge_bot import EdgeDetectionBot; print('✅')"

# 2. Set observation mode (edit config: paused: true)
nano config_15m.yaml

# 3. Run bot
python edge_bot.py

# 4. Watch logs for 2-4 hours

# 5. Enable trading (edit config: paused: false, capital: 500)

# 6. Monitor win rate, Sharpe ratio, drawdown

# 7. Scale up if profitable (10% per week)
```

**You're ready to go! 🚀**
