# Crowd Blending Per-Direction Control - Implementation Guide

## ✅ Code Changes Made

**File Modified:** `edge_detector_advanced.py`

**Changes:**
1. Added check for `disabled_for_directions` config option
2. Bot now skips crowd blending if momentum direction is in the disabled list
3. Added debug logging when blending is skipped

**Lines Modified:** ~153-180

## 🎯 How It Works

### Before (Old Behavior):
```python
if crowd_config.get('enabled', False):
    # ALWAYS blend bot probability with market price
    blended_prob = apply_crowd_blending(bot_prob, market_price)
```

### After (New Behavior):
```python
momentum_direction = momentum.get('direction')  # 'up' or 'down'
disabled_directions = crowd_config.get('disabled_for_directions', [])

if crowd_enabled AND momentum_direction NOT IN disabled_directions:
    # Only blend if direction is NOT disabled
    blended_prob = apply_crowd_blending(bot_prob, market_price)
else:
    # Use bot's raw probability (no crowd influence)
    blended_prob = bot_prob
```

## 📋 Configuration Options

Add to your `config_15m.yaml`:

### Option 1: Disable for UP trends only (RECOMMENDED)
```yaml
calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: ["up"]  # NEW CONFIG OPTION
    high_depth_threshold: 500
    low_depth_threshold: 100
    max_market_weight: 0.8
    min_market_weight: 0.6
```

### Option 2: Disable for DOWN trends only
```yaml
calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: ["down"]
```

### Option 3: Disable for BOTH directions
```yaml
calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: ["up", "down"]  # Same as enabled: false
```

### Option 4: Enable for all (current behavior)
```yaml
calibration:
  crowd_confidence:
    enabled: true
    disabled_for_directions: []  # Empty list = blend all directions
```

## 🧪 Testing

### 1. Update Config
Choose one of the options above and add to `config_15m.yaml`

### 2. Restart Bot
```bash
pkill -f edge_bot.py
python3 edge_bot.py
```

### 3. Monitor Logs
Look for these messages:
```
# When blending IS applied:
👥 KXBTC15M-... | Crowd Blending: 85.0% → 72.0% (market weight based on depth)

# When blending is SKIPPED:
🚫 KXBTC15M-... | Crowd Blending DISABLED for UP trends (using bot's raw probability: 85.0%)
```

### 4. Check Performance After 3-7 Days
```python
python3 << 'EOF'
import pandas as pd

df = pd.read_csv('data/negative_edges/skipped_trades.csv')

# Filter to recent data (after you made the change)
recent = df[df['timestamp'] > '2026-02-11 12:00:00'].copy()
recent['won'] = recent['would_have_won'].astype(str).str.lower() == 'true'

print("PERFORMANCE AFTER CROWD BLENDING CHANGES:")
for trend in ['up', 'down']:
    t = recent[recent['momentum_direction'] == trend]
    if len(t) > 0:
        won = t['won'].sum()
        total = len(t)
        wr = won / total * 100
        print(f"{trend.upper()}: {won}/{total} = {wr:.1f}% WR")
