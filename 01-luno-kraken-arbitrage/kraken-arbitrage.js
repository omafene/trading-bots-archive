// Kraken Auto-Trading Arbitrage Bot - COMPLETE VERSION
// Run: node kraken-arbitrage.js

const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');
const fs = require('fs');

const CONFIG = {
  // API Keys - ADD YOUR KEYS HERE
  apiKey: process.env.KRAKEN_API_KEY,
  apiSecret: process.env.KRAKEN_API_SECRET,
  autoTrade: true,  // ⚠️ SET TO true ONLY AFTER FUNDING ACCOUNT
  minProfitThreshold: 1.0,  // Only trade if profit > 1.5% (accounting for slippage)
  maxSpread: 1.0,  // Maximum spread % per pair
  
  // Risk Controls
  maxTradeUSD: 100,  // Maximum $ per trade
  maxDailyTrades: 999999,  // Max trades per day
  maxDailyLoss: 100,  // Stop trading if daily loss exceeds this
  minBalanceReserve: 25, // Keep this much in reserve (don't trade it all)
  
  // Monitoring
  scanInterval: 5000,  // Scan every 5 seconds when auto-trading
  logToFile: true,
  logFile: 'kraken-arbitrage-opportunities.log',
  tradeLogFile: 'kraken-trades.log',
  
  // Telegram
  telegramEnabled: true,
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN,
  telegramChatId: process.env.TELEGRAM_CHAT_ID,
};

const FEES = {
  market_taker: 0.004,
};

let PATHS = [];
let stats = {
  totalScans: 0,
  totalOpportunities: 0,
  filteredBySpread: 0,
  tradesExecuted: 0,
  tradesSuccessful: 0,
  tradesFailed: 0,
  dailyProfit: 0,
  dailyTrades: 0,
  totalProfit: 0,
  bestProfit: 0,
  bestPath: '',
  startTime: new Date(),
  lastResetDate: new Date().toDateString(),
};

function toEasternTime(date) {
  return new Date(date).toLocaleString('en-US', {
    timeZone: 'America/New_York',
    hour12: true,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function sendTelegramAlert(message) {
  if (!CONFIG.telegramEnabled) return;

  const url = 'https://api.telegram.org/bot' + CONFIG.telegramBotToken + '/sendMessage';
  const postData = JSON.stringify({
    chat_id: CONFIG.telegramChatId,
    text: message,
    parse_mode: 'HTML'
  });

  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': postData.length
    }
  };

  const req = https.request(url, options, (res) => {});
  req.on('error', () => {});
  req.write(postData);
  req.end();
}

function getKrakenSignature(path, request, secret) {
  const message = querystring.stringify(request);
  const secret_buffer = Buffer.from(secret, 'base64');
  const hash = crypto.createHash('sha256');
  const hmac = crypto.createHmac('sha512', secret_buffer);
  const hash_digest = hash.update(request.nonce + message).digest('binary');
  const hmac_digest = hmac.update(path + hash_digest, 'binary').digest('base64');
  return hmac_digest;
}

function krakenAPI(endpoint, params = {}) {
  return new Promise((resolve, reject) => {
    const path = '/0/private/' + endpoint;
    const nonce = Date.now() * 1000;
    
    params.nonce = nonce;
    const signature = getKrakenSignature(path, params, CONFIG.apiSecret);
    
    const postData = querystring.stringify(params);
    
    const options = {
      hostname: 'api.kraken.com',
      path: path,
      method: 'POST',
      headers: {
        'API-Key': CONFIG.apiKey,
        'API-Sign': signature,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': postData.length
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error && parsed.error.length > 0) {
            reject(new Error('Kraken API: ' + parsed.error.join(', ')));
          } else {
            resolve(parsed.result);
          }
        } catch (error) {
          reject(error);
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

function fetchKrakenPrices() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.kraken.com',
      path: '/0/public/Ticker',
      method: 'GET',
      headers: { 'User-Agent': 'Kraken-Monitor/1.0' }
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error && parsed.error.length > 0) {
            reject(new Error('Kraken API error'));
            return;
          }

          const prices = {};
          Object.entries(parsed.result).forEach(([pair, d]) => {
            let p = pair
              .replace('XXBTZ', 'XBT')
              .replace('XXBT', 'XBT')
              .replace(/^XX/, 'X')
              .replace(/^Z/, '')
              .replace(/^X(?!BT)/, '');
            
            if (d.a && d.a[0] && d.b && d.b[0]) {
              const ask = parseFloat(d.a[0]);
              const bid = parseFloat(d.b[0]);
              
              prices[p] = {
                ask: ask,
                bid: bid,
                last: parseFloat(d.c[0]),
                spread: ((ask - bid) / bid * 100),
                krakenPair: pair, // Store original Kraken pair name
              };
            }
          });
          resolve(prices);
        } catch (error) {
          reject(error);
        }
      });
    }).on('error', reject);
  });
}

