/**
 * TELEGRAM INTEGRATION - ENHANCED
 * Remote monitoring and control via Telegram bot
 */

const TelegramBot = require('node-telegram-bot-api');

class TelegramIntegration {
    constructor(config) {
        this.config = config;
        this.bot = null;
        this.enabled = false;
        this.isPaused = false;
        
        // Handler functions (set by main bot)
        this.statsHandler = null;
        this.positionsHandler = null;
        this.balanceHandler = null;
        this.historyHandler = null;
        this.performanceHandler = null;
        this.stopHandler = null;
        this.modeChangeHandler = null;
        
        if (config.token && config.chatId) {
            this.enabled = true;
        }
    }
    
    /**
     * Check if bot is paused
     */
    isPausedCheck() {
        return this.isPaused;
    }
    
    /**
     * Start Telegram bot
     */
    async start() {
        if (!this.enabled) {
            console.log('⚠️  Telegram not configured (optional)');
            return;
        }
        
        try {
            this.bot = new TelegramBot(this.config.token, { polling: true });
            
            // Setup command handlers
            this.setupCommands();
            
            console.log('✅ Telegram bot connected');
            await this.sendMessage('🤖 *Bot Started*\n\nSystematic Trading Bot is now active!\nType /help for commands.');
            
        } catch (error) {
            console.error('❌ Failed to start Telegram bot:', error.message);
            this.enabled = false;
        }
    }
    
