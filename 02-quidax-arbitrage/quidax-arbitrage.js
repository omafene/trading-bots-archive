// Quidax Auto-Trading Arbitrage Bot - NIGERIA ONLY (NGN/USDT)
// Run: node quidax-arbitrage.js

const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');
const fs = require('fs');

const CONFIG = {
  // Quidax API Keys - GET FROM: https://www.quidax.com/settings/api
  apiKey: process.env.QUIDAX_API_KEY,
  apiSecret: process.env.QUIDAX_API_SECRET,

  // Trading Settings
  autoTrade: false,  // ⚠️ Set to true to enable LIVE trading!
  minProfitThreshold: 1.5,  // Lower than Luno because fees are only 0.1%!
  maxSpread: 3.0,  // Quidax typically has tighter spreads

  // Paper Trading Settings
  paperTradeThreshold: 1.5,
  simulateTradeSize: true,

  // Liquidity Requirements
  enableLiquidityCheck: true,
  minAskDepth: 0.1,
  minBidDepth: 0.1,
  maxSpreadForTrade: 4.0,

  // Risk Controls
  maxTradeNGN: 100000,  // ~$60 USD
  maxTradeUSDT: 100,
  maxDailyTrades: 20,
  maxDailyLossNGN: 10000,
  maxDailyLossUSDT: 25,
  minBalanceReserveNGN: 20000,
  minBalanceReserveUSDT: 50,

  // Monitoring
  scanInterval: 10000,  // 10 seconds
  logToFile: true,
  logFile: 'quidax-arbitrage-opportunities.log',
  tradeLogFile: 'quidax-trades.log',
  paperTradeLogFile: 'quidax-paper-trades.log',

  // Telegram
  telegramEnabled: true,
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN,
  telegramChatId: process.env.TELEGRAM_CHAT_ID,
};

// Quidax has UNIFORM 0.1% fees for ALL pairs! Much better than Luno!
const FEES = {
  taker: 0.001,  // 0.1% for all pairs
  maker: 0.001,  // 0.1% for all pairs
};

let PATHS = [];
let stats = {
  totalScans: 0,
  totalOpportunities: 0,
  paperTrades: 0,
  paperProfitNGN: 0,
  paperProfitUSDT: 0,
  liquidityChecksPassed: 0,
  liquidityChecksFailed: 0,
  filteredBySpread: 0,
  tradesExecuted: 0,
  tradesSuccessful: 0,
  tradesFailed: 0,
  dailyProfitNGN: 0,
  dailyProfitUSDT: 0,
  dailyTradesNGN: 0,
  dailyTradesUSDT: 0,
  totalProfitNGN: 0,
  totalProfitUSDT: 0,
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

  const req = https.request(url, options, () => {});
  req.on('error', () => {});
  req.write(postData);
  req.end();
}

// Quidax uses HMAC-SHA256 signature authentication
function generateSignature(verb, uri, query) {
  // Canonical string: VERB|URI|QUERY (sorted alphabetically)
  const canonical = verb + '|' + uri + '|' + query;
  const signature = crypto.createHmac('sha256', CONFIG.apiSecret)
                          .update(canonical)
                          .digest('hex');
  return signature;
}

function quidaxAPI(endpoint, method = 'GET', params = {}) {
  return new Promise((resolve, reject) => {
    const tonce = Date.now();
    
    // Add authentication params
    params.access_key = CONFIG.apiKey;
    params.tonce = tonce;

    // Sort params alphabetically (CRITICAL for signature)
    const sortedKeys = Object.keys(params).sort();
    const sortedParams = {};
    sortedKeys.forEach(key => {
      sortedParams[key] = params[key];
    });

    const query = querystring.stringify(sortedParams);
    const uri = '/api/v2/' + endpoint;
    
    // Generate signature
    const signature = generateSignature(method, uri, query);
    
    let path = uri;
    let postData = '';

    if (method === 'GET') {
      path = uri + '?' + query + '&signature=' + signature;
    } else if (method === 'POST') {
      postData = query + '&signature=' + signature;
    }

    const options = {
      hostname: 'www.quidax.com',
      path: path,
      method: method,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      }
    };

    if (method === 'POST') {
      options.headers['Content-Length'] = postData.length;
    }

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error('Quidax API: ' + JSON.stringify(parsed.error)));
          } else {
            resolve(parsed);
          }
        } catch (error) {
          reject(error);
        }
      });
    });

    req.on('error', reject);
    if (method === 'POST') {
      req.write(postData);
    }
    req.end();
  });
}

function parseQuidaxPair(pair) {
  // Quidax format: btcngn, ethusdt, ltcbtc
  pair = pair.toLowerCase();
  
  if (pair.endsWith('ngn')) {
    return { base: pair.slice(0, -3).toUpperCase(), quote: 'NGN' };
  }
  if (pair.endsWith('usdt')) {
    return { base: pair.slice(0, -4).toUpperCase(), quote: 'USDT' };
  }
  if (pair.endsWith('usdc')) {
    return { base: pair.slice(0, -4).toUpperCase(), quote: 'USDC' };
  }
  if (pair.endsWith('btc')) {
    return { base: pair.slice(0, -3).toUpperCase(), quote: 'BTC' };
  }
  
  return null;
}