async function getBalance() {
  try {
    const balanceData = await krakenAPI('Balance');
    
    // Check for Kraken API errors
    if (balanceData.error && balanceData.error.length > 0) {
      throw new Error('Kraken API error: ' + balanceData.error.join(', '));
    }

    const balances = {};
    
    // Kraken returns: { error: [], result: { "ZUSD": "1500.50", "XXBT": "0.05" } }
    if (balanceData.result) {
      Object.keys(balanceData.result).forEach(asset => {
        const balance = parseFloat(balanceData.result[asset]);
        
        // Skip zero balances
        if (balance === 0) return;
        
        // Remove Kraken's Z/X prefix
        // ZUSD → USD, XXBT → XBT, XETH → ETH
        let cleanAsset = asset;
        if (asset.startsWith('Z') || asset.startsWith('X')) {
          cleanAsset = asset.substring(1);
        }
        
        // Kraken calls Bitcoin "XBT" - normalize to "BTC"
        if (cleanAsset === 'XBT') cleanAsset = 'BTC';
        
        // Kraken returns available balance directly (no reserved field)
        balances[cleanAsset] = {
          available: balance,
          total: balance,
        };
      });
    }

    return balances;
  } catch (error) {
    console.error('Error getting balance:', error.message);
    return {};
  }
}

async function placeOrder(krakenPair, type, volume) {
  try {
    const orderParams = {
      pair: krakenPair,
      type: type,
      ordertype: 'market',
      volume: volume.toFixed(8),
    };
    
    console.log('   Placing order:', orderParams);
    const result = await krakenAPI('AddOrder', orderParams);
    console.log('   ✅ Order placed:', result.txid);
    return result;
  } catch (error) {
    console.error('   ❌ Order failed:', error.message);
    throw error;
  }
}

