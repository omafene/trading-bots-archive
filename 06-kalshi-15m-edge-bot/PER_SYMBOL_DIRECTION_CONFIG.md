# Per-Symbol Direction Filter - Design Proposal

## Problem
Current config has single `allowed_trends: ["down"]` for ALL symbols, but data shows:
- **SOL**: Profitable in BOTH directions (84.6% UP, 97.0% DOWN)
- **BTC**: Only profitable DOWN (31.8% UP, 99.1% DOWN)
- **ETH**: Only profitable DOWN (40.9% UP, 98.8% DOWN)

## Solution: Per-Symbol Direction Filters

### Config Structure (Option A - Simple)
```yaml
strategy:
  # Global fallback (applied if symbol not in symbol_configs)
  allowed_trends: ["down"]

  # Per-symbol overrides
  symbol_configs:
    SOL:
      allowed_trends: ["up", "down"]  # Trade both directions
      min_signal_strength: 25         # Lower threshold for SOL
    BTC:
      allowed_trends: ["down"]        # DOWN only
      min_signal_strength: 25
    ETH:
      allowed_trends: ["down"]        # DOWN only
      min_signal_strength: 30         # Stricter for ETH
```

### Config Structure (Option B - Advanced)
```yaml
strategy:
  symbol_configs:
    SOL:
      up_trades:
        enabled: true
        min_signal_strength: 25
        min_expected_probability: 0.60
        min_minutes_to_close: 3
        max_minutes_to_close: 5  # 61.9% WR in 3-5 min
      down_trades:
        enabled: true
        min_signal_strength: 25
        min_expected_probability: 0.65
        min_minutes_to_close: 1
        max_minutes_to_close: 8

    BTC:
      up_trades:
        enabled: false  # Disable UP (31.8% WR)
      down_trades:
        enabled: true
        min_signal_strength: 25
        min_expected_probability: 0.65
        min_minutes_to_close: 1
        max_minutes_to_close: 8

    ETH:
      up_trades:
        enabled: false  # Disable UP (40.9% WR)
      down_trades:
        enabled: true
        min_signal_strength: 30  # Stricter for ETH
        min_expected_probability: 0.70
        min_minutes_to_close: 3  # ETH best at 3-5 min
        max_minutes_to_close: 5
```

## Implementation Changes Required

### 1. Config Validation (`config_15m.yaml`)
Add new section after line 28:
```yaml
  # Per-symbol direction filters (OPTIONAL - overrides allowed_trends)
  symbol_configs:
    SOL:
      allowed_trends: ["up", "down"]
      min_signal_strength: 25
    BTC:
      allowed_trends: ["down"]
      min_signal_strength: 25
    ETH:
      allowed_trends: ["down"]
      min_signal_strength: 30
```

### 2. Code Changes (`market_scanner_15m.py`)

**Current logic:**
```python
# Global trend filter (line ~300)
allowed_trends = self.config['strategy'].get('allowed_trends', ['up', 'down', 'flat'])
if momentum['direction'] not in allowed_trends:
    self._skip_trade(ticker, "Trend Filter", f"{momentum['direction']} not in allowed_trends")
    return None
```

**New logic:**
```python
# Per-symbol trend filter
symbol = market_data['ticker'].split('15M')[0].replace('KX', '')  # Extract BTC/ETH/SOL
symbol_config = self.config['strategy'].get('symbol_configs', {}).get(symbol, {})

# Use symbol-specific or fall back to global
allowed_trends = symbol_config.get('allowed_trends',
                                    self.config['strategy'].get('allowed_trends', ['up', 'down', 'flat']))

if momentum['direction'] not in allowed_trends:
    self._skip_trade(ticker, "Trend Filter",
                     f"{symbol} {momentum['direction']} not in allowed_trends {allowed_trends}")
    return None

# Apply symbol-specific signal threshold
min_signal = symbol_config.get('min_signal_strength',
                                self.config['strategy'].get('min_signal_strength', 25))
if signal_strength < min_signal:
    self._skip_trade(ticker, "Low Signal", f"{signal_strength:.1f} < {min_signal}")
    return None
```

## Recommended Approach

**Use Option A (Simple)** - it provides 90% of the benefit with minimal complexity:
1. Add `symbol_configs` to config
2. Modify trend filter logic in scanner (5 lines of code)
3. Test with SOL both directions, BTC/ETH down only

**Reserve Option B (Advanced)** for later if you want different time windows per symbol/direction.

## Expected Impact

### Current Config (DOWN only, all symbols)
- Trades/month: ~1,590 (3-5 min) or 4,410 (1-8 min)
- Win Rate: 99.3-100%
- Assets: BTC, ETH, SOL (all DOWN)

### With Per-Symbol Filters (SOL both directions)
- Additional SOL UP trades: ~130/month
- SOL UP Win Rate: 84.6% (3-5 min window)
- Additional Monthly PnL: +$300-400
- **Total increase: +8-10% more trades with 84.6% WR**

## Testing Plan
1. Week 1: Add config, test SOL UP in 3-5 min window only
2. Week 2: If successful, expand SOL UP to 1-8 min window
3. Week 3: Monitor and validate 84.6% WR holds
4. Week 4: Consider adding per-direction time windows (Option B)
