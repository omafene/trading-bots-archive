#!/usr/bin/env node
/**
 * SYSTEMATIC TRADING BOT V2 - MAIN ENTRY
 * Institutional-grade systematic trading with regime detection and Kelly sizing
 */
require('dotenv').config();
const SystematicTradingBot = require('./bot');
const config = require('./config');

async function main() {
    console.log('╔════════════════════════════════════════════════════════════╗');
    console.log('║   SYSTEMATIC TRADING BOT V2 - INSTITUTIONAL EDITION       ║');
    console.log('║                                                            ║');
    console.log('║   ✓ Multi-Timeframe Analysis                              ║');
    console.log('║   ✓ ADX Regime Detection                                  ║');
    console.log('║   ✓ Kelly Criterion Sizing                                ║');
    console.log('║   ✓ Crypto Data Integration                               ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

    // Validate configuration
    if (!config.exchange) {
        console.error('❌ Error: Exchange not configured');
        process.exit(1);
    }

    if (config.mode !== 'paper' && (!config.apiKey || !config.apiSecret)) {
        console.error('❌ Error: API credentials required for live trading');
        console.error('   Set EXCHANGE_API_KEY and EXCHANGE_API_SECRET in .env file');
        process.exit(1);
    }

    // Create bot instance
    console.log(`🎯 Initializing bot in ${config.mode.toUpperCase()} mode...\n`);
    const bot = new SystematicTradingBot(config);

    // Setup Telegram handlers if enabled
    if (bot.telegram && bot.telegram.enabled) {
        // Stats handler - Enhanced with more metrics
        bot.telegram.setStatsHandler(async () => {
            const stats = bot.getStats();
            const trades = stats.trades || 0;
            const wins = stats.wins || 0;
            const losses = stats.losses || 0;
            const totalPnL = parseFloat(stats.totalPnL) || 0;
            
            return {
                startDate: new Date(bot.startTime).toLocaleDateString(),
                uptime: stats.uptime,
                trades: trades,
                wins: wins,
                losses: losses,
                winRate: stats.winRate,
                totalPnL: stats.totalPnL,
                profitFactor: trades > 0 && losses > 0 ? (wins / losses).toFixed(2) : 'N/A',
                avgWin: wins > 0 && totalPnL > 0 ? (totalPnL / wins).toFixed(2) : '0.00',
                avgLoss: losses > 0 && totalPnL < 0 ? (Math.abs(totalPnL) / losses).toFixed(2) : '0.00',
                bestTrade: '0.00',
                worstTrade: '0.00',
                maxDrawdown: 0,
                currentDrawdown: 0,
                sharpeRatio: null,
                activePositions: stats.activePositions,
                todayTrades: trades,
                todayWins: wins,
                todayWinRate: stats.winRate,
                todayPnL: totalPnL
            };
        });
        
        // Positions handler - Enhanced with current prices
        bot.telegram.setPositionsHandler(async () => {
            const positions = Array.from(bot.activeTrades.values());
            
            const enrichedPositions = await Promise.all(positions.map(async (trade) => {
                try {
                    // Try to get current price
                    const ticker = await bot.exchange.fetchTicker(trade.pair);
                    const currentPrice = ticker.last;
                    const pnl = (currentPrice - trade.entryPrice) * trade.size * (trade.side === 'buy' ? 1 : -1);
                    const pnlPercent = (pnl / (trade.entryPrice * trade.size)) * 100;
                    
                    return {
                        pair: trade.pair,
                        side: trade.side,
                        entryPrice: trade.entryPrice,
                        currentPrice: currentPrice,
                        size: trade.size,
                        stopLoss: trade.stopLoss,
                        takeProfit: trade.takeProfit,
                        strategy: trade.strategy,
                        unrealizedPnL: pnl,
                        unrealizedPnLPercent: pnlPercent,
                        duration: bot.formatDuration(Date.now() - trade.entryTime)
                    };
                } catch (error) {
                    // If can't get current price, return basic info
                    return {
                        pair: trade.pair,
                        side: trade.side,
                        entryPrice: trade.entryPrice,
                        currentPrice: trade.entryPrice,
                        size: trade.size,
                        stopLoss: trade.stopLoss,
                        takeProfit: trade.takeProfit,
                        strategy: trade.strategy,
                        unrealizedPnL: 0,
                        unrealizedPnLPercent: 0,
                        duration: bot.formatDuration(Date.now() - trade.entryTime)
                    };
                }
            }));
            
            return enrichedPositions;
        });
        
        // Balance handler - Account overview
        bot.telegram.setBalanceHandler(async () => {
            // Get balance - handle if it's an object or number
            const balanceData = bot.positionManager.getBalance();
            const balance = typeof balanceData === 'number' 
                ? balanceData 
                : (balanceData?.total || balanceData?.balance || 10000);
            
            const activeTrades = Array.from(bot.activeTrades.values());
            
            // Calculate capital in positions
            const inPositions = activeTrades.reduce((sum, trade) => {
                return sum + (trade.size * trade.entryPrice);
            }, 0);
            
            const available = balance - inPositions;
            const totalPnL = parseFloat(bot.stats.totalPnL) || 0;
            const dailyPnLPercent = balance > 0 ? (totalPnL / balance) * 100 : 0;
            
            return {
                total: parseFloat(balance),
                available: parseFloat(available),
                inPositions: parseFloat(inPositions),
                reserved: 0,
                dailyPnL: totalPnL,
                dailyPnLPercent: dailyPnLPercent,
                weeklyPnL: totalPnL, // Same as daily for now
                weeklyPnLPercent: dailyPnLPercent
            };
        });
        
        // History handler - Recent closed trades
        bot.telegram.setHistoryHandler(async (count = 10) => {
            // For now return empty - would need trade history tracking
            // You can add a tradeHistory array to bot.js to track this
            return [];
        });
        
        // Performance handler - By strategy and pair
        bot.telegram.setPerformanceHandler(async () => {
            // For now return empty - would need detailed tracking
            // You can add performance tracking by strategy/pair to bot.js
            return {
                byStrategy: {},
                byPair: {}
            };
        });
        
        // Stop handler
        bot.telegram.setStopHandler(async () => {
            await bot.stop();
            process.exit(0);
        });
        
        // Mode change handler
        bot.telegram.setModeChangeHandler(async (newMode) => {
            bot.mode = newMode;
            bot.positionManager.mode = newMode;
            console.log(`\n🔄 Mode changed to: ${newMode.toUpperCase()}\n`);
        });
    }

    // Handle graceful shutdown
    process.on('SIGINT', async () => {
        console.log('\n\n⚠️  Received SIGINT, shutting down gracefully...');
        await bot.stop();
        process.exit(0);
    });

    process.on('SIGTERM', async () => {
        console.log('\n\n⚠️  Received SIGTERM, shutting down gracefully...');
        await bot.stop();
        process.exit(0);
    });

    // Start the bot
    try {
        await bot.start();

        // Status updates every minute
        setInterval(() => {
            const stats = bot.getStats();
            console.log(`\n📊 Status Update:`);
            console.log(`   Active Positions: ${stats.activePositions}`);
            console.log(`   Signals Today: ${stats.signals}`);
            console.log(`   Win Rate: ${stats.winRate}`);
            console.log(`   Total PnL: $${stats.totalPnL}\n`);
        }, 60000);

    } catch (error) {
        console.error('❌ Fatal error:', error);
        process.exit(1);
    }
}

// Run
main().catch(error => {
    console.error('❌ Unhandled error:', error);
    process.exit(1);
});
