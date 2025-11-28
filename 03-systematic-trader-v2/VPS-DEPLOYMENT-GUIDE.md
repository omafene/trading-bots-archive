# 🖥️ VPS Deployment Guide - Complete Setup

## Why VPS is the Right Choice

✅ **24/7 Uptime** - Never miss a trading opportunity  
✅ **Low Latency** - 5-50ms to exchanges (vs 100-200ms from home)  
✅ **No Internet Issues** - Enterprise-grade connectivity  
✅ **Remote Access** - Monitor from anywhere  
✅ **Professional Setup** - Same infrastructure as institutions  

---

## 📋 Quick Overview

**Total Setup Time:** 30-45 minutes  
**Monthly Cost:** $5-20  
**Difficulty:** Beginner-friendly (step-by-step guide below)

---

## Part 1: Choose & Setup Your VPS (10 minutes)

### Recommended VPS Providers for US Traders

#### 🥇 Option 1: DigitalOcean (RECOMMENDED)
**Best for:** Beginners, ease of use  
**Cost:** $6/month (Basic Droplet)  
**Latency to Coinbase/Kraken:** ~10-20ms  

**Sign up:** https://www.digitalocean.com

**Specifications to Choose:**
- **Plan:** Basic Droplet
- **CPU:** Regular - 1 vCPU
- **RAM:** 1GB (minimum) or 2GB (recommended)
- **Storage:** 25GB SSD
- **Location:** 
  - New York (closest to Coinbase/Kraken US East servers)
  - San Francisco (for West Coast exchanges)
- **OS:** Ubuntu 22.04 LTS x64

**Click "Create Droplet"**

---

#### 🥈 Option 2: AWS Lightsail
**Best for:** Reliability, scalability  
**Cost:** $5/month (Lightsail instance)  
**Latency:** ~5-15ms  

**Sign up:** https://aws.amazon.com/lightsail

**Choose:**
- Platform: Linux/Unix
- Blueprint: Ubuntu 22.04 LTS
- Instance plan: $5/month (1GB RAM, 1 vCPU)
- Region: US East (Virginia) or US West (Oregon)

---

#### 🥉 Option 3: Vultr
**Best for:** Multiple datacenter options  
**Cost:** $6/month  
**Latency:** ~10-25ms  

**Sign up:** https://www.vultr.com

**Choose:**
- Cloud Compute - Shared CPU
- Location: New York or Los Angeles
- Server Type: Ubuntu 22.04 LTS
- Server Size: $6/mo (1GB RAM, 1 vCPU, 25GB SSD)

---

### After VPS is Created

You'll receive:
- **IP Address:** (e.g., YOUR_VPS_IP)
- **Username:** root (default)
- **Password:** Sent via email (or SSH key if you set one up)

**Save these credentials securely!**

---

## Part 2: Connect to Your VPS (5 minutes)

### On Windows:

**Option A: PowerShell (Built-in)**
```powershell
# Open PowerShell
ssh root@YOUR_VPS_IP_ADDRESS

# Example:
ssh root@YOUR_VPS_IP

# Enter password when prompted
```