async function executeTrade(opportunity, prices) {
  const tradeLog = {
    timestamp: new Date().toISOString(),
    timestampET: toEasternTime(new Date()),
    path: opportunity.path,
    expectedProfit: opportunity.netProfit,
    actualProfit: 0,
    success: false,
    error: null,
    trades: [],
    startBalance: 0,
    endBalance: 0,
  };

  try {
    console.log('\n🚀 EXECUTING TRADE: ' + opportunity.path);
    console.log('Expected profit: ' + opportunity.netProfit + '%');
    
    const [pair1, pair2, pair3] = opportunity.pairs;
    const startCurrency = opportunity.startCurrency;
    
    // Get balance
    const balanceBefore = await getBalance();
    console.log('Balance before:', balanceBefore);
    
    // Determine starting amount
    let startAmount = CONFIG.maxTradeUSD;
    
    // Map currency codes to Kraken format
    const currencyMap = {
      'USD': 'ZUSD',
      'USDT': 'USDT', 
      'USDC': 'USDC',
      'XBT': 'XXBT',
      'ETH': 'XETH',
    };
    
    const krakenStartCurrency = currencyMap[startCurrency] || startCurrency;
    const availableBalance = parseFloat(balanceBefore[krakenStartCurrency] || 0);
    
    if (availableBalance < CONFIG.minBalanceReserve) {
      throw new Error('Insufficient balance: ' + availableBalance + ' ' + startCurrency);
    }
    
    // Use smaller of max trade or available (minus reserve)
    startAmount = Math.min(startAmount, availableBalance - CONFIG.minBalanceReserve);
    tradeLog.startBalance = startAmount;
    
    console.log('Trading with: ' + startAmount.toFixed(2) + ' ' + startCurrency);
    
    // Parse pairs to understand buy/sell direction
    const parsePair = (pair) => {
      if (pair.endsWith('USD')) return { base: pair.slice(0, -3), quote: 'USD' };
      if (pair.endsWith('USDT')) return { base: pair.slice(0, -4), quote: 'USDT' };
      if (pair.endsWith('USDC')) return { base: pair.slice(0, -4), quote: 'USDC' };
      if (pair.endsWith('XBT')) return { base: pair.slice(0, -3), quote: 'XBT' };
      if (pair.endsWith('ETH')) return { base: pair.slice(0, -3), quote: 'ETH' };
      return null;
    };
    
    let currentAmount = startAmount;
    let currentCurrency = startCurrency;
    
    // Trade 1
    console.log('\n--- TRADE 1: ' + pair1 + ' ---');
    const p1 = parsePair(pair1);
    const krakenPair1 = prices[pair1].krakenPair;
    
    let trade1Type, trade1Volume;
    if (currentCurrency === p1.quote) {
      // Buy base with quote
      trade1Type = 'buy';
      trade1Volume = currentAmount / prices[pair1].ask;
      currentAmount = trade1Volume;
      currentCurrency = p1.base;
    } else {
      // Sell base for quote
      trade1Type = 'sell';
      trade1Volume = currentAmount;
      currentAmount = currentAmount * prices[pair1].bid;
      currentCurrency = p1.quote;
    }
    
    const order1 = await placeOrder(krakenPair1, trade1Type, trade1Volume);
    tradeLog.trades.push({ pair: pair1, type: trade1Type, volume: trade1Volume, orderId: order1.txid });
    
    // Wait a moment for order to fill
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Trade 2
    console.log('\n--- TRADE 2: ' + pair2 + ' ---');
    const p2 = parsePair(pair2);
    const krakenPair2 = prices[pair2].krakenPair;
    
    let trade2Type, trade2Volume;
    if (currentCurrency === p2.quote) {
      trade2Type = 'buy';
      trade2Volume = currentAmount / prices[pair2].ask;
      currentAmount = trade2Volume;
      currentCurrency = p2.base;
    } else {
      trade2Type = 'sell';
      trade2Volume = currentAmount;
      currentAmount = currentAmount * prices[pair2].bid;
      currentCurrency = p2.quote;
    }
    
    const order2 = await placeOrder(krakenPair2, trade2Type, trade2Volume);
    tradeLog.trades.push({ pair: pair2, type: trade2Type, volume: trade2Volume, orderId: order2.txid });
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Trade 3
    console.log('\n--- TRADE 3: ' + pair3 + ' ---');
    const p3 = parsePair(pair3);
    const krakenPair3 = prices[pair3].krakenPair;
    
    let trade3Type, trade3Volume;
    if (currentCurrency === p3.quote) {
      trade3Type = 'buy';
      trade3Volume = currentAmount / prices[pair3].ask;
      currentAmount = trade3Volume;
      currentCurrency = p3.base;
    } else {
      trade3Type = 'sell';
      trade3Volume = currentAmount;
      currentAmount = currentAmount * prices[pair3].bid;
      currentCurrency = p3.quote;
    }
    
    const order3 = await placeOrder(krakenPair3, trade3Type, trade3Volume);
    tradeLog.trades.push({ pair: pair3, type: trade3Type, volume: trade3Volume, orderId: order3.txid });
    
    // Wait and get final balance
    await new Promise(resolve => setTimeout(resolve, 2000));
    const balanceAfter = await getBalance();
    
    const endAmount = parseFloat(balanceAfter[krakenStartCurrency] || 0);
    const profit = endAmount - availableBalance;
    const profitPercent = (profit / startAmount) * 100;
    
    tradeLog.endBalance = endAmount;
    tradeLog.actualProfit = profitPercent.toFixed(4);
    tradeLog.success = true;
    
    stats.tradesSuccessful++;
    stats.dailyProfit += profit;
    stats.totalProfit += profit;
    
    console.log('\n✅ TRADE COMPLETED!');
    console.log('Started with: ' + startAmount.toFixed(2) + ' ' + startCurrency);
    console.log('Ended with: ' + endAmount.toFixed(2) + ' ' + startCurrency);
    console.log('Profit: ' + profit.toFixed(2) + ' ' + startCurrency + ' (' + profitPercent.toFixed(2) + '%)');
    
    const message = '✅ TRADE SUCCESSFUL!\n\n' +
                   'Path: ' + opportunity.path + '\n' +
                   'Expected: ' + opportunity.netProfit + '%\n' +
                   'Actual: ' + profitPercent.toFixed(2) + '%\n' +
                   'Profit: $' + profit.toFixed(2) + '\n' +
                   'Time: ' + tradeLog.timestampET + ' ET';
    
    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');
    
  } catch (error) {
    console.error('\n❌ TRADE FAILED:', error.message);
    tradeLog.error = error.message;
    tradeLog.success = false;
    stats.tradesFailed++;
    
    const message = '❌ TRADE FAILED\n\n' +
                   'Path: ' + opportunity.path + '\n' +
                   'Error: ' + error.message + '\n' +
                   'Time: ' + tradeLog.timestampET + ' ET';
    
    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');
  } finally {
    stats.dailyTrades++;
    stats.tradesExecuted++;
  }
}

