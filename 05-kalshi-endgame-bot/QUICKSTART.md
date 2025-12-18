# 🚀 QUICK START GUIDE

## Get Running in 10 Minutes

### Step 1: Install Python Dependencies (2 min)
```bash
cd kalshi_bot
pip install -r requirements.txt
```

### Step 2: Configure Bot (3 min)
```bash
nano config.yaml
```

**Change these lines:**
```yaml
api:
  use_demo: true  # Keep true for testing
  email: "your_email@example.com"  # Your Kalshi email
  password: "your_password"          # Your Kalshi password

capital:
  total_capital: 20000  # Your capital amount
```

Save and exit (Ctrl+X, Y, Enter)

### Step 3: Create Kalshi Demo Account (3 min)
1. Go to: https://demo.kalshi.com
2. Sign up with the email you put in config
3. They'll give you free demo money

### Step 4: Run Bot (2 min)
```bash
python endgame_bot.py
```

That's it! Bot is now running.

---

## What You'll See

**Immediately:**
```
============================================================
KALSHI ENDGAME SWEEP BOT STARTING
============================================================
Successfully authenticated as your_email@example.com
Initial Balance: $1,000,000.00
Starting main loop (checking every 300s)...
```

**Every 5 minutes:**
```
Step 1: Updating existing positions...
Step 2: Portfolio Status
  Balance: $1,000,000.00
  Deployed: $0.00
  Utilization: 0.0%
  Open Positions: 0/12
Step 3: Scanning for opportunities...
Found 15 opportunities
Step 4: Evaluating trades...
✓ Executed 3 new positions
```

---

## Stop the Bot

Press: `Ctrl+C`

Bot will save positions and exit gracefully.

---

## Check What Happened

**View logs:**
```bash
tail -f logs/kalshi_bot.log
```

**View positions:**
```bash
cat data/positions.json
```

**See performance:**
Bot prints summary every iteration showing:
- Open positions
- Total P&L
- Win rate
- Average return

---

## After Testing (Moving to Real Money)

### 1. Switch to Production
```yaml
api:
  use_demo: false  # Now using real money!
```

### 2. Start Small
```yaml
capital:
  total_capital: 3000  # Start with $2-3K
```

### 3. Create Real Kalshi Account
1. Go to: https://kalshi.com
2. Complete KYC (ID verification)
3. Deposit funds via ACH

### 4. Monitor Closely
Check bot 2-3 times daily for first week.

### 5. Scale Gradually
Add 20% more capital each week if profitable.

---

## Key Config Settings

### Conservative (Recommended Start)
```yaml
strategy:
  min_probability: 0.97  # Very high confidence
  
capital:
  max_position_size: 300  # Small positions
  max_open_positions: 5   # Few positions

risk:
  whitelist_categories:
    - "ECON"  # Only economics (most reliable)
```

### Moderate (After 1 Month)
```yaml
strategy:
  min_probability: 0.96  # High confidence
  
capital:
  max_position_size: 1000
  max_open_positions: 8

risk:
  whitelist_categories:
    - "ECON"
    - "POLITICS"  # Add politics
```

### Aggressive (After 3+ Months)
```yaml
strategy:
  min_probability: 0.95  # Lower threshold
  
capital:
  max_position_size: 2000
  max_open_positions: 12

risk:
  whitelist_categories:
    - "ECON"
    - "POLITICS"
    - "WEATHER"
    - "SPORTS"
```

---

## Expected Results (Demo Testing)

**Week 1:**
- Bot should find 5-20 opportunities daily
- Should open 2-5 positions
- Win rate should be 95%+

**Week 2:**
- Positions start closing (markets resolve)
- Should see mix of wins and occasional loss
- Total should be positive

**If something's wrong:**
- Zero opportunities? → Lower min_probability to 0.94
- Too many positions? → Increase min_probability to 0.97
- Losing too much? → Tighten category whitelist

---

## Common First-Time Issues

**"Authentication failed"**
- Check email/password in config.yaml
- Make sure use_demo matches account type

**"No opportunities found"**
- Normal if markets are thin
- Try lowering min_probability temporarily
- Check Kalshi website for 95%+ markets

**Bot seems stuck**
- It checks every 5 minutes (be patient)
- Check logs: `tail -f logs/kalshi_bot.log`

---

## Next Steps

1. ✅ Run in demo for 2 weeks minimum
2. ✅ Verify win rate matches probability (95-99%)
3. ✅ Switch to production with $2-3K
4. ✅ Monitor closely for 1 month
5. ✅ Scale to full capital gradually

---

## Pro Tips

💡 **Start conservative, scale gradually**
💡 **Check bot daily for first 2 weeks**
💡 **Keep logs for debugging**
💡 **Backup data/ folder regularly**
💡 **Read full README.md for details**

Questions? Check README.md for comprehensive guide.

Good luck! 🎯
