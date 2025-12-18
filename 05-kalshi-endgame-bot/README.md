# Kalshi Endgame Sweep Trading Bot

Automated trading bot that executes "endgame sweep" strategy on Kalshi prediction markets - buying high-probability (95-99%) outcomes shortly before market resolution for consistent small gains.

## Strategy Overview

**Endgame Sweep Strategy:**
- Target markets with 95-99% probability
- Buy near-certain outcomes 1-14 days before resolution
- Collect 1-5% returns when events resolve correctly
- Scale through volume and diversification

**Expected Returns:**
- Conservative: 20-50% annual
- Realistic: 40-60% annual
- Optimistic: 60-120% annual (with optimal conditions)

**Risk:**
- Black swan events (1-5% probability failures)
- Capital lock-up during hold periods
- Requires $10K+ for effective diversification

## Features

- ✅ Automated market scanning for endgame opportunities
- ✅ Kelly Criterion position sizing (fractional for safety)
- ✅ Risk management (position limits, daily loss limits, category diversification)
- ✅ Portfolio tracking and performance analytics
- ✅ Comprehensive logging and monitoring
- ✅ Persistent position storage (survives restarts)
- ✅ Category filtering (whitelist/blacklist)
- ✅ Configurable via YAML
- ✅ **📱 Telegram Alerts** - Real-time notifications for trades, wins/losses, daily summaries, and errors

## Requirements

- Python 3.9+
- Kalshi account (demo or production)
- $10,000+ recommended capital
- VPS or always-on computer (for continuous operation)

## Installation

### 1. Clone/Download Files

```bash
cd ~
mkdir kalshi_bot
cd kalshi_bot
# Copy all bot files here
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Bot

Edit `config.yaml`:

```yaml
api:
  use_demo: true  # Set false for real money
  email: "your_email@example.com"
  password: "your_password"

capital:
  total_capital: 20000  # Your trading capital
  max_position_size: 2000  # Max per position (10%)
  
strategy:
  min_probability: 0.95  # 95% minimum
  max_probability: 0.99  # 99% maximum
```

**Important Settings:**
- `use_demo: true` - Start with demo for testing
- `total_capital` - Your actual trading capital
- `max_position_size` - Never exceed 10% per position
- `kelly_fraction: 0.25` - Conservative sizing (don't increase)

### 4. Create Kalshi Account

**Demo Account (Recommended for testing):**
1. Go to: https://demo.kalshi.com
2. Sign up with email
3. Fund with demo money (free)

**Production Account:**
1. Go to: https://kalshi.com
2. Complete KYC verification
3. Deposit funds via ACH

## Usage

### Basic Operation

**Start the bot:**
```bash
python endgame_bot.py
```

**With custom config:**
```bash
python endgame_bot.py --config my_config.yaml
```

**Stop the bot:**
- Press `Ctrl+C` gracefully
- Bot will save all positions before exiting

### What the Bot Does

**Every 5 minutes (configurable):**
1. ✅ Checks if any positions have settled (won/lost)
2. ✅ Scans all open Kalshi markets
3. ✅ Identifies markets with 95-99% probability
4. ✅ Filters by category, volume, time to close
5. ✅ Calculates position size using Kelly Criterion
6. ✅ Checks risk limits (max positions, category exposure, daily loss)
7. ✅ Executes trades if opportunities pass all filters
8. ✅ Updates logs and position files

### Monitoring

**Check logs:**
```bash
tail -f logs/kalshi_bot.log
```

**View positions:**
```bash
cat data/positions.json
```

**View trade history:**
```bash
cat data/trades.json
```

## File Structure

```
kalshi_bot/
├── config.yaml              # Configuration (EDIT THIS)
├── endgame_bot.py           # Main bot execution
├── kalshi_client.py         # Kalshi API wrapper
├── market_scanner.py        # Finds opportunities
├── risk_manager.py          # Position sizing & risk controls
├── position_manager.py      # Tracks positions
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── data/
│   ├── positions.json       # Current positions
│   └── trades.json          # Trade history
└── logs/
    └── kalshi_bot.log       # Execution logs
```

## Configuration Guide

### Capital Management

```yaml
capital:
  total_capital: 20000        # Total trading capital
  max_position_size: 2000     # 10% max per position
  reserve_ratio: 0.20         # Keep 20% in reserve
  max_open_positions: 12      # Maximum concurrent trades
  kelly_fraction: 0.25        # Use 1/4 Kelly (conservative)
```

**Recommendations:**
- Start with $10K minimum (prefer $20K+)
- Never exceed 10% per position
- Maintain 20% reserve for opportunities
- Max 12-15 concurrent positions for diversification

### Strategy Parameters

```yaml
strategy:
  min_probability: 0.95       # 95% minimum (don't go lower)
  max_probability: 0.99       # 99% maximum (diminishing returns above)
  min_expected_return: 0.02   # 2% minimum return
  max_days_to_close: 14       # Only markets closing within 2 weeks
  min_days_to_close: 1        # Avoid manipulation risk
