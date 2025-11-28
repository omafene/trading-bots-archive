#!/usr/bin/env node
/**
 * TRADING PERFORMANCE ANALYZER
 * Analyzes trade history and provides actionable insights
 */

const TradeHistoryLogger = require('./trade-history-logger');

class TradingAnalyzer {
    constructor(logPath = './trade-history.json') {
        this.logger = new TradeHistoryLogger(logPath);
    }

    async analyze() {
        await this.logger.initialize();

        const tradeCount = this.logger.getTradeCount();

        console.log('\n╔════════════════════════════════════════════════════════════╗');
        console.log('║           TRADING PERFORMANCE ANALYSIS                     ║');
        console.log('╚════════════════════════════════════════════════════════════╝\n');

        if (tradeCount === 0) {
            console.log('❌ No trades found. Keep trading to collect data!\n');
            return;
        }

        console.log(`📊 Analyzing ${tradeCount} trades...\n`);

        // Overall Statistics
        this.printOverallStats();
        
        // Strategy Performance
        this.printStrategyBreakdown();
        
        // Pair Performance
        this.printPairBreakdown();
        
        // Risk Metrics
        this.printRiskMetrics();
        
        // Recommendations
        this.printRecommendations();

        // Export option
        console.log('\n📁 To export data: node analyze-trades.js --export\n');
    }

    printOverallStats() {
        const stats = this.logger.getStats();

        console.log('📈 OVERALL PERFORMANCE');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log(`Total Trades:      ${stats.totalTrades}`);
        console.log(`Wins:              ${stats.wins} (${stats.winRate}%)`);
        console.log(`Losses:            ${stats.losses}`);
        console.log(`Win Rate:          ${stats.winRate}%`);
        console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        console.log(`Total P&L:         $${stats.totalPnL}`);
        console.log(`Profit Factor:     ${stats.profitFactor}`);
        console.log(`Average Win:       $${stats.avgWin}`);
        console.log(`Average Loss:      $${stats.avgLoss}`);
        console.log(`Best Trade:        $${stats.bestTrade}`);
        console.log(`Worst Trade:       $${stats.worstTrade}`);
        console.log(`Avg Duration:      ${stats.avgDuration}`);
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }

    printStrategyBreakdown() {
        const strategies = this.logger.getStrategyBreakdown();

        console.log('🧠 STRATEGY PERFORMANCE');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        
        Object.entries(strategies).forEach(([name, data]) => {
            console.log(`\n${name}:`);
            console.log(`  Trades:    ${data.trades}`);
            console.log(`  Win Rate:  ${data.winRate}%`);
            console.log(`  P&L:       $${data.pnl}`);
        });
        
        console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }

    printPairBreakdown() {
        const pairs = this.logger.getPairBreakdown();

        console.log('💱 PAIR PERFORMANCE');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        
        // Sort by P&L
        const sorted = Object.entries(pairs).sort((a, b) => 
            parseFloat(b[1].pnl) - parseFloat(a[1].pnl)
        );

        sorted.forEach(([pair, data]) => {
            const emoji = parseFloat(data.pnl) > 0 ? '📈' : '📉';
            console.log(`\n${emoji} ${pair}:`);
            console.log(`  Trades:    ${data.trades}`);
            console.log(`  Win Rate:  ${data.winRate}%`);
            console.log(`  P&L:       $${data.pnl}`);
        });
        
        console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }

    printRiskMetrics() {
        const stats = this.logger.getStats();
        const drawdown = this.logger.getDrawdown();

        console.log('📉 RISK METRICS');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log(`Max Drawdown:      ${drawdown.max}%`);
        console.log(`Current Drawdown:  ${drawdown.current}%`);
        console.log(`Profit Factor:     ${stats.profitFactor}`);
        
        // Calculate Sharpe approximation
        const trades = this.logger.getAllTrades();
        if (trades.length >= 20) {
            const returns = trades.map(t => t.pnlPercent);
            const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
            const stdDev = Math.sqrt(
                returns.reduce((sq, n) => sq + Math.pow(n - avgReturn, 2), 0) / returns.length
            );
            const sharpe = stdDev > 0 ? (avgReturn / stdDev) : 0;
            console.log(`Sharpe Ratio:      ${sharpe.toFixed(2)}`);
        }
        
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }

