/**
 * CRYPTO DATA FETCHER
 * 
 * Fetches crypto-specific data for institutional-grade edge:
 * - Funding rates (perpetual futures)
 * - Open interest
 * - Liquidation levels
 * - Exchange flows
 * - MVRV ratio (on-chain)
 * 
 * Data sources: Exchange APIs, Glassnode, CryptoQuant
 */

class CryptoDataFetcher {
    constructor(config = {}) {
        this.config = config;
        this.cache = new Map();
        this.cacheExpiry = 60000; // 1 minute cache
        
        // Funding rate thresholds
        this.fundingThresholds = {
            extremePositive: 0.001, // 0.1% per 8 hours (~40% annualized)
            positive: 0.0005,        // 0.05% per 8 hours (~20% annualized)
            negative: -0.0005,       // -0.05% per 8 hours
            extremeNegative: -0.001  // -0.1% per 8 hours
        };

        console.log('✅ Crypto Data Fetcher initialized');
    }

    /**
     * Get funding rate for perpetual futures
     * High positive = overleveraged longs (bearish signal)
     * High negative = overleveraged shorts (bullish signal)
     */
    async getFundingRate(exchange, symbol) {
        const cacheKey = `funding_${symbol}`;
        const cached = this.getCache(cacheKey);
        if (cached) return cached;

        try {
            // Fetch funding rate from exchange
            const fundingRate = await this.fetchFundingRate(exchange, symbol);
            
            if (!fundingRate) return null;

            const analysis = this.analyzeFundingRate(fundingRate);
            
            this.setCache(cacheKey, analysis);
            return analysis;

        } catch (error) {
            console.error(`Failed to fetch funding rate for ${symbol}:`, error.message);
            return null;
        }
    }

    /**
     * Fetch funding rate from exchange API
     */
    async fetchFundingRate(exchange, symbol) {
        try {
            // Check if exchange supports funding rates
            if (!exchange.has['fetchFundingRate']) {
                return null;
            }

            const fundingRate = await exchange.fetchFundingRate(symbol);
            
            return {
                rate: fundingRate.fundingRate,
                timestamp: fundingRate.timestamp,
                nextFundingTime: fundingRate.fundingDatetime
            };

        } catch (error) {
            // Silently handle if not available
            return null;
        }
    }

    /**
     * Analyze funding rate and generate trading signals
     */
    analyzeFundingRate(fundingData) {
        if (!fundingData) return null;

        const rate = fundingData.rate;
        let signal = 'NEUTRAL';
        let bias = 'NEUTRAL';
        let confidence = 0;
        let description = '';

        // Extreme positive funding (>0.1% per 8h)
        if (rate > this.fundingThresholds.extremePositive) {
            signal = 'SHORT_BIAS';
            bias = 'BEARISH';
            confidence = 0.8;
            description = 'Extreme positive funding - Overleveraged longs, high short squeeze risk';
        }
        // Positive funding
        else if (rate > this.fundingThresholds.positive) {
            signal = 'CAUTIOUS_LONG';
            bias = 'SLIGHTLY_BEARISH';
            confidence = 0.5;
            description = 'Positive funding - Longs paying shorts, consider reducing long exposure';
        }
        // Extreme negative funding
        else if (rate < this.fundingThresholds.extremeNegative) {
            signal = 'LONG_BIAS';
            bias = 'BULLISH';
            confidence = 0.8;
            description = 'Extreme negative funding - Overleveraged shorts, short squeeze likely';
        }
        // Negative funding
        else if (rate < this.fundingThresholds.negative) {
            signal = 'CAUTIOUS_SHORT';
            bias = 'SLIGHTLY_BULLISH';
            confidence = 0.5;
            description = 'Negative funding - Shorts paying longs, accumulation opportunity';
        }
        // Neutral funding
        else {
            signal = 'NEUTRAL';
            bias = 'NEUTRAL';
            confidence = 0.3;
            description = 'Balanced funding rate - No strong bias';
        }

        // Calculate annualized cost
        const annualizedRate = rate * 365 * 3; // 3x daily (every 8 hours)
        const annualizedPercent = (annualizedRate * 100).toFixed(2);

        return {
            ...fundingData,
            signal,
            bias,
            confidence,
            description,
            annualizedPercent,
            positionAdjustment: this.getPositionAdjustment(rate)
        };
    }

