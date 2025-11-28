/**
 * REGIME DETECTOR
 * 
 * Detects market regimes using ADX and determines which strategies to trade
 */
const EnhancedIndicators = require('../utils/enhanced-indicators');

class RegimeDetector {
    constructor(config = {}) {
        this.adxPeriod = config.adxPeriod || 14;
        this.regimeHistory = new Map();
        
        // Regime thresholds
        this.thresholds = {
            ranging: config.rangingThreshold || 20,
            trending: config.trendingThreshold || 40,
            strong: config.strongThreshold || 60
        };
        
        console.log('✅ Regime Detector initialized');
        console.log(`   ADX Period: ${this.adxPeriod}`);
        console.log(`   Ranging: ADX < ${this.thresholds.ranging}`);
        console.log(`   Trending: ADX ${this.thresholds.ranging}-${this.thresholds.trending}`);
        console.log(`   Strong Trend: ADX > ${this.thresholds.trending}`);
    }

    /**
     * Detect current market regime
     */
    detectRegime(symbol, candles) {
        if (!candles || candles.length < 50) {
            return null;
        }

        const highs = candles.map(c => c.high);
        const lows = candles.map(c => c.low);
        const closes = candles.map(c => c.close);

        const adxData = EnhancedIndicators.adx(highs, lows, closes, this.adxPeriod);
        
        if (!adxData) {
            return null;
        }

        const { adx, plusDI, minusDI } = adxData;
        
        // Store ADX for comparison
        this.storeCurrentADX(symbol, adx);

        // Determine regime
        let regime, allowedStrategies, positionSizeMultiplier, description;

        // EXHAUSTION: Very high ADX with weakening momentum
        const prevADX = this.getPreviousADX(symbol);
        if (adx > 70 && prevADX && adx < prevADX) {
            regime = 'EXHAUSTION';
            allowedStrategies = [];  // No new positions
            positionSizeMultiplier = 0.5;
            description = 'Trend exhaustion - Prepare for reversal';
        }
        // EXTREME_TREND: Very strong trend
        else if (adx > 60) {
            regime = 'EXTREME_TREND';
            allowedStrategies = ['Momentum-Pro'];
            positionSizeMultiplier = 0.7;  // Reduce size at extremes
            description = 'Extreme trend - Reduced size momentum only';
        }
        // STRONG_TREND: Strong trend
        else if (adx > 40) {
            regime = 'STRONG_TREND';
            allowedStrategies = ['Momentum-Pro'];
            positionSizeMultiplier = 1.2;  // Aggressive
            description = 'Very strong trend - Aggressive momentum';
        }
        // TRENDING: Moderate trend
        else if (adx > 25) {
            regime = 'TRENDING';
            allowedStrategies = ['Momentum-Pro', 'VolatilityBreakout-Pro'];
            positionSizeMultiplier = 1.0;
            description = 'Strong trend - Full momentum strategies';
        }
        // WEAK_TREND: Emerging or weakening trend
        else if (adx > 20) {
            regime = 'WEAK_TREND';
            allowedStrategies = ['Momentum-Pro', 'MeanReversion-Pro'];
            positionSizeMultiplier = 0.8;
            description = 'Emerging trend - Cautious momentum + mean reversion';
        }
        // RANGING: Low ADX, sideways market
        else {
            regime = 'RANGING';
            allowedStrategies = ['MeanReversion-Pro'];
            positionSizeMultiplier = 0.9;
            description = 'Weak/sideways market - Mean reversion only';
        }

        // Determine trend direction
        let trendDirection = 'NEUTRAL';
        if (plusDI > minusDI + 5) {
            trendDirection = 'BULLISH';
        } else if (minusDI > plusDI + 5) {
            trendDirection = 'BEARISH';
        }

        const regimeData = {
            symbol,
            regime,
            adx,
            plusDI,
            minusDI,
            trendDirection,
            allowedStrategies,
            positionSizeMultiplier,
            description,
            timestamp: Date.now()
        };

        // Update history
        this.updateRegimeHistory(symbol, regimeData);

        return regimeData;
    }