function buildQuidaxPair(base, quote) {
  // Build pair in Quidax format: lowercase
  return (base + quote).toLowerCase();
}

function checkPairLiquidity(market) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'www.quidax.com',
      path: '/api/v2/depth?market=' + market + '&limit=10',
      method: 'GET',
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const book = JSON.parse(data);

          if (book.asks && book.bids && book.asks.length > 0 && book.bids.length > 0) {
            const top5Asks = book.asks.slice(0, 5);
            const top5Bids = book.bids.slice(0, 5);

            const askDepth = top5Asks.reduce((sum, a) => sum + parseFloat(a.volume || a[1]), 0);
            const bidDepth = top5Bids.reduce((sum, b) => sum + parseFloat(b.volume || b[1]), 0);

            const bestAsk = parseFloat(top5Asks[0].price || top5Asks[0][0]);
            const bestBid = parseFloat(top5Bids[0].price || top5Bids[0][0]);
            const spread = ((bestAsk - bestBid) / bestBid * 100);

            const isLiquid = (
              (askDepth >= CONFIG.minAskDepth || bidDepth >= CONFIG.minBidDepth) &&
              spread <= CONFIG.maxSpreadForTrade
            );

            resolve({
              market: market,
              liquid: isLiquid,
              askDepth: askDepth,
              bidDepth: bidDepth,
              spread: spread,
            });
          } else {
            resolve({
              market: market,
              liquid: false,
              askDepth: 0,
              bidDepth: 0,
              spread: 999,
            });
          }
        } catch (error) {
          resolve({
            market: market,
            liquid: false,
            askDepth: 0,
            bidDepth: 0,
            spread: 999,
            error: error.message,
          });
        }
      });
    }).on('error', (error) => {
      resolve({
        market: market,
        liquid: false,
        askDepth: 0,
        bidDepth: 0,
        spread: 999,
        error: error.message,
      });
    });
  });
}

async function checkPathLiquidity(markets) {
  const [market1, market2, market3] = markets;

  console.log('  🔍 Checking liquidity...');

  const liq1 = await checkPairLiquidity(market1);
  const liq2 = await checkPairLiquidity(market2);
  const liq3 = await checkPairLiquidity(market3);

  const allLiquid = liq1.liquid && liq2.liquid && liq3.liquid;

  console.log('    ' + market1 + ': ' + (liq1.liquid ? '✅' : '❌') + ' (Ask=' + liq1.askDepth.toFixed(2) + ', Bid=' + liq1.bidDepth.toFixed(2) + ', Spread=' + liq1.spread.toFixed(2) + '%)');
  console.log('    ' + market2 + ': ' + (liq2.liquid ? '✅' : '❌') + ' (Ask=' + liq2.askDepth.toFixed(2) + ', Bid=' + liq2.bidDepth.toFixed(2) + ', Spread=' + liq2.spread.toFixed(2) + '%)');
  console.log('    ' + market3 + ': ' + (liq3.liquid ? '✅' : '❌') + ' (Ask=' + liq3.askDepth.toFixed(2) + ', Bid=' + liq3.bidDepth.toFixed(2) + ', Spread=' + liq3.spread.toFixed(2) + '%)');

  if (allLiquid) {
    console.log('  ✅ All markets have sufficient liquidity');
    stats.liquidityChecksPassed++;
  } else {
    console.log('  ⚠️  FAILED liquidity check - Trade skipped');
    stats.liquidityChecksFailed++;
  }

  return {
    passed: allLiquid,
    details: [liq1, liq2, liq3],
  };
}

function fetchQuidaxPrices() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'www.quidax.com',
      path: '/api/v2/tickers',
      method: 'GET',
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const prices = {};

          // Filter for Nigerian markets only (NGN and USDT pairs)
          Object.keys(parsed).forEach(market => {
            const ticker = parsed[market];
            const marketLower = market.toLowerCase();
            
            // Only include NGN, USDT, USDC, and BTC pairs
            if (!marketLower.endsWith('ngn') && 
                !marketLower.endsWith('usdt') && 
                !marketLower.endsWith('usdc') &&
                !marketLower.endsWith('btc')) {
              return;
            }

            const buy = parseFloat(ticker.ticker?.buy || ticker.buy || 0);
            const sell = parseFloat(ticker.ticker?.sell || ticker.sell || 0);
            const last = parseFloat(ticker.ticker?.last || ticker.last || 0);
            const vol = parseFloat(ticker.ticker?.vol || ticker.vol || 0);

            if (buy > 0 && sell > 0) {
              prices[marketLower] = {
                ask: sell,  // Quidax uses 'sell' for ask price
                bid: buy,   // Quidax uses 'buy' for bid price
                last: last,
                spread: ((sell - buy) / buy * 100),
                volume: vol,
              };
            }
          });

          console.log('✅ Loaded ' + Object.keys(prices).length + ' Nigeria markets (NGN/USDT/USDC/BTC)');
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
    const data = await quidaxAPI('members/me');
    const balances = {};

    if (data.accounts) {
      data.accounts.forEach(account => {
        const currency = account.currency.toUpperCase();
        const total = parseFloat(account.balance || 0);
        const locked = parseFloat(account.locked || 0);
        const available = total - locked;

        balances[currency] = {
          available: available,
          reserved: locked,
          total: total,
        };
      });
    }

    return balances;
  } catch (error) {
    console.error('Error getting balance:', error.message);
    return {};
  }
}