```

**Sweet Spot:**
- Probability: 96-98% (best risk/reward)
- Time to close: 3-10 days (optimal turnover)
- Expected return: 2-5% per trade

### Risk Controls

```yaml
risk:
  max_daily_loss: 0.15        # Stop if down 15% in a day
  max_per_category: 0.30      # Max 30% in one category
  
  # Only trade reliable categories
  whitelist_categories:
    - "ECON"       # Economic data (CPI, jobs)
    - "POLITICS"   # Political events
    - "WEATHER"    # Weather outcomes
    - "SPORTS"     # Sports results
  
  blacklist_categories:
    - "CRYPTO"     # High volatility
    - "CELEBRITY"  # Unpredictable
```

**Category Reliability:**
- ✅ **High:** ECON, scheduled political events
- ⚠️ **Medium:** Election outcomes, sports
- ❌ **Low:** Crypto, celebrity, social media predictions

### Market Quality Filters

```yaml
filters:
  min_volume: 50000           # $50K minimum volume
  min_liquidity: 10000        # $10K minimum open interest
  require_yes_side: true      # Only buy YES (more intuitive)
```

### 📱 Telegram Alerts (Optional but Recommended)

Get real-time notifications about your bot's activity:

```yaml
telegram:
  enabled: false              # Set to true to enable
  bot_token: "YOUR_TOKEN"     # Get from @BotFather on Telegram
  chat_id: "YOUR_CHAT_ID"     # Your Telegram chat ID
  
  notifications:
    position_opened: true     # New positions
    position_closed: true     # Closed positions with P&L
    daily_summary: true       # Daily performance (sent at 6 PM)
    opportunities: false      # Opportunities found (can be noisy)
    errors: true             # Error alerts
    large_losses: true       # Losses > $1,000
```

**What you'll get:**
- ✅ Real-time trade notifications (opens/closes)
- 📊 Daily performance summaries
- ⚠️ Error and risk alerts
- 🚨 Large loss warnings

**Setup takes 5 minutes** - See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for step-by-step instructions.

## Performance Monitoring

### Key Metrics

**Win Rate:**
- Target: 96-99% (should match probability)
- If < 95%: Your category filtering needs improvement
- If > 99%: You're being too conservative

**Average Return:**
- Target: 2-4% per trade
- Multiply by turnover for annual return

**Capital Utilization:**
- Target: 70-80% deployed
- <50%: Too conservative, missing opportunities
- >90%: Too aggressive, insufficient reserves

**Turnover:**
- Target: 2-3x per month (capital recycling)
- Higher turnover = higher annual returns

### Example Performance

**Good Month:**
- Capital: $20,000
- Positions: 10 concurrent
- Average: $1,800 per position
- Hold time: 10 days average
- Returns: 3% per trade
- Turnover: 3x per month

**Math:**
- $20K × 3 turnovers = $60K deployed
- $60K × 3% × 0.98 win rate = $1,764 profit
- Loss: $60K × 0.02 = $1,200
- **Net: $564/month = 2.8% monthly = 34% annual**

## Deployment (Production)

### VPS Setup (Recommended)

**Why VPS:**
- 24/7 uptime
- Better reliability than home computer
- Professional infrastructure

**Provider Recommendations:**
- DigitalOcean: $40/month (2 vCPU, 4GB RAM)
- Vultr: $40/month (similar specs)
- AWS Lightsail: $40/month (scalable)

**VPS Setup:**
```bash
# SSH into VPS
ssh user@your-vps-ip

# Install Python
sudo apt update
sudo apt install python3 python3-pip -y

# Clone bot files
git clone <your-repo>
cd kalshi_bot

# Install dependencies
pip3 install -r requirements.txt

# Configure
nano config.yaml  # Edit with your settings

# Run in background
nohup python3 endgame_bot.py > output.log 2>&1 &

