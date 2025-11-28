/**
 * SYSTEMATIC TRADING BOT V2 - ENHANCED CONFIGURATION
 * 
 * Institutional-grade trading bot with:
 * - Multi-timeframe analysis
 * - ADX regime detection
 * - Kelly Criterion position sizing
 * - Crypto-specific data integration
 * - Multi-target profit taking
 * - Tiered drawdown protocols
 */

module.exports = {
    // ========== EXECUTION MODE ==========
    mode: 'paper', // 'paper', 'live-tiny', 'live'

    // ========== EXCHANGE CONFIGURATION ==========
    exchange: 'coinbase', // 'binance', 'kraken', 'bybit', 'coinbase', etc.
    apiKey: process.env.EXCHANGE_API_KEY || '',
    apiSecret: process.env.EXCHANGE_API_SECRET || '',
    marketType: 'spot', // 'spot' or 'futures'
    baseCurrency: 'USDT',

    // ========== TRADING PAIRS ==========
    // Choose liquid pairs with good volume
    pairs: [
        'BTC/USD',
        'ETH/USD',
        'SOL/USD',
        'AVAX/USD',
        
    ],

    // ========== RISK MANAGEMENT (ENHANCED) ==========
    risk: {
        // Base Risk Parameters
        maxRiskPerTrade: 0.02,          // 2% max risk per trade
        maxConcurrentPositions: 3,       // Max 3 positions at once
        maxPortfolioRisk: 0.06,          // 6% max total exposure
        maxDrawdown: 0.15,               // 15% max drawdown (pause trading)
        minRiskRewardRatio: 1.5,         // Minimum 1.5:1 R/R
        maxTradeHours: 24,               // Auto-close after 24 hours
        dailyLossLimit: 0.02,            // 2% max daily loss (halt for 24h)

        // Kelly Criterion (NEW)
        useKelly: true,                  // Enable mathematically optimal sizing
        kellyFraction: 0.25,             // Use 25% of full Kelly (conservative)

        // Volatility Adjustment (NEW)
        useVolatilityAdjustment: true,   // Adjust size based on ATR
        atrMultiplierNormal: 2.0,        // 2x ATR stops in normal volatility
        atrMultiplierHigh: 2.5,          // 2.5x ATR stops in high volatility
        highVolatilityPercentile: 80,    // >80th percentile = high vol

        // Multi-Target Exits (NEW)
        useMultiTargets: true,           // Split exits for better risk/reward
        target1Size: 0.33,               // Close 33% at 1R
        target2Size: 0.33,               // Close 33% at 2R
        target3Trail: true,              // Trail remaining 33%

        // Tiered Drawdown Protocol (NEW)
        drawdownTier1: 0.05,             // 5% DD: Reduce to 90% size
        drawdownTier2: 0.10,             // 10% DD: Reduce to 75% size
        drawdownTier3: 0.15,             // 15% DD: Reduce to 50% size
        drawdownTier4: 0.20              // 20% DD: HALT trading
    },

    // ========== REGIME DETECTION (NEW) ==========
    regimeDetection: {
        enabled: true,                   // CRITICAL: Enable regime switching
        adxPeriod: 14,                   // ADX calculation period
        trendingThreshold: 25,           // ADX > 25 = trending
        strongTrendThreshold: 40,        // ADX > 40 = strong trend
        exhaustionThreshold: 60,         // ADX > 60 = potential exhaustion
        rangingThreshold: 20             // ADX < 20 = ranging
    },

    // ========== CRYPTO-SPECIFIC DATA (NEW) ==========
    cryptoData: {
        enabled: true,                   // Enable crypto-native metrics
        fetchFundingRates: true,         // Monitor perpetual funding rates
        fundingThresholds: {
            extremePositive: 0.001,      // 0.1% per 8h (reduce longs)
            positive: 0.0005,            // 0.05% per 8h
            negative: -0.0005,           // -0.05% per 8h
            extremeNegative: -0.001      // -0.1% per 8h (increase longs)
        },
        fetchOpenInterest: true,         // Monitor OI for liquidation risk
        // MVRV requires external API (Glassnode/CryptoQuant)
        mvrvEnabled: false               // Set to true if you have API key
    },

    // ========== STRATEGY CONFIGURATIONS (UPGRADED) ==========
    strategies: {
        
        // UPGRADED MOMENTUM STRATEGY
        momentum: {
            enabled: true,
            timeframe: '5m',             // Primary timeframe
            // Higher timeframe is auto-calculated (4:1 ratio)
            minConfidence: 0.65,         // 65% min confidence for entry
            
            // Moving Averages
            fastMA: 9,
            slowMA: 21,
            ema50: 50,                   // Higher timeframe filter
            
            // Crypto-Optimized RSI (9 vs traditional 14)
            rsiPeriod: 9,
            rsiOverbought: 75,           // Raised from 70
            rsiOversold: 25,             // Lowered from 30
            rsiEntryLong: 30,            // RSI crosses above 30
            rsiEntryShort: 70,           // RSI crosses below 70
            
            // Crypto-Optimized MACD (5,35,5 vs traditional 12,26,9)
            macdFast: 5,
            macdSlow: 35,
            macdSignal: 5,
            
            // Volume & Trend
            volumeMultiplier: 1.5,       // 1.5x average volume required
            minTrendStrength: 0.02,      // 2% minimum trend
            
            // ADX Requirements (CRITICAL)
            minADX: 25,                  // Only trade when trending
            maxADX: 60                   // Avoid trend exhaustion
        },

        // UPGRADED MEAN REVERSION STRATEGY
        meanReversion: {
            enabled: true,
            timeframe: '15m',
            minConfidence: 0.70,         // Higher threshold for reversals
            
            // Bollinger Bands
            bbPeriod: 20,
            bbStdDev: 2,
            
            // Keltner Channels (for enhanced analysis)
            kcPeriod: 20,
            kcMultiplier: 1.5,
            
            // RSI
            rsiPeriod: 14,
            rsiOversold: 25,             // More extreme thresholds
            rsiOverbought: 75,
            
            // Volume
            volumeMultiplier: 1.3,
            
            // Statistical Entry (NEW)
            minZScore: 2.0,              // Require 2 std deviations
            extremeZScore: 2.5,          // Extreme entry threshold
            
            // Half-Life Requirements (NEW)
            minHalfLife: 5,              // Min 5 bars for reversion
            maxHalfLife: 200,            // Max 200 bars
            
            // ADX Filter (opposite of momentum)
            maxADX: 20                   // Only trade in ranging markets
        },

        // UPGRADED VOLATILITY BREAKOUT STRATEGY
        volatilityBreakout: {
            enabled: true,
            timeframe: '30m',
            minConfidence: 0.68,
            
            // TTM Squeeze Parameters (NEW)
            bbPeriod: 20,
            bbStdDev: 2,
            kcPeriod: 20,
            kcMultiplier: 1.5,
            
            // Squeeze Requirements
            minSqueezeBars: 5,           // Min bars in squeeze
            maxSqueezeBars: 50,          // Max before stale
            
            // ATR
            atrPeriod: 14,
            atrStopMultiplier: 2.0,      // Normal volatility
            atrStopHighVol: 2.5,         // High volatility
            
            // Volume
            volumeMultiplier: 2.0,       // 2x for breakouts
            
            // ADX Requirements
            minADX: 20                   // Min trend for breakout
        }
    },

    // ========== TELEGRAM NOTIFICATIONS ==========
    telegram: {
        token: process.env.TELEGRAM_BOT_TOKEN || '',
        chatId: process.env.TELEGRAM_CHAT_ID || '',
        
        // Notification Settings
        notifyOnEntry: true,
        notifyOnExit: true,
        notifyOnRegimeChange: true,
        notifyOnDrawdownTier: true,
        notifyOnFundingExtreme: true
    },

    // ========== EXECUTION INTERVALS ==========
    evaluationInterval: 5000,            // Check for signals every 5 seconds
    monitoringInterval: 2000,            // Monitor positions every 2 seconds
    regimeCheckInterval: 60000,          // Update regime every 60 seconds
    cryptoDataInterval: 300000,          // Fetch funding rates every 5 minutes

    // ========== PAPER TRADING SETTINGS ==========
    paperTradingBalance: 10000,          // $10k paper trading capital

    // ========== BACKTEST SETTINGS ==========
    backtest: {
        initialCapital: 10000,
        slippageModel: 'realistic',      // 'none', 'realistic', 'pessimistic'
        slippagePercent: 0.001,          // 0.1% slippage
        feePercent: 0.001,               // 0.1% fees (0.2% round-trip)
        
        // Walk-Forward Settings
        walkForwardTrain: 0.70,          // 70% train
        walkForwardTest: 0.30,           // 30% test
        
        // Monte Carlo
        monteCarloIterations: 1000
    },

    // ========== LOGGING & MONITORING ==========
    logging: {
        level: 'info',                   // 'debug', 'info', 'warn', 'error'
        saveToFile: true,
        logDirectory: './logs',
        
        // Performance Logging
        logTrades: true,
        logSignals: true,
        logRegimeChanges: true,
        logRiskEvents: true
    },

    // ========== ADVANCED FEATURES ==========
    advanced: {
        // Multi-timeframe confirmation (ALWAYS ENABLED in v2)
        multiTimeframeRatio: 4,          // 4:1 ratio (5m → 15m, 15m → 1h)
        
        // Correlation filtering (future feature)
        avoidHighCorrelation: false,
        maxCorrelation: 0.7,
        
        // Position correlation limits
        maxSameSidePositions: 2,         // Max 2 longs or 2 shorts
        
        // Emergency controls
        killSwitch: {
            enabled: true,
            triggerOnDrawdown: 0.25,     // 25% emergency stop
            triggerOnDailyLoss: 0.05     // 5% daily loss emergency stop
        }
    }
};
