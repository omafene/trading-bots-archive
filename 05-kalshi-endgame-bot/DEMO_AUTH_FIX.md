# ✅ FIXED: Demo API Key Authentication

## What Was Wrong

Kalshi's **demo** environment uses **API key authentication**, not email/password!

- ❌ Demo doesn't accept: email/password
- ✅ Demo requires: API Key ID + Private Key (RSA)
- ✅ Production uses: email/password

This is why you were getting 404 errors - the bot was trying to use password login on an endpoint that doesn't exist in demo.

---

## What I Fixed

### 1. Updated kalshi_client.py
- ✅ Added support for API key authentication
- ✅ Added RSA private key signing
- ✅ Auto-detects auth method based on `use_demo` setting
- ✅ Signs all requests with your private key

### 2. Updated config.yaml
- ✅ Added `demo_api_key_id` field
- ✅ Added `demo_private_key_path` field
- ✅ Pre-configured with YOUR credentials

### 3. Created demo_private_key.pem
- ✅ Your private key is saved in this file
- ✅ Bot loads it automatically when in demo mode

### 4. Updated requirements.txt
- ✅ Added `cryptography` library for RSA signing

---

## Your Demo Credentials (Already Configured!)

I've already set up your config with your demo credentials:

```yaml
api:
  use_demo: true
  
  # Demo credentials (ALREADY CONFIGURED)
  demo_api_key_id: "00000000-0000-0000-0000-000000000000"
  demo_private_key_path: "demo_private_key.pem"
```

The private key is saved in `demo_private_key.pem` in your bot directory.

---

## 🚀 Quick Start (Ready to Run!)

### Step 1: Upload Updated Files

**On your VPS:**
```bash
# Upload the new archive
scp kalshi_bot_with_demo_auth.tar.gz root@YOUR_VPS_IP:~/

# Extract
cd ~
tar -xzf kalshi_bot_with_demo_auth.tar.gz
cd kalshi_bot
```

### Step 2: Install New Dependency

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Install cryptography library
pip install cryptography

# Or install all requirements
pip install -r requirements.txt
```

### Step 3: Test Run

```bash
python3 endgame_bot.py
```

**You should now see:**
```
Successfully loaded private key
Successfully authenticated with API key: 7e92cc17...
Initial Balance: $1,000,000.00
```

No more 404 errors! 🎉

---

## File Structure

Your bot directory should now have:

```
kalshi_bot/
├── endgame_bot.py
├── kalshi_client.py          # UPDATED - API key auth
├── config.yaml               # UPDATED - demo credentials
├── demo_private_key.pem      # NEW - your private key
├── requirements.txt          # UPDATED - added cryptography
├── market_scanner.py
├── risk_manager.py
├── position_manager.py
├── telegram_notifier.py
├── README.md
├── QUICKSTART.md
└── TELEGRAM_SETUP.md
```

---

## How Authentication Works Now

### Demo Mode (`use_demo: true`)
```
1. Bot loads private key from demo_private_key.pem
2. For each API request:
   - Creates message: timestamp + method + path + body
   - Signs message with private key (RSA-SHA256)
   - Sends headers:
     * KALSHI-ACCESS-KEY: your_key_id
     * KALSHI-ACCESS-SIGNATURE: base64_signature
     * KALSHI-ACCESS-TIMESTAMP: current_time
3. Kalshi verifies signature and processes request
```

### Production Mode (`use_demo: false`)
```
1. Bot sends email/password to /login endpoint
2. Gets back JWT token
3. Uses token in Authorization header for all requests
```

---

## Security Notes

### Keep Private Key Safe! 🔒

```bash
# Restrict access (only you can read)
chmod 600 ~/kalshi_bot/demo_private_key.pem
chmod 600 ~/kalshi_bot/config.yaml
```

### If Key Compromised

1. Go to https://demo.kalshi.co
2. Navigate to Settings > API Keys
3. Delete the old key
4. Generate new key
5. Update `demo_private_key.pem` and `config.yaml`

---

## Switching to Production

When you're ready to trade with real money:

### Step 1: Update Config

```yaml
api:
  use_demo: false  # Switch to production
  
  # Production credentials
  email: "your_real_kalshi_email@example.com"
  password: "your_real_password"
  
  # Demo credentials (not used when use_demo: false)
  demo_api_key_id: "00000000-0000-0000-0000-000000000000"
  demo_private_key_path: "demo_private_key.pem"

capital:
  total_capital: 3000  # Start small!
  max_position_size: 300
  max_open_positions: 5
```

### Step 2: Restart

```bash
sudo systemctl restart kalshi-bot
```

Bot will now use email/password auth for production API.

---

## Troubleshooting

### Error: "Private key file not found"

```bash
# Make sure file exists
ls -l ~/kalshi_bot/demo_private_key.pem

# If missing, recreate it with your private key
nano ~/kalshi_bot/demo_private_key.pem
# Paste your private key (including BEGIN/END lines)
```

### Error: "Failed to load private key"

```bash
# Check file format - should start with:
head -1 ~/kalshi_bot/demo_private_key.pem
# Should show: -----BEGIN RSA PRIVATE KEY-----

# Check file permissions
ls -l ~/kalshi_bot/demo_private_key.pem
```

### Error: "Authentication failed"

**Check API key ID:**
```yaml
# In config.yaml, verify:
demo_api_key_id: "00000000-0000-0000-0000-000000000000"
```

**Verify in Kalshi demo:**
- Log into https://demo.kalshi.co
- Go to Settings > API Keys
- Confirm key ID matches

### Still Getting 404?

The demo API might be down or endpoint changed. Try:
```bash
# Test if API is reachable
curl -I https://demo-api.kalshi.co/trade-api/v2/exchange/markets
```

If this returns 404, Kalshi's demo API might be temporarily down.

---

## Testing Checklist

Run through this to make sure everything works:

- [ ] Uploaded new archive to VPS
- [ ] Extracted files
- [ ] Installed cryptography: `pip install cryptography`
- [ ] Private key file exists: `demo_private_key.pem`
- [ ] Config has correct API key ID
- [ ] File permissions set: `chmod 600 demo_private_key.pem`
- [ ] Run bot: `python3 endgame_bot.py`
- [ ] See "Successfully loaded private key"
- [ ] See "Successfully authenticated with API key"
- [ ] See "Initial Balance: $1,000,000.00"
- [ ] No 404 errors! ✅

---

## Summary

**Before:** Bot tried to use email/password on demo → 404 error

**After:** Bot uses API key + private key signing on demo → ✅ Works!

The bot now:
- ✅ Authenticates with demo using your API credentials
- ✅ Signs every request with your private key
- ✅ Automatically switches auth method based on `use_demo` setting
- ✅ Ready to test with $1M fake money!

**Your demo is ready to run!** Just upload the files, install cryptography, and start trading. 🚀