    /**
     * Store current ADX for next comparison
     */
    storeCurrentADX(symbol, adx) {
        const history = this.regimeHistory.get(symbol);
        if (history && history.current) {
            history.previousADX = history.current.adx;
        }
    }

    /**
     * Get previous ADX value
     */
    getPreviousADX(symbol) {
        return this.regimeHistory.get(symbol)?.previousADX || null;
    }

    /**
     * Update regime history for tracking regime changes
     */
    updateRegimeHistory(symbol, regimeData) {
        if (!this.regimeHistory.has(symbol)) {
            this.regimeHistory.set(symbol, {
                current: null,
                previous: null,
                history: []
            });
        }

        const history = this.regimeHistory.get(symbol);

        // Defensive: Ensure history array exists
        if (!history.history) {
            history.history = [];
        }

        // Detect regime change
        if (history.current && history.current.regime !== regimeData.regime) {
            console.log(`\n🔄 REGIME CHANGE: ${symbol}`);
            console.log(`   ${history.current.regime} → ${regimeData.regime}`);
            console.log(`   ADX: ${history.current.adx.toFixed(2)} → ${regimeData.adx.toFixed(2)}`);
            console.log(`   ${regimeData.description}\n`);
        }

        history.previous = history.current;
        history.current = regimeData;
        history.history.push(regimeData);

        // Keep only last 100 regime records
        if (history.history.length > 100) {
            history.history.shift();
        }
    }

    /**
     * Get current regime for a symbol
     */
    getCurrentRegime(symbol) {
        const history = this.regimeHistory.get(symbol);
        return history?.current || null;
    }

    /**
     * Check if a strategy is allowed in current regime
     */
    isStrategyAllowed(symbol, strategyType) {
        const regime = this.getCurrentRegime(symbol);
        if (!regime) return true;  // Allow by default if no regime data
        
        return regime.allowedStrategies.includes(strategyType);
    }

    /**
     * Get position size multiplier for current regime
     */
    getPositionSizeMultiplier(symbol) {
        const regime = this.getCurrentRegime(symbol);
        return regime?.positionSizeMultiplier || 1.0;
    }

    /**
     * Get regime statistics
     */
    getRegimeStats(symbol) {
        const history = this.regimeHistory.get(symbol);
        if (!history || !history.history || history.history.length === 0) {
            return null;
        }

        const regimes = history.history;
        const regimeCounts = {};
        
        regimes.forEach(r => {
            regimeCounts[r.regime] = (regimeCounts[r.regime] || 0) + 1;
        });

        const totalRegimes = regimes.length;
        const regimePercentages = {};
        
        Object.keys(regimeCounts).forEach(regime => {
            regimePercentages[regime] = (regimeCounts[regime] / totalRegimes) * 100;
        });

        return {
            current: history.current,
            counts: regimeCounts,
            percentages: regimePercentages,
            totalRecords: totalRegimes
        };
    }

    /**
     * Reset history for a symbol
     */
    resetHistory(symbol) {
        this.regimeHistory.delete(symbol);
    }

    /**
     * Reset all history
     */
    resetAllHistory() {
        this.regimeHistory.clear();
    }

    /**
     * Get regime change count
     */
    getRegimeChangeCount(symbol) {
        const history = this.regimeHistory.get(symbol);
        if (!history || !history.history || history.history.length < 2) {
            return 0;
        }

        let changes = 0;
        for (let i = 1; i < history.history.length; i++) {
            if (history.history[i].regime !== history.history[i-1].regime) {
                changes++;
            }
        }

        return changes;
    }

    /**
     * Get average regime duration
     */
    getAverageRegimeDuration(symbol) {
        const history = this.regimeHistory.get(symbol);
        if (!history || !history.history || history.history.length < 2) {
            return null;
        }

        const durations = [];
        let currentRegime = history.history[0].regime;
        let currentCount = 1;

        for (let i = 1; i < history.history.length; i++) {
            if (history.history[i].regime === currentRegime) {
                currentCount++;
            } else {
                durations.push(currentCount);
                currentRegime = history.history[i].regime;
                currentCount = 1;
            }
        }

        if (durations.length === 0) return null;

        const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
        return avgDuration;
    }
}

module.exports = RegimeDetector;
