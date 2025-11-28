/**
 * POSITION MANAGER
 * Handles order execution, position tracking, and exit management
 */

class PositionManager {
    constructor(exchange, config, mode = 'paper') {
        this.exchange = exchange;
        this.config = config;
        this.mode = mode;
        
        // Paper trading state
        this.paperBalance = config.paperTradingBalance || 10000;
        this.paperPositions = new Map();
        
        // Real balance cache
        this.realBalanceCache = null;
        this.balanceCacheTime = 0;
    }
    
    /**
     * Get current account balance
     */
    async getBalance() {
        if (this.mode === 'paper') {
            return this.paperBalance;
        }
        
        // Cache real balance for 5 minutes
        if (this.realBalanceCache && Date.now() - this.balanceCacheTime < 300000) {
            return this.realBalanceCache;
        }
        
        try {
            const balance = await this.exchange.fetchBalance();
            const usdBalance = balance.free.USDT || balance.free.USD || balance.free.BUSD || 0;
            
            this.realBalanceCache = usdBalance;
            this.balanceCacheTime = Date.now();
            
            return usdBalance;
            
        } catch (error) {
            console.error('Error fetching balance:', error.message);
            return this.realBalanceCache || 0;
        }
    }
    
    /**
     * Open a new position
     */
    async openPosition(params) {
        const { pair, side, size, stopLoss, takeProfit, strategy, confidence, regimeData } = params;
        
        if (this.mode === 'paper') {
            return this.openPaperPosition(params);
        } else if (this.mode === 'live-tiny' || this.mode === 'live') {
            return this.openRealPosition(params);
        }
    }
    
    /**
     * Open paper trading position
     */
    openPaperPosition(params) {
        const { pair, side, size, stopLoss, takeProfit, strategy, confidence } = params;
        
        // Get current price (use last known price)
        const entryPrice = params.currentPrice || 0;
        
        const position = {
            id: Date.now().toString(),
            pair,
            side,
            size,
            entryPrice,
            stopLoss,
            takeProfit,
            strategy,
            confidence,
            entryTime: Date.now(),
            mode: 'paper'
        };
        
        // Deduct from paper balance
        const positionValue = entryPrice * size;
        this.paperBalance -= positionValue;
        
        return position;
    }
    
    /**
     * Open real position on exchange
     */
    async openRealPosition(params) {
        const { pair, side, size, stopLoss, takeProfit, strategy, confidence } = params;
        
        try {
            // Place market order
            const order = await this.exchange.createOrder(
                pair,
                'market',
                side,
                size
            );
            
            if (!order) {
                throw new Error('Order failed');
            }
            
            // Place stop loss order
            if (stopLoss) {
                try {
                    await this.exchange.createOrder(
                        pair,
                        'stop_loss',
                        side === 'buy' ? 'sell' : 'buy',
                        size,
                        stopLoss
                    );
                } catch (error) {
                    console.warn('Failed to set stop loss:', error.message);
                }
            }
            
            // Place take profit order
            if (takeProfit) {
                try {
                    await this.exchange.createOrder(
                        pair,
                        'limit',
                        side === 'buy' ? 'sell' : 'buy',
                        size,
                        takeProfit
                    );
                } catch (error) {
                    console.warn('Failed to set take profit:', error.message);
                }
            }
            
            const position = {
                id: order.id,
                pair,
                side,
                size,
                entryPrice: order.average || order.price,
                stopLoss,
                takeProfit,
                strategy,
                confidence,
                entryTime: Date.now(),
                mode: this.mode,
                orderId: order.id
            };
            
            return position;
            
        } catch (error) {
            console.error('Failed to open real position:', error.message);
            return null;
        }
    }
    
    /**
     * Check if position should be closed
     */
    shouldClosePosition(position, currentPrice) {
        const { side, stopLoss, takeProfit, entryTime } = position;
        
        // Check stop loss
        if (side === 'buy' && currentPrice <= stopLoss) {
            return { close: true, reason: 'stop_loss' };
        }
        if (side === 'sell' && currentPrice >= stopLoss) {
            return { close: true, reason: 'stop_loss' };
        }
        
        // Check take profit
        if (side === 'buy' && currentPrice >= takeProfit) {
            return { close: true, reason: 'take_profit' };
        }
        if (side === 'sell' && currentPrice <= takeProfit) {
            return { close: true, reason: 'take_profit' };
        }
        
        // Check time-based exits (optional)
        const maxHoldTime = this.config.maxHoldTime || 86400000; // 24 hours default
        if (Date.now() - entryTime > maxHoldTime) {
            return { close: true, reason: 'time_limit' };
        }
        
        return { close: false };
    }
    
    /**
     * Close a position
     */
    async closePosition(position, currentPrice, reason) {
        if (position.mode === 'paper') {
            return this.closePaperPosition(position, currentPrice);
        } else {
            return this.closeRealPosition(position, currentPrice);
        }
    }
    
    /**
     * Close paper position
     */
    closePaperPosition(position, currentPrice) {
        const pnl = this.calculatePnL(position, currentPrice);
        
        // Return to paper balance
        const closeValue = currentPrice * position.size;
        this.paperBalance += closeValue;
        
        return {
            success: true,
            pnl,
            closePrice: currentPrice
        };
    }
    
    /**
     * Close real position
     */
    async closeRealPosition(position, currentPrice) {
        try {
            const oppositeOrder = await this.exchange.createOrder(
                position.pair,
                'market',
                position.side === 'buy' ? 'sell' : 'buy',
                position.size
            );
            
            const pnl = this.calculatePnL(position, oppositeOrder.average || currentPrice);
            
            return {
                success: true,
                pnl,
                closePrice: oppositeOrder.average || currentPrice
            };
            
        } catch (error) {
            console.error('Failed to close real position:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    /**
     * Calculate PnL for a position
     */
    calculatePnL(position, currentPrice) {
        const { side, entryPrice, size } = position;
        
        let pnl;
        if (side === 'buy') {
            pnl = (currentPrice - entryPrice) * size;
        } else {
            pnl = (entryPrice - currentPrice) * size;
        }
        
        // Deduct fees (assume 0.1% per trade)
        const fees = (entryPrice * size * 0.001) + (currentPrice * size * 0.001);
        pnl -= fees;
        
        return pnl;
    }
    
    /**
     * Get all open positions
     */
    async getOpenPositions() {
        if (this.mode === 'paper') {
            return Array.from(this.paperPositions.values());
        }
        
        try {
            const positions = await this.exchange.fetchPositions();
            return positions.filter(p => Math.abs(p.contracts) > 0);
        } catch (error) {
            console.error('Error fetching positions:', error.message);
            return [];
        }
    }
}

module.exports = PositionManager;
