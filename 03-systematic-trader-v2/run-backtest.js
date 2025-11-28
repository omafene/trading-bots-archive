#!/usr/bin/env node
require('dotenv').config();
const ccxt = require('ccxt');
const config = require('./config');
const RegimeDetector = require('./core/regime-detector');
const EnhancedRiskManager = require('./core/enhanced-risk-manager');
const UpgradedMomentum = require('./strategies/upgraded-momentum');
const UpgradedMeanReversion = require('./strategies/upgraded-mean-reversion');
const UpgradedVolatilityBreakout = require('./strategies/upgraded-volatility-breakout');

function formatDuration(ms) {
    const hours = Math.floor(ms / 3600000);
    const minutes = Math.floor((ms % 3600000) / 60000);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

async function runBacktest(pair, days = 30) {
    console.log(`\n📈 Testing ${pair}...`);
    
    const exchange = new ccxt[config.exchange]({ enableRateLimit: true });
    const regimeDetector = new RegimeDetector(config.regimeDetection);
    const riskManager = new EnhancedRiskManager(config.risk);
    
    const strategies = [];
    if (config.strategies.momentum.enabled) {
        strategies.push(new UpgradedMomentum(config.strategies.momentum));
    }
    if (config.strategies.meanReversion.enabled) {
        strategies.push(new UpgradedMeanReversion(config.strategies.meanReversion));
    }
    if (config.strategies.volatilityBreakout.enabled) {
        strategies.push(new UpgradedVolatilityBreakout(config.strategies.volatilityBreakout));
    }
    
    const timeframe = '5m';
    const candlesToFetch = days * 288 + 200;
    
    console.log(`   Fetching ${candlesToFetch} candles...`);
    let candles;
    try {
        candles = await exchange.fetchOHLCV(pair, timeframe, undefined, candlesToFetch);
    } catch (error) {
        console.error(`   ❌ Failed to fetch data for ${pair}:`, error.message);
        return null;
    }
    
    console.log(`   ✓ Loaded ${candles.length} candles`);
    
    let balance = config.paperTradingBalance || 10000;
    const initialBalance = balance;
    let activePosition = null;
    
    const result = {
        pair,
        tradesList: [],
        wins: 0,
        losses: 0,
        totalProfit: 0,
        totalLoss: 0,
        maxDrawdown: 0,
        equity: [balance]
    };
    
    for (let i = 200; i < candles.length; i++) {
        const currentCandle = {
            timestamp: candles[i][0],
            open: candles[i][1],
            high: candles[i][2],
            low: candles[i][3],
            close: candles[i][4],
            volume: candles[i][5]
        };
        
        const historicalCandles = candles.slice(Math.max(0, i - 200), i + 1).map(c => ({
            timestamp: c[0],
            open: c[1],
            high: c[2],
            low: c[3],
            close: c[4],
            volume: c[5]
        }));
        
        // Check exit conditions
        if (activePosition) {
            let shouldClose = false;
            let closeReason = '';
            
            if (activePosition.side === 'buy') {
                if (currentCandle.low <= activePosition.stopLoss) {
                    shouldClose = true;
                    closeReason = 'stop_loss';
                } else if (currentCandle.high >= activePosition.takeProfit) {
                    shouldClose = true;
                    closeReason = 'take_profit';
                }
            } else {
                if (currentCandle.high >= activePosition.stopLoss) {
                    shouldClose = true;
                    closeReason = 'stop_loss';
                } else if (currentCandle.low <= activePosition.takeProfit) {
                    shouldClose = true;
                    closeReason = 'take_profit';
                }
            }
            
            if (shouldClose) {
                const exitPrice = closeReason === 'stop_loss' ? activePosition.stopLoss : activePosition.takeProfit;
                const pnl = activePosition.side === 'buy' ?
                    (exitPrice - activePosition.entryPrice) * activePosition.size :
                    (activePosition.entryPrice - exitPrice) * activePosition.size;
                
                balance += pnl;
                
                result.tradesList.push({
                    pair,
                    strategy: activePosition.strategy,
                    side: activePosition.side,
                    entryPrice: activePosition.entryPrice,
                    exitPrice,
                    size: activePosition.size,
                    pnl,
                    reason: closeReason,
                    duration: currentCandle.timestamp - activePosition.entryTime
                });
                
                if (pnl > 0) {
                    result.wins++;
                    result.totalProfit += pnl;
                } else {
                    result.losses++;
                    result.totalLoss += pnl;
                }
                
                activePosition = null;
            }
        }
        
        // Check for new entries
        if (!activePosition) {
            const regimeData = regimeDetector.detectRegime(pair, historicalCandles);
            
            if (!regimeData) continue;
            
            const dataPackage = {
                symbol: pair,
                primaryCandles: historicalCandles,
                higherCandles: historicalCandles,
                regimeData
            };
            
            for (const strategy of strategies) {
                if (strategy.name === 'Momentum-Pro' && 
                    !['TRENDING', 'STRONG_TREND', 'WEAK_TREND'].includes(regimeData.regime)) {
                    continue;
                }
                if (strategy.name === 'MeanReversion-Pro' &&
                    !['RANGING', 'WEAK_TREND'].includes(regimeData.regime)) {
                    continue;
                }
                
                try {
                    const signal = await strategy.evaluate(dataPackage);
                    
                    if (signal && signal.action !== 'HOLD') {
                        const positionSize = riskManager.calculatePosition(
                            signal,
                            balance,
                            historicalCandles,
                            regimeData,
                            null
                        );
                        
                        if (!positionSize) continue;
                        
                        activePosition = {
                            pair,
                            side: signal.action.toLowerCase() === 'buy' ? 'buy' : 'sell',
                            size: positionSize.size,
                            entryPrice: currentCandle.close,
                            stopLoss: signal.stopLoss,
                            takeProfit: signal.takeProfit,
                            strategy: strategy.name,
                            entryTime: currentCandle.timestamp
                        };
                        
                        break;
                    }
                } catch (error) {
                    // Skip on error
                }
            }
        }
        
        result.equity.push(balance);
    }
    
    const totalTrades = result.wins + result.losses;
    result.winRate = totalTrades > 0 ? (result.wins / totalTrades) * 100 : 0;
    result.profitFactor = result.totalLoss !== 0 ?
        Math.abs(result.totalProfit / result.totalLoss) : null;
    result.totalPnL = balance - initialBalance;
    
    let peak = initialBalance;
    for (const equity of result.equity) {
        if (equity > peak) peak = equity;
        const drawdown = ((peak - equity) / peak) * 100;
        if (drawdown > result.maxDrawdown) result.maxDrawdown = drawdown;
    }
    
    console.log(`\n   Results for ${pair}:`);
    console.log(`   Trades: ${totalTrades}`);
    console.log(`   Win Rate: ${result.winRate.toFixed(1)}%`);
    console.log(`   Profit Factor: ${result.profitFactor ? result.profitFactor : 'N/A'}`);
    console.log(`   Total PnL: $${result.totalPnL.toFixed(2)}`);
    console.log(`   Max Drawdown: ${result.maxDrawdown.toFixed(2)}%`);
    
    return result;
}

function calculateStrategyStats(allTrades) {
    const strategyStats = {};
    
    allTrades.forEach(trade => {
        const stratName = trade.strategy || 'Unknown';
        
        if (!strategyStats[stratName]) {
            strategyStats[stratName] = {
                trades: 0,
                wins: 0,
                losses: 0,
                totalPnL: 0,
                totalWinPnL: 0,
                totalLossPnL: 0,
                durations: []
            };
        }
        
        const stats = strategyStats[stratName];
        stats.trades++;
        stats.totalPnL += trade.pnl;
        stats.durations.push(trade.duration);
        
        if (trade.pnl > 0) {
            stats.wins++;
            stats.totalWinPnL += trade.pnl;
        } else {
            stats.losses++;
            stats.totalLossPnL += trade.pnl;
        }
    });
    
    Object.keys(strategyStats).forEach(strat => {
        const stats = strategyStats[strat];
        stats.winRate = stats.trades > 0 ? (stats.wins / stats.trades) * 100 : 0;
        stats.avgWin = stats.wins > 0 ? stats.totalWinPnL / stats.wins : 0;
        stats.avgLoss = stats.losses > 0 ? stats.totalLossPnL / stats.losses : 0;
        stats.expectancy = stats.trades > 0 ? stats.totalPnL / stats.trades : 0;
        stats.profitFactor = stats.totalLossPnL !== 0 ? 
            Math.abs(stats.totalWinPnL / stats.totalLossPnL) : null;
        stats.avgDuration = stats.durations.length > 0 ?
            stats.durations.reduce((a, b) => a + b, 0) / stats.durations.length : 0;
    });
    
    return strategyStats;
}

function printResults(results) {
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║                   BACKTEST RESULTS                         ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');
    
    const totalTrades = results.overall.wins + results.overall.losses;
    const winRate = totalTrades > 0 ? (results.overall.wins / totalTrades) * 100 : 0;
    const profitFactor = results.overall.totalLoss !== 0 ?
        Math.abs(results.overall.totalProfit / results.overall.totalLoss) : 'N/A';
    
    console.log('📊 Overall Statistics:');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`Total Trades:      ${totalTrades}`);
    console.log(`Wins:              ${results.overall.wins}`);
    console.log(`Losses:            ${results.overall.losses}`);
    console.log(`Win Rate:          ${winRate.toFixed(2)}%`);
    console.log(`Profit Factor:     ${typeof profitFactor === 'number' ? profitFactor.toFixed(2) : profitFactor}`);
    console.log(`Total PnL:         $${results.overall.totalPnL.toFixed(2)}`);
    console.log(`Max Drawdown:      ${results.overall.maxDrawdown.toFixed(2)}%`);
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    
    if (totalTrades > 0 && results.overall.allTrades.length > 0) {
        console.log('📊 Strategy Performance Breakdown:');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        
        const strategyStats = calculateStrategyStats(results.overall.allTrades);
        const sortedStrategies = Object.keys(strategyStats).sort((a, b) => 
            strategyStats[b].totalPnL - strategyStats[a].totalPnL
        );
        
        sortedStrategies.forEach(stratName => {
            const stats = strategyStats[stratName];
            const pctOfTotal = ((stats.trades / totalTrades) * 100).toFixed(1);
            
            console.log(`\n${stratName}:`);
            console.log(`  Trades: ${stats.trades} (${pctOfTotal}% of total)`);
            console.log(`  Win Rate: ${stats.winRate.toFixed(1)}%`);
            console.log(`  Total PnL: $${stats.totalPnL.toFixed(2)}`);
            console.log(`  Avg Win: $${stats.avgWin.toFixed(2)}`);
            console.log(`  Avg Loss: $${stats.avgLoss.toFixed(2)}`);
            console.log(`  Expectancy: $${stats.expectancy.toFixed(2)} per trade`);
            console.log(`  Profit Factor: ${stats.profitFactor ? stats.profitFactor.toFixed(2) : 'N/A'}`);
            console.log(`  Avg Duration: ${formatDuration(stats.avgDuration)}`);
        });
        
        console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }
    
    console.log('✅ Evaluation:');
    if (winRate >= 55 && results.overall.totalPnL > 0) {
        console.log('   ✅ EXCELLENT - Strong strategy performance');
    } else if (winRate >= 45 && results.overall.totalPnL > 0) {
        console.log('   ✅ GOOD - Strategy showing promise');
    } else if (winRate >= 40) {
        console.log('   ⚠️  MARGINAL - Needs improvement');
    } else {
        console.log('   ❌ POOR - Strategy needs major revision');
    }
    
    console.log('\n📝 Recommendations:');
    if (totalTrades < 30) {
        console.log('   • Low trade count - Consider longer test period or more pairs');
    }
    if (winRate < 50) {
        console.log('   • Win rate below 50% - Review entry criteria');
    }
    if (results.overall.maxDrawdown > 10) {
        console.log('   • High drawdown - Tighten risk management');
    }
}