    printRecommendations() {
        const stats = this.logger.getStats();
        const strategies = this.logger.getStrategyBreakdown();
        const pairs = this.logger.getPairBreakdown();
        const drawdown = this.logger.getDrawdown();

        console.log('💡 ANALYSIS & RECOMMENDATIONS');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

        // Sample size check
        if (stats.totalTrades < 50) {
            console.log('⚠️  INSUFFICIENT DATA');
            console.log(`   You have ${stats.totalTrades} trades. Need 50+ for reliable analysis.`);
            console.log(`   Continue paper trading for ${50 - stats.totalTrades} more trades.\n`);
        } else if (stats.totalTrades < 100) {
            console.log('✅ ADEQUATE SAMPLE SIZE');
            console.log(`   ${stats.totalTrades} trades is enough for initial evaluation.`);
            console.log(`   100+ trades recommended for high confidence.\n`);
        } else {
            console.log('✅ EXCELLENT SAMPLE SIZE');
            console.log(`   ${stats.totalTrades} trades provides statistically significant results.\n`);
        }

        // Win rate evaluation
        const winRate = parseFloat(stats.winRate);
        if (winRate >= 60) {
            console.log('✅ EXCELLENT WIN RATE');
            console.log(`   ${stats.winRate}% exceeds target of 55-60%`);
            console.log('   → Ready to consider live trading\n');
        } else if (winRate >= 55) {
            console.log('✅ GOOD WIN RATE');
            console.log(`   ${stats.winRate}% meets institutional target`);
            console.log('   → On track for live deployment\n');
        } else if (winRate >= 50) {
            console.log('⚠️  BORDERLINE WIN RATE');
            console.log(`   ${stats.winRate}% is below target of 55%`);
            console.log('   → Continue paper trading and optimize\n');
        } else {
            console.log('❌ LOW WIN RATE');
            console.log(`   ${stats.winRate}% is below profitable threshold`);
            console.log('   → Strategy needs adjustment before live trading\n');
        }

        // Profit factor evaluation
        const profitFactor = parseFloat(stats.profitFactor);
        if (!isNaN(profitFactor)) {
            if (profitFactor >= 2.0) {
                console.log('✅ EXCELLENT PROFIT FACTOR');
                console.log(`   ${stats.profitFactor} indicates strong edge\n`);
            } else if (profitFactor >= 1.5) {
                console.log('✅ GOOD PROFIT FACTOR');
                console.log(`   ${stats.profitFactor} meets minimum target\n`);
            } else if (profitFactor >= 1.0) {
                console.log('⚠️  LOW PROFIT FACTOR');
                console.log(`   ${stats.profitFactor} is barely profitable\n`);
            } else {
                console.log('❌ UNPROFITABLE');
                console.log(`   Profit factor ${stats.profitFactor} < 1.0\n`);
            }
        }

        // Drawdown evaluation
        const maxDD = parseFloat(drawdown.max);
        if (maxDD <= 5) {
            console.log('✅ EXCELLENT RISK CONTROL');
            console.log(`   Max drawdown ${drawdown.max}% is very low\n`);
        } else if (maxDD <= 10) {
            console.log('✅ GOOD RISK CONTROL');
            console.log(`   Max drawdown ${drawdown.max}% is acceptable\n`);
        } else if (maxDD <= 15) {
            console.log('⚠️  MODERATE DRAWDOWN');
            console.log(`   Max drawdown ${drawdown.max}% - tighten risk management\n`);
        } else {
            console.log('❌ HIGH DRAWDOWN');
            console.log(`   Max drawdown ${drawdown.max}% is concerning\n`);
        }

        // Strategy recommendations
        console.log('🎯 STRATEGY INSIGHTS:');
        const sortedStrategies = Object.entries(strategies).sort((a, b) => 
            parseFloat(b[1].pnl) - parseFloat(a[1].pnl)
        );
        
        sortedStrategies.forEach(([name, data]) => {
            const wr = parseFloat(data.winRate);
            if (wr >= 55) {
                console.log(`   ✅ ${name}: Strong performer (${data.winRate}%)`);
            } else if (wr >= 45) {
                console.log(`   ⚠️  ${name}: Needs optimization (${data.winRate}%)`);
            } else {
                console.log(`   ❌ ${name}: Consider disabling (${data.winRate}%)`);
            }
        });

        console.log('\n💱 PAIR INSIGHTS:');
        const sortedPairs = Object.entries(pairs).sort((a, b) => 
            parseFloat(b[1].winRate) - parseFloat(a[1].winRate)
        );
        
        sortedPairs.forEach(([pair, data]) => {
            const wr = parseFloat(data.winRate);
            const pnl = parseFloat(data.pnl);
            if (wr >= 55 && pnl > 0) {
                console.log(`   ✅ ${pair}: Best performer`);
            } else if (wr < 45 || pnl < 0) {
                console.log(`   ❌ ${pair}: Consider removing`);
            }
        });

        console.log('\n🚦 GO/NO-GO DECISION:');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        
        const readyForLive = 
            stats.totalTrades >= 50 &&
            winRate >= 55 &&
            profitFactor >= 1.5 &&
            maxDD <= 10;

        if (readyForLive) {
            console.log('✅ READY FOR LIVE TRADING');
            console.log('   All criteria met. Consider starting with /mode live-tiny\n');
        } else {
            console.log('⚠️  NOT READY YET');
            console.log('   Continue paper trading. Address issues above.\n');
        }

        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    }
}

// Run analysis
async function main() {
    const analyzer = new TradingAnalyzer('./trade-history.json');
    
    if (process.argv.includes('--export')) {
        await analyzer.logger.initialize();
        await analyzer.logger.exportCSV();
    } else {
        await analyzer.analyze();
    }
}

main().catch(error => {
    console.error('❌ Analysis error:', error);
    process.exit(1);
});
