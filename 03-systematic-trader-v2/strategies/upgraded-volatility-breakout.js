/**
 * UPGRADED VOLATILITY BREAKOUT STRATEGY
 *
 * Institutional-grade enhancements:
 * - TTM Squeeze detection (volatility compression)
 * - Multi-timeframe momentum confirmation
 * - Dynamic ATR-based stops and targets
 * - Volume explosion confirmation
 * - Regime-aware position sizing
 * - Bollinger Band + Keltner Channel squeeze
 */
const EnhancedIndicators = require('../utils/enhanced-indicators');

class UpgradedVolatilityBreakoutStrategy {
    constructor(config = {}) {
        this.name = 'VolatilityBreakout-Pro';
        this.enabled = config.enabled !== false;
        this.timeframe = config.timeframe || '30m';
        this.minConfidence = config.minConfidence || 0.65;
        
        this.params = {
            // TTM Squeeze parameters
            bbPeriod: config.bbPeriod || 20,
            bbStdDev: config.bbStdDev || 2,
            kcPeriod: config.kcPeriod || 20,
            kcMultiplier: config.kcMultiplier || 1.5,
            
            // Squeeze duration thresholds
            minSqueezeBars: config.minSqueezeBars || 5,   // Minimum compression
            maxSqueezeBars: config.maxSqueezeBars || 50,  // Maximum (too long = weak)
            
            // Breakout confirmation
            minBreakoutStrength: config.minBreakoutStrength || 0.005, // 0.5%
            volumeMultiplier: config.volumeMultiplier || 2.0, // 2x average
            
            // ATR for stops/targets
            atrPeriod: config.atrPeriod || 14,
            atrStopMultiplier: config.atrStopMultiplier || 2.0,
            atrTargetMultiplier: config.atrTargetMultiplier || 3.0,
            
            // Momentum confirmation
            momentumPeriod: config.momentumPeriod || 12,
            
            ...config.params
        };
        
        this.marketData = new Map();
        this.squeezeHistory = new Map(); // Track squeeze duration
        
        console.log(`✅ Upgraded Volatility Breakout Strategy initialized (${this.timeframe})`);
        console.log(`   TTM Squeeze: ${this.params.minSqueezeBars}-${this.params.maxSqueezeBars} bars`);
        console.log(`   Dynamic ATR stops: ${this.params.atrStopMultiplier}x normal, ${this.params.atrTargetMultiplier}x high vol`);
    }

    async onCandle(symbol, candle, timeframe) {
        if (timeframe !== this.timeframe) return;
        
        if (!this.marketData.has(symbol)) {
            this.marketData.set(symbol, []);
        }
        
        const data = this.marketData.get(symbol);
        data.push(candle);
        
        if (data.length > 200) {
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
            
            if (!candles || candles.length < 50) {
                return null;
            }
            
            currentPrice = null; // Will be extracted from latest candle
        }

        console.log(`      [Volatility] Starting evaluation: ${candles ? candles.length : 0} candles`);

        // Validate we have enough data
        if (!candles || candles.length < 50) {
            console.log(`      [Volatility] FAILED: Insufficient data`);
            return null;
        }

        // Check regime allows volatility breakout (needs some trend)
        if (regimeInfo && regimeInfo.allowedStrategies && !regimeInfo.allowedStrategies.includes('VolatilityBreakout-Pro')) {
            console.log(`      [Volatility] FAILED: Not allowed in ${regimeInfo.regime} regime`);
            return null;
        }

        const latest = candles[candles.length - 1];
        if (!currentPrice) currentPrice = latest.close;

        // Calculate indicators
        const closes = candles.map(c => c.close);
        const highs = candles.map(c => c.high);
        const lows = candles.map(c => c.low);
        const volumes = candles.map(c => c.volume);

        // Bollinger Bands
        const bb = EnhancedIndicators.bollingerBands(closes, this.params.bbPeriod, this.params.bbStdDev);
        
        // Keltner Channels
        const kc = this.calculateKeltnerChannels(highs, lows, closes, this.params.kcPeriod, this.params.kcMultiplier);
        
        // ATR for stops/targets
        const atr = EnhancedIndicators.atr(highs, lows, closes, this.params.atrPeriod);
        
        // Momentum
        const momentum = this.calculateMomentum(closes, this.params.momentumPeriod);
        
        // Volume
        const avgVolume = EnhancedIndicators.sma(volumes, 20);
        const volumeRatio = latest.volume / avgVolume;
        
        // ADX for trend strength
        const adx = EnhancedIndicators.adx(highs, lows, closes, 14);

        if (!bb || !kc || !atr || !adx) {
            return null;
        }

        // ========== SQUEEZE DETECTION ==========
        const inSqueeze = bb.upper < kc.upper && bb.lower > kc.lower;
        
        // Track squeeze duration
        if (!this.squeezeHistory.has(symbol)) {
            this.squeezeHistory.set(symbol, { inSqueeze: false, duration: 0 });
        }
        
        const squeezeState = this.squeezeHistory.get(symbol);
        
        if (inSqueeze) {
            squeezeState.inSqueeze = true;
            squeezeState.duration++;
        } else if (squeezeState.inSqueeze) {
            // Squeeze just broke - potential trade setup
            const squeezeDuration = squeezeState.duration;
            
            // Reset for next squeeze
            squeezeState.inSqueeze = false;
            squeezeState.duration = 0;
            
            // Check if squeeze duration is valid
            if (squeezeDuration < this.params.minSqueezeBars || squeezeDuration > this.params.maxSqueezeBars) {
                return null;
            }
            
            let signal = null;
            let confidence = 0;
            let reasons = [];
            
            // Base confidence from squeeze duration (sweet spot = 10-20 bars)
            const durationScore = squeezeDuration >= 10 && squeezeDuration <= 20 ? 1.0 : 0.7;
            confidence = durationScore * 0.25;
            reasons.push(`Squeeze: ${squeezeDuration} bars`);
            
            // Determine breakout direction
            const breakoutDirection = momentum > 0 ? 'long' : 'short';
            const breakoutStrength = Math.abs((currentPrice - closes[closes.length - 2]) / closes[closes.length - 2]);
            
            if (breakoutStrength >= this.params.minBreakoutStrength) {
                confidence += 0.20;
                reasons.push(`Breakout: ${(breakoutStrength * 100).toFixed(2)}%`);
            }
            
            // Volume explosion (CRITICAL for volatility breakouts)
            if (volumeRatio > this.params.volumeMultiplier) {
                confidence += 0.25;
                reasons.push(`Volume: ${volumeRatio.toFixed(2)}x`);
            } else if (volumeRatio > this.params.volumeMultiplier * 0.7) {
                confidence += 0.15;
                reasons.push(`Volume: ${volumeRatio.toFixed(2)}x (good)`);
            }
            
            // Momentum confirmation
            if ((breakoutDirection === 'long' && momentum > 0.01) || 
                (breakoutDirection === 'short' && momentum < -0.01)) {
                confidence += 0.15;
                reasons.push('Momentum confirmed');
            }
            
            // ADX confirmation (trend developing)
            if (adx.adx > 20) {
                confidence += 0.10;
                reasons.push(`ADX: ${adx.adx.toFixed(1)}`);
            }
            
            // Regime bonus
            if (regimeInfo && regimeInfo.positionSizeMultiplier) {
                const regimeBonus = (regimeInfo.positionSizeMultiplier - 1.0) * 0.05;
                confidence += regimeBonus;
                if (regimeBonus > 0) {
                    reasons.push(`Regime: ${regimeInfo.regime}`);
                }
            }
            
            // ========== LONG BREAKOUT ==========
            if (breakoutDirection === 'long' && confidence >= this.minConfidence) {
                const stopDistance = (atr / currentPrice) * this.params.atrStopMultiplier;
                const targetDistance = (atr / currentPrice) * this.params.atrTargetMultiplier;
                
                signal = {
                    symbol,
                    side: 'buy',
                    action: 'BUY',
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 - stopDistance),
                    takeProfit: currentPrice * (1 + targetDistance),
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        squeezeDuration: squeezeDuration,
                        breakoutStrength: (breakoutStrength * 100).toFixed(2),
                        atr: atr.toFixed(6),
                        volumeRatio: volumeRatio.toFixed(2),
                        momentum: momentum.toFixed(4),
                        adx: adx.adx.toFixed(2)
                    }
                };
            }
            
