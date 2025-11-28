/**
 * ENHANCED RISK MANAGER
 * 
 * Institutional-grade risk management:
 * - Fractional Kelly Criterion position sizing
 * - Volatility-adjusted sizing (ATR normalization)
 * - Multi-target profit taking (33%/33%/33%)
 * - Regime-based position adjustments
 * - Funding rate / liquidation risk adjustments
 * - Tiered drawdown protocols
 */

const EnhancedIndicators = require('../utils/enhanced-indicators');

class EnhancedRiskManager {
    constructor(config) {
        this.config = {
            maxRiskPerTrade: config.maxRiskPerTrade || 0.02,
            maxConcurrentPositions: config.maxConcurrentPositions || 3,
            maxPortfolioRisk: config.maxPortfolioRisk || 0.06,
            maxDrawdown: config.maxDrawdown || 0.15,
            minRiskRewardRatio: config.minRiskRewardRatio || 1.5,
            
            // Kelly Criterion settings
            useKelly: config.useKelly !== false,
            kellyFraction: config.kellyFraction || 0.25, // 25% of full Kelly
            
            // Volatility adjustment
            useVolatilityAdjustment: config.useVolatilityAdjustment !== false,
            atrMultiplierNormal: config.atrMultiplierNormal || 2.0,
            atrMultiplierHigh: config.atrMultiplierHigh || 2.5,
            highVolatilityPercentile: config.highVolatilityPercentile || 80,
            
            // Multi-target exits
            useMultiTargets: config.useMultiTargets !== false,
            target1Size: config.target1Size || 0.33,    // 33% at 1R
            target2Size: config.target2Size || 0.33,    // 33% at 2R
            target3Trail: config.target3Trail !== false, // Trail remaining 33%
            
            // Drawdown tiers
            drawdownTier1: config.drawdownTier1 || 0.05,  // 5%
            drawdownTier2: config.drawdownTier2 || 0.10,  // 10%
            drawdownTier3: config.drawdownTier3 || 0.15,  // 15%
            drawdownTier4: config.drawdownTier4 || 0.20,  // 20% HALT
            
            ...config
        };

        this.portfolioPeak = 0;
        this.currentDrawdown = 0;
        this.activeDrawdownTier = 0;
        this.dailyLossLimit = config.dailyLossLimit || 0.02; // 2% daily max loss
        this.dailyLoss = 0;
        this.lastResetDate = new Date().toDateString();
        
        // Performance tracking for Kelly
        this.tradeHistory = [];
        this.winRate = 0.5; // Default 50%
        this.avgWin = 0;
        this.avgLoss = 0;
        
        console.log('✅ Enhanced Risk Manager initialized');
        console.log(`   Max Risk per Trade: ${(this.config.maxRiskPerTrade * 100).toFixed(2)}%`);
        console.log(`   Kelly Criterion: ${this.config.useKelly ? 'ENABLED' : 'DISABLED'}`);
        console.log(`   Volatility Adjustment: ${this.config.useVolatilityAdjustment ? 'ENABLED' : 'DISABLED'}`);
        console.log(`   Multi-Target Exits: ${this.config.useMultiTargets ? 'ENABLED' : 'DISABLED'}`);
    }

    canOpenPosition(currentPositionCount, accountBalance) {
        // Reset daily loss if new day
        this.resetDailyLossIfNeeded();

        // Check daily loss limit
        if (this.dailyLoss >= this.config.dailyLossLimit * accountBalance) {
            console.log(`⚠️ Daily loss limit reached: $${this.dailyLoss.toFixed(2)}`);
            return false;
        }

        // Check concurrent position limit
        if (currentPositionCount >= this.config.maxConcurrentPositions) {
            console.log(`⚠️ Max concurrent positions reached (${currentPositionCount})`);
            return false;
        }

        // Check drawdown limit
        if (this.currentDrawdown >= this.config.maxDrawdown) {
            console.log(`⚠️ Max drawdown exceeded (${(this.currentDrawdown * 100).toFixed(2)}%)`);
            return false;
        }

        // Check tier 4 halt
        if (this.activeDrawdownTier >= 4) {
            console.log(`🛑 Trading HALTED - Tier 4 drawdown reached`);
            return false;
        }

        return true;
    }