function generateArbitragePaths(prices) {
  const paths = [];
  const pairList = Object.keys(prices);

  const parsePair = (pair) => {
    if (pair.endsWith('USD')) return { base: pair.slice(0, -3), quote: 'USD' };
    if (pair.endsWith('USDT')) return { base: pair.slice(0, -4), quote: 'USDT' };
    if (pair.endsWith('USDC')) return { base: pair.slice(0, -4), quote: 'USDC' };
    if (pair.endsWith('XBT')) return { base: pair.slice(0, -3), quote: 'XBT' };
    if (pair.endsWith('ETH')) return { base: pair.slice(0, -3), quote: 'ETH' };
    return null;
  };

  const pairMap = {};
  pairList.forEach(p => {
    const parsed = parsePair(p);
    if (parsed) {
      pairMap[parsed.base + '-' + parsed.quote] = p;
      pairMap[parsed.quote + '-' + parsed.base] = p;
    }
  });

  const baseCurrencies = ['USD', 'USDT', 'USDC'];  // Focus on stablecoins

  baseCurrencies.forEach(startCurrency => {
    const startPairs = pairList.filter(p => {
      const parsed = parsePair(p);
      return parsed && (parsed.base === startCurrency || parsed.quote === startCurrency);
    });

    startPairs.forEach(pair1 => {
      const p1 = parsePair(pair1);
      if (!p1) return;

      const cryptoA = p1.base === startCurrency ? p1.quote : p1.base;
      if (cryptoA === startCurrency) return;

      pairList.forEach(pair2 => {
        const p2 = parsePair(pair2);
        if (!p2) return;
        if (p2.base !== cryptoA && p2.quote !== cryptoA) return;

        const cryptoB = p2.base === cryptoA ? p2.quote : p2.base;
        if (cryptoB === cryptoA || cryptoB === startCurrency) return;

        const pair3 = pairMap[cryptoB + '-' + startCurrency] || pairMap[startCurrency + '-' + cryptoB];

        if (pair3 && pair3 !== pair1 && pair3 !== pair2) {
          paths.push({
            name: [startCurrency, cryptoA, cryptoB, startCurrency].join('->'),
            pairs: [pair1, pair2, pair3],
            startCurrency,
          });
        }
      });
    });
  });

  const uniquePaths = [];
  const seen = new Set();
  paths.forEach(path => {
    if (!seen.has(path.name)) {
      seen.add(path.name);
      uniquePaths.push(path);
    }
  });

  return uniquePaths;
}

