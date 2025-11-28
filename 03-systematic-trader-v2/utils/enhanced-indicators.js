/**
 * ENHANCED TECHNICAL INDICATORS
 * 
 * Professional-grade indicators including:
 * - ADX (Average Directional Index) for regime detection
 * - Keltner Channels for TTM Squeeze
 * - Half-life calculation for mean reversion
 * - Enhanced volatility metrics
 */

class EnhancedIndicators {
    
    // ============== EXISTING INDICATORS ===============
    
    static sma(data, period) {
        if (data.length < period) return null;
        const slice = data.slice(-period);
        const sum = slice.reduce((a, b) => a + b, 0);
        return sum / period;
    }

    static ema(data, period) {
        if (data.length < period) return null;
        const multiplier = 2 / (period + 1);
        let ema = this.sma(data.slice(0, period), period);
        for (let i = period; i < data.length; i++) {
            ema = (data[i] - ema) * multiplier + ema;
        }
        return ema;
    }

    static rsi(data, period = 14) {
        if (data.length < period + 1) return null;
        const changes = [];
        for (let i = 1; i < data.length; i++) {
            changes.push(data[i] - data[i - 1]);
        }
        const gains = changes.map(c => c > 0 ? c : 0);
        const losses = changes.map(c => c < 0 ? Math.abs(c) : 0);
        let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
        let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
        for (let i = period; i < changes.length; i++) {
            avgGain = (avgGain * (period - 1) + gains[i]) / period;
            avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
        }
        if (avgLoss === 0) return 100;
        const rs = avgGain / avgLoss;
        return 100 - (100 / (1 + rs));
    }

    static bollingerBands(data, period = 20, stdDev = 2) {
        if (data.length < period) return null;
        const sma = this.sma(data, period);
        const slice = data.slice(-period);
        const squaredDiffs = slice.map(val => Math.pow(val - sma, 2));
        const variance = squaredDiffs.reduce((a, b) => a + b, 0) / period;
        const sd = Math.sqrt(variance);
        return {
            upper: sma + (sd * stdDev),
            middle: sma,
            lower: sma - (sd * stdDev),
            bandwidth: (sd * stdDev * 2) / sma
        };
    }

    static atr(highs, lows, closes, period = 14) {
        if (highs.length < period + 1) return null;
        const trueRanges = [];
        for (let i = 1; i < highs.length; i++) {
            const tr = Math.max(
                highs[i] - lows[i],
                Math.abs(highs[i] - closes[i - 1]),
                Math.abs(lows[i] - closes[i - 1])
            );
            trueRanges.push(tr);
        }
        let atr = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
        for (let i = period; i < trueRanges.length; i++) {
            atr = (atr * (period - 1) + trueRanges[i]) / period;
        }
        return atr;
    }

    static macd(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
        if (data.length < slowPeriod + signalPeriod) return null;
        const fastEMA = this.ema(data, fastPeriod);
        const slowEMA = this.ema(data, slowPeriod);
        const macdLine = fastEMA - slowEMA;
        const macdHistory = [];
        for (let i = slowPeriod; i <= data.length; i++) {
            const slice = data.slice(0, i);
            const fast = this.ema(slice, fastPeriod);
            const slow = this.ema(slice, slowPeriod);
            macdHistory.push(fast - slow);
        }
        const signalLine = this.ema(macdHistory, signalPeriod);
        return {
            macd: macdLine,
            signal: signalLine,
            histogram: macdLine - signalLine
        };
    }

    // ============== NEW INSTITUTIONAL-GRADE INDICATORS ===============