    /**
     * Get position adjustment based on funding rate
     */
    getPositionAdjustment(rate) {
        if (rate > this.fundingThresholds.extremePositive) {
            return {
                action: 'REDUCE_LONG',
                multiplier: 0.5, // Cut long positions by 50%
                reason: 'Extreme funding cost for longs'
            };
        } else if (rate < this.fundingThresholds.extremeNegative) {
            return {
                action: 'INCREASE_LONG',
                multiplier: 1.25, // Increase long positions by 25%
                reason: 'Shorts paying premium, squeeze potential'
            };
        }
        return {
            action: 'NEUTRAL',
            multiplier: 1.0,
            reason: 'Normal funding rate'
        };
    }

    /**
     * Get open interest data
     * High OI + extreme funding = liquidation cascade risk
     */
    async getOpenInterest(exchange, symbol) {
        const cacheKey = `oi_${symbol}`;
        const cached = this.getCache(cacheKey);
        if (cached) return cached;

        try {
            // Fetch open interest if exchange supports it
            if (!exchange.has['fetchOpenInterest']) {
                return null;
            }

            const oi = await exchange.fetchOpenInterest(symbol);
            
            const analysis = {
                openInterest: oi,
                timestamp: Date.now(),
                isHigh: false, // Would need historical data to determine
                description: 'Open interest data'
            };

            this.setCache(cacheKey, analysis);
            return analysis;

        } catch (error) {
            return null;
        }
    }

    /**
     * Calculate liquidation risk score
     * Combines: OI percentile + funding extremity + leverage concentration
     */
    calculateLiquidationRisk(fundingData, openInterestData) {
        if (!fundingData) return { score: 0, level: 'UNKNOWN' };

        let riskScore = 0;

        // Funding contribution (0-0.4)
        const fundingMagnitude = Math.abs(fundingData.rate);
        riskScore += Math.min(fundingMagnitude / 0.001, 0.4);

        // High OI contribution (0-0.3)
        if (openInterestData && openInterestData.isHigh) {
            riskScore += 0.3;
        }

        // Direction contribution (0-0.3)
        if (Math.abs(fundingData.rate) > this.fundingThresholds.extremePositive) {
            riskScore += 0.3;
        }

        // Classify risk level
        let level;
        if (riskScore > 0.7) {
            level = 'EXTREME';
        } else if (riskScore > 0.5) {
            level = 'HIGH';
        } else if (riskScore > 0.3) {
            level = 'MODERATE';
        } else {
            level = 'LOW';
        }

        return {
            score: riskScore.toFixed(2),
            level,
            recommendation: this.getLiquidationRiskRecommendation(level)
        };
    }

    /**
     * Get trading recommendation based on liquidation risk
     */
    getLiquidationRiskRecommendation(level) {
        switch (level) {
            case 'EXTREME':
                return {
                    action: 'REDUCE_ALL_POSITIONS',
                    multiplier: 0.25,
                    description: 'Extreme liquidation risk - Cut all positions to 25%'
                };
            case 'HIGH':
                return {
                    action: 'REDUCE_POSITIONS',
                    multiplier: 0.5,
                    description: 'High liquidation risk - Reduce positions by 50%'
                };
            case 'MODERATE':
                return {
                    action: 'CAUTIOUS',
                    multiplier: 0.75,
                    description: 'Moderate risk - Reduce position sizes to 75%'
                };
            default:
                return {
                    action: 'NORMAL',
                    multiplier: 1.0,
                    description: 'Normal conditions'
                };
        }
    }

    /**
     * MVRV Ratio (Market Value to Realized Value)
     * Requires on-chain data - mock implementation
     * 
     * MVRV > 3.5: Late bull cycle (reduce longs)
     * MVRV < 1.0: Accumulation zone (increase longs)
     */
    async getMVRV(symbol = 'BTC') {
        // This would require Glassnode or similar API
        // Mock implementation for now
        const cacheKey = `mvrv_${symbol}`;
        const cached = this.getCache(cacheKey);
        if (cached) return cached;

        // In production, fetch from Glassnode/CryptoQuant
        // For now, return mock data structure
        const mockMVRV = {
            ratio: 2.1, // Mock value
            signal: 'NEUTRAL',
            description: 'MVRV data requires on-chain API (Glassnode)',
            available: false
        };

        this.setCache(cacheKey, mockMVRV, 3600000); // Cache for 1 hour
        return mockMVRV;
    }