async function placeOrder(market, side, volume, price = null) {
  try {
    const params = {
      market: market,
      side: side.toLowerCase(),  // 'buy' or 'sell'
      volume: volume.toFixed(8),
      ord_type: 'market',  // Market order for immediate execution
    };

    if (price) {
      params.price = price.toFixed(2);
      params.ord_type = 'limit';
    }

    console.log('   Placing order:', params);
    const result = await quidaxAPI('orders', 'POST', params);
    console.log('   ✅ Order placed:', result.id);
    return result;
  } catch (error) {
    console.error('   ❌ Order failed:', error.message);
    throw error;
  }
}

function simulatePaperTrade(opportunity) {
  const startCurrency = opportunity.startCurrency;
  const tradeSize = startCurrency === 'NGN' ? CONFIG.maxTradeNGN : CONFIG.maxTradeUSDT;

  const netProfitPercent = parseFloat(opportunity.netProfit);
  const grossProfitPercent = parseFloat(opportunity.grossProfit);

  const slippagePercent = 0.5;  // Lower slippage on Quidax (better liquidity)
  const estimatedNetProfit = netProfitPercent - slippagePercent;
  const estimatedProfitAmount = (tradeSize * estimatedNetProfit) / 100;

  const paperLog = {
    timestamp: new Date().toISOString(),
    timestampET: toEasternTime(new Date()),
    path: opportunity.path,
    startCurrency: startCurrency,
    tradeSize: tradeSize,
    grossProfit: grossProfitPercent,
    netProfit: netProfitPercent,
    estimatedSlippage: slippagePercent,
    estimatedNetProfit: estimatedNetProfit,
    estimatedProfitAmount: estimatedProfitAmount,
    avgSpread: opportunity.avgSpread,
    spreads: [opportunity.spread1, opportunity.spread2, opportunity.spread3],
    markets: opportunity.markets,
  };

  fs.appendFileSync(CONFIG.paperTradeLogFile, JSON.stringify(paperLog, null, 2) + '\n');

  stats.paperTrades++;
  if (startCurrency === 'NGN') {
    stats.paperProfitNGN += estimatedProfitAmount;
  } else {
    stats.paperProfitUSDT += estimatedProfitAmount;
  }

  return paperLog;
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

    const [market1, market2, market3] = opportunity.markets;
    const startCurrency = opportunity.startCurrency;

    const balanceBefore = await getBalance();
    console.log('Balance before:', balanceBefore);

    const availableBalance = balanceBefore[startCurrency]?.available || 0;

    let maxTrade = startCurrency === 'NGN' ? CONFIG.maxTradeNGN : CONFIG.maxTradeUSDT;
    let minReserve = startCurrency === 'NGN' ? CONFIG.minBalanceReserveNGN : CONFIG.minBalanceReserveUSDT;

    if (availableBalance < minReserve) {
      throw new Error('Insufficient balance: ' + availableBalance + ' ' + startCurrency);
    }

    let startAmount = Math.min(maxTrade, availableBalance - minReserve);
    tradeLog.startBalance = startAmount;

    console.log('Trading with: ' + startAmount.toFixed(2) + ' ' + startCurrency);

    let currentAmount = startAmount;
    let currentCurrency = startCurrency;

    // Trade 1
    console.log('\n--- TRADE 1: ' + market1 + ' ---');
    const p1 = parseQuidaxPair(market1);
    if (!p1) throw new Error('Invalid market: ' + market1);

    let trade1Side, trade1Volume;
    if (currentCurrency === p1.quote) {
      trade1Side = 'buy';  // Buy base with quote
      trade1Volume = currentAmount / prices[market1].ask;
      currentAmount = trade1Volume * (1 - FEES.taker);
      currentCurrency = p1.base;
    } else {
      trade1Side = 'sell';  // Sell base for quote
      trade1Volume = currentAmount;
      currentAmount = (currentAmount * prices[market1].bid) * (1 - FEES.taker);
      currentCurrency = p1.quote;
    }

    const order1 = await placeOrder(market1, trade1Side, trade1Volume);
    tradeLog.trades.push({ market: market1, side: trade1Side, volume: trade1Volume, fee: FEES.taker, orderId: order1.id });

    await new Promise(resolve => setTimeout(resolve, 2000));

    // Trade 2
    console.log('\n--- TRADE 2: ' + market2 + ' ---');
    const p2 = parseQuidaxPair(market2);
    if (!p2) throw new Error('Invalid market: ' + market2);

    let trade2Side, trade2Volume;
    if (currentCurrency === p2.quote) {
      trade2Side = 'buy';
      trade2Volume = currentAmount / prices[market2].ask;
      currentAmount = trade2Volume * (1 - FEES.taker);
      currentCurrency = p2.base;
    } else {
      trade2Side = 'sell';
      trade2Volume = currentAmount;
      currentAmount = (currentAmount * prices[market2].bid) * (1 - FEES.taker);
      currentCurrency = p2.quote;
    }

    const order2 = await placeOrder(market2, trade2Side, trade2Volume);
    tradeLog.trades.push({ market: market2, side: trade2Side, volume: trade2Volume, fee: FEES.taker, orderId: order2.id });

    await new Promise(resolve => setTimeout(resolve, 2000));

    // Trade 3
    console.log('\n--- TRADE 3: ' + market3 + ' ---');
    const p3 = parseQuidaxPair(market3);
    if (!p3) throw new Error('Invalid market: ' + market3);

    let trade3Side, trade3Volume;
    if (currentCurrency === p3.quote) {
      trade3Side = 'buy';
      trade3Volume = currentAmount / prices[market3].ask;
      currentAmount = trade3Volume * (1 - FEES.taker);
      currentCurrency = p3.base;
    } else {
      trade3Side = 'sell';
      trade3Volume = currentAmount;
      currentAmount = (currentAmount * prices[market3].bid) * (1 - FEES.taker);
      currentCurrency = p3.quote;
    }

    const order3 = await placeOrder(market3, trade3Side, trade3Volume);
    tradeLog.trades.push({ market: market3, side: trade3Side, volume: trade3Volume, fee: FEES.taker, orderId: order3.id });

    await new Promise(resolve => setTimeout(resolve, 3000));

    const balanceAfter = await getBalance();
    const endAmount = balanceAfter[startCurrency]?.available || 0;
    const profit = endAmount - availableBalance;
    const profitPercent = (profit / startAmount) * 100;

    tradeLog.endBalance = endAmount;
    tradeLog.actualProfit = profitPercent.toFixed(4);
    tradeLog.success = true;

    stats.tradesSuccessful++;

    if (startCurrency === 'NGN') {
      stats.dailyProfitNGN += profit;
      stats.totalProfitNGN += profit;
      stats.dailyTradesNGN++;
    } else {
      stats.dailyProfitUSDT += profit;
      stats.totalProfitUSDT += profit;
      stats.dailyTradesUSDT++;
    }

    console.log('\n✅ TRADE COMPLETED!');
    console.log('Started with: ' + startAmount.toFixed(2) + ' ' + startCurrency);
    console.log('Ended with: ' + endAmount.toFixed(2) + ' ' + startCurrency);
    console.log('Profit: ' + profit.toFixed(2) + ' ' + startCurrency + ' (' + profitPercent.toFixed(2) + '%)');

    const currencySymbol = startCurrency === 'NGN' ? '₦' : '$';
    const message = '✅ <b>LIVE TRADE SUCCESSFUL!</b> [QUIDAX]\n\n' +
                   '<b>Path:</b> ' + opportunity.path + '\n' +
                   '<b>Expected:</b> ' + opportunity.netProfit + '%\n' +
                   '<b>Actual:</b> ' + profitPercent.toFixed(2) + '%\n' +
                   '<b>Profit:</b> ' + currencySymbol + profit.toFixed(2) + '\n' +
                   '<b>Time:</b> ' + tradeLog.timestampET + ' ET\n\n' +
                   '🟢 <i>AUTO-TRADING ENABLED</i>';

    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');

  } catch (error) {
    console.error('\n❌ TRADE FAILED:', error.message);
    tradeLog.error = error.message;
    tradeLog.success = false;
    stats.tradesFailed++;

    const message = '❌ <b>LIVE TRADE FAILED</b> [QUIDAX]\n\n' +
                   '<b>Path:</b> ' + opportunity.path + '\n' +
                   '<b>Error:</b> ' + error.message + '\n' +
                   '<b>Time:</b> ' + tradeLog.timestampET + ' ET\n\n' +
                   '🟢 <i>AUTO-TRADING ENABLED</i>';

    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');
  } finally {
    stats.tradesExecuted++;
  }
}