    /**
     * ADX (Average Directional Index) - CRITICAL for regime detection
     * Returns: { adx, plusDI, minusDI }
     * ADX < 20: Weak/sideways (mean reversion)
     * ADX 25-40: Strong trend (momentum)
     * ADX > 60: Trend exhaustion
     */
    static adx(highs, lows, closes, period = 14) {
        if (highs.length < period + 1) return null;

        const trueRanges = [];
        const plusDM = [];
        const minusDM = [];

        // Calculate directional movement
        for (let i = 1; i < highs.length; i++) {
            const tr = Math.max(
                highs[i] - lows[i],
                Math.abs(highs[i] - closes[i - 1]),
                Math.abs(lows[i] - closes[i - 1])
            );
            trueRanges.push(tr);

            const highDiff = highs[i] - highs[i - 1];
            const lowDiff = lows[i - 1] - lows[i];

            plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0);
            minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0);
        }

        // Smooth the values
        let smoothedTR = trueRanges.slice(0, period).reduce((a, b) => a + b, 0);
        let smoothedPlusDM = plusDM.slice(0, period).reduce((a, b) => a + b, 0);
        let smoothedMinusDM = minusDM.slice(0, period).reduce((a, b) => a + b, 0);

        for (let i = period; i < trueRanges.length; i++) {
            smoothedTR = smoothedTR - (smoothedTR / period) + trueRanges[i];
            smoothedPlusDM = smoothedPlusDM - (smoothedPlusDM / period) + plusDM[i];
            smoothedMinusDM = smoothedMinusDM - (smoothedMinusDM / period) + minusDM[i];
        }

        // Calculate directional indicators
        const plusDI = (smoothedPlusDM / smoothedTR) * 100;
        const minusDI = (smoothedMinusDM / smoothedTR) * 100;

        // Calculate DX and ADX
        const dx = Math.abs(plusDI - minusDI) / (plusDI + minusDI) * 100;
        
        return {
            adx: dx,
            plusDI: plusDI,
            minusDI: minusDI
        };
    }

    /**
     * Keltner Channels - Used with Bollinger Bands for TTM Squeeze
     * More stable than BB, uses ATR instead of standard deviation
     */
    static keltnerChannels(highs, lows, closes, period = 20, atrMultiplier = 2) {
        if (closes.length < period) return null;

        const ema = this.ema(closes, period);
        const atr = this.atr(highs, lows, closes, period);

        if (!ema || !atr) return null;

        return {
            upper: ema + (atr * atrMultiplier),
            middle: ema,
            lower: ema - (atr * atrMultiplier)
        };
    }

    /**
     * TTM Squeeze Detector
     * Squeeze active when BB inside KC = volatility compression
     * Breakout when BB expands outside KC
     */
    static ttmSqueeze(highs, lows, closes, bbPeriod = 20, kcPeriod = 20) {
        const bb = this.bollingerBands(closes, bbPeriod, 2);
        const kc = this.keltnerChannels(highs, lows, closes, kcPeriod, 1.5);

        if (!bb || !kc) return null;

        const squeezeOn = bb.upper < kc.upper && bb.lower > kc.lower;
        const squeezeOff = bb.upper >= kc.upper || bb.lower <= kc.lower;

        return {
            squeezeOn,
            squeezeOff,
            bb,
            kc
        };
    }

    /**
     * Half-Life Calculation for Mean Reversion
     * Critical for institutional mean reversion strategies
     * Returns expected bars until half-way reversion to mean
     */
    static calculateHalfLife(prices) {
        if (prices.length < 20) return null;

        const differences = [];
        const laggedPrices = [];
        
        for (let i = 1; i < prices.length; i++) {
            differences.push(prices[i] - prices[i - 1]);
            laggedPrices.push(prices[i - 1]);
        }

        const n = differences.length;
        const meanDiff = differences.reduce((a, b) => a + b, 0) / n;
        const meanLagged = laggedPrices.reduce((a, b) => a + b, 0) / n;

        let numerator = 0;
        let denominator = 0;

        for (let i = 0; i < n; i++) {
            numerator += (laggedPrices[i] - meanLagged) * (differences[i] - meanDiff);
            denominator += Math.pow(laggedPrices[i] - meanLagged, 2);
        }

        const lambda = numerator / denominator;

        if (lambda >= 0) return null;

        const halfLife = -Math.log(2) / lambda;

        return {
            halfLife: halfLife,
            meanReversionSpeed: lambda,
            isReverting: lambda < 0,
            tradeable: halfLife > 5 && halfLife < 200
        };
    }

    /**
     * Enhanced ATR with percentile ranking
     */
    static atrPercentile(highs, lows, closes, period = 14, lookback = 100) {
        if (highs.length < lookback) return null;

        const currentATR = this.atr(highs, lows, closes, period);
        const historicalATRs = [];

        for (let i = period; i < Math.min(highs.length, lookback); i++) {
            const sliceH = highs.slice(i - period, i);
            const sliceL = lows.slice(i - period, i);
            const sliceC = closes.slice(i - period, i);
            const atr = this.atr(sliceH, sliceL, sliceC, period);
            if (atr) historicalATRs.push(atr);
        }

        historicalATRs.sort((a, b) => a - b);
        const rank = historicalATRs.filter(atr => atr <= currentATR).length;
        const percentile = (rank / historicalATRs.length) * 100;

        return {
            currentATR,
            percentile,
            isHighVolatility: percentile > 80,
            isLowVolatility: percentile < 20
        };
    }

    /**
     * Crypto-optimized MACD (5,35,5)
     */
    static cryptoMACD(data) {
        return this.macd(data, 5, 35, 5);
    }

    /**
     * Z-Score for mean reversion
     */
    static zScore(data, period = 20) {
        if (data.length < period) return null;
        const mean = this.sma(data, period);
        const stdDev = this.stdDev(data, period);
        const current = data[data.length - 1];
        if (stdDev === 0) return 0;
        return (current - mean) / stdDev;
    }

    static stdDev(data, period) {
        if (data.length < period) return null;
        const slice = data.slice(-period);
        const mean = slice.reduce((a, b) => a + b, 0) / period;
        const squaredDiffs = slice.map(val => Math.pow(val - mean, 2));
        const variance = squaredDiffs.reduce((a, b) => a + b, 0) / period;
        return Math.sqrt(variance);
    }
}

module.exports = EnhancedIndicators;
