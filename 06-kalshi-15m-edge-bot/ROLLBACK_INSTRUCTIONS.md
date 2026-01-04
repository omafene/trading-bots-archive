# Rollback Instructions - Calibration Upgrade

## Backup Location
```
backups/calibration_upgrade_20260206_120106/
```

## Files Modified
1. `config_15m.yaml` - Updated thresholds and enabled crowd confidence
2. `edge_detector_advanced.py` - Added trend strength filter and crowd blending
3. `momentum_analyzer.py` - No changes (backup created for safety)

## To Rollback

### Option 1: Quick Rollback (restore all files)
```bash
cd /root/kalshi_15m_bot
cp backups/calibration_upgrade_20260206_120106/config_15m.yaml .
cp backups/calibration_upgrade_20260206_120106/edge_detector_advanced.py .
pkill -f edge_bot.py  # Restart bot
python3 edge_bot.py
```

### Option 2: Selective Rollback

#### Disable Crowd Confidence Only
Edit `config_15m.yaml`:
```yaml
calibration:
  crowd_confidence:
    enabled: false  # Change to false
```

#### Revert Thresholds Only
Edit `config_15m.yaml`:
```yaml
strategy:
  min_momentum_pct: 0.20  # Change from 0.50 to 0.20
  min_trend_strength: null  # Remove or comment out
```

## Changes Summary

### Config Changes
1. **min_momentum_pct**: 0.20 → 0.50 (avoid 0.2-0.5% zone with 33% win rate)
2. **min_trend_strength**: Added 0.30 threshold (>0.3 = 43% win rate)
3. **crowd_confidence.enabled**: false → true (market 68-84% accurate)

### Code Changes
1. **Trend Strength Filter**: Added filter at line ~122 in edge_detector_advanced.py
2. **Crowd Confidence Blending**: Added blending logic at line ~138
3. **Helper Method**: Added `_apply_crowd_confidence_blending()` method

## Testing After Upgrade

Monitor these metrics for 1-2 days:
- Win rate on executed trades (target: >55%)
- Number of trades per day (expect ~40% fewer trades)
- Edge quality (should see higher average edge)
- Crowd blending logs (look for 👥 messages)

## Expected Behavior

### Before Upgrade
- Win rate: ~37% on filtered trades
- High trade volume
- Many trades in 0.2-0.5% momentum zone (33% win rate)

### After Upgrade
- Win rate: Target 55-65% on executed trades
- ~40% fewer trades (higher quality)
- Crowd blending active (check logs for 👥 emoji)
- No trades with <0.50% momentum or <0.30 trend strength
