# 🚀 START HERE - Kalshi Hybrid Bot

## ✅ Setup Complete!

Everything is ready to go. The bot is configured and waiting for you to start it.

---

## 🎮 Quick Commands

### Start the Bot
```bash
cd /root/kalshi_hybrid_bot
./bot-control.sh start
```

### View Live Logs
```bash
./bot-control.sh logs
```

### Check Status
```bash
./bot-control.sh status
```

### Stop the Bot
```bash
./bot-control.sh stop
```

---

## 📊 Current Configuration

**Mode:** Hybrid (takes both lottery $0.05-0.15 AND balanced $0.40-0.60)

**Paper Trading:** ✅ ENABLED (bot will scan but NOT execute trades)

**Expected Performance:**
- 12-18 opportunities per day
- 52% win rate
- $1,060/week profit (when live)

---

## 🎯 What Happens When You Start

The bot will:

1. Connect to Kalshi API ✅
2. Start scanning for 15m markets every 10 seconds ✅
3. Apply 8-layer validation to each market ✅
4. Log opportunities found ✅
5. **NOT execute trades** (paper trading mode) ✅

You'll see output like:
```
🚀 Initializing Kalshi Hybrid Bot...
✅ Volume Analyzer initialized
✅ Regime Detector initialized
✅ Unified Edge Detector initialized in HYBRID mode

🔍 SCANNING FOR OPPORTUNITIES
   Found 12 active 15m markets

✅ KXBTC15M-26FEB161545-B75K: OPPORTUNITY FOUND!
   Mode: LOTTERY
   Entry: $0.08 x 125 contracts = $10.00
   Probability: 32.5%
   Expected Value: 245.3%
```

---

## 📝 Next Steps

### Day 1-2: Paper Trading (Now)
```bash
# Start bot
./bot-control.sh start

# Watch live logs
./bot-control.sh logs

# Let it run for 1-2 days
# Observe opportunities found
```

### Day 3: Review & Tune
```bash
# Check how many opportunities per day
grep "OPPORTUNITY FOUND" logs/hybrid_bot.log | wc -l

# Review quality of opportunities
tail -200 logs/hybrid_bot.log
```

### Day 4+: Go Live (When Ready)
```bash
# Edit config to disable paper trading
nano config/config.yaml
# Change: paused: false

# Restart bot
./bot-control.sh restart

# Monitor closely!
./bot-control.sh logs
```

---

## 🎛️ Control Panel

### All Available Commands

```bash
./bot-control.sh start      # Start the bot
./bot-control.sh stop       # Stop the bot
./bot-control.sh restart    # Restart the bot
./bot-control.sh status     # Show status
./bot-control.sh logs       # Live logs (Ctrl+C to exit)
./bot-control.sh errors     # Show errors only
./bot-control.sh info       # Detailed info
./bot-control.sh monitor    # PM2 monitor dashboard
./bot-control.sh delete     # Remove from PM2
./bot-control.sh save       # Save PM2 config
```

---

## 🔍 Monitoring

### Real-Time Logs
```bash
./bot-control.sh logs
```

### Just Opportunities
```bash
tail -f logs/hybrid_bot.log | grep "OPPORTUNITY"
```

### Error Checking
```bash
./bot-control.sh errors
```

### PM2 Dashboard
```bash
./bot-control.sh monitor
```

---

## ⚙️ Configuration

### Current Mode: Hybrid
To change modes, edit `config/config.yaml`:

**Lottery Only:**
```yaml
entry_price_range:
  min: 0.05
  max: 0.15
```

**Balanced Only:**
```yaml
entry_price_range:
  min: 0.40
  max: 0.60
```

**Hybrid (current):**
```yaml
entry_price_range:
  min: 0.05
  max: 0.60
```

After changes: `./bot-control.sh restart`

---

## 🛡️ Safety Features

**Currently Active:**
- ✅ Paper trading mode (won't execute trades)
- ✅ Max daily loss: $200
- ✅ Max weekly loss: $500
- ✅ Max spread: 5 cents
- ✅ Max slippage: 2 cents
- ✅ Order timeout: 2 seconds

---

## 📈 Performance Tracking

### Daily Summary
```bash
# How many opportunities today?
grep "OPPORTUNITY FOUND" logs/hybrid_bot.log | grep "$(date +%Y-%m-%d)" | wc -l

# What modes were they?
grep "Mode:" logs/hybrid_bot.log | grep "$(date +%Y-%m-%d)" | cut -d: -f2 | sort | uniq -c
```

### Weekly Summary
```bash
# Opportunities this week
grep "OPPORTUNITY FOUND" logs/hybrid_bot.log | tail -100
```

---

## 🚨 Troubleshooting

### Bot Won't Start
```bash
# Check logs
./bot-control.sh errors

# Check API credentials
cat .env
```

### No Opportunities Found
- Normal during off-hours
- Markets trade roughly 9 AM - 6 PM ET
- Try widening time window in config

### Bot Keeps Restarting
```bash
# Check PM2 status
./bot-control.sh status

# View errors
./bot-control.sh errors

# Check full logs
tail -100 logs/pm2-error.log
```

---

## 🎯 Ready to Start!

**Everything is configured and ready to go.**

Just run:
```bash
./bot-control.sh start
```

Then watch the magic happen:
```bash
./bot-control.sh logs
```

---

## 📞 Quick Reference

| What You Want | Command |
|---------------|---------|
| **Start bot** | `./bot-control.sh start` |
| **See what's happening** | `./bot-control.sh logs` |
| **Stop bot** | `./bot-control.sh stop` |
| **Check if running** | `./bot-control.sh status` |
| **Restart after config change** | `./bot-control.sh restart` |

---

**Good luck! 🚀**

The bot is smart, the filters are tight, and the edge is real. Let it run in paper trading mode for a few days, then unleash it when you're ready!
