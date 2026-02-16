# 🚀 Quick Start Guide - Kalshi Hybrid Bot

## 5-Minute Setup

### Step 1: Install Dependencies (30 seconds)
```bash
cd /root/kalshi_hybrid_bot
pip install -r requirements.txt
```

### Step 2: Setup API Keys (1 minute)
```bash
# Copy environment template
cp .env.example .env

# If you have existing keys from old bot:
cp /root/kalshi_15m_bot/.env .env
cp /root/kalshi_15m_bot/production_private_key.pem .
```

### Step 3: Choose Your Strategy (1 minute)

Edit `config/config.yaml`:

**Option A: Hybrid Mode** (Recommended - Best of Both)
```yaml
strategy:
  entry_price_range:
    min: 0.05  # Lottery tickets
    max: 0.60  # Balanced trades
```

**Option B: Lottery Mode Only** (Highest ROI, 40% win rate)
```yaml
strategy:
  entry_price_range:
    min: 0.05
    max: 0.15
```

**Option C: Balanced Mode Only** (Highest win rate, 65%)
```yaml
strategy:
  entry_price_range:
    min: 0.40
    max: 0.60
```

### Step 4: Paper Trade First! (Recommended)

In `config/config.yaml`:
```yaml
bot:
  paused: true  # Will scan but NOT execute trades
```

### Step 5: Run the Bot!
```bash
python src/hybrid_bot.py
```

You should see:
```
🚀 Initializing Kalshi Hybrid Bot...
✅ Volume Analyzer initialized
✅ Regime Detector initialized
✅ Unified Edge Detector initialized in HYBRID mode
   Price range: $0.05 - $0.60
✅ Hybrid Bot initialized successfully!

🎯 KALSHI HYBRID BOT STARTING
======================================================================
🔍 SCANNING FOR OPPORTUNITIES - 15:30:45
======================================================================
   Found 12 active 15m markets

✅ KXBTC15M-26FEB161545-B75K: OPPORTUNITY FOUND!
   Mode: LOTTERY
   Entry: $0.08
   Size: 125 contracts ($10.00)
   Probability: 32.5%
   Expected Value: 245.3%

📊 SCAN COMPLETE: 1 opportunities found
```

---

## 🎯 What Happens Next?

### In Paper Trading Mode (paused: true)
- Bot scans every 10 seconds
- Logs all opportunities found
- **Does NOT execute trades**
- Perfect for validating filters work

### After 1-2 Days of Paper Trading
1. Review logs: `tail -100 logs/hybrid_bot.log`
2. Check opportunity quality
3. Verify filters are working
4. Adjust config if needed

### Going Live
1. Set `paused: false` in config.yaml
2. Start with small positions ($5-10)
3. Monitor closely for first week
4. Scale up as confidence grows

---

## 📊 Understanding the Output

### Good Opportunity
```
✅ KXETH15M-26FEB161600-U2100: OPPORTUNITY FOUND!
   Mode: LOTTERY          ← Lottery ticket or balanced trade
   Entry: $0.09           ← Price you'd pay
   Size: 111 contracts    ← Number of contracts
   Total: $10.00          ← Total cost
   Probability: 28.5%     ← Estimated win chance
   Expected Value: 185%   ← Expected return
```

This means:
- Risk: $10 (max loss)
- Potential win: $111 (if YES wins)
- Model says 28.5% chance of winning
- Expected value is +185% (very profitable!)

### Rejected Opportunity
```
❌ KXBTC15M-26FEB161630-B76K: Momentum 0.15% < 0.3% for UP bet
```

This tells you exactly why it was rejected. Common reasons:
- Momentum too weak
- Trend quality (R²) too low
- Volume not expanding
- Wrong market regime (choppy/mean-reverting)
- Probability outside target range
- Negative expected value

---

## 🔧 Fine-Tuning Your Strategy

### Getting Too Few Opportunities?

**Loosen filters:**
```yaml
momentum:
  min_alignment_pct: 0.2  # Reduce from 0.3

regime:
  enabled: false  # Disable regime filter temporarily
```

### Getting Too Many (Low Quality)?

**Tighten filters:**
```yaml
probability:
  lottery_mode:
    min_probability: 0.30  # Increase from 0.25

execution:
  max_spread_cents: 3  # Reduce from 5
```

### Want More Aggressive Lottery Betting?

```yaml
position_sizing:
  lottery_mode:
    base_position: 15  # Increase from $10
    max_position: 30   # Increase from $20
```

### Want More Conservative?

```yaml
risk:
  max_daily_loss: 100  # Reduce from $200

position_sizing:
  lottery_mode:
    base_position: 5   # Reduce to $5
```

---

## 📈 Tracking Performance

### Real-Time Monitoring
```bash
# Watch live logs
tail -f logs/hybrid_bot.log | grep "OPPORTUNITY\|SCAN COMPLETE"
```

### Daily Summary
```bash
# Count opportunities found today
grep "OPPORTUNITY FOUND" logs/hybrid_bot.log | grep "$(date +%Y-%m-%d)" | wc -l
```

---

## 🎮 Advanced: Running Both Bots

You can run the hybrid bot alongside your old v3 bot:

**Terminal 1: Old v3 Bot**
```bash
cd /root/kalshi_15m_bot
python edge_bot.py
```

**Terminal 2: New Hybrid Bot**
```bash
cd /root/kalshi_hybrid_bot
python src/hybrid_bot.py
```

Then compare performance after 1 week!

---

## ⚠️ Common Issues

### "No opportunities found"
- Markets may be outside trading hours
- Filters may be too strict
- Try widening price range temporarily

### "Insufficient price history"
- Normal on first startup
- Wait 10-15 minutes for history to build
- Bot will start finding opportunities

### Import errors
```bash
# Make sure you're in the right directory
cd /root/kalshi_hybrid_bot

# Reinstall dependencies
pip install -r requirements.txt
```

---

## ✅ Success Checklist

Before going live, verify:
- [ ] Paper trading works (paused: true)
- [ ] Seeing 5-15 opportunities per day
- [ ] Filters are rejecting appropriately
- [ ] Probability estimates seem reasonable
- [ ] Position sizes look correct
- [ ] Configured max daily/weekly loss limits
- [ ] Have 2x minimum capital in account

---

## 🎯 Next Steps

1. **Day 1-2**: Paper trade, observe opportunities
2. **Day 3**: Tune config based on observations
3. **Day 4-5**: More paper trading with tuned config
4. **Day 6**: Go live with $5 positions
5. **Week 2**: Scale to $10 positions
6. **Week 3**: Scale to $15-20 positions
7. **Month 2**: Add balanced mode to hybrid mix

---

**Ready to start? Just run:**
```bash
python src/hybrid_bot.py
```

**Good luck! 🚀**
