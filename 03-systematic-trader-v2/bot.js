/**
 * SYSTEMATIC TRADING BOT V2 - COMPLETE WITH TRADE LOGGING
 * Main orchestrator with institutional-grade enhancements
 */

const ccxt = require('ccxt');
const DataEngine = require('./core/data-engine');
const PositionManager = require('./core/position-manager');
const RegimeDetector = require('./core/regime-detector');
const CryptoDataFetcher = require('./core/crypto-data-fetcher');
const EnhancedRiskManager = require('./core/enhanced-risk-manager');
const TelegramIntegration = require('./core/telegram-integration');
const TradeHistoryLogger = require('./trade-history-logger');

// Enhanced strategies
const UpgradedMomentum = require('./strategies/upgraded-momentum');
const UpgradedMeanReversion = require('./strategies/upgraded-mean-reversion');
const UpgradedVolatilityBreakout = require('./strategies/upgraded-volatility-breakout');

class SystematicTradingBot {
    constructor(config) {
        this.config = config;
        this.mode = config.mode || 'paper';
        this.running = false;
        this.startTime = Date.now();

        // Statistics
        this.stats = {
            signals: 0,
            trades: 0,
            wins: 0,
            losses: 0,
            totalPnL: 0,
            activePositions: 0
        };

        // Active trades map
        this.activeTrades = new Map();

        // Initialize trade history logger
        this.tradeLogger = new TradeHistoryLogger('./trade-history.json');

        // Initialize exchange
        this.initializeExchange();

        // Initialize core components
        this.dataEngine = new DataEngine(this.exchange, config);
        this.positionManager = new PositionManager(this.exchange, config, this.mode);
        this.riskManager = new EnhancedRiskManager(config.risk);

        // Initialize regime detector
        this.regimeDetector = new RegimeDetector(config.regimeDetection);

        // Initialize crypto data fetcher (if enabled)
        if (config.cryptoData && config.cryptoData.enabled) {
            this.cryptoDataFetcher = new CryptoDataFetcher(config.cryptoData);
        }

        // Initialize strategies
        this.strategies = this.initializeStrategies();

        // Initialize Telegram (if configured)
        if (config.telegram && config.telegram.token) {
            this.telegram = new TelegramIntegration(config.telegram);
        }

        console.log(`✅ Bot initialized in ${this.mode.toUpperCase()} mode`);
        console.log(`📊 Monitoring ${config.pairs.length} pairs`);
        console.log(`🧠 Active strategies: ${this.strategies.length}`);
    }

    initializeExchange() {
        const exchangeName = this.config.exchange;
        const ExchangeClass = ccxt[exchangeName];

        if (!ExchangeClass) {
            throw new Error(`Exchange ${exchangeName} not supported`);
        }

        this.exchange = new ExchangeClass({
            apiKey: this.config.apiKey || process.env.EXCHANGE_API_KEY,
            secret: this.config.apiSecret || process.env.EXCHANGE_API_SECRET,
            enableRateLimit: true,
            options: {
                defaultType: this.config.marketType || 'spot'
            }
        });

        console.log(`🔗 Connected to ${exchangeName}`);
    }

    initializeStrategies() {
        const strategies = [];
        const strategyConfig = this.config.strategies;

        // Initialize enabled strategies
        if (strategyConfig.momentum && strategyConfig.momentum.enabled) {
            strategies.push(new UpgradedMomentum(strategyConfig.momentum));
            console.log('✓ Momentum strategy loaded');
        }

        if (strategyConfig.meanReversion && strategyConfig.meanReversion.enabled) {
            strategies.push(new UpgradedMeanReversion(strategyConfig.meanReversion));
            console.log('✓ Mean Reversion strategy loaded');
        }

        if (strategyConfig.volatilityBreakout && strategyConfig.volatilityBreakout.enabled) {
            strategies.push(new UpgradedVolatilityBreakout(strategyConfig.volatilityBreakout));
            console.log('✓ Volatility Breakout strategy loaded');
        }

        return strategies;
    }