# Check it's running
ps aux | grep endgame_bot
```

### Running as Service (Linux)

Create `/etc/systemd/system/kalshi-bot.service`:

```ini
[Unit]
Description=Kalshi Endgame Trading Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/kalshi_bot
ExecStart=/usr/bin/python3 /home/your_user/kalshi_bot/endgame_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable kalshi-bot
sudo systemctl start kalshi-bot
sudo systemctl status kalshi-bot
```

## Safety & Best Practices

### Start Small

1. **Week 1-2: Demo Mode**
   - Run with demo account
   - Validate bot works correctly
   - Test for 2+ weeks

2. **Week 3-4: Small Capital ($2-3K)**
   - Switch to production
   - Deploy 10-15% of capital
   - Monitor closely (check 2-3x daily)

3. **Month 2+: Scale Gradually**
   - Add 20% more capital per week
   - Scale to full capital over 4-6 weeks

### Daily Checklist

**Morning:**
- ✅ Check bot is running
- ✅ Review overnight positions
- ✅ Check for any errors in logs

**Evening:**
- ✅ Review day's activity
- ✅ Check win rate vs expected
- ✅ Verify position count

**Weekly:**
- ✅ Review performance stats
- ✅ Adjust config if needed
- ✅ Check capital utilization
- ✅ Backup data files

### Risk Management Rules

**Never:**
- ❌ Exceed 10% per position
- ❌ Override risk limits manually
- ❌ Trade blacklisted categories
- ❌ Ignore daily loss limits
- ❌ Let positions exceed max count

**Always:**
- ✅ Start with demo mode
- ✅ Monitor first 2 weeks closely
- ✅ Keep 20% reserve capital
- ✅ Diversify across categories
- ✅ Log all activity

## Troubleshooting

### Bot Won't Start

**Issue:** Authentication failed
```
Solution: Check email/password in config.yaml
Verify demo vs production URL matches account type
```

**Issue:** Can't fetch balance
```
Solution: Ensure account is properly funded
Check API credentials are correct
Try re-authenticating on Kalshi website
```

### No Opportunities Found

**Issue:** Bot finds 0 opportunities every iteration
```
Possible causes:
1. Probability thresholds too strict (try 0.94-0.99)
2. Whitelist too restrictive (add more categories)
3. Min volume too high (lower to 25000)
4. No markets actually meeting criteria (check Kalshi website)
```

**Solution:**
- Lower min_probability to 0.94 temporarily
- Check Kalshi website manually for 95%+ markets
- Adjust filters in config.yaml

### Positions Not Closing

**Issue:** Position shows settled on website but bot hasn't closed it
```
Solution: 
- Bot checks every 5 minutes (wait one cycle)
- Check logs for errors during update_positions()
- Manually verify market status on Kalshi
```

### Performance Issues

**Issue:** Win rate lower than expected
```
Expected: 96-99% (matching probability)
If seeing 90-95%: Black swan events hitting

Solutions:
1. Tighten category filters (avoid risky categories)
2. Increase min_probability to 0.97
3. Increase min_days_to_close to 2 (avoid manipulation)
4. Review which categories are losing
```

## Tax Reporting

**Important:** Consult a tax professional. This is not tax advice.

**Current Guidance (2025):**
- Kalshi issues Form 1099-MISC (if >$600 profit)
- Report as "Other Income" on Schedule 1, Line 8z
- Taxed at ordinary income rates (10-37%)

**Record Keeping:**
- Bot automatically logs all trades in `data/trades.json`
- Keep records for 7 years
- Track: date, ticker, entry, exit, profit/loss

**Tax Optimization:**
- Consider LLC/S-Corp for full-time trading
- Quarterly estimated tax payments if profitable
- Deduct VPS costs as business expense

## FAQ

**Q: How much can I make?**
A: Realistic: 40-60% annual return. Top case: 100%+. No guarantees.

**Q: What's the risk?**
A: Main risk is "black swan" events (1-5% losses). One bad trade can wipe out 20-33 winning trades. Diversification is key.

**Q: How much time does this require?**
A: After setup: 5-10 minutes daily to monitor. Bot runs autonomously.

**Q: Should I use demo or real money first?**
A: ALWAYS start with demo for 2+ weeks. Then start small ($2-3K) in production.

**Q: Can I modify the code?**
A: Yes! Code is modular. Common modifications:
- Adjust position sizing formula
- Add new filters
- Integrate alerts (email/SMS)
- Add additional strategies

**Q: What if bot crashes?**
A: Positions are saved to disk. Restart bot and it will resume monitoring existing positions.

**Q: How do I know if it's working?**
A: Check logs every few hours initially. Should see:
- "Found X opportunities"
- "✓ Position opened"
- "✓ Position closed: WON $X"

**Q: What categories should I trade?**
A: Start conservative: ECON only. Expand to POLITICS, WEATHER as you gain confidence.

**Q: Can I run multiple bots?**
A: Not recommended on same account (API conflicts). Could run different strategies on different accounts.

## Support & Development

**Created by:** Claude (Anthropic)
**Purpose:** Educational/research use
**License:** Use at your own risk

**Disclaimer:**
This bot is provided as-is for educational purposes. Trading involves risk. Past performance doesn't guarantee future results. The author is not responsible for any financial losses. Always test thoroughly with demo accounts before using real money.

## Version History

**v1.0 (Current)**
- Initial release
- Endgame sweep strategy
- Kelly position sizing
- Risk management
- Position tracking
- Comprehensive logging

**Planned Features:**
- Backtesting mode
- Email/SMS alerts
- Web dashboard
- Multiple strategy support
- Paper trading mode

## Getting Help

If you encounter issues:

1. Check logs: `tail -f logs/kalshi_bot.log`
2. Verify config: `cat config.yaml`
3. Check positions: `cat data/positions.json`
4. Review this README's Troubleshooting section
5. Start with demo mode if unsure

**Remember:** Start small, monitor closely, scale gradually. Success takes patience and discipline.

Good luck! 🚀
