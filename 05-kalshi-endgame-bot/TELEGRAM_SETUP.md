# 📱 Telegram Alerts Setup Guide

Get real-time notifications about your trading bot's activity directly in Telegram.

---

## Why Telegram Alerts?

- **Instant Notifications**: Know immediately when positions open/close
- **Performance Tracking**: Daily summaries of wins, losses, and P&L
- **Error Alerts**: Get notified if something goes wrong
- **Mobile Access**: Monitor your bot from anywhere

---

## What You'll Get

### Position Alerts
- ✅ **Position Opened**: Details about new trades
- 🎉 **Won Position**: Successful trades with P&L
- ❌ **Lost Position**: Failed trades (black swan events)

### Daily Summary
- Portfolio status (open positions, deployed capital)
- Win rate and total P&L
- Average returns
- Sent once per day after 6 PM

### Error Alerts
- API connection issues
- Authentication failures
- Unexpected errors

### Risk Alerts
- 🛑 Daily loss limit reached
- 🚨 Large loss warnings (>$1,000)

---

## Step-by-Step Setup (5 minutes)

### Step 1: Create Your Telegram Bot

1. **Open Telegram** and search for `@BotFather`
   - This is the official bot for creating bots
   
2. **Start a chat** with @BotFather
   - Click "Start" or send `/start`

3. **Create new bot** by sending:
   ```
   /newbot
   ```

4. **Choose a name** for your bot:
   ```
   Kalshi Trading Bot
   ```
   (or any name you like)

5. **Choose a username** (must end in 'bot'):
   ```
   your_kalshi_bot
   ```
   or
   ```
   kalshi_trader_bot
   ```

6. **Save your token!** BotFather will respond with:
   ```
   Done! Your token is:
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   
   **IMPORTANT**: Copy this token! You'll need it for the config.

---

### Step 2: Get Your Chat ID

**Method A: Using @userinfobot (Easiest)**

1. Search for `@userinfobot` in Telegram
2. Start a chat and send any message
3. It will reply with your Chat ID:
   ```
   Id: 987654321
   ```
4. Copy this number

**Method B: Using Your Bot**

1. Search for your bot (the username you just created)
2. Start a chat and send any message (like "Hello")
3. Open this URL in your browser (replace YOUR_BOT_TOKEN):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":987654321}` in the response
5. Copy that number

---

### Step 3: Configure Your Bot

Edit your `config.yaml` file:

```yaml
# Telegram Notifications
telegram:
  enabled: true                    # Change to true
  bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Paste your token
  chat_id: "123456789"             # Paste your chat ID
  
  # Configure which notifications to receive
  notifications:
    position_opened: true   # Alert when opening positions
    position_closed: true   # Alert when closing positions
    daily_summary: true     # Daily performance summary
    opportunities: false    # Alert when opportunities found (can be noisy!)
    errors: true           # Alert on errors
    large_losses: true     # Alert on losses > $1,000
```

**Important Notes:**
- Both `bot_token` and `chat_id` must be in quotes
- `chat_id` is a number but keep it as a string (in quotes)
- Set `opportunities: false` initially (it can send many messages)

---

### Step 4: Test the Setup

1. **Restart your bot** (if it was running):
   ```bash
   sudo systemctl restart kalshi-bot
   ```
   
   Or if running manually:
   ```bash
   cd ~/kalshi_bot
   python3 endgame_bot.py
   ```

2. **You should receive a test message** in Telegram:
   ```
   🤖 Kalshi Bot Started
   
   Telegram alerts are active!
   ```

3. **If you DON'T receive a message**, check:
   - Is `enabled: true`?
   - Did you copy the full bot token (including the colon)?
   - Did you start a chat with your bot?
   - Check the logs: `tail -f ~/kalshi_bot/logs/kalshi_bot.log`

---

## Customizing Notifications

### Reduce Noise

If you're getting too many alerts:

```yaml
notifications:
  position_opened: true    # Keep important ones
  position_closed: true
  daily_summary: true
  opportunities: false     # Turn off noisy ones
  errors: true
  large_losses: true
```

### Only Critical Alerts

For minimal interruptions:

```yaml
notifications:
  position_opened: false
  position_closed: true    # Only final results
  daily_summary: true
  opportunities: false
  errors: true
  large_losses: true
```

### Everything Enabled

For maximum visibility:

```yaml
notifications:
  position_opened: true
  position_closed: true
  daily_summary: true
  opportunities: true
  errors: true
  large_losses: true
```

---

## Example Telegram Messages

### Position Opened
```
✅ POSITION OPENED

Market: KXELEC-25JAN03
Title: Will Republican Party control both U.S. House...
Side: YES
Probability: 97.5%
Entry Price: $0.98
Position Size: $1,854
Expected Return: 2.6%
Days to Close: 7.3
Category: POLITICS

⏰ 2025-12-18 14:30:00
```