    /**
     * Calculate position size using multiple methods and select optimal
     */
    calculatePosition(signal, accountBalance, candles = null, regimeData = null, cryptoData = null) {
        const { entryPrice, stopLoss, takeProfit, confidence } = signal;

        // Validate risk/reward ratio
        const riskDistance = Math.abs(entryPrice - stopLoss) / entryPrice;
        const rewardDistance = Math.abs(takeProfit - entryPrice) / entryPrice;
        const riskRewardRatio = rewardDistance / riskDistance;

        if (riskRewardRatio < this.config.minRiskRewardRatio) {
            console.log(`⚠️ Position Rejected: Poor R/R ratio ${riskRewardRatio.toFixed(2)}`);
            return null;
        }

        // Base position size using fixed fractional
        let positionSize = this.calculateFixedFractional(
            accountBalance,
            riskDistance,
            entryPrice
        );

        // Apply Kelly Criterion if enabled
        if (this.config.useKelly && this.tradeHistory.length >= 20) {
            const kellySize = this.calculateKellyPosition(
                accountBalance,
                riskDistance,
                entryPrice,
                riskRewardRatio
            );
            positionSize = Math.min(positionSize, kellySize);
        }

        // Apply volatility adjustment if candles provided
        if (this.config.useVolatilityAdjustment && candles) {
            positionSize = this.applyVolatilityAdjustment(
                positionSize,
                candles,
                entryPrice,
                riskDistance
            );
        }

        // Apply confidence scaling
        const confidenceMultiplier = 0.5 + (confidence * 0.5); // 0.5 to 1.0
        positionSize *= confidenceMultiplier;

        // Apply regime-based adjustment
        if (regimeData) {
            positionSize *= regimeData.positionSizeMultiplier;
        }

        // Apply crypto data adjustments (funding rate, liquidation risk)
        if (cryptoData && cryptoData.positionSizeAdjustment) {
            positionSize *= cryptoData.positionSizeAdjustment.multiplier;
        }

        // Apply drawdown tier reduction
        positionSize *= this.getDrawdownMultiplier();

        // Ensure position doesn't exceed max portfolio risk
        const positionValue = positionSize * entryPrice;
        const maxPositionValue = accountBalance * this.config.maxPortfolioRisk;
        const finalSize = Math.min(positionSize, maxPositionValue / entryPrice);

        // Calculate multi-target exits if enabled
        const targets = this.calculateMultiTargets(
            entryPrice,
            stopLoss,
            takeProfit,
            finalSize,
            riskDistance
        );

        return {
            size: finalSize,
            riskAmount: finalSize * entryPrice * riskDistance,
            positionValue: finalSize * entryPrice,
            riskPercent: ((finalSize * entryPrice * riskDistance) / accountBalance) * 100,
            riskRewardRatio: riskRewardRatio.toFixed(2),
            targets: targets,
            adjustments: {
                confidence: confidenceMultiplier,
                regime: regimeData?.positionSizeMultiplier || 1.0,
                crypto: cryptoData?.positionSizeAdjustment?.multiplier || 1.0,
                drawdown: this.getDrawdownMultiplier()
            }
        };
    }

    /**
     * Fixed fractional position sizing
     */
    calculateFixedFractional(accountBalance, riskDistance, entryPrice) {
        const riskAmount = accountBalance * this.config.maxRiskPerTrade;
        return riskAmount / (riskDistance * entryPrice);
    }

    /**
     * Kelly Criterion position sizing
     * f* = (Win Rate × R/R - Loss Rate) / R/R
     * Use fractional Kelly (25%) to reduce variance
     */
    calculateKellyPosition(accountBalance, riskDistance, entryPrice, rrRatio) {
        const lossRate = 1 - this.winRate;
        const kelly = (this.winRate * rrRatio - lossRate) / rrRatio;
        
        // Apply Kelly fraction (typically 0.25 for 1/4 Kelly)
        const fractionalKelly = kelly * this.config.kellyFraction;
        
        // Ensure Kelly is positive and reasonable
        const safeKelly = Math.max(0, Math.min(fractionalKelly, 0.05)); // Max 5% of capital
        
        const kellyRisk = accountBalance * safeKelly;
        return kellyRisk / (riskDistance * entryPrice);
    }

    /**
     * Volatility-adjusted position sizing using ATR
     */
    applyVolatilityAdjustment(baseSize, candles, entryPrice, targetRiskDistance) {
        const highs = candles.map(c => c.high);
        const lows = candles.map(c => c.low);
        const closes = candles.map(c => c.close);

        // Get ATR percentile
        const atrData = EnhancedIndicators.atrPercentile(highs, lows, closes);
        
        if (!atrData) return baseSize;

        // Adjust ATR multiplier based on volatility regime
        let atrMultiplier;
        if (atrData.isHighVolatility) {
            atrMultiplier = this.config.atrMultiplierHigh; // Wider stops in high vol
            return baseSize * 0.75; // Reduce size by 25% in high volatility
        } else {
            atrMultiplier = this.config.atrMultiplierNormal;
            return baseSize;
        }
    }

