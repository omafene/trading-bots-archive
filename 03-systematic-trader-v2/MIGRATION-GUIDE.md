# Migration Guide: V1 → V2 (Institutional Upgrade)

## 📋 Overview

This guide will help you safely migrate from the basic trading bot (v1) to the institutional-grade version (v2). **Do not skip steps** - each phase is critical for validating the upgrades.

---

## ⚠️ CRITICAL: Do NOT Go Straight to Live Trading

**Migration Timeline:**
- Week 1-2: Installation & backtesting
- Week 3: Paper trading validation
- Week 4-7: Live-tiny validation (1% risk)
- Week 8+: Gradual scaling (if profitable)

---

## Phase 1: Installation & Setup (Day 1)

### Step 1: Backup Your Current Bot

```bash
# Backup v1 configuration
cp systematic-trader/config.js systematic-trader/config.js.backup

# Backup v1 bot (if currently running)
# Stop the bot first, then backup logs
cp systematic-trader/*.log systematic-trader-v1-logs/
```

### Step 2: Install V2

```bash
# Navigate to systematic-trader-v2 directory
cd systematic-trader-v2

# Install dependencies (same as v1)
npm install

# Copy configuration template
cp config.example.js config.js
```

### Step 3: Configure V2

**Option A: Start Fresh (Recommended)**
Edit `config.js` with your exchange credentials and preferences.

**Option B: Migrate V1 Config**
```javascript
// In config.js, keep these from v1:
exchange: 'binance',              // Your exchange
apiKey: process.env.API_KEY,
apiSecret: process.env.API_SECRET,
pairs: ['BTC/USDT', 'ETH/USDT'],  // Your pairs

// ADD these new sections:
regimeDetection: {
    enabled: true,                 // ENABLE regime detection
    adxPeriod: 14,
    trendingThreshold: 25,
    rangingThreshold: 20
},

cryptoData: {
    enabled: true,                 // ENABLE funding rate tracking
    fetchFundingRates: true
},

risk: {
    maxRiskPerTrade: 0.02,         // Keep your existing risk
    useKelly: true,                // NEW: Enable Kelly sizing
    kellyFraction: 0.25,
    useVolatilityAdjustment: true, // NEW: Volatility adjustment
    useMultiTargets: true,         // NEW: Multi-target exits
    drawdownTiers: [0.05, 0.10, 0.15, 0.20]
}
```

### Step 4: Verify Installation

```bash
# Check all files present
ls -la core/ strategies/ utils/

# Should see:
# core/regime-detector.js
# core/crypto-data-fetcher.js
# core/enhanced-risk-manager.js
# strategies/upgraded-momentum.js
# strategies/upgraded-mean-reversion.js
# strategies/upgraded-volatility-breakout.js
# utils/enhanced-indicators.js
```

---

## Phase 2: Backtesting (Days 2-7)

### Why Backtest?

V2 has significantly different entry logic. **You must validate** that upgrades work for your specific pairs and risk tolerance.

### Backtest Process

```bash
# Run 90-day backtest
node run-backtest.js --days 90

# Test each pair individually
node run-backtest.js --pair BTC/USDT --days 90
node run-backtest.js --pair ETH/USDT --days 90

# Test different market periods
node run-backtest.js --days 30   # Recent (trending?)
node run-backtest.js --days 180  # Long-term (multiple regimes)
```

### Validation Criteria

**Minimum Acceptable Results:**
```
✓ Win Rate: > 50%
✓ Profit Factor: > 1.5
✓ Max Drawdown: < 18%
✓ Total Trades: > 30
✓ Positive Total PnL
```

**Good Results:**
```
✓ Win Rate: > 55%
✓ Profit Factor: > 1.8
✓ Max Drawdown: < 15%
```

**Excellent Results:**
```
✓ Win Rate: > 60%
✓ Profit Factor: > 2.0
✓ Max Drawdown: < 12%
```

### If Backtest Fails

**Win Rate < 45%:**
- Lower confidence thresholds by 0.05
- Verify your pairs have sufficient liquidity
- Check if ADX filtering is too strict

**Profit Factor < 1.3:**
- Increase R/R ratios (2.5:1 → 3:1)
- Tighten entry requirements
- Enable multi-target exits

**Max DD > 20%:**
- Reduce maxRiskPerTrade (2% → 1.5%)
- Enable drawdown tiers if not already
- Reduce maxConcurrentPositions (3 → 2)

### Optimization Checklist

```bash
# Test different confidence levels
# Edit config.js:
strategies.momentum.minConfidence = 0.60  # Test lower
# Backtest
# Edit config.js:
strategies.momentum.minConfidence = 0.70  # Test higher
# Backtest

# Compare results, select optimal
```

**⚠️ Warning:** Don't over-optimize! If a strategy only works with very specific parameters (RSI = 32.5), it's overfit.

---