### Position Won
```
🎉 POSITION CLOSED - WON

Market: KXELEC-25JAN03
Title: Will Republican Party control both U.S. House...
Side: YES
Entry Price: $0.98
Exit Price: $1.00
Position Size: $1,854
P&L: +$48.23 (+2.6%)
Hold Time: 7d 4h

⏰ 2025-12-25 18:30:00
```

### Daily Summary
```
📊 DAILY SUMMARY

Open Positions: 8
Total Deployed: $14,832.00
Available Capital: $5,168.00
Utilization: 74.2%

PERFORMANCE
Total Trades: 47
Win Rate: 97.9% (46W/1L)
Total P&L: +$1,247.53
Avg Return: +2.7%
Avg Win: +$27.89
Avg Loss: -$142.00

⏰ 2025-12-18 18:05:00
```

### Daily Loss Limit Hit
```
🛑 DAILY LOSS LIMIT HIT

Daily P&L: -$3,147.82 (-15.7%)
Action: Trading stopped for today

⏰ 2025-12-18 11:23:00
```

### Large Loss Alert
```
🚨 LARGE LOSS ALERT

Market: CRYPTO-BTC-100K
Loss: -$1,847.00
Position Size: $1,850.00
Category: CRYPTO

⏰ 2025-12-18 16:45:00
```

---

## Troubleshooting

### "Telegram connection test failed"

**Problem**: Bot can't send messages

**Solutions**:
1. Check bot token is correct (copy-paste carefully)
2. Make sure you started a chat with your bot
3. Verify `chat_id` is correct
4. Check internet connection on VPS

### No test message received

**Problem**: Bot starts but no Telegram notification

**Check**:
```bash
# View logs
tail -f ~/kalshi_bot/logs/kalshi_bot.log

# Look for:
# "Telegram alerts enabled" - Good!
# "Telegram connection test failed" - Problem
# "Telegram alerts disabled" - Check config
```

**Fix**:
```yaml
# Make sure in config.yaml:
telegram:
  enabled: true  # Not false!
```

### Wrong chat getting messages

**Problem**: Messages going to wrong person/group

**Solution**:
- Each Telegram account has unique chat ID
- Verify your chat ID using @userinfobot
- Update config.yaml with correct ID

### Too many messages

**Problem**: Getting spammed with alerts

**Solution**:
```yaml
notifications:
  opportunities: false  # This one is noisy
  position_opened: false  # Reduce if too frequent
```

---

## Security Notes

### Keep Your Token Secret

- **NEVER** share your bot token publicly
- **NEVER** commit it to Git/GitHub
- Anyone with your token can send messages as your bot

### Secure Your config.yaml

```bash
# Restrict access (only you can read)
chmod 600 ~/kalshi_bot/config.yaml
```

### If Token Leaked

1. Go to @BotFather
2. Send `/token`
3. Choose your bot
4. Click "Revoke current token"
5. Get new token and update config

---

## Advanced: Group/Channel Notifications

Want to share alerts with a team?

### Setup Group Notifications

1. **Create a Telegram group**
2. **Add your bot** to the group
3. **Make bot an admin** (optional but recommended)
4. **Get group chat ID**:
   - Send a message in the group
   - Visit: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
   - Look for `"chat":{"id":-123456789}` (note the negative number)
   - Use this as your `chat_id`

```yaml
telegram:
  chat_id: "123456789"  # Negative for groups
```

### Setup Channel Notifications

1. **Create a Telegram channel**
2. **Add your bot** as an administrator
3. **Get channel ID** (similar to group method)
4. **Channel IDs start with -100**:
   ```yaml
   chat_id: "123456789"
   ```

---

## FAQ

**Q: Can I use the same bot for multiple trading bots?**
A: Yes! Just use the same bot token in all config files.

**Q: Can notifications be sent to multiple people?**
A: Use a group and add everyone you want to receive notifications.

**Q: Do I need Telegram on my phone?**
A: No, you can use Telegram Web or Desktop apps too.

**Q: Will this slow down my bot?**
A: No, Telegram notifications are sent asynchronously and won't affect trading.

**Q: Can I turn off notifications without stopping the bot?**
A: Yes, just set `enabled: false` in config and restart the bot.

**Q: What if Telegram is down?**
A: The bot will continue trading normally. Notifications will fail silently and be logged.

---

## Next Steps

1. ✅ Create your bot with @BotFather
2. ✅ Get your chat ID
3. ✅ Update config.yaml
4. ✅ Restart bot and test
5. ✅ Customize notification settings
6. ✅ Monitor your trades in real-time!

---

## Support

If you have issues:

1. Check logs: `tail -f ~/kalshi_bot/logs/kalshi_bot.log`
2. Verify config syntax (YAML is sensitive to spaces)
3. Test manually: Send yourself a test message using the Telegram API
4. Review this guide step-by-step

Happy trading! 🚀