    async start() {
        this.running = true;

        console.log('\n🚀 Starting systematic trading bot...\n');

        // Initialize trade history logger
        console.log('📝 Initializing trade logger...');
        await this.tradeLogger.initialize();
        console.log('✅ Trade logger ready');

        // Start Telegram bot
        if (this.telegram) {
            console.log('📱 Starting Telegram bot...');
            try {
                await this.telegram.start();
                await this.telegram.sendMessage('🚀 Bot started in ' + this.mode.toUpperCase() + ' mode');
                console.log('✅ Telegram ready');
            } catch (error) {
                console.log('⚠️  Telegram failed to start:', error.message);
                console.log('   Bot will continue without Telegram');
                this.telegram = null;
            }
        }

        // Main trading loop
        console.log('🔄 Starting trading loop...\n');
        await this.runTradingLoop();
    }

    async runTradingLoop() {
        console.log('✅ Trading loop STARTED - will scan every 30 seconds');
        
        while (this.running) {
            try {
                console.log(`\n📊 Scanning ${this.config.pairs.length} pairs...`);
                
                // Scan all pairs
                for (const pair of this.config.pairs) {
                    await this.scanPair(pair);
                }

                // Check existing positions
                await this.managePositions();

                // Wait before next scan
                console.log('⏳ Waiting 30 seconds before next scan...');
                await this.sleep(this.config.scanInterval || 30000); // 30 seconds default

            } catch (error) {
                console.error('❌ Error in trading loop:', error.message);
                console.error('Stack:', error.stack);

                if (this.telegram) {
                    await this.telegram.sendMessage(`⚠️ Error: ${error.message}`);
                }

                // Wait before retry
                await this.sleep(60000);
            }
        }
    }

    async scanPair(pair) {
        try {
            console.log(`  → Scanning ${pair}...`);
            
            // Fetch multi-timeframe candle data
            const primaryTimeframe = this.config.primaryTimeframe || '15m';
            const higherTimeframe = this.config.higherTimeframe || '1h';

            console.log(`     Fetching ${primaryTimeframe} candles...`);
            const primaryCandles = await this.dataEngine.fetchCandles(pair, primaryTimeframe, 200);
            const higherCandles = await this.dataEngine.fetchCandles(pair, higherTimeframe, 100);

            if (!primaryCandles || primaryCandles.length < 100) {
                console.log(`     ⚠️ Not enough data for ${pair} (${primaryCandles?.length || 0} candles)`);
                return; // Not enough data
            }

            console.log(`     ✓ Got ${primaryCandles.length} candles`);

            // Get current price
            const currentPrice = primaryCandles[primaryCandles.length - 1].close;

            // Detect market regime using ADX
            console.log(`     Detecting regime...`);
            const regimeData = this.regimeDetector.detectRegime(pair, primaryCandles);

            // Get crypto-specific data (if enabled)
            let cryptoData = null;
            if (this.cryptoDataFetcher) {
                cryptoData = await this.cryptoDataFetcher.fetchAllData(pair);
            }

            // Check if any strategy-market regime mismatch would halt trading
            if (cryptoData && cryptoData.liquidationRisk && cryptoData.liquidationRisk.score > 0.8) {
                console.log(`⚠️  ${pair}: High liquidation risk (${(cryptoData.liquidationRisk.score * 100).toFixed(1)}%) - Reducing position sizes`);
            }

            // Evaluate each strategy
            console.log(`     Evaluating ${this.strategies.length} strategies...`);
            for (const strategy of this.strategies) {
       
                const isAllowed = regimeData?.allowedStrategies.includes(strategy.name);
console.log(`       → ${strategy.name} ${isAllowed ? '✓' : '✗'} (regime: ${regimeData?.regime || 'unknown'})`);

// Check if strategy is allowed in current regime
if (regimeData && !isAllowed) {
    continue; // Skip silently, already logged above
}
                console.log(`         ✓ Evaluating...`);

                // Prepare data package
                const dataPackage = {
                    pair,
                    primaryCandles,
                    higherCandles,
                    currentPrice,
                    regimeData,
                    cryptoData
                };

                // Evaluate strategy
                const signal = await strategy.evaluate(dataPackage);
                
                // Log strategy output
                if (signal) {
                    console.log(`         Signal: ${signal.action} (confidence: ${(signal.confidence * 100).toFixed(1)}%)`);
                } else {
                    console.log(`         Signal: NONE`);
                }

                if (signal && signal.action !== 'HOLD') {
                    this.stats.signals++;

                    // Check if we already have a position
                    if (this.activeTrades.has(pair)) {
                        continue; // Skip if already in position
                    }

                    // Process signal
                    await this.processSignal(signal, dataPackage);
                }
            }

        } catch (error) {
            console.error(`     ❌ Error scanning ${pair}:`, error.message);
            console.error(`     Stack:`, error.stack);
        }
    }

