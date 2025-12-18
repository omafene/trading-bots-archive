# Quick Deployment - Telegram Commands

## What Changed

Added remote control to your bot! You can now:
- ✅ Pause/resume trading from Telegram
- ✅ Check status and balance
- ✅ View open positions
- ✅ Toggle opportunity alerts
- ✅ Shut down bot remotely

## Files Updated

1. **telegram_notifier.py** - Added command handling
2. **endgame_bot.py** - Added bot controller methods

## Deploy in 3 Steps

### Step 1: Upload Files to VPS

```bash
# On your local machine (download the files from outputs first):
scp telegram_notifier.py root@YOUR_VPS_IP:~/kalshi_bot/
scp endgame_bot.py root@YOUR_VPS_IP:~/kalshi_bot/
```

### Step 2: Make Sure Telegram is Configured

```bash
# On VPS:
cd ~/kalshi_bot
nano config.yaml
```

Verify:
```yaml
telegram:
  enabled: true
  bot_token: "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
  chat_id: "YOUR_CHAT_ID"  # Get from @userinfobot
```

Save: `Ctrl+X`, `Y`, `Enter`

### Step 3: Start the Bot

```bash
python3 endgame_bot.py
```

Look for these lines:
```
Telegram alerts enabled
Telegram command listener started
```

## Test It!

Open Telegram and send:
```
/help
```

You should get a response with all commands! 🎉

## Available Commands

```
/status              - Show bot status
/pause               - Pause trading
/resume              - Resume trading  
/balance             - Check balance
/positions           - List positions
/opportunities on/off - Toggle alerts
/stop                - Shut down bot
/help                - Show commands
```

## Example Usage

```
You: /status
Bot: 
🤖 BOT STATUS

State: ▶️ RUNNING
Balance: $2,450.00
Open Positions: 0
...

You: /pause
Bot: ⏸️ BOT PAUSED
Trading stopped. No new positions will be opened.

You: /resume  
Bot: ▶️ BOT RESUMED
Trading active.
```

## If Commands Don't Work

1. **Check chat_id:**
   ```bash
   grep chat_id config.yaml
   ```
   Should show: `chat_id: "123456789"` (in quotes!)

2. **Check logs:**
   ```bash
   tail -f logs/kalshi_bot.log | grep -i telegram
   ```

3. **Restart bot:**
   ```bash
   # Stop: Ctrl+C
   python3 endgame_bot.py
   ```

## Running as Service

If using systemd:

```bash
# Restart service
sudo systemctl restart kalshi-bot

# Check status
sudo systemctl status kalshi-bot

# View logs
sudo journalctl -u kalshi-bot -f
```

---

That's it! Your bot now has remote control. 🚀

See TELEGRAM_COMMANDS.md for full documentation.
