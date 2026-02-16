# 📱 Telegram Notifications Setup

## ✅ Yes! You Can Get Telegram Notifications

The bot will send you notifications about:
- 🎯 Opportunities found (in paper mode too!)
- ✅ Trades executed (when live)
- 🎉 Winning trades
- 📊 Daily summaries

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g., "My Kalshi Bot")
4. Choose a username (e.g., "my_kalshi_bot")
5. **Copy the bot token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. Start a chat with your new bot (click the link BotFather gives you)
2. Send any message to your bot (e.g., "hello")
3. Open this URL in your browser (replace TOKEN):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
4. Look for `"chat":{"id":123456789}` in the response
5. **Copy your chat ID** (the number)

### Step 3: Configure the Bot

Edit `config/config.yaml`:

```yaml
notifications:
  telegram:
    enabled: true  # Change from false to true
    bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Paste your token
    chat_id: "123456789"  # Paste your chat ID

  alerts:
    on_trade: true        # Notify when opportunity found
    on_win: true          # Notify when trade wins
    on_loss: false        # Don't notify losses (too noisy in lottery mode)
    on_daily_summary: true  # Send daily summary
    on_error: true        # Notify on errors
```

### Step 4: Restart the Bot

```bash
./bot-control.sh restart
```

You should immediately get a test message in Telegram! 🎉

---

## 📊 Example Notifications

### Opportunity Found (Paper Mode)
```
🎲 Opportunity Found 📝 PAPER MODE

Market: KXBTC15M-26FEB161700-B75K
Mode: LOTTERY
Symbol: BTC

Entry: $0.08
Size: 125 contracts
Cost: $10.00

Win Probability: 32.5%
Expected Value: 245.3%
Momentum: +0.42%

Closes in: 9.2 minutes
```

### Opportunity Found (Live Mode)
```
⚖️ Opportunity Found 💰 LIVE

Market: KXETH15M-26FEB161715-U2100
Mode: BALANCED
Symbol: ETH

Entry: $0.52
Size: 96 contracts
Cost: $50.00

Win Probability: 68.2%
Expected Value: 31.5%
Momentum: +0.58%

Closes in: 10.1 minutes
```

### Daily Summary
```
📊 Daily Summary

Date: 2026-02-16

Opportunities: 18
Trades: 12
Wins: 5 (41.7%)
Losses: 7

Total Profit: +$245.00
ROI: 204.2%

Balance: $1,245.00
```

---

## ⚙️ Notification Settings

### Get Alerts for Everything
```yaml
alerts:
  on_trade: true
  on_win: true
  on_loss: true
  on_daily_summary: true
  on_error: true
```

### Quiet Mode (Only wins and summaries)
```yaml
alerts:
  on_trade: false     # Don't notify every opportunity
  on_win: true        # Only notify wins
  on_loss: false      # Skip losses
  on_daily_summary: true
  on_error: true
```

### Paper Trading Mode (See opportunities)
```yaml
alerts:
  on_trade: true      # YES - See all opportunities found
  on_win: false       # Not applicable in paper mode
  on_loss: false
  on_daily_summary: true
  on_error: true
```

---

## 🔧 Troubleshooting

### Not Receiving Messages?

**Check bot token:**
```bash
grep bot_token config/config.yaml
```

**Check chat ID:**
```bash
grep chat_id config/config.yaml
```

**Test the connection:**
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

Should return bot info if token is valid.

**Check logs:**
```bash
./bot-control.sh logs | grep Telegram
```

### Getting Too Many Notifications?

In lottery mode with 15 opportunities/day, you might get a lot!

**Solution 1:** Only notify wins
```yaml
alerts:
  on_trade: false  # Don't notify every opportunity
  on_win: true     # Only wins
```

**Solution 2:** Batched daily summary
```yaml
alerts:
  on_trade: false
  on_win: false
  on_loss: false
  on_daily_summary: true  # Just one message per day
```

---

## 📱 Advanced: Multiple Notification Channels

Want notifications in multiple places?

### Option 1: Add Multiple Chat IDs (Group)
1. Create a Telegram group
2. Add your bot to the group
3. Get the group chat ID (negative number)
4. Use that as chat_id

### Option 2: Forward to Email
Some Telegram bots can forward to email. Search for "Telegram to Email" bots.

---

## ✅ Recommended Settings

### For Paper Trading (Now)
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_TOKEN"
  chat_id: "YOUR_CHAT_ID"

alerts:
  on_trade: true        # See all opportunities! ✅
  on_win: false         # Not applicable yet
  on_loss: false
  on_daily_summary: true  # Get daily stats
  on_error: true        # Know if something breaks
```

### For Live Trading (Later)
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_TOKEN"
  chat_id: "YOUR_CHAT_ID"

alerts:
  on_trade: true        # See when trades execute
  on_win: true          # Celebrate wins! 🎉
  on_loss: false        # Skip losses (70% of lottery trades)
  on_daily_summary: true  # Daily performance
  on_error: true        # Critical errors only
```

---

## 🎯 Summary

**YES, you get Telegram notifications in paper mode!**

In fact, paper mode is the BEST time to enable them because:
- ✅ See what opportunities the bot finds
- ✅ Validate the filters are working
- ✅ Get familiar with the notification format
- ✅ Tune alert settings before going live

**Setup time:** 5 minutes
**Cost:** Free!
**Value:** Priceless (know what your bot is doing!)

---

## 🚀 Quick Start

```bash
# 1. Get Telegram token from @BotFather
# 2. Get chat ID from getUpdates API
# 3. Edit config/config.yaml
nano config/config.yaml

# 4. Enable telegram:
#    enabled: true
#    bot_token: "..."
#    chat_id: "..."

# 5. Restart bot
./bot-control.sh restart

# 6. Check you got the test message! 📱
```

Done! 🎉