    async processSignal(signal, dataPackage) {
        const { pair, currentPrice, regimeData, cryptoData } = dataPackage;

        console.log(`\n🎯 ${this.mode.toUpperCase()} SIGNAL DETECTED`);
        console.log(`   Pair: ${pair}`);
        console.log(`   Strategy: ${signal.strategy}`);
        console.log(`   Action: ${signal.action}`);
        console.log(`   Price: ${currentPrice}`);
        console.log(`   Confidence: ${(signal.confidence * 100).toFixed(1)}%`);

        // Calculate position size using risk manager
        const balanceData = this.positionManager.getBalance();
        const balance = typeof balanceData === 'number' 
            ? balanceData 
            : (balanceData?.total || balanceData?.balance || 10000);

        const positionSize = this.riskManager.calculatePosition(
            signal,
            balance,
            dataPackage.primaryCandles,
            regimeData,
            cryptoData
        );

        if (!positionSize) {
            console.log('⚠️  Position rejected by risk manager (poor R/R ratio)');
            return;
        }

        console.log(`   Position Size: ${positionSize.size} (${positionSize.riskPercent.toFixed(2)}%)`);
        console.log(`   Stop Loss: ${signal.stopLoss}`);
        console.log(`   Take Profit: ${signal.takeProfit}\n`);

        // Check risk limits
        if (!this.riskManager.canOpenPosition(this.activeTrades.size, balance)) {
            console.log('⚠️  Risk limits exceeded - skipping trade');
            return;
        }

        // Check if bot is paused via Telegram
        if (this.telegram && this.telegram.isPaused) {
            console.log('⏸️  Bot paused - skipping trade signal');
            console.log('   Use /resume in Telegram to continue trading\n');
            return;
        }

        // Execute trade
        try {
            const trade = await this.positionManager.openPosition({
                pair,
                side: signal.action.toLowerCase(),
                currentPrice: currentPrice,
                size: positionSize.size,
                stopLoss: signal.stopLoss,
                takeProfit: signal.takeProfit,
                strategy: signal.strategy,
                confidence: signal.confidence,
                regimeData
            });

            if (trade) {
                this.activeTrades.set(pair, trade);
                this.stats.trades++;
                this.stats.activePositions++;

                console.log(`✅ Position opened: ${pair} ${signal.action}`);

                // Send Telegram notification
                if (this.telegram) {
                    await this.telegram.sendMessage(
                        `🎯 ${this.mode.toUpperCase()} ENTRY\n\n` +
                        `${pair} ${signal.action.toLowerCase()}\n` +
                        `Strategy: ${signal.strategy}\n` +
                        `Entry: ${currentPrice}\n` +
                        `Size: ${positionSize.size}\n` +
                        `Risk: $${(positionSize.size * Math.abs(currentPrice - signal.stopLoss)).toFixed(2)}\n` +
                        `SL: ${signal.stopLoss}\n` +
                        `TP: ${signal.takeProfit}\n` +
                        `Confidence: ${(signal.confidence * 100).toFixed(1)}%`
                    );
                }
            }

        } catch (error) {
            console.error(`❌ Failed to open position:`, error.message);
        }
    }

    async managePositions() {
        for (const [pair, trade] of this.activeTrades.entries()) {
            try {
                // Fetch current price
                const ticker = await this.exchange.fetchTicker(pair);
                const currentPrice = ticker.last;

                // Check if position should be closed
                const shouldClose = this.positionManager.shouldClosePosition(trade, currentPrice);

                if (shouldClose.close) {
                    await this.closePosition(pair, trade, currentPrice, shouldClose.reason);
                }

            } catch (error) {
                console.error(`❌ Error managing position ${pair}:`, error.message);
            }
        }
    }