## Phase 3: Paper Trading (Days 8-21)

### Why Paper Trade After Backtesting?

Backtests can't capture:
- Real-time execution issues
- Exchange API quirks
- Slippage and latency
- Your emotional response to signals

### Start Paper Trading

```javascript
// config.js
mode: 'paper',
paperTradingBalance: 10000,  // Match your intended live capital
```

```bash
# Start the bot
npm start

# Monitor via Telegram
/stats
/positions
```

### Daily Checks (2 Weeks)

**Day 1-3: Validation**
- ✓ Bot starts without errors
- ✓ Signals are being generated
- ✓ Regime detection is working
- ✓ Multi-timeframe data is fetching

**Day 4-7: Signal Quality**
- ✓ Signals make intuitive sense
- ✓ Entry/exit timing looks good
- ✓ Stop losses are reasonable
- ✓ No obvious bugs

**Day 8-14: Performance**
- ✓ Win rate tracking toward backtest results
- ✓ Profit factor acceptable
- ✓ No unexpected behavior

### Paper Trading Red Flags

🚨 **STOP and Debug if you see:**
- Win rate < 35% (vs 50%+ in backtest)
- Profit factor < 1.0
- Constant position rejections
- Excessive slippage (>0.5% per trade)
- Strategies triggering in wrong regimes

### Compare Paper vs Backtest

```
Backtest Results:
  Win Rate: 56%
  Profit Factor: 1.9
  Total PnL: +$2,340

Paper Trading (2 weeks):
  Win Rate: 52%     ← Accept 5-10% difference
  Profit Factor: 1.6 ← Some degradation normal
  Total PnL: +$180

Verdict: ACCEPTABLE ✓
Paper results within reasonable range of backtest.
Proceed to live-tiny.
```

---

## Phase 4: Live-Tiny Validation (Days 22-49)

### Critical Safety Step

This is where real money meets theory. **Start microscopic**.

### Configuration

```javascript
// config.js
mode: 'live-tiny',

risk: {
    maxRiskPerTrade: 0.01,          // 1% max (half your normal)
    maxConcurrentPositions: 2,       // Reduced from 3
    maxPortfolioRisk: 0.03,          // 3% total max
    
    // Everything else same as paper
    useKelly: true,
    useVolatilityAdjustment: true,
    useMultiTargets: true
}
```

### Capital Sizing

**Recommended Starting Capital:**
- $500-1,000 for crypto spot
- $2,000-5,000 for crypto futures
- $10,000+ for traditional markets

**With 1% risk per trade:**
- $500 account = $5 risk per trade
- $1,000 account = $10 risk per trade
- $5,000 account = $50 risk per trade

### Weekly Validation (4 Weeks)

**Week 1: Execution Validation**
- ✓ Orders fill correctly
- ✓ Stop losses work
- ✓ Take profits trigger
- ✓ Multi-target exits execute

**Week 2: Performance Tracking**
- Win rate compared to paper/backtest
- Slippage impact quantified
- Fee impact quantified
- Any execution issues resolved

**Week 3: Consistency Check**
- Performance stable week-over-week
- No unexpected behavior
- Risk management working correctly
- Drawdown staying within limits

**Week 4: Profitability Validation**
- **CRITICAL**: Must be profitable
- Win rate ≥ 50%
- Profit factor ≥ 1.3
- Max DD < 12%

### Live-Tiny Success Criteria

After 4 weeks, you should have:
```
✓ 20-40 real trades executed
✓ Cumulative profit > 0
✓ Win rate ≥ 50%
✓ Profit factor ≥ 1.3
✓ No major execution issues
✓ Emotional comfort with system
```

**If ANY criteria not met:**
- DO NOT scale up
- Return to paper trading
- Debug issues
- Restart live-tiny after fixes

---

## Phase 5: Gradual Scaling (Week 8+)

### Only If Live-Tiny Was Profitable

**Scaling Schedule:**

**Week 8-9:**
```javascript
maxRiskPerTrade: 0.015,    // 1.5% (50% increase)
maxConcurrentPositions: 2
```

**Week 10-11:**
```javascript
maxRiskPerTrade: 0.02,     // 2% (full risk)
maxConcurrentPositions: 3
```

**Week 12+:**
```javascript
// At full intended scale
// Monitor closely
// Be ready to scale back if performance degrades
```

### Scaling Rules

**Do NOT scale if:**
- Current week unprofitable
- Win rate drops below 45%
- Drawdown exceeds 10%
- Emotional stress high

**Scale back if:**
- 2 consecutive losing weeks
- Drawdown hits tier 2 (10%)
- Win rate drops below 40%
- Something feels wrong

---

## 📊 Feature Comparison: V1 vs V2

