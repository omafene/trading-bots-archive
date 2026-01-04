# Linear Regression Momentum Upgrade

## What Changed

Upgraded from simple 2-point momentum to **Linear Regression with R² confidence**.

### Old Method (Backed up in `momentum_analyzer_simple.py`)
```python
start_price, end_price = recent_prices[0][1], recent_prices[-1][1]
percent_change = ((end_price - start_price) / start_price) * 100
```
- Used only 2 data points
- Sensitive to endpoint noise
- No confidence measure

### New Method (Current `momentum_analyzer.py`)
```python
# Fit line through ALL ~450 data points
slope, intercept = np.polyfit(times, prices, 1)

# Calculate R² (goodness of fit)
r_squared = 1 - (ss_res / ss_tot)
```
- Uses ALL price data (150-450 samples per candle)
- R² tells you trend quality (0-1 scale)
- Filters out false signals from noise

## Key Metrics

### R² (Trend Confidence)
| R² Value | Quality | What It Means |
|----------|---------|---------------|
| **0.7 - 1.0** | High | Strong, clean trend - high confidence |
| **0.4 - 0.7** | Medium | Acceptable trend quality |
| **0.0 - 0.4** | Low | Noisy, choppy - skip these |

### Signal Strength Adjustments
- **R² ≥ 0.7**: +15 points (confidence bonus)
- **R² 0.4-0.7**: +0 points (neutral)
- **R² < 0.4**: -10 points (noise penalty)

## New Config Options

```yaml
strategy:
  # R² Confidence Filter
  r_squared_filter_enabled: true    # Skip noisy markets
  min_r_squared: 0.3                # Minimum R² threshold
```

### Recommended Settings

**Balanced (Default):**
```yaml
r_squared_filter_enabled: true
min_r_squared: 0.3
```
- Filters obvious noise
- Still allows decent opportunities
- Good starting point

**Conservative:**
```yaml
r_squared_filter_enabled: true
min_r_squared: 0.5
```
- Only very clean trends
- Fewer but higher quality signals
- Lower risk of false positives

**Aggressive:**
```yaml
r_squared_filter_enabled: true
min_r_squared: 0.2
```
- More opportunities
- Accepts some choppy markets
- Higher signal volume but more noise

**Disabled:**
```yaml
r_squared_filter_enabled: false
```
- No R² filtering
- Signal strength still uses R² bonuses/penalties
- More signals but mixed quality

## What You'll See in Logs

### Skipped Noisy Markets
```
⏭️ BTC-ABOVE-95000 skip: Low R² (0.23 < 0.30) - noisy trend
```

### Good Signals
```
🎯 BTC-ABOVE-95000 | Edge: 12.3% | Signal: 68/100
   R²: 0.78 (high confidence)
   Trend: up +0.62%
```

## Benefits

✅ **Uses all data** - 450 samples vs 2 samples
✅ **Filters noise** - R² < 0.3 = skip choppy markets
✅ **Confidence measure** - Know when trends are real vs random
✅ **Better signals** - +15 pts for clean trends, -10 for noise
✅ **Fewer false positives** - Don't trade on random volatility

## Example: Clean Trend vs Noise

**Clean Trend (R² = 0.82):**
```
Price steadily rising: 95000 → 95100 → 95200 → 95300
All points close to trend line
Signal strength: 72 (with +15 R² bonus)
```

**Noisy Market (R² = 0.21):**
```
Price choppy: 95000 → 95200 → 94900 → 95300 → 94800
Points scattered around trend line
Signal strength: 35 (with -10 R² penalty)
SKIPPED if r_squared_filter_enabled: true
```

## Monitoring

Check logs for R² values to tune your threshold:
```bash
grep "R²" logs/edge_bot.log
```

If you're missing good opportunities, lower `min_r_squared`.
If you're getting fake signals, raise `min_r_squared`.

## Rollback

If you want to revert to simple momentum:
```bash
cp momentum_analyzer_simple.py momentum_analyzer.py
```

Then restart the bot.
