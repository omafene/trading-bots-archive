# 🚀 VPS Quick Setup - 30 Minute Guide

**Complete step-by-step for absolute beginners**

---

## Step 1: Get a VPS (5 min)

**Recommended: DigitalOcean**
- Go to: https://www.digitalocean.com
- Sign up and add payment
- Click "Create" → "Droplets"
- Choose:
  - **OS:** Ubuntu 22.04 LTS
  - **Plan:** Basic $6/month (1GB RAM)
  - **Location:** New York or San Francisco
- Click "Create Droplet"

**Save these credentials:**
- IP Address: ___________________
- Password: ___________________

---

## Step 2: Connect to VPS (2 min)

**Windows PowerShell or Mac Terminal:**
```bash
ssh root@YOUR_IP_ADDRESS
# Type 'yes' when asked
# Enter password
```

**✅ You're in!**

---

## Step 3: Setup Server (5 min)

**Copy-paste each command:**

```bash
# Update system
apt update && apt upgrade -y

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
apt install -y nodejs

# Install PM2
npm install -g pm2

# Install Git
apt install -y git

# Verify
node --version
pm2 --version
```

**✅ Server ready!**

---

## Step 4: Upload Bot Files (5 min)

**Option A - FileZilla (Easiest):**
1. Download FileZilla from https://filezilla-project.org
2. Connect:
   - Host: `sftp://YOUR_IP`
   - Username: `root`
   - Password: YOUR_PASSWORD
   - Port: `22`
3. Drag `systematic-trader-v2` folder to VPS

**Option B - SCP Command:**
```bash
# On YOUR computer (not VPS):
scp -r systematic-trader-v2 root@YOUR_IP:/root/
```

**✅ Files uploaded!**

---

## Step 5: Configure Bot (5 min)

```bash
# Go to bot directory
cd /root/systematic-trader-v2

# Install dependencies
npm install

# Create environment file
cp .env.example .env
nano .env
```

**Add your credentials:**
```
EXCHANGE_API_KEY=your_key_here
EXCHANGE_API_SECRET=your_secret_here
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Save:** Ctrl+X → Y → Enter

```bash
# Create config file
cp config.enhanced.js config.js
nano config.js
```

**Set these to `true`:**
```javascript
regimeDetection: { enabled: true }
cryptoData: { enabled: true }
risk: {
    useKelly: true,
    useVolatilityAdjustment: true,
    useMultiTargets: true
}
```

**Save:** Ctrl+X → Y → Enter

**✅ Bot configured!**

---

## Step 6: Test (3 min)

```bash
# Quick backtest
node run-backtest.js --days=7

# Should show backtest results
```

**If errors:** Check .env and config.js syntax

**✅ Bot tested!**

---

## Step 7: Start Bot 24/7 (2 min)

```bash
# Start with PM2
pm2 start index.js --name trading-bot

# Check status
pm2 status

# View logs
pm2 logs trading-bot

# Press Ctrl+C to exit logs (bot keeps running)
```

**✅ Bot running!**

---

## Step 8: Auto-Start on Reboot (2 min)

```bash
# Save PM2 config
pm2 save

# Setup auto-start
pm2 startup

# Copy and run the command it gives you
```

**✅ Bot will survive reboots!**

---

## Step 9: Test Telegram (1 min)

**Open Telegram, send to your bot:**
```
/stats
```

**Should show:**
```
📊 Performance Stats
⏱ Uptime: 2m
📈 Signals: 0
🎯 Trades: 0
...
```

**✅ Remote monitoring works!**

---

## Daily Commands

```bash
# Connect to VPS
ssh root@YOUR_IP

# Check bot status
pm2 status

# View recent activity
pm2 logs trading-bot --lines 50

# Restart bot
pm2 restart trading-bot

# Disconnect (bot keeps running)
exit
```

---

## Troubleshooting

**Bot not starting?**
```bash
cd /root/systematic-trader-v2
node index.js
# Read error message, fix config
```

**Can't see logs?**
```bash
pm2 logs trading-bot --lines 100
```

**Need to update config?**
```bash
cd /root/systematic-trader-v2
nano config.js
# Make changes
pm2 restart trading-bot
```

**Out of memory?**
```bash
free -h
# If <200MB free, upgrade VPS to 2GB
```

---

## Cost: $6/month

**What you get:**
- 24/7 uptime
- 10-20ms latency to exchanges
- Auto-restart on crashes
- Remote monitoring
- Professional setup

**Upgrade when needed:**
- $12/mo for 2GB RAM (more pairs)
- $18/mo for 4GB RAM (multiple bots)

---

## Security (Optional but Recommended)

```bash
# Setup firewall
ufw allow 22/tcp
ufw enable

# Create non-root user
adduser trader
usermod -aG sudo trader
```

---

## ✅ You're Done!

Your bot is now:
- ✅ Running 24/7 on VPS
- ✅ Auto-restarts if crashes
- ✅ Auto-starts on reboot
- ✅ Monitorable via Telegram
- ✅ Low latency to exchanges

**Next:** Start paper trading, monitor daily via `/stats`

**Monthly cost:** $6  
**Setup time:** 30 minutes  
**Worth it:** 100% yes

---

## Quick Reference Card

**VPS Info:**
- IP: _________________
- Username: root
- Password: _________________

**Connect:**
```bash
ssh root@YOUR_IP
```

**Bot Location:**
```bash
cd /root/systematic-trader-v2
```

**Essential Commands:**
```bash
pm2 status              # Check bot
pm2 logs trading-bot    # View logs
pm2 restart trading-bot # Restart
```

**Telegram:**
```
/stats      # Performance
/positions  # Active trades
/mode paper # Switch mode
```

**Need help?** Read VPS-DEPLOYMENT-GUIDE.md for full details.

---

**Save this file for quick reference!**
