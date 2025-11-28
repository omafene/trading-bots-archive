/**
 * UPGRADED MEAN REVERSION STRATEGY
 *
 * Institutional-grade enhancements:
 * - Statistical mean reversion (half-life calculation)
 * - Z-score entry/exit
 * - Bollinger Bands confirmation
 * - RSI oversold/overbought
 * - Volume spike confirmation
 * - Candlestick pattern recognition
 * - Only trades in ranging markets (ADX < 20)
 */
const EnhancedIndicators = require('../utils/enhanced-indicators');

class UpgradedMeanReversionStrategy {
    constructor(config = {}) {
        this.name = 'MeanReversion-Pro';
        this.enabled = config.enabled !== false;
        this.timeframe = config.timeframe || '15m';
        this.minConfidence = config.minConfidence || 0.60;
        
        this.params = {
            // Z-Score thresholds
            zScoreEntry: config.zScoreEntry || 1.6,   // Enter when |z| > 2, now 1.6
            zScoreExit: config.zScoreExit || 0.5,     // Exit when |z| < 0.5
            
            // Half-life calculation
            minHalfLife: config.minHalfLife || 3,     // Minimum 3 bars
            maxHalfLife: config.maxHalfLife || 200,   // Maximum 200 bars
            lookbackPeriod: config.lookbackPeriod || 100,
            
            // Bollinger Bands
            bbPeriod: config.bbPeriod || 20,
            bbStdDev: config.bbStdDev || 2,
            
            // RSI
            rsiPeriod: config.rsiPeriod || 14,
            rsiOversold: config.rsiOversold || 30,
            rsiOverbought: config.rsiOverbought || 70,
            
            // Volume
            volumeMultiplier: config.volumeMultiplier || 1.3,
            
            // ADX - only trade in ranging markets
            maxADX: config.maxADX || 20,
            
            ...config.params
        };
        
        this.marketData = new Map();
        
        console.log(`✅ Upgraded Mean Reversion Strategy initialized (${this.timeframe})`);
        console.log(`   Half-Life Range: ${this.params.minHalfLife}-${this.params.maxHalfLife} bars`);
        console.log(`   Z-Score Threshold: ${this.params.zScoreEntry}`);
        console.log(`   ADX Filter: < ${this.params.maxADX} (ranging only)`);
    }

    async onCandle(symbol, candle, timeframe) {
        if (timeframe !== this.timeframe) return;
        
        if (!this.marketData.has(symbol)) {
            this.marketData.set(symbol, []);
        }
        
        const data = this.marketData.get(symbol);
        data.push(candle);
        
        if (data.length > this.params.lookbackPeriod + 50) {
            data.shift();
        }
    }