function calculateArbitrage(prices) {
  const opportunities = [];

  PATHS.forEach(path => {
    try {
      const [pair1, pair2, pair3] = path.pairs;
      if (!prices[pair1] || !prices[pair2] || !prices[pair3]) return;

      const spread1 = prices[pair1].spread;
      const spread2 = prices[pair2].spread;
      const spread3 = prices[pair3].spread;
      const avgSpread = (spread1 + spread2 + spread3) / 3;
      const maxPairSpread = Math.max(spread1, spread2, spread3);
      
      if (maxPairSpread > CONFIG.maxSpread) {
        stats.filteredBySpread++;
        return;
      }

      const fee = FEES.market_taker;

      const parsePair = (pair) => {
        if (pair.endsWith('USD')) return { base: pair.slice(0, -3), quote: 'USD' };
        if (pair.endsWith('USDT')) return { base: pair.slice(0, -4), quote: 'USDT' };
        if (pair.endsWith('USDC')) return { base: pair.slice(0, -4), quote: 'USDC' };
        if (pair.endsWith('XBT')) return { base: pair.slice(0, -3), quote: 'XBT' };
        if (pair.endsWith('ETH')) return { base: pair.slice(0, -3), quote: 'ETH' };
        return null;
      };

      let startAmount = 1000;

      let amount = startAmount;
      let holding = path.startCurrency;

      const p1 = parsePair(pair1);
      if (!p1) return;
      if (!prices[pair1].ask || !prices[pair1].bid || prices[pair1].ask <= 0 || prices[pair1].bid <= 0) return;

      if (holding === p1.quote) {
        amount = (amount / prices[pair1].ask) * (1 - fee);
        holding = p1.base;
      } else if (holding === p1.base) {
        amount = (amount * prices[pair1].bid) * (1 - fee);
        holding = p1.quote;
      } else {
        return;
      }

      const p2 = parsePair(pair2);
      if (!p2) return;
      if (!prices[pair2].ask || !prices[pair2].bid || prices[pair2].ask <= 0 || prices[pair2].bid <= 0) return;

      if (holding === p2.quote) {
        amount = (amount / prices[pair2].ask) * (1 - fee);
        holding = p2.base;
      } else if (holding === p2.base) {
        amount = (amount * prices[pair2].bid) * (1 - fee);
        holding = p2.quote;
      } else {
        return;
      }

      const p3 = parsePair(pair3);
      if (!p3) return;
      if (!prices[pair3].ask || !prices[pair3].bid || prices[pair3].ask <= 0 || prices[pair3].bid <= 0) return;

      if (holding === p3.quote) {
        amount = (amount / prices[pair3].ask) * (1 - fee);
        holding = p3.base;
      } else if (holding === p3.base) {
        amount = (amount * prices[pair3].bid) * (1 - fee);
        holding = p3.quote;
      } else {
        return;
      }

      if (holding !== path.startCurrency) return;

      const finalAmount = amount;
      if (!isFinite(finalAmount) || finalAmount <= 0 || isNaN(finalAmount)) return;

      const grossProfit = ((finalAmount / Math.pow(1 - fee, 3) - startAmount) / startAmount) * 100;
      const netProfit = ((finalAmount - startAmount) / startAmount) * 100;

      if (!isFinite(grossProfit) || !isFinite(netProfit) || isNaN(grossProfit) || isNaN(netProfit)) return;

      if (netProfit > CONFIG.minProfitThreshold) {
        opportunities.push({
          path: path.name,
          grossProfit: grossProfit.toFixed(4),
          netProfit: netProfit.toFixed(4),
          avgSpread: avgSpread.toFixed(3),
          spread1: spread1.toFixed(3),
          spread2: spread2.toFixed(3),
          spread3: spread3.toFixed(3),
          startCurrency: path.startCurrency,
          pairs: path.pairs,
          timestamp: new Date().toISOString(),
        });
      }
    } catch (error) {
      return;
    }
  });

  return opportunities;
}

function logOpportunity(opp, prices) {
  const netProfitNum = parseFloat(opp.netProfit);
  const alert = netProfitNum >= 2.0 ? 'HIGH PROFIT!' : 'Opportunity';

  let message = '\n' + alert + ' [KRAKEN] ' + opp.path + '\n';
  message += '  Gross: ' + opp.grossProfit + '% (before fees)\n';
  message += '  Net: ' + opp.netProfit + '% (after fees)\n';
  message += '  Avg Spread: ' + opp.avgSpread + '%\n';
  message += '  Time: ' + toEasternTime(opp.timestamp) + ' ET\n';
  
  if (CONFIG.autoTrade && canTrade()) {
    message += '  🤖 EXECUTING AUTO-TRADE...\n';
  }
  
  message += '======================================================================\n';

  console.log(message);
  if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);

  if (netProfitNum > stats.bestProfit) {
    stats.bestProfit = netProfitNum;
    stats.bestPath = opp.path;
  }

  if (CONFIG.autoTrade && canTrade()) {
    executeTrade(opp, prices);
  }
}

function canTrade() {
  const today = new Date().toDateString();
  if (stats.lastResetDate !== today) {
    stats.dailyTrades = 0;
    stats.dailyProfit = 0;
    stats.lastResetDate = today;
  }

  if (stats.dailyTrades >= CONFIG.maxDailyTrades) {
    console.log('⚠️ Daily trade limit reached');
    return false;
  }

  if (stats.dailyProfit <= -CONFIG.maxDailyLoss) {
    console.log('⚠️ Daily loss limit reached');
    sendTelegramAlert('🛑 TRADING STOPPED - Daily loss limit reached: $' + stats.dailyProfit.toFixed(2));
    return false;
  }

  return true;
}