    async closePosition(pair, trade, currentPrice, reason) {
        try {
            const pnl = this.positionManager.calculatePnL(trade, currentPrice);
            const pnlPercent = (pnl / (trade.entryPrice * trade.size)) * 100;

            // LOG THE TRADE TO HISTORY
            await this.tradeLogger.logTrade({
                pair: pair,
                strategy: trade.strategy,
                side: trade.side,
                entryPrice: trade.entryPrice,
                exitPrice: currentPrice,
                entryTime: trade.entryTime,
                exitTime: Date.now(),
                size: trade.size,
                pnl: pnl,
                pnlPercent: pnlPercent,
                duration: Date.now() - trade.entryTime,
                exitReason: reason,
                confidence: trade.confidence,
                regime: trade.regimeData?.regime,
                stopLoss: trade.stopLoss,
                takeProfit: trade.takeProfit,
                mode: this.mode
            });

            // Close the position
            await this.positionManager.closePosition(trade, currentPrice, reason);

            // Update statistics
            this.activeTrades.delete(pair);
            this.stats.activePositions--;
            this.stats.totalPnL += pnl;

            if (pnl > 0) {
                this.stats.wins++;
            } else {
                this.stats.losses++;
            }

            console.log(`\n🚪 ${this.mode.toUpperCase()} EXIT: ${reason.toUpperCase()}`);
            console.log(`   Pair: ${pair} ${pnl >= 0 ? '✅' : '❌'}`);
console.log(`   Entry: ${trade.entryPrice}`);
console.log(`   Exit: ${currentPrice}`);
console.log(`   PnL: $${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)`);
console.log(`   Duration: ${this.formatDuration(Date.now() - trade.entryTime)}`);
console.log(`   📊 Total Trades: ${this.tradeLogger.getTradeCount()}\n`);

            // Send Telegram notification
            if (this.telegram) {
                const winRate = this.stats.trades > 0
                    ? ((this.stats.wins / this.stats.trades) * 100).toFixed(1)
                    : '0.0';

                await this.telegram.sendMessage(
                    `🚪 ${this.mode.toUpperCase()} EXIT: ${reason.toUpperCase()}\n\n` +
                    `${pair} ${pnl >= 0 ? '✅' : '❌'}\n` +
                    `Entry: ${trade.entryPrice}\n` +
                    `Exit: ${currentPrice}\n` +
                    `PnL: $${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)\n` +
                    `Duration: ${this.formatDuration(Date.now() - trade.entryTime)}\n\n` +
                    `📊 Session Stats:\n` +
                    `Win Rate: ${winRate}%\n` +
                    `Total PnL: $${this.stats.totalPnL.toFixed(2)}\n` +
                    `Total Trades: ${this.tradeLogger.getTradeCount()}`
                );
            }

        } catch (error) {
            console.error(`❌ Failed to close position ${pair}:`, error.message);
        }
    }

    getStats() {
        const uptime = Date.now() - this.startTime;
        const winRate = this.stats.trades > 0
            ? ((this.stats.wins / this.stats.trades) * 100).toFixed(1) + '%'
            : '0%';

        return {
            uptime: this.formatDuration(uptime),
            mode: this.mode,
            signals: this.stats.signals,
            trades: this.stats.trades,
            wins: this.stats.wins,
            losses: this.stats.losses,
            winRate,
            totalPnL: this.stats.totalPnL.toFixed(2),
            activePositions: this.stats.activePositions
        };
    }

    formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ${hours % 24}h`;
        if (hours > 0) return `${hours}h ${minutes % 60}m`;
        if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
        return `${seconds}s`;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async stop() {
        console.log('\n🛑 Stopping bot...\n');
        this.running = false;

        // Close all positions
        for (const [pair, trade] of this.activeTrades.entries()) {
            try {
                const ticker = await this.exchange.fetchTicker(pair);
                await this.closePosition(pair, trade, ticker.last, 'shutdown');
            } catch (error) {
                console.error(`Failed to close ${pair}:`, error.message);
            }
        }

        // Final statistics
        const stats = this.getStats();
        const loggerStats = this.tradeLogger.getStats();
        
        console.log('📊 Final Statistics:');
        console.log(`   Total Runtime: ${stats.uptime}`);
        console.log(`   Total Trades: ${this.tradeLogger.getTradeCount()}`);
        console.log(`   Win Rate: ${loggerStats ? loggerStats.winRate + '%' : stats.winRate}`);
        console.log(`   Total PnL: $${stats.totalPnL}\n`);

        if (this.telegram) {
            await this.telegram.sendMessage(
                `🛑 Bot stopped\n\n` +
                `Runtime: ${stats.uptime}\n` +
                `Trades: ${this.tradeLogger.getTradeCount()}\n` +
                `Win Rate: ${stats.winRate}\n` +
                `Total PnL: $${stats.totalPnL}`
            );
            await this.telegram.stop();
        }

        console.log('✅ Bot stopped gracefully\n');
    }
}

module.exports = SystematicTradingBot;