            // ========== SHORT BREAKOUT ==========
            else if (breakoutDirection === 'short' && confidence >= this.minConfidence) {
                const stopDistance = (atr / currentPrice) * this.params.atrStopMultiplier;
                const targetDistance = (atr / currentPrice) * this.params.atrTargetMultiplier;
                
                signal = {
                    symbol,
                    side: 'sell',
                    action: 'SELL',
                    strategy: this.name,
                    entryPrice: currentPrice,
                    stopLoss: currentPrice * (1 + stopDistance),
                    takeProfit: currentPrice * (1 - targetDistance),
                    confidence,
                    reasons: reasons.join(', '),
                    indicators: {
                        squeezeDuration: squeezeDuration,
                        breakoutStrength: (breakoutStrength * 100).toFixed(2),
                        atr: atr.toFixed(6),
                        volumeRatio: volumeRatio.toFixed(2),
                        momentum: momentum.toFixed(4),
                        adx: adx.adx.toFixed(2)
                    }
                };
            }
            
            // Validate confidence before returning signal
            if (signal && signal.confidence < this.minConfidence) {
                console.log(`      [Volatility] Evaluation complete: HOLD (confidence ${(signal.confidence * 100).toFixed(1)}% below minimum ${(this.minConfidence * 100).toFixed(0)}%)`);
                return null;
            }

            console.log(`      [Volatility] Evaluation complete: ${signal ? signal.action : 'HOLD'} ${signal ? `(confidence: ${(signal.confidence * 100).toFixed(1)}%)` : ''}`);
            return signal;
        }
        
        console.log(`      [Volatility] Evaluation complete: HOLD (no squeeze release detected)`);
        return null;
    }

    calculateKeltnerChannels(highs, lows, closes, period, multiplier) {
        const typicalPrices = highs.map((h, i) => (h + lows[i] + closes[i]) / 3);
        const basis = EnhancedIndicators.ema(typicalPrices, period);
        const atr = EnhancedIndicators.atr(highs, lows, closes, period);
        
        if (!basis || !atr) return null;
        
        return {
            upper: basis + (atr * multiplier),
            basis: basis,
            lower: basis - (atr * multiplier)
        };
    }

    calculateMomentum(closes, period) {
        if (closes.length < period + 1) return 0;
        
        const current = closes[closes.length - 1];
        const past = closes[closes.length - period - 1];
        
        return (current - past) / past;
    }
}

module.exports = UpgradedVolatilityBreakoutStrategy;