function generateArbitragePaths(prices) {
  const paths = [];
  const marketList = Object.keys(prices);

  const marketMap = {};
  marketList.forEach(m => {
    const parsed = parseQuidaxPair(m);
    if (parsed) {
      marketMap[parsed.base + '-' + parsed.quote] = m;
      marketMap[parsed.quote + '-' + parsed.base] = m;
    }
  });

  const baseCurrencies = ['USDT', 'NGN'];

  baseCurrencies.forEach(startCurrency => {
    const startMarkets = marketList.filter(m => {
      const parsed = parseQuidaxPair(m);
      return parsed && (parsed.base === startCurrency || parsed.quote === startCurrency);
    });

    startMarkets.forEach(market1 => {
      const p1 = parseQuidaxPair(market1);
      if (!p1) return;

      const cryptoA = p1.base === startCurrency ? p1.quote : p1.base;
      if (cryptoA === startCurrency) return;

      marketList.forEach(market2 => {
        const p2 = parseQuidaxPair(market2);
        if (!p2) return;
        if (p2.base !== cryptoA && p2.quote !== cryptoA) return;

        const cryptoB = p2.base === cryptoA ? p2.quote : p2.base;
        if (cryptoB === cryptoA || cryptoB === startCurrency) return;

        const market3 = marketMap[cryptoB + '-' + startCurrency] || marketMap[startCurrency + '-' + cryptoB];

        if (market3 && market3 !== market1 && market3 !== market2) {
          paths.push({
            name: [startCurrency, cryptoA, cryptoB, startCurrency].join('->'),
            markets: [market1, market2, market3],
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
      const [market1, market2, market3] = path.markets;
      if (!prices[market1] || !prices[market2] || !prices[market3]) return;

      const spread1 = prices[market1].spread;
      const spread2 = prices[market2].spread;
      const spread3 = prices[market3].spread;
      const avgSpread = (spread1 + spread2 + spread3) / 3;
      const maxMarketSpread = Math.max(spread1, spread2, spread3);

      if (maxMarketSpread > CONFIG.maxSpread) {
        stats.filteredBySpread++;
        return;
      }

      let startAmount = path.startCurrency === 'NGN' ? 100000 : 1000;

      let amount = startAmount;
      let holding = path.startCurrency;

      const p1 = parseQuidaxPair(market1);
      if (!p1) return;
      if (!prices[market1].ask || !prices[market1].bid || prices[market1].ask <= 0 || prices[market1].bid <= 0) return;

      if (holding === p1.quote) {
        amount = (amount / prices[market1].ask) * (1 - FEES.taker);
        holding = p1.base;
      } else if (holding === p1.base) {
        amount = (amount * prices[market1].bid) * (1 - FEES.taker);
        holding = p1.quote;
      } else {
        return;
      }

      const p2 = parseQuidaxPair(market2);
      if (!p2) return;
      if (!prices[market2].ask || !prices[market2].bid || prices[market2].ask <= 0 || prices[market2].bid <= 0) return;

      if (holding === p2.quote) {
        amount = (amount / prices[market2].ask) * (1 - FEES.taker);
        holding = p2.base;
      } else if (holding === p2.base) {
        amount = (amount * prices[market2].bid) * (1 - FEES.taker);
        holding = p2.quote;
      } else {
        return;
      }

      const p3 = parseQuidaxPair(market3);
      if (!p3) return;
      if (!prices[market3].ask || !prices[market3].bid || prices[market3].ask <= 0 || prices[market3].bid <= 0) return;

      if (holding === p3.quote) {
        amount = (amount / prices[market3].ask) * (1 - FEES.taker);
        holding = p3.base;
      } else if (holding === p3.base) {
        amount = (amount * prices[market3].bid) * (1 - FEES.taker);
        holding = p3.quote;
      } else {
        return;
      }

      if (holding !== path.startCurrency) return;

      const finalAmount = amount;
      if (!isFinite(finalAmount) || finalAmount <= 0 || isNaN(finalAmount)) return;

      const grossProfit = ((finalAmount / Math.pow(1 - FEES.taker, 3) - startAmount) / startAmount) * 100;
      const netProfit = ((finalAmount - startAmount) / startAmount) * 100;

      if (!isFinite(grossProfit) || !isFinite(netProfit) || isNaN(grossProfit) || isNaN(netProfit)) return;

      if (netProfit > CONFIG.minProfitThreshold) {
        opportunities.push({
          path: path.name,
          grossProfit: grossProfit.toFixed(4),
          netProfit: netProfit.toFixed(4),
          avgSpread: avgSpread.toFixed(3),
          avgFee: (FEES.taker * 100).toFixed(3) + '%',
          spread1: spread1.toFixed(3),
          spread2: spread2.toFixed(3),
          spread3: spread3.toFixed(3),
          startCurrency: path.startCurrency,
          markets: path.markets,
          timestamp: new Date().toISOString(),
        });
      }
    } catch (error) {
      return;
    }
  });

  return opportunities;
}

async function logOpportunity(opp, prices) {
  const netProfitNum = parseFloat(opp.netProfit);
  const alert = netProfitNum >= 2.5 ? 'HIGH PROFIT!' : 'Opportunity';

  let message = '\n' + alert + ' [QUIDAX] ' + opp.path + '\n';
  message += '  Gross: ' + opp.grossProfit + '% (before fees)\n';
  message += '  Net: ' + opp.netProfit + '% (after fees)\n';
  message += '  Avg Fee: ' + opp.avgFee + ' (FLAT 0.1%!)\n';
  message += '  Avg Spread: ' + opp.avgSpread + '%\n';
  message += '  Spreads: ' + opp.spread1 + '%, ' + opp.spread2 + '%, ' + opp.spread3 + '%\n';
  message += '  Time: ' + toEasternTime(opp.timestamp) + ' ET\n';

  console.log(message);
  if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);

  if (netProfitNum > stats.bestProfit) {
    stats.bestProfit = netProfitNum;
    stats.bestPath = opp.path;
  }

  if (netProfitNum >= CONFIG.paperTradeThreshold) {
    
    let liquidityCheck = { passed: true, details: [] };
    
    if (CONFIG.enableLiquidityCheck) {
      liquidityCheck = await checkPathLiquidity(opp.markets);
      
      if (!liquidityCheck.passed) {
        message = '  ⚠️  SKIPPED - Failed liquidity check\n';
        message += '======================================================================\n';
        console.log(message);
        if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);
        return;
      }
    }
    
    if (CONFIG.autoTrade && canTrade(opp.startCurrency)) {
      message = '  🤖 EXECUTING AUTO-TRADE...\n';
      message += '======================================================================\n';
      console.log(message);
      if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);
      
      await executeTrade(opp, prices);
    } else {
      message = '  📝 PAPER TRADE (autoTrade disabled)\n';
      message += '======================================================================\n';
      console.log(message);
      if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);
      
      const paperLog = simulatePaperTrade(opp);

      const currencySymbol = paperLog.startCurrency === 'NGN' ? '₦' : '$';
      const tradeSize = paperLog.startCurrency === 'NGN' ? CONFIG.maxTradeNGN : CONFIG.maxTradeUSDT;

      let telegramMsg = '📝 <b>PAPER TRADE OPPORTUNITY</b> [QUIDAX]\n\n' +
                       '<b>Path:</b> ' + opp.path + '\n' +
                       '<b>Markets:</b> ' + opp.markets.join(' → ') + '\n\n' +
                       '<b>Gross Profit:</b> ' + opp.grossProfit + '%\n' +
                       '<b>Net Profit:</b> ' + opp.netProfit + '%\n' +
                       '<b>Est. After Slippage:</b> ' + paperLog.estimatedNetProfit.toFixed(2) + '%\n\n' +
                       '<b>Avg Spread:</b> ' + opp.avgSpread + '%\n' +
                       '<b>Spreads:</b> ' + opp.spread1 + '%, ' + opp.spread2 + '%, ' + opp.spread3 + '%\n\n';

      if (CONFIG.enableLiquidityCheck && liquidityCheck.passed) {
        telegramMsg += '<b>Liquidity Check:</b> ✅ PASSED\n';
        liquidityCheck.details.forEach((liq, i) => {
          telegramMsg += '  ' + opp.markets[i] + ': Ask=' + liq.askDepth.toFixed(2) + ', Bid=' + liq.bidDepth.toFixed(2) + '\n';
        });
        telegramMsg += '\n';
      }

      telegramMsg += '<b>Trade Size:</b> ' + currencySymbol + tradeSize.toFixed(2) + '\n' +
                    '<b>Est. Profit:</b> ' + currencySymbol + paperLog.estimatedProfitAmount.toFixed(2) + '\n\n' +
                    '<b>Time:</b> ' + paperLog.timestampET + ' ET\n\n' +
                    '🔴 <i>AUTO-TRADING DISABLED (Paper Trade Only)</i>';

      sendTelegramAlert(telegramMsg);

      console.log('📝 Paper trade simulated - Would have made: ' + currencySymbol + paperLog.estimatedProfitAmount.toFixed(2));
    }
  } else {
    message = '======================================================================\n';
    console.log(message);
    if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);
  }
}

function canTrade(currency) {
  const today = new Date().toDateString();
  if (stats.lastResetDate !== today) {
    stats.dailyTradesNGN = 0;
    stats.dailyTradesUSDT = 0;
    stats.dailyProfitNGN = 0;
    stats.dailyProfitUSDT = 0;
    stats.lastResetDate = today;
  }

  const totalDailyTrades = stats.dailyTradesNGN + stats.dailyTradesUSDT;
  if (CONFIG.maxDailyTrades > 0 && totalDailyTrades >= CONFIG.maxDailyTrades) {
    console.log('⚠️ Daily trade limit reached');
    return false;
  }

  if (currency === 'NGN' && stats.dailyProfitNGN <= -CONFIG.maxDailyLossNGN) {
    console.log('⚠️ NGN daily loss limit reached');
    sendTelegramAlert('🛑 QUIDAX TRADING STOPPED - NGN daily loss limit: ₦' + stats.dailyProfitNGN.toFixed(2));
    return false;
  }

  if (currency === 'USDT' && stats.dailyProfitUSDT <= -CONFIG.maxDailyLossUSDT) {
    console.log('⚠️ USDT daily loss limit reached');
    sendTelegramAlert('🛑 QUIDAX TRADING STOPPED - USDT daily loss limit: $' + stats.dailyProfitUSDT.toFixed(2));
    return false;
  }

  return true;
}

function printStats() {
  const uptime = Math.floor((new Date() - stats.startTime) / 1000);
  const hours = Math.floor(uptime / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);

  const ngnPaths = PATHS.filter(p => p.startCurrency === 'NGN').length;
  const usdtPaths = PATHS.filter(p => p.startCurrency === 'USDT').length;

  console.log('\n======================================================================');
  console.log('STATISTICS [QUIDAX NIGERIA]');
  console.log('======================================================================');
  console.log('Mode: ' + (CONFIG.autoTrade ? '🟢 LIVE TRADING' : '📝 PAPER TRADING'));
  console.log('Liquidity Check: ' + (CONFIG.enableLiquidityCheck ? '✅ ENABLED' : '❌ DISABLED'));
  console.log('Uptime: ' + hours + 'h ' + minutes + 'm');
  console.log('Scans: ' + stats.totalScans);
  console.log('Paths: ' + PATHS.length + ' (NGN: ' + ngnPaths + ', USDT: ' + usdtPaths + ')');
  console.log('Opportunities: ' + stats.totalOpportunities);
  console.log('Filtered (Wide Spread): ' + stats.filteredBySpread);
  console.log('');
  console.log('Liquidity Checks: Passed=' + stats.liquidityChecksPassed + ', Failed=' + stats.liquidityChecksFailed);
  console.log('');
  console.log('Paper Trades: ' + stats.paperTrades);
  console.log('Paper Profit: ₦' + stats.paperProfitNGN.toFixed(2) + ' / $' + stats.paperProfitUSDT.toFixed(2));
  console.log('');
  console.log('Live Trades Executed: ' + stats.tradesExecuted);
  console.log('  Successful: ' + stats.tradesSuccessful);
  console.log('  Failed: ' + stats.tradesFailed);
  console.log('Daily Trades: ' + (stats.dailyTradesNGN + stats.dailyTradesUSDT) + '/' + CONFIG.maxDailyTrades);
  console.log('Daily P&L: ₦' + stats.dailyProfitNGN.toFixed(2) + ' / $' + stats.dailyProfitUSDT.toFixed(2));
  console.log('Total P&L: ₦' + stats.totalProfitNGN.toFixed(2) + ' / $' + stats.totalProfitUSDT.toFixed(2));
  console.log('Best: ' + stats.bestProfit.toFixed(4) + '% ' + (stats.bestPath || ''));
  console.log('======================================================================\n');
}

async function scan() {
  try {
    stats.totalScans++;
    console.log('\n[' + toEasternTime(new Date()) + ' ET] Scan #' + stats.totalScans);

    const prices = await fetchQuidaxPrices();

    if (PATHS.length === 0) {
      PATHS = generateArbitragePaths(prices);
      console.log('\n🇳🇬 Found ' + PATHS.length + ' Nigeria-only paths (USDT/NGN)!\n');

      const ngnPaths = PATHS.filter(p => p.startCurrency === 'NGN').length;
      const usdtPaths = PATHS.filter(p => p.startCurrency === 'USDT').length;
      console.log('NGN paths: ' + ngnPaths);
      console.log('USDT paths: ' + usdtPaths);
      console.log('Fees: FLAT 0.1% taker for ALL pairs! 🎉\n');
    }

    const opportunities = calculateArbitrage(prices);

    if (opportunities.length > 0) {
      stats.totalOpportunities += opportunities.length;
      console.log('\nFound ' + opportunities.length + ' opportunity(ies)!\n');

      opportunities.sort((a, b) => parseFloat(b.netProfit) - parseFloat(a.netProfit));

      for (const opp of opportunities.slice(0, 3)) {
        await logOpportunity(opp, prices);
      }
    } else {
      console.log('No opportunities (Min: ' + CONFIG.minProfitThreshold + '%, Max spread: ' + CONFIG.maxSpread + '%)');
    }

    if (stats.totalScans % 20 === 0) printStats();

  } catch (error) {
    console.error('Error: ' + error.message);
  }
}

console.log('\n======================================================================');
console.log('QUIDAX AUTO-TRADING BOT - NIGERIA 🇳🇬');
console.log('======================================================================');
console.log('Mode: ' + (CONFIG.autoTrade ? '🟢 LIVE TRADING ENABLED' : '📝 PAPER TRADING MODE'));
console.log('Liquidity Check: ' + (CONFIG.enableLiquidityCheck ? '✅ ENABLED' : '❌ DISABLED'));
console.log('Strategy: Triangular arbitrage (USDT/NGN only)');
console.log('Fees: FLAT 0.1% taker for ALL pairs (better than Luno!)');
console.log('Interval: ' + (CONFIG.scanInterval / 1000) + 's');
console.log('Min profit: ' + CONFIG.minProfitThreshold + '%');
console.log('Paper trade threshold: ' + CONFIG.paperTradeThreshold + '%');
console.log('Max spread: ' + CONFIG.maxSpread + '%');
console.log('Max trade: ₦' + CONFIG.maxTradeNGN + ' / $' + CONFIG.maxTradeUSDT);
console.log('Daily limits: ' + CONFIG.maxDailyTrades + ' trades');
if (CONFIG.enableLiquidityCheck) {
  console.log('Liquidity req: Ask≥' + CONFIG.minAskDepth + ', Bid≥' + CONFIG.minBidDepth + ', Spread≤' + CONFIG.maxSpreadForTrade + '%');
}
console.log('======================================================================\n');

if (!CONFIG.autoTrade) {
  console.log('📝 PAPER TRADING MODE - Simulating trades without execution');
  console.log('Telegram alerts will show estimated profits');
  console.log('Liquidity checks: ' + (CONFIG.enableLiquidityCheck ? 'ENABLED ✅' : 'DISABLED ❌'));
  console.log('Set autoTrade: true to enable LIVE trading\n');

  const startMsg = '📝 <b>Quidax Bot Started - PAPER TRADING MODE</b>\n\n' +
                  '<b>Pairs:</b> USDT/NGN only\n' +
                  '<b>Min profit:</b> ' + CONFIG.minProfitThreshold + '%\n' +
                  '<b>Paper trade alert:</b> ' + CONFIG.paperTradeThreshold + '%\n' +
                  '<b>Max spread:</b> ' + CONFIG.maxSpread + '%\n' +
                  '<b>Liquidity check:</b> ' + (CONFIG.enableLiquidityCheck ? '✅ Enabled' : '❌ Disabled') + '\n' +
                  '<b>Fees:</b> FLAT 0.1% for ALL pairs! 🎉\n\n' +
                  '🔴 <i>AUTO-TRADING DISABLED</i>';
  sendTelegramAlert(startMsg);

  scan();
  setInterval(scan, CONFIG.scanInterval);
} else {
  console.log('⚠️  WARNING: LIVE TRADING IS ENABLED!');
  console.log('⚠️  The bot will execute REAL trades on QUIDAX!');
  console.log('⚠️  Liquidity checks: ' + (CONFIG.enableLiquidityCheck ? 'ENABLED ✅' : 'DISABLED ❌'));
  console.log('⚠️  Press Ctrl+C within 10 seconds to cancel...\n');

  setTimeout(() => {
    console.log('🤖 Live trading started on Quidax Nigeria!\n');

    const startMsg = '🟢 <b>Quidax Bot Started - LIVE TRADING ENABLED</b>\n\n' +
                    '<b>Pairs:</b> USDT/NGN only\n' +
                    '<b>Min profit:</b> ' + CONFIG.minProfitThreshold + '%\n' +
                    '<b>Max spread:</b> ' + CONFIG.maxSpread + '%\n' +
                    '<b>Trade size:</b> ₦' + CONFIG.maxTradeNGN + ' / $' + CONFIG.maxTradeUSDT + '\n' +
                    '<b>Daily limit:</b> ' + CONFIG.maxDailyTrades + ' trades\n' +
                    '<b>Liquidity check:</b> ' + (CONFIG.enableLiquidityCheck ? '✅ Enabled' : '❌ Disabled') + '\n' +
                    '<b>Fees:</b> FLAT 0.1% for ALL pairs! 🎉\n\n' +
                    '🟢 <b>REAL TRADES WILL BE EXECUTED!</b>';
    sendTelegramAlert(startMsg);

    scan();
    setInterval(scan, CONFIG.scanInterval);
  }, 10000);
}

process.on('SIGINT', () => {
  const mode = CONFIG.autoTrade ? 'LIVE TRADING' : 'PAPER TRADING';
  const finalMsg = '🛑 <b>Quidax Bot Stopped (' + mode + ')</b>\n\n' +
                  '<b>Paper Trades:</b> ' + stats.paperTrades + '\n' +
                  '<b>Paper Profit:</b> ₦' + stats.paperProfitNGN.toFixed(2) + ' / $' + stats.paperProfitUSDT.toFixed(2) + '\n' +
                  '<b>Liquidity Checks:</b> Pass=' + stats.liquidityChecksPassed + ', Fail=' + stats.liquidityChecksFailed + '\n\n' +
                  '<b>Live Trades:</b> ' + stats.tradesExecuted + '\n' +
                  '<b>Successful:</b> ' + stats.tradesSuccessful + '\n' +
                  '<b>Failed:</b> ' + stats.tradesFailed + '\n' +
                  '<b>Total P&L:</b> ₦' + stats.totalProfitNGN.toFixed(2) + ' / $' + stats.totalProfitUSDT.toFixed(2);
  sendTelegramAlert(finalMsg);
  printStats();
  console.log('Goodbye!\n');
  process.exit(0);
});
