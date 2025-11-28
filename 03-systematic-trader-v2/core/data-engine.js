/**
 * DATA ENGINE
 * Handles fetching and caching market data with multi-timeframe support
 */

class DataEngine {
    constructor(exchange, config) {
        this.exchange = exchange;
        this.config = config;
        this.cache = new Map();
        this.cacheTimeout = 60000; // 1 minute cache
    }
    
    /**
     * Fetch OHLCV candle data with caching
     */
    async fetchCandles(pair, timeframe = '15m', limit = 200) {
        const cacheKey = `${pair}_${timeframe}_${limit}`;
        const cached = this.cache.get(cacheKey);
        
        // Return cached if fresh
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        
        try {
            // Fetch from exchange
            const ohlcv = await this.exchange.fetchOHLCV(pair, timeframe, undefined, limit);
            
            if (!ohlcv || ohlcv.length === 0) {
                return null;
            }
            
            // Convert to candlestick format
            const candles = ohlcv.map(candle => ({
                timestamp: candle[0],
                open: candle[1],
                high: candle[2],
                low: candle[3],
                close: candle[4],
                volume: candle[5]
            }));
            
            // Cache the result
            this.cache.set(cacheKey, {
                data: candles,
                timestamp: Date.now()
            });
            
            return candles;
            
        } catch (error) {
            console.error(`Error fetching candles for ${pair} ${timeframe}:`, error.message);
            return null;
        }
    }
    
    /**
     * Fetch multi-timeframe data
     */
    async fetchMultiTimeframe(pair, primaryTF, higherTF, limit = 200) {
        const [primary, higher] = await Promise.all([
            this.fetchCandles(pair, primaryTF, limit),
            this.fetchCandles(pair, higherTF, Math.floor(limit / 4)) // Higher TF needs less bars
        ]);
        
        return {
            primary,
            higher
        };
    }
    
    /**
     * Fetch current ticker price
     */
    async fetchTicker(pair) {
        try {
            return await this.exchange.fetchTicker(pair);
        } catch (error) {
            console.error(`Error fetching ticker for ${pair}:`, error.message);
            return null;
        }
    }
    
    /**
     * Fetch order book depth
     */
    async fetchOrderBook(pair, limit = 20) {
        try {
            return await this.exchange.fetchOrderBook(pair, limit);
        } catch (error) {
            console.error(`Error fetching order book for ${pair}:`, error.message);
            return null;
        }
    }
    
    /**
     * Clear cache
     */
    clearCache() {
        this.cache.clear();
    }
    
    /**
     * Get cache statistics
     */
    getCacheStats() {
        return {
            entries: this.cache.size,
            timeout: this.cacheTimeout
        };
    }
}

module.exports = DataEngine;