    /**
     * Analyze MVRV ratio for macro signals
     */
    analyzeMVRV(ratio) {
        if (ratio > 3.5) {
            return {
                signal: 'LATE_CYCLE',
                bias: 'BEARISH',
                confidence: 0.7,
                action: 'SCALE_OUT_LONGS',
                description: 'MVRV > 3.5 - Late bull cycle, consider profit taking'
            };
        } else if (ratio > 2.5) {
            return {
                signal: 'MID_CYCLE',
                bias: 'NEUTRAL',
                confidence: 0.5,
                action: 'NORMAL',
                description: 'MVRV 2.5-3.5 - Mid cycle, normal positioning'
            };
        } else if (ratio < 1.0) {
            return {
                signal: 'ACCUMULATION',
                bias: 'BULLISH',
                confidence: 0.8,
                action: 'INCREASE_LONGS',
                description: 'MVRV < 1.0 - Accumulation zone, strong buy opportunity'
            };
        } else {
            return {
                signal: 'NEUTRAL',
                bias: 'NEUTRAL',
                confidence: 0.3,
                action: 'NORMAL',
                description: 'MVRV 1.0-2.5 - Normal range'
            };
        }
    }

    /**
     * Get comprehensive market data package
     */
    async getMarketIntelligence(exchange, symbol) {
        const [fundingData, openInterestData, mvrvData] = await Promise.all([
            this.getFundingRate(exchange, symbol),
            this.getOpenInterest(exchange, symbol),
            this.getMVRV(symbol.split('/')[0]) // Get base currency
        ]);

        const liquidationRisk = this.calculateLiquidationRisk(fundingData, openInterestData);

        // Combine signals
        let overallBias = 'NEUTRAL';
        let confidence = 0;
        const factors = [];

        if (fundingData) {
            factors.push({
                name: 'Funding Rate',
                bias: fundingData.bias,
                confidence: fundingData.confidence
            });
        }

        if (liquidationRisk.level !== 'UNKNOWN') {
            factors.push({
                name: 'Liquidation Risk',
                level: liquidationRisk.level,
                recommendation: liquidationRisk.recommendation
            });
        }

        return {
            symbol,
            timestamp: Date.now(),
            funding: fundingData,
            openInterest: openInterestData,
            mvrv: mvrvData,
            liquidationRisk,
            overallBias,
            factors,
            positionSizeAdjustment: this.calculateOverallPositionAdjustment(
                fundingData,
                liquidationRisk
            )
        };
    }

    /**
     * Calculate overall position size adjustment from all factors
     */
    calculateOverallPositionAdjustment(fundingData, liquidationRisk) {
        let multiplier = 1.0;

        // Apply funding adjustment
        if (fundingData && fundingData.positionAdjustment) {
            multiplier *= fundingData.positionAdjustment.multiplier;
        }

        // Apply liquidation risk adjustment
        if (liquidationRisk && liquidationRisk.recommendation) {
            multiplier *= liquidationRisk.recommendation.multiplier;
        }

        return {
            multiplier: Math.max(0.1, multiplier), // Min 10% of normal size
            description: `Adjusted to ${(multiplier * 100).toFixed(0)}% of base size`
        };
    }

    /**
     * Cache management
     */
    getCache(key) {
        const cached = this.cache.get(key);
        if (!cached) return null;
        
        if (Date.now() - cached.timestamp > this.cacheExpiry) {
            this.cache.delete(key);
            return null;
        }
        
        return cached.data;
    }

