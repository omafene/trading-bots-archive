/**
 * UPGRADED MOMENTUM STRATEGY
 *
 * Institutional-grade enhancements:
 * - Multi-timeframe alignment (4:1 ratio required)
 * - ADX filtering (only trade when ADX > 25)
 * - Crypto-optimized MACD (5,35,5)
 * - Crypto-optimized RSI (9-10 period)
 * - Enhanced volume confirmation
 * - Higher timeframe trend filter
 * - Regime-aware entry/exit
 */
const EnhancedIndicators = require('../utils/enhanced-indicators');

class UpgradedMomentumStrategy {
    constructor(config = {}) {
        this.name = 'Momentum-Pro';
        this.enabled = config.enabled !== false;
        this.timeframe = config.timeframe || '5m';
        this.minConfidence = config.minConfidence || 0.65;
        
        // Determine higher timeframe (4:1 ratio)
        this.higherTimeframe = this.calculateHigherTimeframe(this.timeframe);
        
        // Crypto-optimized parameters
        this.params = {
            fastMA: config.fastMA || 9,
            slowMA: config.slowMA || 21,
            ema50: 50, // Higher timeframe trend filter
            
            // Crypto-optimized RSI (9-10 vs traditional 14)
            rsiPeriod: config.rsiPeriod || 9,
            rsiOverbought: config.rsiOverbought || 75,  // Raised from 70
            rsiOversold: config.rsiOversold || 25,      // Lowered from 30
            rsiEntryLong: 30,  // RSI crosses above 30
            rsiEntryShort: 70, // RSI crosses below 70
            
            // Crypto-optimized MACD (5,35,5 vs traditional 12,26,9)
            macdFast: config.macdFast || 5,
            macdSlow: config.macdSlow || 35,
            macdSignal: config.macdSignal || 5,
            
            // Volume confirmation
            volumeMultiplier: config.volumeMultiplier || 1.5,
            
            // Trend strength (2% minimum)
            minTrendStrength: config.minTrendStrength || 0.02,
            
            // ADX requirements
            minADX: config.minADX || 25,  // Only trade in trending markets
            maxADX: config.maxADX || 60,  // Avoid exhaustion
            
            ...config.params
        };
        
        // Data storage for multiple timeframes
        this.marketData = new Map();
        
        console.log(`✅ Upgraded Momentum Strategy initialized`);
        console.log(`   Primary: ${this.timeframe} | Higher: ${this.higherTimeframe}`);
        console.log(`   Crypto MACD: (${this.params.macdFast},${this.params.macdSlow},${this.params.macdSignal})`);
        console.log(`   Crypto RSI: ${this.params.rsiPeriod}`);
        console.log(`   ADX Filter: ${this.params.minADX}-${this.params.maxADX}`);
    }

    /**
     * Calculate higher timeframe (4:1 ratio)
     * 1m → 5m, 5m → 15m, 15m → 1h, 1h → 4h
     */
    calculateHigherTimeframe(tf) {
        const map = {
            '1m': '5m',
            '5m': '15m',
            '15m': '1h',
            '30m': '2h',
            '1h': '4h',
            '4h': '1d',
            '1d': '1w'
        };
        return map[tf] || '1h';
    }

    async onCandle(symbol, candle, timeframe) {
        // Store candles for both primary and higher timeframe
        if (!this.marketData.has(symbol)) {
            this.marketData.set(symbol, {
                primary: [],
                higher: []
            });
        }

        const data = this.marketData.get(symbol);
        
        if (timeframe === this.timeframe) {
            data.primary.push(candle);
            if (data.primary.length > 200) {
                data.primary.shift();
            }
        } else if (timeframe === this.higherTimeframe) {
            data.higher.push(candle);
            if (data.higher.length > 200) {
                data.higher.shift();
            }
        }
    }