function printStats() {
  const uptime = Math.floor((new Date() - stats.startTime) / 1000);
  const hours = Math.floor(uptime / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);

  console.log('\n======================================================================');
  console.log('STATISTICS');
  console.log('======================================================================');
  console.log('Uptime: ' + hours + 'h ' + minutes + 'm');
  console.log('Scans: ' + stats.totalScans);
  console.log('Paths: ' + PATHS.length);
  console.log('Opportunities: ' + stats.totalOpportunities);
  console.log('Filtered (Wide Spread): ' + stats.filteredBySpread);
  console.log('Trades Executed: ' + stats.tradesExecuted);
  console.log('  Successful: ' + stats.tradesSuccessful);
  console.log('  Failed: ' + stats.tradesFailed);
  console.log('Daily Trades: ' + stats.dailyTrades + '/' + CONFIG.maxDailyTrades);
  console.log('Daily P&L: $' + stats.dailyProfit.toFixed(2));
  console.log('Total P&L: $' + stats.totalProfit.toFixed(2));
  console.log('Best: ' + stats.bestProfit.toFixed(4) + '% ' + (stats.bestPath || ''));
  console.log('======================================================================\n');
}

async function scan() {
  try {
    stats.totalScans++;
    console.log('\n[' + toEasternTime(new Date()) + ' ET] Scan #' + stats.totalScans);

    const prices = await fetchKrakenPrices();

    if (PATHS.length === 0) {
      PATHS = generateArbitragePaths(prices);
      console.log('\nFound ' + PATHS.length + ' triangular arbitrage paths (USD/USDT/USDC)!\n');
    }

    const opportunities = calculateArbitrage(prices);

    if (opportunities.length > 0) {
      stats.totalOpportunities += opportunities.length;
      console.log('\nFound ' + opportunities.length + ' opportunity(ies)!\n');
      
      // Sort by profit and take best one
      opportunities.sort((a, b) => parseFloat(b.netProfit) - parseFloat(a.netProfit));
      
      opportunities.slice(0, 3).forEach(opp => logOpportunity(opp, prices));
    } else {
      console.log('No opportunities (Min: ' + CONFIG.minProfitThreshold + '%, Max spread: ' + CONFIG.maxSpread + '%)');
    }

    if (stats.totalScans % 20 === 0) printStats();

  } catch (error) {
    console.error('Error: ' + error.message);
  }
}

console.log('\n======================================================================');
console.log('KRAKEN AUTO-TRADING ARBITRAGE BOT');
console.log('======================================================================');
console.log('Auto-Trade: ' + (CONFIG.autoTrade ? '🤖 ENABLED' : '📊 DISABLED'));
console.log('Strategy: Triangular arbitrage (USD, USDT, USDC)');
console.log('Interval: ' + (CONFIG.scanInterval / 1000) + 's');
console.log('Min profit: ' + CONFIG.minProfitThreshold + '%');
console.log('Max spread: ' + CONFIG.maxSpread + '%');
console.log('Max trade: $' + CONFIG.maxTradeUSD);
console.log('Daily limits: ' + CONFIG.maxDailyTrades + ' trades, $' + CONFIG.maxDailyLoss + ' loss');
console.log('======================================================================\n');

if (!CONFIG.autoTrade) {
  console.log('📊 MONITORING MODE - No trades will be executed');
  console.log('Set autoTrade: true to enable trading\n');
  scan();
  setInterval(scan, CONFIG.scanInterval);
} else {
  console.log('⚠️  WARNING: AUTO-TRADING IS ENABLED!');
  console.log('⚠️  The bot will execute REAL trades with REAL money!');
  console.log('⚠️  Make sure your account is funded!');
  console.log('⚠️  Press Ctrl+C within 10 seconds to cancel...\n');
  
  setTimeout(() => {
    console.log('🤖 Auto-trading started!\n');
    sendTelegramAlert('🤖 Kraken Auto-Trading Started\n\nMax trade: $' + CONFIG.maxTradeUSD + '\nMin profit: ' + CONFIG.minProfitThreshold + '%');
    scan();
    setInterval(scan, CONFIG.scanInterval);
  }, 10000);
}

process.on('SIGINT', () => {
  const finalMsg = '🛑 Kraken Bot Stopped\n\n' +
                  'Total trades: ' + stats.tradesExecuted + '\n' +
                  'Successful: ' + stats.tradesSuccessful + '\n' +
                  'Failed: ' + stats.tradesFailed + '\n' +
                  'Total P&L: $' + stats.totalProfit.toFixed(2);
  sendTelegramAlert(finalMsg);
  printStats();
  console.log('Goodbye!\n');
  process.exit(0);
});