async function main() {
    const args = process.argv.slice(2);
    const daysArg = args.find(arg => arg.startsWith('--days='));
    const days = daysArg ? parseInt(daysArg.split('=')[1]) : 7;
    
    console.log('╔════════════════════════════════════════════════════════════╗');
    console.log('║              SYSTEMATIC TRADING BOT BACKTEST               ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');
    
    console.log(`📅 Testing period: ${days} days`);
    console.log('📊 Testing all configured pairs\n');
    
    const regimeDetector = new RegimeDetector(config.regimeDetection);
    const riskManager = new EnhancedRiskManager(config.risk);
    
    const enabledStrategies = [];
    if (config.strategies.momentum.enabled) {
        const momentum = new UpgradedMomentum(config.strategies.momentum);
        enabledStrategies.push(momentum.name);
    }
    if (config.strategies.meanReversion.enabled) {
        const meanRev = new UpgradedMeanReversion(config.strategies.meanReversion);
        enabledStrategies.push(meanRev.name);
    }
    if (config.strategies.volatilityBreakout.enabled) {
        const volBreak = new UpgradedVolatilityBreakout(config.strategies.volatilityBreakout);
        enabledStrategies.push(volBreak.name);
    }
    
    console.log(`🧠 Testing ${enabledStrategies.length} strategies\n`);
    
    const results = {
        pairs: {},
        overall: {
            wins: 0,
            losses: 0,
            totalProfit: 0,
            totalLoss: 0,
            totalPnL: 0,
            maxDrawdown: 0,
            allTrades: []
        }
    };
    
    for (const pair of config.pairs) {
        const result = await runBacktest(pair, days);
        if (result) {
            results.pairs[pair] = result;
            results.overall.wins += result.wins;
            results.overall.losses += result.losses;
            results.overall.totalProfit += result.totalProfit;
            results.overall.totalLoss += result.totalLoss;
            results.overall.totalPnL += result.totalPnL;
            results.overall.maxDrawdown = Math.max(results.overall.maxDrawdown, result.maxDrawdown);
            
            if (result.tradesList && result.tradesList.length > 0) {
                results.overall.allTrades.push(...result.tradesList);
            }
        }
    }
    
    printResults(results);
}

main().catch(error => {
    console.error('❌ Backtest failed:', error);
    process.exit(1);
});