    /**
     * Calculate multi-target exit levels
     * Take profits at: 1R (33%), 2R (33%), Trail (33%)
     */
    calculateMultiTargets(entryPrice, stopLoss, takeProfit, totalSize, riskDistance) {
        if (!this.config.useMultiTargets) {
            return [{
                targetPrice: takeProfit,
                size: totalSize,
                rMultiple: 1.0,
                description: 'Full exit'
            }];
        }

        const rewardDistance = Math.abs(takeProfit - entryPrice) / entryPrice;
        const direction = entryPrice < takeProfit ? 1 : -1;

        return [
            {
                targetPrice: entryPrice + (direction * riskDistance * entryPrice * 1), // 1R
                size: totalSize * this.config.target1Size,
                rMultiple: 1.0,
                description: 'First target at 1R'
            },
            {
                targetPrice: entryPrice + (direction * riskDistance * entryPrice * 2), // 2R
                size: totalSize * this.config.target2Size,
                rMultiple: 2.0,
                description: 'Second target at 2R'
            },
            {
                targetPrice: takeProfit,
                size: totalSize * (1 - this.config.target1Size - this.config.target2Size),
                rMultiple: rewardDistance / riskDistance,
                trail: this.config.target3Trail,
                description: 'Final target with trailing stop'
            }
        ];
    }

    /**
     * Update performance metrics for Kelly Criterion
     */
    recordTrade(trade) {
        this.tradeHistory.push(trade);

        // Keep last 100 trades
        if (this.tradeHistory.length > 100) {
            this.tradeHistory.shift();
        }

        // Recalculate metrics
        const wins = this.tradeHistory.filter(t => t.pnl > 0);
        const losses = this.tradeHistory.filter(t => t.pnl <= 0);

        this.winRate = wins.length / this.tradeHistory.length;
        this.avgWin = wins.length > 0 
            ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length 
            : 0;
        this.avgLoss = losses.length > 0 
            ? Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0) / losses.length)
            : 0;

        // Update daily loss
        if (trade.pnl < 0) {
            this.dailyLoss += Math.abs(trade.pnl);
        }
    }

    /**
     * Tiered drawdown protocol
     */
    updateDrawdown(accountBalance) {
        // Track peak balance
        if (accountBalance > this.portfolioPeak) {
            this.portfolioPeak = accountBalance;
            this.activeDrawdownTier = 0; // Reset tier when new high
        }

        // Calculate current drawdown
        this.currentDrawdown = (this.portfolioPeak - accountBalance) / this.portfolioPeak;

        // Determine active tier
        let previousTier = this.activeDrawdownTier;

        if (this.currentDrawdown >= this.config.drawdownTier4) {
            this.activeDrawdownTier = 4; // HALT TRADING
        } else if (this.currentDrawdown >= this.config.drawdownTier3) {
            this.activeDrawdownTier = 3; // 50% size
        } else if (this.currentDrawdown >= this.config.drawdownTier2) {
            this.activeDrawdownTier = 2; // 75% size
        } else if (this.currentDrawdown >= this.config.drawdownTier1) {
            this.activeDrawdownTier = 1; // 90% size
        } else {
            this.activeDrawdownTier = 0; // Normal
        }

        // Alert on tier change
        if (this.activeDrawdownTier !== previousTier) {
            console.log(`\n⚠️ DRAWDOWN TIER CHANGE: ${previousTier} → ${this.activeDrawdownTier}`);
            console.log(`Current Drawdown: ${(this.currentDrawdown * 100).toFixed(2)}%`);
            console.log(`Position Size: ${(this.getDrawdownMultiplier() * 100).toFixed(0)}%\n`);
        }

        return this.currentDrawdown;
    }

    /**
     * Get position size multiplier based on drawdown tier
     */
    getDrawdownMultiplier() {
        switch (this.activeDrawdownTier) {
            case 0: return 1.0;   // Normal
            case 1: return 0.9;   // 5% DD: 90% size
            case 2: return 0.75;  // 10% DD: 75% size
            case 3: return 0.5;   // 15% DD: 50% size
            case 4: return 0.0;   // 20% DD: HALT
            default: return 1.0;
        }
    }

    /**
     * Reset daily loss tracking
     */
    resetDailyLossIfNeeded() {
        const today = new Date().toDateString();
        if (today !== this.lastResetDate) {
            this.dailyLoss = 0;
            this.lastResetDate = today;
        }
    }

    /**
     * Get current risk status
     */
    getStatus() {
        return {
            maxRiskPerTrade: `${(this.config.maxRiskPerTrade * 100).toFixed(2)}%`,
            maxConcurrentPositions: this.config.maxConcurrentPositions,
            currentDrawdown: `${(this.currentDrawdown * 100).toFixed(2)}%`,
            maxDrawdown: `${(this.config.maxDrawdown * 100).toFixed(2)}%`,
            drawdownTier: this.activeDrawdownTier,
            positionSizeMultiplier: this.getDrawdownMultiplier(),
            dailyLoss: `$${this.dailyLoss.toFixed(2)}`,
            dailyLossLimit: `$${(this.config.dailyLossLimit * this.portfolioPeak).toFixed(2)}`,
            winRate: `${(this.winRate * 100).toFixed(1)}%`,
            avgWin: `$${this.avgWin.toFixed(2)}`,
            avgLoss: `$${this.avgLoss.toFixed(2)}`,
            tradeCount: this.tradeHistory.length
        };
    }
}

module.exports = EnhancedRiskManager;