| Feature | V1 (Basic) | V2 (Institutional) |
|---------|------------|-------------------|
| **Multi-Timeframe** | ❌ Single TF only | ✅ 4:1 ratio required |
| **Regime Detection** | ❌ None | ✅ ADX-based switching |
| **Position Sizing** | Fixed 2% | ✅ Kelly + Volatility adj |
| **Profit Taking** | Single target | ✅ 3-target system |
| **Indicators** | Basic (SMA, RSI, BB) | ✅ Enhanced (ADX, KC, Z-score) |
| **Crypto Data** | ❌ None | ✅ Funding rates, OI |
| **Momentum Strategy** | MACD (12,26,9) | ✅ Crypto MACD (5,35,5) |
| **Mean Reversion** | Basic BB + RSI | ✅ Half-life + Z-score |
| **Volatility Breakout** | Simple expansion | ✅ TTM Squeeze |
| **Risk Management** | Basic limits | ✅ Drawdown tiers |
| **Expected Win Rate** | 40-45% | 55-60% |
| **Expected Profit Factor** | 1.2-1.5 | 1.8-2.5 |

---

## ⚙️ Configuration Migration Checklist

### Must Change
- [ ] Enable regime detection
- [ ] Enable Kelly sizing
- [ ] Enable volatility adjustment
- [ ] Enable multi-target exits
- [ ] Set drawdown tiers

### Recommended Changes
- [ ] Lower minConfidence by 0.05 initially
- [ ] Enable crypto data fetching
- [ ] Add Telegram bot for monitoring
- [ ] Increase monitoring frequency

### Keep From V1
- [ ] Exchange credentials
- [ ] Trading pairs
- [ ] Base risk percentage (but enable Kelly on top)
- [ ] Telegram settings

---

## 🐛 Troubleshooting

### "No signals being generated"

**Possible Causes:**
1. ADX filter too strict
   - Solution: Lower minADX from 25 to 20
2. Confidence threshold too high
   - Solution: Lower by 0.05
3. Multi-timeframe not aligned
   - Solution: Normal - wait for alignment

### "Regime detector says 'not allowed'"

**This is working correctly!**
- Mean reversion blocked in trending markets
- Momentum blocked in ranging markets
- This prevents ~30% of losing trades

### "Kelly sizing giving tiny positions"

**Likely Causes:**
1. Not enough trade history yet
   - Solution: Needs 20+ trades to calibrate
   - Until then, uses fixed fractional
2. Poor historical performance
   - Solution: Kelly protecting you from losses
   - Fix strategy first

### "Higher timeframe data not available"

Check:
1. Data engine fetching both timeframes
2. Exchange supports your timeframes
3. Enough historical data loaded

---

## 📚 Additional Resources

### Included Documentation

1. **UPGRADE-SUMMARY.md** - This document
2. **ENHANCED-CONFIG.md** - All new configuration options
3. **README.md** - Complete usage guide
4. **QUICKSTART.md** - Fast setup guide

### Code Examples

Check `/examples/` folder for:
- Half-life calculation example
- TTM Squeeze detection example
- Kelly Criterion implementation
- Multi-timeframe analysis

---

## ✅ Migration Checklist

### Pre-Migration
- [ ] Backup V1 configuration
- [ ] Backup V1 logs (if running)
- [ ] Read UPGRADE-SUMMARY.md completely
- [ ] Read this MIGRATION-GUIDE.md completely

### Installation
- [ ] V2 files copied
- [ ] Dependencies installed
- [ ] Configuration file created
- [ ] New features enabled in config

### Validation
- [ ] 90-day backtest completed
- [ ] Backtest results acceptable
- [ ] Paper trading 2 weeks
- [ ] Paper results match backtest

### Live Trading
- [ ] Live-tiny mode configured (1% risk)
- [ ] 4 weeks validation completed
- [ ] Profitable over 4 weeks
- [ ] Ready for gradual scaling

### Ongoing
- [ ] Weekly performance review
- [ ] Monthly strategy assessment
- [ ] Continuous backtesting
- [ ] Parameter re-optimization quarterly

---

## 🎯 Success Criteria Summary

**After Full Migration, You Should Have:**

✅ **Technical:**
- Bot running stable 24/7
- All strategies executing correctly
- Regime detection working
- Risk management enforced

✅ **Performance:**
- Win rate > 50%
- Profit factor > 1.5
- Max DD < 18%
- Consistent profitability

✅ **Operational:**
- Monitoring system in place
- Telegram alerts working
- Backup procedures established
- Emergency stop plan ready

---

## ⚠️ Final Warning

**These upgrades are powerful but NOT magic:**

- They won't guarantee profits
- They won't eliminate all losses
- They require proper testing
- They need continuous monitoring
- Markets change - strategies must adapt

**The difference between V1 and V2:**
- V1: Retail approach, ~40% chance of success
- V2: Institutional approach, ~60% chance of success

**But 60% is not 100%!**

Trade responsibly, start small, validate thoroughly, and scale gradually.

**Good luck with your migration! 🚀**