**Option B: PuTTY (If PowerShell doesn't work)**
1. Download PuTTY: https://www.putty.org
2. Install and open PuTTY
3. Host Name: YOUR_VPS_IP_ADDRESS
4. Port: 22
5. Connection Type: SSH
6. Click "Open"
7. Enter username: root
8. Enter password

---

### On Mac/Linux:

**Open Terminal:**
```bash
ssh root@YOUR_VPS_IP_ADDRESS

# Example:
ssh root@YOUR_VPS_IP

# Enter password when prompted
```

---

### First Connection

You'll see a warning about authenticity - type `yes` and press Enter.

**You're now connected to your VPS!**

---

## Part 3: Initial Server Setup (5 minutes)

### Step 1: Update System Packages

```bash
# Update package list
apt update

# Upgrade installed packages
apt upgrade -y

# This takes 2-5 minutes
```

### Step 2: Install Node.js 18

```bash
# Add NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -

# Install Node.js
apt install -y nodejs

# Verify installation
node --version
# Should show: v18.x.x

npm --version
# Should show: 9.x.x or 10.x.x
```

### Step 3: Install PM2 (Process Manager)

```bash
# Install PM2 globally
npm install -g pm2

# Verify
pm2 --version
# Should show version number
```

### Step 4: Install Git (for easy updates)

```bash
apt install -y git

# Verify
git --version
```

---

## Part 4: Upload Your Bot to VPS (10 minutes)

### Option A: Using SFTP (GUI - Easier)

**1. Download FileZilla:**
- https://filezilla-project.org/download.php?type=client

**2. Connect to VPS:**
- Host: sftp://YOUR_VPS_IP
- Username: root
- Password: YOUR_PASSWORD
- Port: 22
- Click "Quickconnect"

**3. Upload Files:**
- Left side: Your local computer (navigate to systematic-trader-v2 folder)
- Right side: Your VPS (navigate to /root/)
- Drag & drop the entire systematic-trader-v2 folder from left to right

**Wait for upload to complete** (2-5 minutes depending on internet speed)

---

### Option B: Using SCP (Command Line - Faster)

**On your LOCAL computer** (not VPS):

```bash
# Navigate to where you downloaded the bot
cd /path/to/downloads

# Upload entire folder to VPS
scp -r systematic-trader-v2 root@YOUR_VPS_IP:/root/

# Example:
scp -r systematic-trader-v2 root@YOUR_VPS_IP:/root/

# Enter password when prompted
```

---

### Option C: Using Git (Best for Updates)

**On your VPS** (after SSH connection):

```bash
# Navigate to home directory
cd /root

# If you've uploaded to GitHub (optional):
git clone https://github.com/YOUR_USERNAME/systematic-trader-v2.git

# Otherwise, use SFTP or SCP to upload
```

---

## Part 5: Configure Bot on VPS (5 minutes)

### Step 1: Navigate to Bot Directory

```bash
cd /root/systematic-trader-v2

# List files to verify upload
ls -la

# You should see:
# bot.js, index.js, config.enhanced.js, package.json, etc.
```

### Step 2: Install Dependencies

```bash
npm install

# This takes 1-2 minutes
# Should show: "added ~150 packages"
```

### Step 3: Create Environment File

```bash
# Copy template
cp .env.example .env

# Edit with nano
nano .env
```

**Add your credentials:**
```env
EXCHANGE_API_KEY=your_coinbase_api_key_here
EXCHANGE_API_SECRET=your_coinbase_secret_here

TELEGRAM_BOT_TOKEN=your_telegram_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

**Save and exit:**
- Press `Ctrl+X`
- Press `Y`
- Press `Enter`

### Step 4: Create Configuration File

```bash
# Copy config template
cp config.enhanced.js config.js

# Edit configuration
nano config.js
```

**Key settings to configure:**
```javascript
// Line 8: Your exchange
exchange: 'coinbase',

// Line 15-21: Your trading pairs
pairs: [
    'BTC/USD',
    'ETH/USD',
    'SOL/USD'
],

// Line 52: ENABLE regime detection
regimeDetection: {
    enabled: true,
},

// Line 62: ENABLE crypto data (for crypto trading)
cryptoData: {
    enabled: true,
    fetchFundingRates: true,
},

// Line 77-81: ENABLE enhanced risk features
risk: {
    useKelly: true,
    useVolatilityAdjustment: true,
    useMultiTargets: true,
}
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

---

## Part 6: Test Configuration (5 minutes)

### Run Quick Backtest

```bash
node run-backtest.js --days=7
```

**Expected output:**
```
╔════════════════════════════════════════════════════════════╗
║              SYSTEMATIC TRADING BOT BACKTEST               ║
╚════════════════════════════════════════════════════════════╝

📅 Testing period: 7 days
📊 Testing all configured pairs

📈 Testing BTC/USD...
   Fetching 672 candles...
   ✓ Loaded 672 candles
   ...
```

**If you see errors:**
- Check your .env file has correct API keys
- Verify config.js syntax (no missing commas)
- Check exchange is spelled correctly

**If successful, proceed to next step!**

---

## Part 7: Run Bot with PM2 (24/7 Operation)

### Why PM2?

✅ Keeps bot running 24/7  
✅ Auto-restarts if crash  
✅ Auto-starts on VPS reboot  
✅ Easy monitoring and logs  
✅ Professional process management  

### Start Bot with PM2

```bash
# Start bot in paper mode first
pm2 start index.js --name trading-bot

# You'll see:
# ┌────┬────────────────┬─────────┬────────┐
# │ id │ name           │ status  │ cpu    │
# ├────┼────────────────┼─────────┼────────┤
# │ 0  │ trading-bot    │ online  │ 0%     │
# └────┴────────────────┴─────────┴────────┘
```

### Check Status

```bash
pm2 status

# Should show:
# ┌────┬────────────────┬─────────┬────────┬───────┐
# │ id │ name           │ status  │ cpu    │ mem   │
# ├────┼────────────────┼─────────┼────────┼───────┤
# │ 0  │ trading-bot    │ online  │ 5%     │ 85MB  │
# └────┴────────────────┴─────────┴────────┴───────┘
```

### View Logs

```bash
# View live logs
pm2 logs trading-bot

# You'll see:
# 🎯 Systematic Trading Bot initialized in PAPER mode
# 📊 Monitoring 3 pairs
# 🧠 Active strategies: 3
# ✅ Bot running - waiting for signals...

# Press Ctrl+C to exit logs (bot keeps running)
```

### Save PM2 Configuration

```bash
# Save current process list
pm2 save

# Setup auto-start on VPS reboot
pm2 startup

# Copy and run the command it gives you (looks like):
# sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u root --hp /root
```

**Your bot will now:**
- ✅ Run 24/7
- ✅ Auto-restart if it crashes
- ✅ Auto-start when VPS reboots
- ✅ Keep running even if you disconnect SSH

---

## Part 8: Monitor Your Bot (Daily)

### Via SSH (When Connected to VPS)

```bash
# Check bot status
pm2 status

# View recent logs
pm2 logs trading-bot --lines 50

# View last 100 lines
pm2 logs trading-bot --lines 100

# Monitor live
pm2 logs trading-bot
```

### Via Telegram (From Anywhere)

**Much easier! Set this up:**

```
Send to your bot:
/stats         - Get performance stats
/positions     - View active trades
/mode paper    - Switch modes
```

### Other Useful PM2 Commands

```bash
# Restart bot
pm2 restart trading-bot

# Stop bot
pm2 stop trading-bot

# Start bot again
pm2 start trading-bot

# View detailed info
pm2 show trading-bot

# Delete bot from PM2
pm2 delete trading-bot

# View all processes
pm2 list
```

---

## Part 9: Security Best Practices

### 1. Create a Non-Root User (Recommended)

```bash
# Create new user
adduser trader

# Add to sudo group
usermod -aG sudo trader

# Switch to new user
su - trader

# All future operations should use this user
```

### 2. Setup SSH Keys (More Secure than Password)

**On your LOCAL computer:**

```bash
# Generate SSH key pair (if you don't have one)
ssh-keygen -t rsa -b 4096

# Copy public key to VPS
ssh-copy-id root@YOUR_VPS_IP

# Now you can connect without password:
ssh root@YOUR_VPS_IP
```

### 3. Setup Firewall

```bash
# Allow SSH
ufw allow 22/tcp

# Enable firewall
ufw enable

# Check status
ufw status
```

### 4. Disable Root Login (After setting up non-root user)

```bash
# Edit SSH config
nano /etc/ssh/sshd_config

# Change this line:
PermitRootLogin no

# Save and restart SSH
systemctl restart sshd
```

---

## Part 10: Maintenance & Updates

### Daily Monitoring (5 minutes)

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Check bot status
pm2 status

# View recent activity
pm2 logs trading-bot --lines 50

# Check if any errors
pm2 logs trading-bot --err
```

**Or just use Telegram `/stats`** (much easier!)

### Weekly Maintenance (15 minutes)

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Navigate to bot directory
cd /root/systematic-trader-v2

# View performance logs
pm2 logs trading-bot --lines 200

# Check system resources
htop
# (Press 'q' to exit)

# Check disk space
df -h

# Check memory usage
free -h
```

### Updating the Bot

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Stop bot
pm2 stop trading-bot

# Navigate to directory
cd /root/systematic-trader-v2

# Backup current config
cp config.js config.backup.js
cp .env .env.backup

# Upload new files via SFTP
# (or use git pull if using GitHub)

# Install any new dependencies
npm install

# Restore your config
cp config.backup.js config.js
cp .env.backup .env

# Start bot
pm2 start trading-bot

# Check logs
pm2 logs trading-bot
```

### If Bot Crashes

```bash
# Check what happened
pm2 logs trading-bot --err --lines 100

# Restart
pm2 restart trading-bot

# If keeps crashing, check config:
cd /root/systematic-trader-v2
nano config.js
# Look for syntax errors
```

---

## Part 11: VPS Cost Optimization

### Starting Plan: $6/month (1GB RAM)
✅ Good for 3-5 pairs  
✅ Paper trading + live-tiny  
✅ Single strategy testing  

### If You Need More (Later):
- **$12/month (2GB RAM)** - 10+ pairs, multiple strategies
- **$18/month (4GB RAM)** - Production trading, multiple bots

### How to Check if You Need Upgrade:

```bash
# Check memory usage
free -h

# If "available" is < 200MB consistently, upgrade
```

---

## Part 12: Backup Strategy

### Automated Backups

```bash
# Create backup script
nano /root/backup-bot.sh
```

**Add this:**
```bash
#!/bin/bash
cd /root/systematic-trader-v2
tar -czf ~/bot-backup-$(date +%Y%m%d).tar.gz .
# Keep only last 7 days
find ~/bot-backup-*.tar.gz -mtime +7 -delete
```

**Make executable:**
```bash
chmod +x /root/backup-bot.sh
```

**Schedule daily backup:**
```bash
crontab -e

# Add this line:
0 2 * * * /root/backup-bot.sh
# (Runs at 2 AM daily)
```

### Manual Backup

```bash
# Create backup
cd /root
tar -czf bot-backup.tar.gz systematic-trader-v2

# Download to local computer via SFTP
# Or copy with SCP:
# scp root@YOUR_VPS_IP:/root/bot-backup.tar.gz ~/Downloads/
```

---

## Part 13: Troubleshooting

### Bot Won't Start

```bash
# Check for syntax errors
cd /root/systematic-trader-v2
node index.js

# If you see error messages, fix config.js or .env
nano config.js
```

### Can't Connect to VPS

1. Check VPS is running (check provider dashboard)
2. Verify IP address hasn't changed
3. Check firewall settings
4. Try rebooting VPS from provider dashboard

### High CPU Usage

```bash
# Check what's using CPU
htop

# If trading-bot is using >50% constantly:
# - Reduce scan interval in config
# - Reduce number of pairs
# - Check for infinite loops in logs
```

### Out of Memory

```bash
# Check memory
free -h

# Restart bot to clear memory
pm2 restart trading-bot

# If happens often, upgrade VPS to 2GB RAM
```

### Lost SSH Connection

```bash
# Reconnect
ssh root@YOUR_VPS_IP

# Bot keeps running thanks to PM2
pm2 status
# Should still show "online"
```

---

## 📋 VPS Setup Checklist

### Initial Setup:
- [ ] VPS created and running
- [ ] Can connect via SSH
- [ ] Node.js installed and working
- [ ] PM2 installed
- [ ] Bot files uploaded
- [ ] Dependencies installed (`npm install`)
- [ ] `.env` file configured
- [ ] `config.js` configured
- [ ] Backtest runs successfully
- [ ] Bot starts with PM2
- [ ] PM2 auto-startup configured
- [ ] Telegram alerts working

### Security:
- [ ] Non-root user created (optional but recommended)
- [ ] SSH keys setup (optional but recommended)
- [ ] Firewall configured
- [ ] Passwords stored securely

### Monitoring:
- [ ] Can check PM2 status
- [ ] Can view logs
- [ ] Telegram commands working
- [ ] Backup strategy in place

---

## 🎯 Quick Command Reference

```bash
# Connect to VPS
ssh root@YOUR_VPS_IP

# Navigate to bot
cd /root/systematic-trader-v2

# Check bot status
pm2 status

# View logs
pm2 logs trading-bot

# Restart bot
pm2 restart trading-bot

# Update bot
pm2 stop trading-bot
# (upload new files via SFTP)
npm install
pm2 start trading-bot

# Check system resources
htop           # CPU/Memory (press 'q' to exit)
df -h          # Disk space
free -h        # Memory usage
```

---

## ✅ You're All Set!

Your bot is now running 24/7 on a professional VPS with:
- ✅ Auto-restart on crashes
- ✅ Auto-start on reboot
- ✅ Low latency to exchanges
- ✅ Remote monitoring via Telegram
- ✅ Professional infrastructure

**Monitor daily, review weekly, optimize monthly.**

Good luck with your systematic trading! 🚀