    async evaluate(symbolOrData, regimeData = null) {
        // DETECT CALLING MODE: Backtest passes dataPackage object, Live passes symbol string
        let symbol, primaryCandles, higherCandles, currentPrice, regimeInfo;

        if (typeof symbolOrData === 'object' && symbolOrData !== null) {
            // BACKTEST MODE: Extract data from dataPackage
            symbol = symbolOrData.pair;
            primaryCandles = symbolOrData.primaryCandles;
            higherCandles = symbolOrData.higherCandles || symbolOrData.primaryCandles;
            currentPrice = symbolOrData.currentPrice;
            regimeInfo = symbolOrData.regimeData;
        } else {
            // LIVE MODE: Use internal marketData
            symbol = symbolOrData;
            regimeInfo = regimeData;
            
            // Initialize data if not exists (defensive)
            if (!this.marketData.has(symbol)) {
                this.marketData.set(symbol, {
                    primary: [],
                    higher: []
                });
            }

            const data = this.marketData.get(symbol);
            
            if (!data || data.primary.length < 50 || data.higher.length < 50) {
                return null;
            }

            primaryCandles = data.primary;
            higherCandles = data.higher;
            currentPrice = null; // Will be extracted from latest candle
        }

        console.log(`      [Momentum] Starting evaluation: primary ${primaryCandles?.length || 0} candles, higher ${higherCandles?.length || 0} candles`);

        // Validate we have enough data
        if (!primaryCandles || primaryCandles.length < 50 || !higherCandles || higherCandles.length < 50) {
            console.log(`      [Momentum] FAILED: Insufficient data`);
            return null;
        }

        // Check regime allows momentum trading
        if (regimeInfo && regimeInfo.allowedStrategies && !regimeInfo.allowedStrategies.includes('Momentum-Pro')) {
            console.log(`      [Momentum] FAILED: Not allowed in ${regimeInfo.regime} regime`);
            return null;
        }

        const latest = primaryCandles[primaryCandles.length - 1];
        if (!currentPrice) currentPrice = latest.close;

        // Calculate indicators - Primary timeframe
        const closes = primaryCandles.map(c => c.close);
        const highs = primaryCandles.map(c => c.high);
        const lows = primaryCandles.map(c => c.low);
        const volumes = primaryCandles.map(c => c.volume);

        const fastMA = EnhancedIndicators.sma(closes, this.params.fastMA);
        const slowMA = EnhancedIndicators.sma(closes, this.params.slowMA);
        const rsi = EnhancedIndicators.rsi(closes, this.params.rsiPeriod);
        const macd = EnhancedIndicators.macd(
            closes,
            this.params.macdFast,
            this.params.macdSlow,
            this.params.macdSignal
        );
        const avgVolume = EnhancedIndicators.sma(volumes, 20);

        // Calculate ADX - CRITICAL for regime filtering
        const adx = EnhancedIndicators.adx(highs, lows, closes, 14);

        // Higher timeframe trend filter
        const higherCloses = higherCandles.map(c => c.close);
        const ema50Higher = EnhancedIndicators.ema(higherCloses, this.params.ema50);

        if (!fastMA || !slowMA || !rsi || !macd || !adx || !ema50Higher) {
            return null;
        }

        currentPrice = latest.close;
        const currentVolume = latest.volume;

        // ========== ADX FILTER (MOST IMPORTANT) ==========
        // Only take momentum trades in trending markets
        if (adx.adx < this.params.minADX) {
            return null; // Not trending enough
        }
        if (adx.adx > this.params.maxADX) {
    console.log(`      [Momentum] BLOCKED: ADX ${adx.adx.toFixed(1)} > ${this.params.maxADX} (trend exhaustion)`);
    return null; // Trend exhaustion
        }

        let signal = null;
        let confidence = 0;
        let reasons = [];

        // ========== LONG SETUP ==========
        if (this.detectBullishMomentum(
            currentPrice, fastMA, slowMA, rsi, macd,
            currentVolume, avgVolume, adx, ema50Higher, higherCloses
        )) {
            // Base confidence from trend strength
            const trendStrength = (fastMA - slowMA) / slowMA;
            confidence = Math.min(trendStrength / this.params.minTrendStrength, 1.0) * 0.25;

            // RSI confirmation (crosses above 30)
            if (rsi > this.params.rsiEntryLong && rsi < this.params.rsiOverbought) {
                confidence += 0.20;
                reasons.push(`RSI bullish: ${rsi.toFixed(1)}`);
            }

            // MACD confirmation (histogram positive)
            if (macd.histogram > 0) {
                confidence += 0.15;
                reasons.push('MACD bullish histogram');
            }

            // MACD crossover (extra boost)
            if (macd.macd > macd.signal) {
                confidence += 0.10;
                reasons.push('MACD crossover');
            }

            // Volume confirmation
            const volumeRatio = currentVolume / avgVolume;
            if (volumeRatio > this.params.volumeMultiplier) {
                confidence += 0.15;
                reasons.push(`Volume: ${volumeRatio.toFixed(2)}x`);
            }

            // ADX strength bonus
            if (adx.adx > 30) {
                confidence += 0.10;
                reasons.push(`Strong trend ADX: ${adx.adx.toFixed(1)}`);
            }

            // Higher timeframe alignment (CRITICAL)
            const higherPrice = higherCloses[higherCloses.length - 1];
            if (higherPrice > ema50Higher) {
                confidence += 0.20;
                reasons.push('Higher TF CONFIRMED');
            } else {
               // HARD REJECT if higher TF doesn't align
                //OLD confidence *= 0.7; // Penalty for misalignment
                //OLD reasons.push('Higher TF not aligned (reduced confidence)');
              console.log(`      [Momentum] REJECTED: Higher TF not aligned`);
              return null;  // Don't trade against higher TF
            }

      // Cap confidence at 90% (over-confident trades lose)
            confidence = Math.min(confidence, 1.00);            
if (confidence >= this.minConfidence) {
                const stopDistance = this.calculateStopDistance(primaryCandles, 'long', adx);
                
                signal = {
                    symbol,
                    side: 'sell',
                    action: 'SELL',  // For backtest compatibility
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 + stopDistance),
                    takeProfit: currentPrice * (1 - stopDistance * 2.5), // 2.5:1 R/R
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        fastMA: fastMA.toFixed(6),
                        slowMA: slowMA.toFixed(6),
                        rsi: rsi.toFixed(2),
                        macd: macd.histogram.toFixed(6),
                        adx: adx.adx.toFixed(2),
                        volumeRatio: volumeRatio.toFixed(2),
                        higherTrendAligned: higherPrice > ema50Higher
                    }
                };
            }
        }

        // ========== SHORT SETUP ==========
        else if (this.detectBearishMomentum(
            currentPrice, fastMA, slowMA, rsi, macd,
            currentVolume, avgVolume, adx, ema50Higher, higherCloses
        )) {
            const trendStrength = (slowMA - fastMA) / slowMA;
            confidence = Math.min(trendStrength / this.params.minTrendStrength, 1.0) * 0.25;

            if (rsi < this.params.rsiEntryShort && rsi > this.params.rsiOversold) {
                confidence += 0.20;
                reasons.push(`RSI bearish: ${rsi.toFixed(1)}`);
            }

            if (macd.histogram < 0) {
                confidence += 0.15;
                reasons.push('MACD bearish histogram');
            }

            if (macd.macd < macd.signal) {
                confidence += 0.10;
                reasons.push('MACD crossunder');
            }

            const volumeRatio = currentVolume / avgVolume;
            if (volumeRatio > this.params.volumeMultiplier) {
                confidence += 0.15;
                reasons.push(`Volume: ${volumeRatio.toFixed(2)}x`);
            }

            if (adx.adx > 30) {
                confidence += 0.10;
                reasons.push(`Strong trend ADX: ${adx.adx.toFixed(1)}`);
            }

            const higherPrice = higherCloses[higherCloses.length - 1];
            if (higherPrice < ema50Higher) {
                confidence += 0.20;
                reasons.push('Higher TF bearish CONFIRMED');
            } else {
            // HARD REJECT if higher TF doesn't align
    console.log(`      [Momentum] REJECTED: Higher TF not aligned`);
    return null;  // Don't trade against higher TF
            }

// Cap confidence at 90% (over-confident trades lose)
            confidence = Math.min(confidence, 0.90);

            if (confidence >= this.minConfidence) {
                const stopDistance = this.calculateStopDistance(primaryCandles, 'short', adx);
                
                signal = {
                    symbol,
                    side: 'buy',
                    action: 'BUY',  // For backtest compatibility
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 - stopDistance),
                    takeProfit: currentPrice * (1 + stopDistance * 2.5),
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        fastMA: fastMA.toFixed(6),
                        slowMA: slowMA.toFixed(6),
                        rsi: rsi.toFixed(2),
                        macd: macd.histogram.toFixed(6),
                        adx: adx.adx.toFixed(2),
                        volumeRatio: volumeRatio.toFixed(2),
                        higherTrendAligned: higherPrice < ema50Higher
                    }
                };
            }
        }

        console.log(`      [Momentum] Evaluation complete: ${signal ? signal.action : 'HOLD'} ${signal ? `(confidence: ${(signal.confidence * 100).toFixed(1)}%)` : ''}`);
        return signal;
    }

    detectBullishMomentum(price, fastMA, slowMA, rsi, macd, volume, avgVolume, adx, ema50Higher, higherCloses) {
        // Golden cross
        if (fastMA <= slowMA) return false;
        
        // Price above fast MA
        if (price < fastMA) return false;
        
        // RSI not overbought
        if (rsi >= this.params.rsiOverbought) return false;
        
        // MACD bullish
        if (macd.histogram <= 0) return false;
        
        // Higher timeframe aligned (price above EMA50)
        const higherPrice = higherCloses[higherCloses.length - 1];
        if (higherPrice < ema50Higher) return false;
        
        return true;
    }

    detectBearishMomentum(price, fastMA, slowMA, rsi, macd, volume, avgVolume, adx, ema50Higher, higherCloses) {
        // Death cross
        if (fastMA >= slowMA) return false;
        
        // Price below fast MA
        if (price > fastMA) return false;
        
        // RSI not oversold
        if (rsi <= this.params.rsiOversold) return false;
        
        // MACD bearish
        if (macd.histogram >= 0) return false;
        
        // Higher timeframe aligned (price below EMA50)
        const higherPrice = higherCloses[higherCloses.length - 1];
        if (higherPrice > ema50Higher) return false;
        
        return true;
    }

    calculateStopDistance(candles, side, adx) {
        // Dynamic stop based on volatility
        const closes = candles.slice(-20).map(c => c.close);
        const atr = EnhancedIndicators.atr(
            candles.slice(-20).map(c => c.high),
            candles.slice(-20).map(c => c.low),
            closes,
            14
        );
        
        const currentPrice = closes[closes.length - 1];
        
let stopMultiplier = 3.0; // Base 3 ATR (crypto needs wider stops)
        
        // WIDER stops in volatile/strong trends
        if (adx.adx > 50) {
            stopMultiplier = 3.5;  // Very strong trend = give it room
        } else if (adx.adx < 30) {
            stopMultiplier = 2.5;  // Weak trend = slightly tighter
        }
        return (atr / currentPrice) * stopMultiplier;
    }
}

module.exports = UpgradedMomentumStrategy;
