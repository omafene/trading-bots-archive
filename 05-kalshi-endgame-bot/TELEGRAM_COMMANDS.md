# Telegram Remote Control - User Guide

## Overview

Your Kalshi bot now supports **remote control via Telegram**! You can pause/resume trading, check status, view positions, and more - all from your phone.

## Available Commands

### 📊 Monitoring Commands

**`/status`** - Get complete bot status
```
Shows:
- Running/Paused state
- Current balance
- Open positions
- Deployed capital
- Utilization percentage
- Performance stats (trades, win rate, P&L)
```

**`/balance`** - Quick balance check
```
Shows just your current account balance
```

**`/positions`** - List all open positions
```
Shows details for each position:
- Ticker
- Side (Yes/No)
- Cost
- Probability
- Days until close
```

### ⏯️ Control Commands

**`/pause`** - Pause trading
```
Stops the bot from opening NEW positions
Existing positions continue to be monitored
Use this when:
- You want to stop for the day
- Market conditions change
- You need to adjust strategy
```

**`/resume`** - Resume trading
```
Resumes normal trading operations
Bot will start opening positions again
```

**`/stop`** - Shut down the bot
```
Gracefully stops the entire bot
Use this when you want to completely stop the bot
You'll need to restart it manually via SSH
```

### 🔔 Alert Management

**`/opportunities`** - Toggle opportunity alerts
```
Usage:
/opportunities          - Check current status
/opportunities on       - Enable opportunity alerts
/opportunities off      - Disable opportunity alerts

Note: Opportunity alerts can be noisy during market hours
Recommended: Keep OFF unless you want frequent updates
```

**`/help`** - Show command list
```
Displays all available commands
```

## How It Works

### Background Polling
- Bot checks for Telegram messages every 2 seconds
- Commands are processed immediately
- Only responds to messages from YOUR chat_id (secure)
- Runs in background thread - doesn't interfere with trading

### Command Processing
1. You send a command (e.g., `/status`)
2. Bot receives it within 2 seconds
3. Bot processes the command
4. Bot sends response back to Telegram

### Security
- Bot only responds to YOUR chat_id
- Commands from other users are ignored
- No authentication needed (chat_id is the auth)

## Setup Instructions

### 1. Make Sure Telegram is Enabled

Edit your config:
```bash
cd ~/kalshi_bot
nano config.yaml
```

Verify these settings:
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"  # Must be in quotes!
```

### 2. Upload Updated Files

Replace two files on your VPS:
```bash
# On your local machine:
scp telegram_notifier.py root@YOUR_VPS_IP:~/kalshi_bot/
scp endgame_bot.py root@YOUR_VPS_IP:~/kalshi_bot/
```

### 3. Restart the Bot

```bash
cd ~/kalshi_bot
python3 endgame_bot.py
```

You should see:
```
Telegram alerts enabled
Telegram command listener started
```

### 4. Test Commands

Open Telegram and send:
```
/help
```

You should get a response with all commands!

## Usage Examples

### Morning Startup
```
User: /status
Bot: [Shows balance, positions, performance]

User: /resume
Bot: ▶️ BOT RESUMED - Trading active
```

### During Trading Day
```
User: /positions
Bot: [Lists all open positions with details]

User: /balance
Bot: 💰 Current Balance: $2,450.00
```

### Emergency Stop
```
User: /pause
Bot: ⏸️ BOT PAUSED - No new positions will be opened

[Market stabilizes]

User: /resume
Bot: ▶️ BOT RESUMED - Trading active
```

### End of Day
```
User: /status
Bot: [Shows daily performance]

User: /opportunities off
Bot: 🔕 Opportunity alerts DISABLED

User: /pause
Bot: ⏸️ BOT PAUSED
```

## Troubleshooting

### Commands Not Working

**Check bot logs:**
```bash
cd ~/kalshi_bot
tail -f logs/kalshi_bot.log | grep -i telegram
```

**Common issues:**

1. **"Bot controller not available"**
   - File versions might not match
   - Re-upload both files and restart

2. **No response to commands**
   - Check chat_id is correct in config.yaml
   - Verify it's in quotes: `"123456789"`
   - Check bot is running: `ps aux | grep endgame_bot`

3. **"Telegram command listener not started"**
   - Check `enabled: true` in config
   - Verify bot_token is valid
   - Restart the bot

### Verify Setup

Send this to your bot:
```
/help
```

If you get a response, everything is working!

## Best Practices

### ✅ DO:
- Use `/pause` instead of `/stop` for temporary pauses
- Check `/status` regularly to monitor performance
- Keep `/opportunities off` to avoid notification spam
- Use `/positions` to review before end of day

### ❌ DON'T:
- Don't share your bot_token (anyone can control your bot)
- Don't use `/stop` unless you really want to shut down
- Don't enable opportunities during market hours (too noisy)
- Don't forget to `/resume` after pausing!

## Command Reference Card

Save this to your phone:

```
🤖 KALSHI BOT COMMANDS

MONITORING:
/status     - Full status report
/balance    - Quick balance check
/positions  - List open positions

CONTROL:
/pause      - Stop opening positions
/resume     - Resume trading
/stop       - Shut down bot

ALERTS:
/opportunities on/off

HELP:
/help       - Show commands
```

## Technical Details

### Threading
- Commands processed in separate daemon thread
- Non-blocking - doesn't slow down trading
- Graceful shutdown on bot stop

### API Polling
- Uses Telegram getUpdates API
- 2-second polling interval
- Long polling timeout: 10 seconds
- Handles rate limits automatically

### Error Handling
- Commands fail gracefully
- Errors logged but don't crash bot
- User receives error message if command fails

## What's Next?

Possible future enhancements:
- `/logs` - Get last 20 log lines
- `/config` - View/modify settings
- `/backtest` - Run strategy backtests
- Scheduled commands (pause at 4 PM daily)
- Position-specific commands (/close TICKER)

Let me know if you want any of these added!

---

**Need help?** Check logs: `tail -f ~/kalshi_bot/logs/kalshi_bot.log`