    /**
     * Setup bot commands
     */
    setupCommands() {
        // /start command
        this.bot.onText(/\/start/, (msg) => {
            const chatId = msg.chat.id;
            this.bot.sendMessage(chatId, 
                '🤖 *Systematic Trading Bot*\n\n' +
                'Your institutional-grade crypto trading system is ready!\n\n' +
                '📊 *Quick Commands:*\n' +
                '/status - Current overview\n' +
                '/pause - Pause trading\n' +
                '/resume - Resume trading\n' +
                '/positions - Active trades\n' +
                '/help - Full command list',
                { parse_mode: 'Markdown' }
            );
        });
        
        // /status command - Overview of everything
        this.bot.onText(/\/status/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.statsHandler && this.positionsHandler && this.balanceHandler) {
                try {
                    const stats = await this.statsHandler();
                    const positions = await this.positionsHandler();
                    const balance = await this.balanceHandler();
                    
                    let message = '📊 *TRADING STATUS*\n\n';
                    
                    // Bot State
                    const stateEmoji = this.isPaused ? '⏸️' : '▶️';
                    const stateText = this.isPaused ? 'PAUSED' : 'ACTIVE';
                    message += `${stateEmoji} *Bot State: ${stateText}*\n`;
                    if (this.isPaused) {
                        message += '⚠️ Not entering new positions\n';
                    }
                    message += '\n';
                    
                    // Balance Section
                    message += '💰 *Account Balance*\n';
                    message += `Capital: $${balance.total.toFixed(2)}\n`;
                    message += `Available: $${balance.available.toFixed(2)} (${((balance.available/balance.total)*100).toFixed(1)}%)\n`;
                    message += `In Positions: $${balance.inPositions.toFixed(2)} (${((balance.inPositions/balance.total)*100).toFixed(1)}%)\n`;
                    
                    if (balance.dailyPnL !== undefined) {
                        const pnlEmoji = balance.dailyPnL >= 0 ? '📈' : '📉';
                        const pnlSign = balance.dailyPnL >= 0 ? '+' : '';
                        message += `Daily PnL: ${pnlSign}$${balance.dailyPnL.toFixed(2)} (${pnlSign}${balance.dailyPnLPercent.toFixed(2)}%) ${pnlEmoji}\n`;
                    }
                    
                    message += '\n';
                    
                    // Positions Section
                    message += `📈 *Open Positions: ${positions.length}*\n`;
                    if (positions.length > 0) {
                        positions.forEach((pos, i) => {
                            const unrealizedPnL = pos.unrealizedPnL || 0;
                            const pnlSign = unrealizedPnL >= 0 ? '+' : '';
                            const sideEmoji = pos.side === 'buy' ? '🟢' : '🔴';
                            
                            message += `\n${sideEmoji} ${pos.pair} ${pos.side.toUpperCase()} (${pos.strategy})\n`;
                            message += `  Entry: $${pos.entryPrice} | Current: $${pos.currentPrice || pos.entryPrice}\n`;
                            message += `  Size: ${pos.size} ($${(pos.size * pos.entryPrice).toFixed(2)})\n`;
                            if (unrealizedPnL !== 0) {
                                message += `  Unrealized: ${pnlSign}$${unrealizedPnL.toFixed(2)} (${pnlSign}${pos.unrealizedPnLPercent?.toFixed(2)}%)\n`;
                            }
                            message += `  Stop: $${pos.stopLoss} | Target: $${pos.takeProfit}\n`;
                        });
                    } else {
                        message += 'No active positions\n';
                    }
                    
                    message += '\n';
                    
                    // Today's Performance
                    message += '🎯 *Today\'s Performance*\n';
                    message += `Trades: ${stats.todayTrades || 0} | Wins: ${stats.todayWins || 0} (${stats.todayWinRate || '0.0'}%)\n`;
                    if (stats.todayPnL !== undefined) {
                        const pnlSign = stats.todayPnL >= 0 ? '+' : '';
                        message += `Total PnL: ${pnlSign}$${stats.todayPnL.toFixed(2)}\n`;
                    }
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching status: ' + error.message);
                }
            } else {
                this.bot.sendMessage(chatId, '⚠️ Status handlers not configured');
            }
        });
        
        // /balance command - Detailed account info
        this.bot.onText(/\/balance/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.balanceHandler) {
                try {
                    const balance = await this.balanceHandler();
                    
                    let message = '💰 *ACCOUNT BALANCE*\n\n';
                    
                    message += `💵 Total Capital: $${balance.total.toFixed(2)}\n`;
                    message += `✅ Available: $${balance.available.toFixed(2)}\n`;
                    message += `📊 In Positions: $${balance.inPositions.toFixed(2)}\n`;
                    message += `🔒 Reserved: $${balance.reserved?.toFixed(2) || '0.00'}\n\n`;
                    
                    message += '*Allocation:*\n';
                    message += `Available: ${((balance.available/balance.total)*100).toFixed(1)}%\n`;
                    message += `Deployed: ${((balance.inPositions/balance.total)*100).toFixed(1)}%\n\n`;
                    
                    if (balance.dailyPnL !== undefined) {
                        message += '*Today:*\n';
                        const pnlSign = balance.dailyPnL >= 0 ? '+' : '';
                        const emoji = balance.dailyPnL >= 0 ? '📈' : '📉';
                        message += `${emoji} ${pnlSign}$${balance.dailyPnL.toFixed(2)} (${pnlSign}${balance.dailyPnLPercent.toFixed(2)}%)\n\n`;
                    }
                    
                    if (balance.weeklyPnL !== undefined) {
                        message += '*This Week:*\n';
                        const pnlSign = balance.weeklyPnL >= 0 ? '+' : '';
                        message += `${pnlSign}$${balance.weeklyPnL.toFixed(2)} (${pnlSign}${balance.weeklyPnLPercent?.toFixed(2)}%)\n\n`;
                    }
                    
                    message += `🕐 Last Updated: ${new Date().toLocaleTimeString()}`;
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching balance: ' + error.message);
                }
            } else {
                this.bot.sendMessage(chatId, '⚠️ Balance handler not configured');
            }
        });
        
        // /stats command - Performance statistics
        this.bot.onText(/\/stats/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.statsHandler) {
                try {
                    const stats = await this.statsHandler();
                    
                    let message = '📊 *PERFORMANCE STATISTICS*\n\n';
                    
                    message += `⏱ Trading Since: ${stats.startDate || 'N/A'}\n`;
                    message += `⏰ Uptime: ${stats.uptime}\n\n`;
                    
                    message += '🎯 *Overall Performance*\n';
                    message += `Total Trades: ${stats.trades}\n`;
                    message += `✅ Wins: ${stats.wins} (${stats.winRate})\n`;
                    message += `❌ Losses: ${stats.losses}\n`;
                    message += `⚖️ Win Rate: ${stats.winRate}\n\n`;
                    
                    message += '💰 *Financial Performance*\n';
                    message += `Total PnL: $${stats.totalPnL}\n`;
                    if (stats.profitFactor) {
                        message += `📈 Profit Factor: ${stats.profitFactor}\n`;
                    }
                    if (stats.avgWin) {
                        message += `Avg Win: $${stats.avgWin}\n`;
                        message += `Avg Loss: $${stats.avgLoss}\n`;
                    }
                    if (stats.bestTrade) {
                        message += `🏆 Best: $${stats.bestTrade}\n`;
                        message += `💀 Worst: $${stats.worstTrade}\n`;
                    }
                    message += '\n';
                    
                    message += '📉 *Risk Metrics*\n';
                    if (stats.maxDrawdown !== undefined) {
                        message += `Max Drawdown: ${stats.maxDrawdown}%\n`;
                    }
                    if (stats.currentDrawdown !== undefined) {
                        message += `Current Drawdown: ${stats.currentDrawdown}%\n`;
                    }
                    if (stats.sharpeRatio) {
                        message += `Sharpe Ratio: ${stats.sharpeRatio}\n`;
                    }
                    message += `📍 Active Positions: ${stats.activePositions}`;
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching stats: ' + error.message);
                }
            }
        });
        
        // /positions command - Active positions detail
        this.bot.onText(/\/positions/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.positionsHandler) {
                try {
                    const positions = await this.positionsHandler();
                    
                    if (positions.length === 0) {
                        this.bot.sendMessage(chatId, '📍 *No Active Positions*\n\nWaiting for entry signals...', { parse_mode: 'Markdown' });
                        return;
                    }
                    
                    let message = `📍 *ACTIVE POSITIONS (${positions.length})*\n\n`;
                    
                    positions.forEach((pos, i) => {
                        const unrealizedPnL = pos.unrealizedPnL || 0;
                        const pnlSign = unrealizedPnL >= 0 ? '+' : '';
                        const sideEmoji = pos.side === 'buy' ? '🟢 LONG' : '🔴 SHORT';
                        
                        message += `*${i + 1}. ${pos.pair} ${sideEmoji}*\n`;
                        message += `Strategy: ${pos.strategy}\n`;
                        message += `Entry: $${pos.entryPrice}\n`;
                        if (pos.currentPrice) {
                            message += `Current: $${pos.currentPrice}\n`;
                        }
                        message += `Size: ${pos.size}\n`;
                        message += `Value: $${(pos.size * pos.entryPrice).toFixed(2)}\n`;
                        
                        if (unrealizedPnL !== 0) {
                            const emoji = unrealizedPnL >= 0 ? '📈' : '📉';
                            message += `${emoji} Unrealized: ${pnlSign}$${unrealizedPnL.toFixed(2)} (${pnlSign}${pos.unrealizedPnLPercent?.toFixed(2)}%)\n`;
                        }
                        
                        message += `Stop Loss: $${pos.stopLoss}\n`;
                        message += `Take Profit: $${pos.takeProfit}\n`;
                        
                        if (pos.duration) {
                            message += `Duration: ${pos.duration}\n`;
                        }
                        
                        message += '\n';
                    });
                    
                    message += `🕐 Last Updated: ${new Date().toLocaleTimeString()}`;
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching positions: ' + error.message);
                }
            }
        });
        
        // /history command - Recent trade history
        this.bot.onText(/\/history(?:\s+(\d+))?/, async (msg, match) => {
            const chatId = msg.chat.id;
            const count = match[1] ? parseInt(match[1]) : 10;
            
            if (this.historyHandler) {
                try {
                    const history = await this.historyHandler(count);
                    
                    if (!history || history.length === 0) {
                        this.bot.sendMessage(chatId, '📜 No trade history available yet');
                        return;
                    }
                    
                    let message = `📜 *RECENT TRADES (Last ${Math.min(count, history.length)})*\n\n`;
                    
                    history.slice(0, count).forEach((trade, i) => {
                        const pnlSign = trade.pnL >= 0 ? '+' : '';
                        const emoji = trade.pnL >= 0 ? '✅' : '❌';
                        
                        message += `${emoji} *${trade.pair} ${trade.side.toUpperCase()}*\n`;
                        message += `Entry: $${trade.entryPrice} → Exit: $${trade.exitPrice}\n`;
                        message += `PnL: ${pnlSign}$${trade.pnL.toFixed(2)} (${pnlSign}${trade.pnLPercent?.toFixed(2)}%)\n`;
                        message += `Strategy: ${trade.strategy}\n`;
                        if (trade.duration) {
                            message += `Duration: ${trade.duration}\n`;
                        }
                        message += `Time: ${new Date(trade.exitTime).toLocaleString()}\n\n`;
                    });
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching history: ' + error.message);
                }
            } else {
                this.bot.sendMessage(chatId, '⚠️ History handler not configured');
            }
        });
        
        // /performance command - Strategy & pair breakdown
        this.bot.onText(/\/performance/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.performanceHandler) {
                try {
                    const perf = await this.performanceHandler();
                    
                    let message = '📈 *PERFORMANCE BREAKDOWN*\n\n';
                    
                    // By Strategy
                    if (perf.byStrategy && Object.keys(perf.byStrategy).length > 0) {
                        message += '*By Strategy:*\n';
                        Object.entries(perf.byStrategy).forEach(([strategy, data]) => {
                            message += `\n${strategy}:\n`;
                            message += `  Trades: ${data.trades}\n`;
                            message += `  Win Rate: ${data.winRate}%\n`;
                            message += `  PnL: $${data.pnl.toFixed(2)}\n`;
                        });
                        message += '\n';
                    }
                    
                    // By Pair
                    if (perf.byPair && Object.keys(perf.byPair).length > 0) {
                        message += '*By Pair:*\n';
                        Object.entries(perf.byPair).forEach(([pair, data]) => {
                            message += `\n${pair}:\n`;
                            message += `  Trades: ${data.trades}\n`;
                            message += `  Win Rate: ${data.winRate}%\n`;
                            message += `  PnL: $${data.pnl.toFixed(2)}\n`;
                        });
                    }
                    
                    this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
                } catch (error) {
                    this.bot.sendMessage(chatId, '⚠️ Error fetching performance: ' + error.message);
                }
            } else {
                this.bot.sendMessage(chatId, '⚠️ Performance handler not configured');
            }
        });
        
        // /mode command
        this.bot.onText(/\/mode (.+)/, async (msg, match) => {
            const chatId = msg.chat.id;
            const newMode = match[1].toLowerCase();
            
            const validModes = ['paper', 'live-tiny', 'live'];
            
            if (!validModes.includes(newMode)) {
                this.bot.sendMessage(chatId, 
                    '⚠️ *Invalid mode*\n\n' +
                    'Valid options:\n' +
                    '• `paper` - Simulated trading\n' +
                    '• `live-tiny` - Real trading with 1% risk\n' +
                    '• `live` - Full live trading',
                    { parse_mode: 'Markdown' }
                );
                return;
            }
            
            if (this.modeChangeHandler) {
                await this.modeChangeHandler(newMode);
                this.bot.sendMessage(chatId, `✅ *Mode Changed*\n\nNow running in: *${newMode.toUpperCase()}*`, { parse_mode: 'Markdown' });
            }
        });
        
        // /pause command
        this.bot.onText(/\/pause/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (this.isPaused) {
                this.bot.sendMessage(chatId, '⚠️ *Already Paused*\n\nBot is currently paused. Use /resume to continue trading.', { parse_mode: 'Markdown' });
                return;
            }
            
            this.isPaused = true;
            let message = '⏸️ *TRADING PAUSED*\n\n';
            message += '✅ Bot is still running and monitoring\n';
            message += '🛑 Will NOT enter new positions\n';
            message += '📊 Existing positions remain open\n';
            message += '🔔 Still receiving alerts\n\n';
            message += 'Use /resume to continue trading\n';
            message += 'Use /positions to check open trades';
            
            this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
        });
        
        // /resume command
        this.bot.onText(/\/resume/, async (msg) => {
            const chatId = msg.chat.id;
            
            if (!this.isPaused) {
                this.bot.sendMessage(chatId, '⚠️ *Already Active*\n\nBot is currently trading. Use /pause to stop.', { parse_mode: 'Markdown' });
                return;
            }
            
            this.isPaused = false;
            let message = '▶️ *TRADING RESUMED*\n\n';
            message += '✅ Bot is now actively trading\n';
            message += '📊 Looking for entry signals\n';
            message += '🎯 Risk management active\n\n';
            message += 'Use /status to check current state\n';
            message += 'Use /pause to stop trading';
            
            this.bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
        });
        
        // /stop command
        this.bot.onText(/\/stop/, async (msg) => {
            const chatId = msg.chat.id;
            
            this.bot.sendMessage(chatId, '🛑 *Stopping Bot*\n\nClosing positions and shutting down...', { parse_mode: 'Markdown' });
            
            if (this.stopHandler) {
                await this.stopHandler();
            }
        });
        
        // /help command
        this.bot.onText(/\/help/, (msg) => {
            const chatId = msg.chat.id;
            this.bot.sendMessage(chatId, 
                '🤖 *SYSTEMATIC TRADING BOT*\n\n' +
                '*📊 Monitoring Commands:*\n' +
                '/status - Complete overview (balance, positions, daily stats)\n' +
                '/balance - Detailed account balance\n' +
                '/positions - Active positions with P&L\n' +
                '/stats - Performance statistics\n' +
                '/history [n] - Recent trades (default 10)\n' +
                '/performance - Strategy & pair breakdown\n\n' +
                '*⚙️ Control Commands:*\n' +
                '/pause - Pause trading (keeps bot running)\n' +
                '/resume - Resume trading\n' +
                '/mode <mode> - Switch trading mode\n' +
                '/stop - Stop the bot completely\n\n' +
                '*🎯 Trading Modes:*\n' +
                '• `paper` - Simulated trading (no real money)\n' +
                '• `live-tiny` - Real trading with 1% risk\n' +
                '• `live` - Full live trading (2% risk)\n\n' +
                '*🔔 Auto Notifications:*\n' +
                'You\'ll receive alerts for:\n' +
                '• 📊 Trade entries/exits\n' +
                '• 🔄 Market regime changes\n' +
                '• ⚠️ Drawdown warnings\n' +
                '• 💰 Daily summaries\n\n' +
                '*Examples:*\n' +
                '`/history 5` - Show last 5 trades\n' +
                '`/mode paper` - Switch to paper trading',
                { parse_mode: 'Markdown' }
            );
        });
    }
    
    /**
     * Set handler functions
     */
    setStatsHandler(handler) {
        this.statsHandler = handler;
    }
    
    setPositionsHandler(handler) {
        this.positionsHandler = handler;
    }
    
    setBalanceHandler(handler) {
        this.balanceHandler = handler;
    }
    
    setHistoryHandler(handler) {
        this.historyHandler = handler;
    }
    
    setPerformanceHandler(handler) {
        this.performanceHandler = handler;
    }
    
    setStopHandler(handler) {
        this.stopHandler = handler;
    }
    
    setModeChangeHandler(handler) {
        this.modeChangeHandler = handler;
    }
    
    /**
     * Send message to configured chat
     */
    async sendMessage(message) {
        if (!this.enabled || !this.bot) {
            return;
        }
        
        try {
            await this.bot.sendMessage(this.config.chatId, message, { parse_mode: 'Markdown' });
        } catch (error) {
            console.error('Failed to send Telegram message:', error.message);
        }
    }
    
    /**
     * Send trade alert
     */
    async sendTradeAlert(type, data) {
        if (!this.enabled) return;
        
        let message = '';
        
        if (type === 'ENTRY') {
            const sideEmoji = data.side === 'buy' ? '🟢' : '🔴';
            message = `${sideEmoji} *${data.side.toUpperCase()} SIGNAL - ${data.pair}*\n\n`;
            message += `Strategy: ${data.strategy}\n`;
            message += `Entry: $${data.entryPrice}\n`;
            message += `Stop Loss: $${data.stopLoss} (${data.stopPercent}%)\n`;
            message += `Take Profit: $${data.takeProfit} (${data.profitPercent}%)\n`;
            message += `Position Size: ${data.size}\n`;
            message += `Value: $${data.value.toFixed(2)}\n`;
            message += `Confidence: ${data.confidence}%\n`;
            if (data.reasons) {
                message += `\nReasons: ${data.reasons}`;
            }
        } else if (type === 'EXIT') {
            const emoji = data.pnl >= 0 ? '✅' : '❌';
            const pnlSign = data.pnl >= 0 ? '+' : '';
            message = `${emoji} *CLOSED ${data.side.toUpperCase()} - ${data.pair}*\n\n`;
            message += `Entry: $${data.entryPrice}\n`;
            message += `Exit: $${data.exitPrice}\n`;
            message += `PnL: ${pnlSign}$${data.pnl.toFixed(2)} (${pnlSign}${data.pnlPercent.toFixed(2)}%)\n`;
            message += `Duration: ${data.duration}\n`;
            message += `Strategy: ${data.strategy}\n`;
            if (data.exitReason) {
                message += `Exit: ${data.exitReason}`;
            }
        }
        
        await this.sendMessage(message);
    }
    
    /**
     * Send daily summary
     */
    async sendDailySummary(summary) {
        if (!this.enabled) return;
        
        const emoji = summary.pnl >= 0 ? '📈' : '📉';
        const pnlSign = summary.pnl >= 0 ? '+' : '';
        
        let message = `${emoji} *DAILY SUMMARY - ${summary.date}*\n\n`;
        message += `📊 Trades: ${summary.totalTrades}\n`;
        message += `✅ Wins: ${summary.wins} (${summary.winRate}%)\n`;
        message += `❌ Losses: ${summary.losses}\n`;
        message += `💰 Total PnL: ${pnlSign}$${summary.pnl.toFixed(2)} (${pnlSign}${summary.pnlPercent.toFixed(2)}%)\n`;
        message += `📉 Max Drawdown: ${summary.maxDrawdown.toFixed(2)}%\n`;
        message += `💵 Balance: $${summary.balance.toFixed(2)}`;
        
        await this.sendMessage(message);
    }
    
    /**
     * Stop bot
     */
    async stop() {
        if (this.bot) {
            await this.bot.stopPolling();
            console.log('✅ Telegram bot stopped');
        }
    }
}

module.exports = TelegramIntegration;
