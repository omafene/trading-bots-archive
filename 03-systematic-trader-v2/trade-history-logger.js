/**
 * TRADE HISTORY LOGGER
 * Logs all trades to JSON file for analysis
 */
const fs = require('fs').promises;
const path = require('path');

class TradeHistoryLogger {
    constructor(logPath = './trade-history.json') {
        this.logPath = logPath;
        this.trades = [];
        this.loaded = false;
    }

    async initialize() {
        try {
            const data = await fs.readFile(this.logPath, 'utf8');
            this.trades = JSON.parse(data);
            console.log(`✅ Loaded ${this.trades.length} historical trades`);
        } catch (error) {
            // File doesn't exist yet, start fresh
            this.trades = [];
            console.log('📝 Starting new trade history log');
        }
        this.loaded = true;
    }

    async logTrade(trade) {
        const tradeRecord = {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            pair: trade.pair,
            strategy: trade.strategy,
            side: trade.side,
            entryPrice: trade.entryPrice,
            exitPrice: trade.exitPrice,
            entryTime: trade.entryTime,
            exitTime: trade.exitTime,
            size: trade.size,
            pnl: trade.pnl,
            pnlPercent: trade.pnlPercent,
            duration: trade.duration,
            exitReason: trade.exitReason,
            confidence: trade.confidence,
            regime: trade.regime,
            stopLoss: trade.stopLoss,
            takeProfit: trade.takeProfit,
            mode: trade.mode || 'paper'
        };

        this.trades.push(tradeRecord);

        // Save to file
        try {
            await fs.writeFile(
                this.logPath,
                JSON.stringify(this.trades, null, 2),
                'utf8'
            );
        } catch (error) {
            console.error('❌ Failed to save trade history:', error.message);
        }

        return tradeRecord;
    }

    getAllTrades() {
        return this.trades;
    }

    getTradeCount() {
        return this.trades.length;
    }

    getRecentTrades(count = 10) {
        return this.trades.slice(-count).reverse();
    }

    // Analysis methods
    getStats() {
        if (this.trades.length === 0) {
            return null;
        }

        const wins = this.trades.filter(t => t.pnl > 0);
        const losses = this.trades.filter(t => t.pnl < 0);
        
        const totalPnL = this.trades.reduce((sum, t) => sum + t.pnl, 0);
        const totalWins = wins.reduce((sum, t) => sum + t.pnl, 0);
        const totalLosses = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0));

        return {
            totalTrades: this.trades.length,
            wins: wins.length,
            losses: losses.length,
            winRate: ((wins.length / this.trades.length) * 100).toFixed(2),
            totalPnL: totalPnL.toFixed(2),
            totalWins: totalWins.toFixed(2),
            totalLosses: totalLosses.toFixed(2),
            profitFactor: totalLosses > 0 ? (totalWins / totalLosses).toFixed(2) : 'N/A',
            avgWin: wins.length > 0 ? (totalWins / wins.length).toFixed(2) : '0.00',
            avgLoss: losses.length > 0 ? (totalLosses / losses.length).toFixed(2) : '0.00',
            bestTrade: wins.length > 0 ? Math.max(...wins.map(t => t.pnl)).toFixed(2) : '0.00',
            worstTrade: losses.length > 0 ? Math.min(...losses.map(t => t.pnl)).toFixed(2) : '0.00',
            avgDuration: this.getAverageDuration()
        };
    }

    getStrategyBreakdown() {
        const byStrategy = {};

        this.trades.forEach(trade => {
            if (!byStrategy[trade.strategy]) {
                byStrategy[trade.strategy] = {
                    trades: 0,
                    wins: 0,
                    losses: 0,
                    pnl: 0
                };
            }

            byStrategy[trade.strategy].trades++;
            byStrategy[trade.strategy].pnl += trade.pnl;
            
            if (trade.pnl > 0) {
                byStrategy[trade.strategy].wins++;
            } else {
                byStrategy[trade.strategy].losses++;
            }
        });

        // Calculate win rates
        Object.keys(byStrategy).forEach(strategy => {
            const data = byStrategy[strategy];
            data.winRate = ((data.wins / data.trades) * 100).toFixed(2);
            data.pnl = data.pnl.toFixed(2);
        });

        return byStrategy;
    }

    getPairBreakdown() {
        const byPair = {};

        this.trades.forEach(trade => {
            if (!byPair[trade.pair]) {
                byPair[trade.pair] = {
                    trades: 0,
                    wins: 0,
                    losses: 0,
                    pnl: 0
                };
            }

            byPair[trade.pair].trades++;
            byPair[trade.pair].pnl += trade.pnl;
            
            if (trade.pnl > 0) {
                byPair[trade.pair].wins++;
            } else {
                byPair[trade.pair].losses++;
            }
        });

        // Calculate win rates
        Object.keys(byPair).forEach(pair => {
            const data = byPair[pair];
            data.winRate = ((data.wins / data.trades) * 100).toFixed(2);
            data.pnl = data.pnl.toFixed(2);
        });

        return byPair;
    }

    getAverageDuration() {
        if (this.trades.length === 0) return '0m';

        const durations = this.trades.map(t => {
            return new Date(t.exitTime) - new Date(t.entryTime);
        });

        const avgMs = durations.reduce((a, b) => a + b, 0) / durations.length;
        const minutes = Math.floor(avgMs / 60000);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        }
        return `${minutes}m`;
    }

    getDrawdown() {
        if (this.trades.length === 0) return { max: 0, current: 0 };

        let peak = 0;
        let maxDrawdown = 0;
        let runningPnL = 0;

        this.trades.forEach(trade => {
            runningPnL += trade.pnl;
            
            if (runningPnL > peak) {
                peak = runningPnL;
            }

            const drawdown = ((peak - runningPnL) / peak) * 100;
            if (drawdown > maxDrawdown) {
                maxDrawdown = drawdown;
            }
        });

        const currentDrawdown = peak > 0 ? ((peak - runningPnL) / peak) * 100 : 0;

        return {
            max: maxDrawdown.toFixed(2),
            current: currentDrawdown.toFixed(2)
        };
    }

    async exportCSV(filename = 'trades-export.csv') {
        const headers = [
            'ID', 'Timestamp', 'Pair', 'Strategy', 'Side', 
            'Entry Price', 'Exit Price', 'Size', 'PnL', 'PnL%',
            'Duration', 'Exit Reason', 'Confidence', 'Regime', 'Mode'
        ].join(',');

        const rows = this.trades.map(t => [
            t.id,
            t.timestamp,
            t.pair,
            t.strategy,
            t.side,
            t.entryPrice,
            t.exitPrice,
            t.size,
            t.pnl,
            t.pnlPercent,
            this.formatDuration(new Date(t.exitTime) - new Date(t.entryTime)),
            t.exitReason,
            t.confidence,
            t.regime,
            t.mode
        ].join(','));

        const csv = [headers, ...rows].join('\n');

        await fs.writeFile(filename, csv, 'utf8');
        console.log(`✅ Exported ${this.trades.length} trades to ${filename}`);

        return filename;
    }

    formatDuration(ms) {
        const minutes = Math.floor(ms / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ${hours % 24}h`;
        if (hours > 0) return `${hours}h ${minutes % 60}m`;
        return `${minutes}m`;
    }
}

module.exports = TradeHistoryLogger;