    async evaluate(symbolOrData, regimeData = null) {
        // DETECT CALLING MODE: Backtest passes dataPackage object, Live passes symbol string
        let symbol, candles, currentPrice, regimeInfo;

        if (typeof symbolOrData === 'object' && symbolOrData !== null) {
            // BACKTEST MODE: Extract data from dataPackage
            symbol = symbolOrData.pair;
            candles = symbolOrData.primaryCandles;
            currentPrice = symbolOrData.currentPrice;
            regimeInfo = symbolOrData.regimeData;
        } else {
            // LIVE MODE: Use internal marketData
            symbol = symbolOrData;
            regimeInfo = regimeData;
            
            if (!this.marketData.has(symbol)) {
                this.marketData.set(symbol, []);
            }

            candles = this.marketData.get(symbol);
            
            if (!candles || candles.length < this.params.lookbackPeriod) {
                return null;
            }
            
            currentPrice = null; // Will be extracted from latest candle
        }

        console.log(`      [MeanRev] Starting evaluation: ${candles ? candles.length : 0} candles, price: ${currentPrice}`);

        // Validate we have enough data
        if (!candles || candles.length < this.params.lookbackPeriod) {
            console.log(`      [MeanRev] FAILED: Insufficient data (need ${this.params.lookbackPeriod}, have ${candles?.length || 0})`);
            return null;
        }

        // Check regime allows mean reversion (ranging markets only)
        if (regimeInfo && regimeInfo.allowedStrategies && !regimeInfo.allowedStrategies.includes('MeanReversion-Pro')) {
            console.log(`      [MeanRev] FAILED: Not allowed in ${regimeInfo.regime} regime (allowed: ${regimeInfo.allowedStrategies.join(', ')})`);
            return null;
        }

        const latest = candles[candles.length - 1];
        if (!currentPrice) currentPrice = latest.close;

        // Calculate indicators
        const closes = candles.map(c => c.close);
        const highs = candles.map(c => c.high);
        const lows = candles.map(c => c.low);
        const volumes = candles.map(c => c.volume);

        // Z-Score calculation
        const lookbackCloses = closes.slice(-this.params.lookbackPeriod);
        const mean = lookbackCloses.reduce((a, b) => a + b, 0) / lookbackCloses.length;
        const variance = lookbackCloses.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / lookbackCloses.length;
        const stdDev = Math.sqrt(variance);
        const zScore = (currentPrice - mean) / stdDev;

        // Half-life calculation (mean reversion speed)
        const halfLife = this.calculateHalfLife(lookbackCloses);
        
        if (halfLife < this.params.minHalfLife || halfLife > this.params.maxHalfLife) {
            console.log(`      [MeanRev] FAILED: Half-life ${halfLife.toFixed(1)} outside range ${this.params.minHalfLife}-${this.params.maxHalfLife}`);
            return null; // Not mean-reverting enough or too slow
        }

        // Bollinger Bands
        const bb = EnhancedIndicators.bollingerBands(closes, this.params.bbPeriod, this.params.bbStdDev);
        
        // RSI
        const rsi = EnhancedIndicators.rsi(closes, this.params.rsiPeriod);
        
        // Volume
        const avgVolume = EnhancedIndicators.sma(volumes, 20);
        const volumeRatio = latest.volume / avgVolume;
        
        // ADX - only trade in ranging markets
        const adx = EnhancedIndicators.adx(highs, lows, closes, 14);
        
        if (!bb || !rsi || !adx) {
            console.log(`      [MeanRev] FAILED: Missing indicators (BB:${!!bb}, RSI:${!!rsi}, ADX:${!!adx})`);
            return null;
        }

        // Reject if market is trending (ADX too high)
        if (adx.adx > this.params.maxADX) {
            console.log(`      [MeanRev] FAILED: ADX ${adx.adx.toFixed(2)} > ${this.params.maxADX} (market trending, not ranging)`);
            return null;
        }

        let signal = null;
        let confidence = 0;
        let reasons = [];

        // ========== LONG SETUP (Price oversold, expect bounce) ==========
        if (zScore < -this.params.zScoreEntry) {
            // Base confidence from z-score
            confidence = Math.min(Math.abs(zScore) / 3.0, 1.0) * 0.30;
            reasons.push(`Z-Score: ${zScore.toFixed(2)}`);

            // Bollinger Band confirmation
            if (currentPrice <= bb.lower) {
                confidence += 0.20;
                reasons.push('Price at lower BB');
            }

            // RSI oversold
            if (rsi < this.params.rsiOversold) {
                confidence += 0.15;
                reasons.push(`RSI oversold: ${rsi.toFixed(1)}`);
            }

            // Volume spike (panic selling)
            if (volumeRatio > this.params.volumeMultiplier) {
                confidence += 0.15;
                reasons.push(`Volume spike: ${volumeRatio.toFixed(2)}x`);
            }

            // Bullish reversal candle pattern
            const prevCandle = candles[candles.length - 2];
            if (this.isBullishReversal(prevCandle, latest)) {
                confidence += 0.10;
                reasons.push('Bullish reversal candle');
            }

            // Half-life bonus (faster mean reversion = better)
            if (halfLife < 30) {
                confidence += 0.10;
                reasons.push(`Fast mean reversion: ${halfLife.toFixed(0)} bars`);
            }

            if (confidence >= this.minConfidence) {
                const stopDistance = Math.abs(currentPrice - bb.lower) / currentPrice;
                
                signal = {
                    symbol,
                    side: 'buy',
                    action: 'BUY',
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 - stopDistance * 1.5),
                    takeProfit: mean, // Target the mean
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        zScore: zScore.toFixed(2),
                        mean: mean.toFixed(6),
                        halfLife: halfLife.toFixed(1),
                        rsi: rsi.toFixed(2),
                        bbLower: bb.lower.toFixed(6),
                        adx: adx.adx.toFixed(2),
                        volumeRatio: volumeRatio.toFixed(2)
                    }
                };
            }
        }

        // ========== SHORT SETUP (Price overbought, expect pullback) ==========
        else if (zScore > this.params.zScoreEntry) {
            confidence = Math.min(Math.abs(zScore) / 3.0, 1.0) * 0.30;
            reasons.push(`Z-Score: ${zScore.toFixed(2)}`);

            if (currentPrice >= bb.upper) {
                confidence += 0.20;
                reasons.push('Price at upper BB');
            }

            if (rsi > this.params.rsiOverbought) {
                confidence += 0.15;
                reasons.push(`RSI overbought: ${rsi.toFixed(1)}`);
            }

            if (volumeRatio > this.params.volumeMultiplier) {
                confidence += 0.15;
                reasons.push(`Volume spike: ${volumeRatio.toFixed(2)}x`);
            }

            const prevCandle = candles[candles.length - 2];
            if (this.isBearishReversal(prevCandle, latest)) {
                confidence += 0.10;
                reasons.push('Bearish reversal candle');
            }

            if (halfLife < 30) {
                confidence += 0.10;
                reasons.push(`Fast mean reversion: ${halfLife.toFixed(0)} bars`);
            }

            if (confidence >= this.minConfidence) {
                const stopDistance = Math.abs(currentPrice - bb.upper) / currentPrice;
                
                signal = {
                    symbol,
                    side: 'sell',
                    action: 'SELL',
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 + stopDistance * 1.5),
                    takeProfit: mean,
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        zScore: zScore.toFixed(2),
                        mean: mean.toFixed(6),
                        halfLife: halfLife.toFixed(1),
                        rsi: rsi.toFixed(2),
                        bbUpper: bb.upper.toFixed(6),
                        adx: adx.adx.toFixed(2),
                        volumeRatio: volumeRatio.toFixed(2)
                    }
                };
            }
        }

        console.log(`      [MeanRev] Evaluation complete: ${signal ? signal.action : 'HOLD'} ${signal ? `(conf: ${(signal.confidence * 100).toFixed(1)}%, z-score: ${zScore.toFixed(2)})` : `(z-score: ${zScore.toFixed(2)} not extreme enough)`}`);
        return signal;
    }

    calculateHalfLife(prices) {
        // Calculate half-life of mean reversion using Ornstein-Uhlenbeck process
        const n = prices.length;
        let sumLag = 0, sumPrev = 0, sumLagPrev = 0, sumPrevSq = 0;
        
        for (let i = 1; i < n; i++) {
            const lag = prices[i] - prices[i-1];
            const prev = prices[i-1];
            
            sumLag += lag;
            sumPrev += prev;
            sumLagPrev += lag * prev;
            sumPrevSq += prev * prev;
        }
        
        const meanLag = sumLag / (n - 1);
        const meanPrev = sumPrev / (n - 1);
        
        const numerator = sumLagPrev - (n - 1) * meanLag * meanPrev;
        const denominator = sumPrevSq - (n - 1) * meanPrev * meanPrev;
        
        if (denominator === 0) return Infinity;
        
        const lambda = -numerator / denominator;
        
        if (lambda <= 0) return Infinity;
        
        return Math.log(2) / lambda;
    }

    isBullishReversal(prev, current) {
        // Hammer or bullish engulfing
        const prevBody = Math.abs(prev.close - prev.open);
        const currentBody = Math.abs(current.close - current.open);
        const currentLowerShadow = Math.min(current.open, current.close) - current.low;
        
        // Hammer: long lower shadow, small body
        if (currentLowerShadow > currentBody * 2 && current.close > current.open) {
            return true;
        }
        
        // Bullish engulfing
        if (prev.close < prev.open && // Previous red
            current.close > current.open && // Current green
            current.close > prev.open && // Engulfs previous
            current.open < prev.close) {
            return true;
        }
        
        return false;
    }

    isBearishReversal(prev, current) {
        // Shooting star or bearish engulfing
        const prevBody = Math.abs(prev.close - prev.open);
        const currentBody = Math.abs(current.close - current.open);
        const currentUpperShadow = current.high - Math.max(current.open, current.close);
        
        // Shooting star: long upper shadow, small body
        if (currentUpperShadow > currentBody * 2 && current.close < current.open) {
            return true;
        }
        
        // Bearish engulfing
        if (prev.close > prev.open && // Previous green
            current.close < current.open && // Current red
            current.close < prev.open && // Engulfs previous
            current.open > prev.close) {
            return true;
        }
        
        return false;
    }
}

module.exports = UpgradedMeanReversionStrategy;