    setCache(key, data, customExpiry = null) {
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            expiry: customExpiry || this.cacheExpiry
        });
    }

    clearCache() {
        this.cache.clear();
    }

    /**
     * Fetch all crypto data for a symbol
     */
    async fetchAllData(symbol) {
        try {
            // Parse symbol for exchange and base
            const exchange = 'coinbase'; // Default to spot exchange
            
            // Fetch all available data (some may fail, that's OK)
            const [fundingRate, openInterest, mvrv, marketIntel] = await Promise.allSettled([
                this.fetchFundingRate('binance', symbol).catch(() => null),
                this.getOpenInterest('binance', symbol).catch(() => null),
                symbol.includes('BTC') ? this.getMVRV('BTC').catch(() => null) : Promise.resolve(null),
                this.getMarketIntelligence('binance', symbol).catch(() => null)
            ]);

            return {
                symbol,
                timestamp: Date.now(),
                fundingRate: fundingRate.status === 'fulfilled' ? fundingRate.value : null,
                openInterest: openInterest.status === 'fulfilled' ? openInterest.value : null,
                mvrv: mvrv.status === 'fulfilled' ? mvrv.value : null,
                marketIntelligence: marketIntel.status === 'fulfilled' ? marketIntel.value : null
            };
        } catch (error) {
            console.log(`⚠️  Could not fetch crypto data for ${symbol}: ${error.message}`);
            return null;
        }
    }

    /**
     * Fetch all crypto data for a symbol
     */
    async fetchAllData(symbol) {
        try {
            // Parse symbol for exchange and base
            const exchange = 'coinbase'; // Default to spot exchange
            
            // Fetch all available data (some may fail, that's OK)
            const [fundingRate, openInterest, mvrv, marketIntel] = await Promise.allSettled([
                this.fetchFundingRate('binance', symbol).catch(() => null),
                this.getOpenInterest('binance', symbol).catch(() => null),
                symbol.includes('BTC') ? this.getMVRV('BTC').catch(() => null) : Promise.resolve(null),
                this.getMarketIntelligence('binance', symbol).catch(() => null)
            ]);

            return {
                symbol,
                timestamp: Date.now(),
                fundingRate: fundingRate.status === 'fulfilled' ? fundingRate.value : null,
                openInterest: openInterest.status === 'fulfilled' ? openInterest.value : null,
                mvrv: mvrv.status === 'fulfilled' ? mvrv.value : null,
                marketIntelligence: marketIntel.status === 'fulfilled' ? marketIntel.value : null
            };
        } catch (error) {
            console.log(`⚠️  Could not fetch crypto data for ${symbol}: ${error.message}`);
            return null;
        }
    }

    /**
     * Fetch all crypto data for a symbol
     */
    async fetchAllData(symbol) {
        try {
            // Parse symbol for exchange and base
            const exchange = 'coinbase'; // Default to spot exchange
            
            // Fetch all available data (some may fail, that's OK)
            const [fundingRate, openInterest, mvrv, marketIntel] = await Promise.allSettled([
                this.fetchFundingRate('binance', symbol).catch(() => null),
                this.getOpenInterest('binance', symbol).catch(() => null),
                symbol.includes('BTC') ? this.getMVRV('BTC').catch(() => null) : Promise.resolve(null),
                this.getMarketIntelligence('binance', symbol).catch(() => null)
            ]);

            return {
                symbol,
                timestamp: Date.now(),
                fundingRate: fundingRate.status === 'fulfilled' ? fundingRate.value : null,
                openInterest: openInterest.status === 'fulfilled' ? openInterest.value : null,
                mvrv: mvrv.status === 'fulfilled' ? mvrv.value : null,
                marketIntelligence: marketIntel.status === 'fulfilled' ? marketIntel.value : null
            };
        } catch (error) {
            console.log(`⚠️  Could not fetch crypto data for ${symbol}: ${error.message}`);
            return null;
        }
    }

    /**
     * Fetch all crypto data for a symbol
     */
    async fetchAllData(symbol) {
        try {
            // Parse symbol for exchange and base
            const exchange = 'coinbase'; // Default to spot exchange
            
            // Fetch all available data (some may fail, that's OK)
            const [fundingRate, openInterest, mvrv, marketIntel] = await Promise.allSettled([
                this.fetchFundingRate('binance', symbol).catch(() => null),
                this.getOpenInterest('binance', symbol).catch(() => null),
                symbol.includes('BTC') ? this.getMVRV('BTC').catch(() => null) : Promise.resolve(null),
                this.getMarketIntelligence('binance', symbol).catch(() => null)
            ]);

            return {
                symbol,
                timestamp: Date.now(),
                fundingRate: fundingRate.status === 'fulfilled' ? fundingRate.value : null,
                openInterest: openInterest.status === 'fulfilled' ? openInterest.value : null,
                mvrv: mvrv.status === 'fulfilled' ? mvrv.value : null,
                marketIntelligence: marketIntel.status === 'fulfilled' ? marketIntel.value : null
            };
        } catch (error) {
            console.log(`⚠️  Could not fetch crypto data for ${symbol}: ${error.message}`);
            return null;
        }
    }

    /**
     * Fetch all crypto data for a symbol
     */
    async fetchAllData(symbol) {
        try {
            // Parse symbol for exchange and base
            const exchange = 'coinbase'; // Default to spot exchange
            
            // Fetch all available data (some may fail, that's OK)
            const [fundingRate, openInterest, mvrv, marketIntel] = await Promise.allSettled([
                this.fetchFundingRate('binance', symbol).catch(() => null),
                this.getOpenInterest('binance', symbol).catch(() => null),
                symbol.includes('BTC') ? this.getMVRV('BTC').catch(() => null) : Promise.resolve(null),
                this.getMarketIntelligence('binance', symbol).catch(() => null)
            ]);

            return {
                symbol,
                timestamp: Date.now(),
                fundingRate: fundingRate.status === 'fulfilled' ? fundingRate.value : null,
                openInterest: openInterest.status === 'fulfilled' ? openInterest.value : null,
                mvrv: mvrv.status === 'fulfilled' ? mvrv.value : null,
                marketIntelligence: marketIntel.status === 'fulfilled' ? marketIntel.value : null
            };
        } catch (error) {
            console.log(`⚠️  Could not fetch crypto data for ${symbol}: ${error.message}`);
            return null;
        }
    }
}

module.exports = CryptoDataFetcher;
