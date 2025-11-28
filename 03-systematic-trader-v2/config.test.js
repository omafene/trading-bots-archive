/**
 * AGGRESSIVE TEST CONFIG - FOR NOTIFICATION TESTING ONLY
 * DO NOT USE FOR REAL TRADING!
 */

const baseConfig = require('./config.js');

module.exports = {
    ...baseConfig,
    
    // Faster scanning
    scanInterval: 10000,  // 10 seconds
    evaluationInterval: 3000,  // 3 seconds
    monitoringInterval: 1000,  // 1 second (faster exit checks)
    
    // VERY AGGRESSIVE RISK (for quick exits)
    risk: {
        ...baseConfig.risk,
        atrMultiplierNormal: 0.8,  // Tight stops = quick exits
        atrMultiplierHigh: 1.0,
        maxTradeHours: 1,  // Auto-close after 1 hour max
    },
    
    // VERY LOW CONFIDENCE (more entries)
    strategies: {
        momentum: {
            ...baseConfig.strategies.momentum,
            minConfidence: 0.40,  // 40% instead of 80%
            minADX: 15,  // Lower threshold
            maxADX: 70,  // Higher threshold
        },
        meanReversion: {
            ...baseConfig.strategies.meanReversion,
            minConfidence: 0.40,  // 40% instead of 70%
            maxADX: 30,
            zScoreEntry: 1.5,  // Enter easier
        },
        volatilityBreakout: {
            ...baseConfig.strategies.volatilityBreakout,
            minConfidence: 0.40,  // 40% instead of 72%
            minADX: 15,
            atrStopMultiplier: 0.8,  // Tighter stops
        }
    }
};
