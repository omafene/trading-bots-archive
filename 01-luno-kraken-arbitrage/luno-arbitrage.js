// Luno Auto-Trading Arbitrage Bot - NIGERIA ONLY (NGN/USDT)
// Run: node luno-arbitrage.js

const https = require('https');
const fs = require('fs');

const CONFIG = {
  // Luno API Keys
  apiKey: process.env.LUNO_API_KEY,
  apiSecret: process.env.LUNO_API_SECRET,

  // Trading Settings
  autoTrade: false,
  minProfitThreshold: 1.0,
  maxSpread: 8.0,

  // Paper Trading Settings
  paperTradeThreshold: 0.5,
  simulateTradeSize: true,

  // Liquidity Requirements
  enableLiquidityCheck: true,
  minAskDepth: 0.05,
  minBidDepth: 0.05,
  maxSpreadForTrade: 8.0,

  // Risk Controls
  maxTradeNGN: 50000,
  maxTradeUSDT: 50,
  maxDailyTrades: 20,
  maxDailyLossNGN: 5000,
  maxDailyLossUSDT: 15,
  minBalanceReserveNGN: 1000,
  minBalanceReserveUSDT: 5,

  // Monitoring
  scanInterval: 5000,
  logToFile: true,
  logFile: 'luno-arbitrage-opportunities.log',
  tradeLogFile: 'luno-trades.log',
  paperTradeLogFile: 'luno-paper-trades.log',

  // Telegram
  telegramEnabled: true,
  telegramBotToken: process.env.TELEGRAM_BOT_TOKEN,
  telegramChatId: process.env.TELEGRAM_CHAT_ID,
};

// ============================================
// DECIMAL CACHING SYSTEM (with adaptive learning)
// ============================================
const decimalCache = {
  base: {},
  counter: {}
};

const workingDecimalCache = {
  base: {},
  counter: {}
};

const WORKING_DECIMALS_FILE = './luno-working-decimals.json';

function loadWorkingDecimals() {
  try {
    if (fs.existsSync(WORKING_DECIMALS_FILE)) {
      const data = JSON.parse(fs.readFileSync(WORKING_DECIMALS_FILE, 'utf8'));
      workingDecimalCache.base = data.base || {};
      workingDecimalCache.counter = data.counter || {};
      console.log('📚 Loaded working decimals cache:', Object.keys(workingDecimalCache.base).length + Object.keys(workingDecimalCache.counter).length, 'entries');
      if (Object.keys(workingDecimalCache.base).length > 0) {
        console.log('   Base pairs:', Object.keys(workingDecimalCache.base).join(', '));
      }
      if (Object.keys(workingDecimalCache.counter).length > 0) {
        console.log('   Counter pairs:', Object.keys(workingDecimalCache.counter).join(', '));
      }
    } else {
      console.log('📚 No working decimals cache found, will learn from trades');
    }
  } catch (error) {
    console.log('⚠️  Could not load working decimals cache:', error.message);
  }
}

function saveWorkingDecimals() {
  try {
    fs.writeFileSync(WORKING_DECIMALS_FILE, JSON.stringify(workingDecimalCache, null, 2));
    console.log('   💾 Saved working decimals to disk');
  } catch (error) {
    console.error('❌ Failed to save working decimals cache:', error.message);
  }
}

// ============================================
// MINIMUM ORDER SIZE SYSTEM (with dynamic learning)
// ============================================
const minimumOrderSizes = {
  'XRP': 10,
  'ETH': 0.01,
  'LTC': 0.1,
  'SOL': 0.1,
  'XBT': 0.0001,
  'ZEC': 0.01,
  'ADA': 50,
  'DOGE': 100,
  'TRX': 100,
  'MATIC': 10,
  'LINK': 1,
  'AAVE': 0.1,
  'ALGO': 50,
  'ATOM': 1,
  'AVAX': 0.5,
  'CRV': 10,
  'DOT': 1,
  'FTM': 20,
  'GRT': 50,
  'NEAR': 2,
  'SAND': 20,
  'SKY': 1,
  'SNX': 2,
  'UNI': 2,
  'XLM': 50,
  'BCH': 0.01,
  'NGN': 100,
  'USDT': 5,
  'USDC': 5
};

const MINIMUM_SIZES_FILE = './luno-minimum-sizes.json';

function loadMinimumSizes() {
  try {
    if (fs.existsSync(MINIMUM_SIZES_FILE)) {
      const data = JSON.parse(fs.readFileSync(MINIMUM_SIZES_FILE, 'utf8'));
      Object.assign(minimumOrderSizes, data);
      console.log('📏 Loaded minimum order sizes:', Object.keys(data).length, 'currencies');
      const learned = Object.keys(data).filter(k => data[k] !== minimumOrderSizes[k]);
      if (learned.length > 0) {
        console.log('   Learned from API: ' + learned.join(', '));
      }
    } else {
      console.log('📏 No learned minimum sizes found, using defaults');
    }
  } catch (error) {
    console.log('⚠️  Could not load minimum sizes:', error.message);
  }
}

function saveMinimumSizes() {
  try {
    fs.writeFileSync(MINIMUM_SIZES_FILE, JSON.stringify(minimumOrderSizes, null, 2));
    console.log('   💾 Saved minimum order sizes to disk');
  } catch (error) {
    console.error('❌ Failed to save minimum sizes:', error.message);
  }
}

function extractMinimumFromError(errorMessage, currency) {
  const patterns = [
    /minimum.*?order.*?(?:is|:)\s*(\d+\.?\d*)/i,
    /minimum.*?(\d+\.?\d*)\s*(?:of|for)/i,
    /order.*?must.*?(?:be|exceed)\s*(\d+\.?\d*)/i,
    /(\d+\.?\d*)\s*minimum/i
  ];

  for (const pattern of patterns) {
    const match = errorMessage.match(pattern);
    if (match) {
      const minSize = parseFloat(match[1]);
      if (minSize > 0 && minSize < 1000000) {
        console.log('   📏 LEARNED: ' + currency + ' minimum order size is ' + minSize);
        minimumOrderSizes[currency] = minSize;
        saveMinimumSizes();
        return minSize;
      }
    }
  }
  return null;
}

// Telegram Bot Command Handler
const TelegramBot = require('node-telegram-bot-api');
let bot;

if (CONFIG.telegramEnabled) {
  bot = new TelegramBot(CONFIG.telegramBotToken, { polling: true });

  function isAuthorized(chatId) {
    return chatId.toString() === CONFIG.telegramChatId;
  }

  bot.onText(/\/status/, async (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    const uptime = Math.floor((new Date() - stats.startTime) / 1000);
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);

    const response =
      '📊 <b>BOT STATUS</b>\n\n' +
      '<b>Mode:</b> ' + (CONFIG.autoTrade ? '🟢 LIVE TRADING' : '📝 PAPER TRADING') + '\n' +
      '<b>Uptime:</b> ' + hours + 'h ' + minutes + 'm\n' +
      '<b>Scans:</b> ' + stats.totalScans + '\n' +
      '<b>Opportunities:</b> ' + stats.totalOpportunities + '\n' +
      '<b>Paper Trades:</b> ' + stats.paperTrades + '\n' +
      '<b>Paper Profit:</b> ₦' + stats.paperProfitNGN.toFixed(2) + ' / $' + stats.paperProfitUSDT.toFixed(2) + '\n\n' +
      '<b>Live Trades:</b> ' + stats.tradesExecuted + ' (✅' + stats.tradesSuccessful + ' ❌' + stats.tradesFailed + ')\n' +
      '<b>Total P&L:</b> ₦' + stats.totalProfitNGN.toFixed(2) + ' / $' + stats.totalProfitUSDT.toFixed(2) + '\n\n' +
      '<b>Liquidity Checks:</b> ✅' + stats.liquidityChecksPassed + ' ❌' + stats.liquidityChecksFailed + '\n' +
      '<b>Best:</b> ' + stats.bestProfit.toFixed(2) + '% ' + stats.bestPath + '\n\n' +
      '<b>Settings:</b>\n' +
      '  Min profit: ' + CONFIG.minProfitThreshold + '%\n' +
      '  Alert threshold: ' + CONFIG.paperTradeThreshold + '%\n' +
      '  Max spread: ' + CONFIG.maxSpread + '%\n' +
      '  Daily limit: ' + (stats.dailyTradesNGN + stats.dailyTradesUSDT) + '/' + CONFIG.maxDailyTrades;

    bot.sendMessage(msg.chat.id, response, { parse_mode: 'HTML' });
  });

  bot.onText(/\/decimals/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    const detectedBase = Object.keys(decimalCache.base).length;
    const detectedCounter = Object.keys(decimalCache.counter).length;
    const workingBase = Object.keys(workingDecimalCache.base).length;
    const workingCounter = Object.keys(workingDecimalCache.counter).length;

    let message = '📊 <b>DECIMAL PRECISION CACHES</b>\n\n';

    message += '🎓 <b>Working (API-Verified):</b>\n';
    if (workingBase > 0 || workingCounter > 0) {
      if (workingBase > 0) {
        message += '<b>Base:</b>\n';
        Object.keys(workingDecimalCache.base).forEach(pair => {
          message += '  • ' + pair + ': ' + workingDecimalCache.base[pair] + ' decimals\n';
        });
      }
      if (workingCounter > 0) {
        message += '<b>Counter:</b>\n';
        Object.keys(workingDecimalCache.counter).forEach(pair => {
          message += '  • ' + pair + ': ' + workingDecimalCache.counter[pair] + ' decimals\n';
        });
      }
    } else {
      message += 'None yet - will learn from first trades\n';
    }

    message += '\n🔍 <b>Detected (from orderbook):</b>\n';
    if (detectedBase > 0 || detectedCounter > 0) {
      if (detectedBase > 0) {
        message += '<b>Base:</b>\n';
        Object.keys(decimalCache.base).forEach(pair => {
          message += '  • ' + pair + ': ' + decimalCache.base[pair] + ' decimals\n';
        });
      }
      if (detectedCounter > 0) {
        message += '<b>Counter:</b>\n';
        Object.keys(decimalCache.counter).forEach(pair => {
          message += '  • ' + pair + ': ' + decimalCache.counter[pair] + ' decimals\n';
        });
      }
    } else {
      message += 'None yet\n';
    }

    message += '\n💡 <i>Working cache is used first (learned from successful trades)</i>';

    bot.sendMessage(msg.chat.id, message, { parse_mode: 'HTML' });
  });

  bot.onText(/\/minimums/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    let message = '📏 <b>MINIMUM ORDER SIZES</b>\n\n';

    const currencies = Object.keys(minimumOrderSizes).sort();

    message += '<b>Crypto Assets:</b>\n';
    currencies.filter(c => !['NGN', 'USDT', 'USDC'].includes(c)).forEach(curr => {
      message += '  • ' + curr + ': ' + minimumOrderSizes[curr] + '\n';
    });

    message += '\n<b>Fiat/Stablecoins:</b>\n';
    ['NGN', 'USDT', 'USDC'].forEach(curr => {
      if (minimumOrderSizes[curr]) {
        message += '  • ' + curr + ': ' + minimumOrderSizes[curr] + '\n';
      }
    });

    message += '\n💡 <i>These are learned from API errors and updated automatically</i>';

    bot.sendMessage(msg.chat.id, message, { parse_mode: 'HTML' });
  });

  bot.onText(/\/mode (.+)/, (msg, match) => {
    if (!isAuthorized(msg.chat.id)) return;

    const mode = match[1].toLowerCase();

    if (mode === 'live') {
      CONFIG.autoTrade = true;
      bot.sendMessage(msg.chat.id,
        '🟢 <b>LIVE TRADING ENABLED</b>\n\n' +
        '⚠️ Bot will now execute REAL trades!\n' +
        'Use /mode paper to disable.',
        { parse_mode: 'HTML' }
      );
      console.log('\n🟢 SWITCHED TO LIVE TRADING MODE via Telegram\n');
    } else if (mode === 'paper') {
      CONFIG.autoTrade = false;
      bot.sendMessage(msg.chat.id,
        '📝 <b>PAPER TRADING ENABLED</b>\n\n' +
        'Bot will simulate trades only.\n' +
        'Use /mode live to enable real trading.',
        { parse_mode: 'HTML' }
      );
      console.log('\n📝 SWITCHED TO PAPER TRADING MODE via Telegram\n');
    } else {
      bot.sendMessage(msg.chat.id, '❌ Invalid mode. Use: /mode live OR /mode paper');
    }
  });

  bot.onText(/\/threshold (\d+\.?\d*)/, (msg, match) => {
    if (!isAuthorized(msg.chat.id)) return;

    const newThreshold = parseFloat(match[1]);

    if (newThreshold >= 0.1 && newThreshold <= 10) {
      CONFIG.paperTradeThreshold = newThreshold;
      CONFIG.minProfitThreshold = newThreshold;
      bot.sendMessage(msg.chat.id,
        '✅ <b>Thresholds Updated</b>\n\n' +
        'Min profit: ' + newThreshold + '%\n' +
        'Alert threshold: ' + newThreshold + '%',
        { parse_mode: 'HTML' }
      );
      console.log('\n✅ Threshold changed to ' + newThreshold + '% via Telegram\n');
    } else {
      bot.sendMessage(msg.chat.id, '❌ Invalid threshold. Use 0.1 to 10.0');
    }
  });

  bot.onText(/\/spread (\d+\.?\d*)/, (msg, match) => {
    if (!isAuthorized(msg.chat.id)) return;

    const newSpread = parseFloat(match[1]);

    if (newSpread >= 1 && newSpread <= 15) {
      CONFIG.maxSpread = newSpread;
      bot.sendMessage(msg.chat.id,
        '✅ <b>Max Spread Updated</b>\n\nMax spread: ' + newSpread + '%',
        { parse_mode: 'HTML' }
      );
      console.log('\n✅ Max spread changed to ' + newSpread + '% via Telegram\n');
    } else {
      bot.sendMessage(msg.chat.id, '❌ Invalid spread. Use 1.0 to 15.0');
    }
  });

  bot.onText(/\/balance/, async (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    try {
      bot.sendMessage(msg.chat.id, '🔍 Fetching balances...');
      const balances = await getBalance();

      let response = '💰 <b>LUNO BALANCES</b>\n\n';

      const currencies = ['NGN', 'USDT', 'XBT', 'ETH', 'LTC', 'SOL', 'XRP', 'ZEC', 'ADA', 'DOGE'];
      currencies.forEach(cur => {
        if (balances[cur] && balances[cur].total > 0) {
          const symbol = cur === 'NGN' ? '₦' : cur === 'USDT' ? '$' : '';
          response += '<b>' + cur + ':</b> ' + symbol + balances[cur].available.toFixed(4) + '\n';
          if (balances[cur].reserved > 0) {
            response += '  <i>Reserved: ' + symbol + balances[cur].reserved.toFixed(4) + '</i>\n';
          }
        }
      });

      bot.sendMessage(msg.chat.id, response, { parse_mode: 'HTML' });
    } catch (error) {
      bot.sendMessage(msg.chat.id, '❌ Error fetching balance: ' + error.message);
    }
  });

  bot.onText(/\/opportunities/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    try {
      const logContent = fs.readFileSync(CONFIG.logFile, 'utf8');
      const lines = logContent.split('\n');

      let opportunities = [];
      for (let i = lines.length - 1; i >= 0 && opportunities.length < 3; i--) {
        if (lines[i].includes('Opportunity [LUNO]')) {
          let opp = lines[i] + '\n';
          for (let j = i + 1; j < i + 7 && j < lines.length; j++) {
            opp += lines[j] + '\n';
          }
          opportunities.push(opp);
        }
      }

      if (opportunities.length > 0) {
        let response = '📊 <b>RECENT OPPORTUNITIES</b>\n\n';
        opportunities.reverse().forEach((opp, idx) => {
          response += '<code>' + opp + '</code>\n\n';
        });
        bot.sendMessage(msg.chat.id, response, { parse_mode: 'HTML' });
      } else {
        bot.sendMessage(msg.chat.id, '📊 No opportunities found yet.');
      }
    } catch (error) {
      bot.sendMessage(msg.chat.id, '❌ Error reading opportunities: ' + error.message);
    }
  });

  bot.onText(/\/liquidity (.+)/, (msg, match) => {
    if (!isAuthorized(msg.chat.id)) return;

    const mode = match[1].toLowerCase();

    if (mode === 'on') {
      CONFIG.enableLiquidityCheck = true;
      bot.sendMessage(msg.chat.id, '✅ Liquidity checks ENABLED');
      console.log('\n✅ Liquidity checks ENABLED via Telegram\n');
    } else if (mode === 'off') {
      CONFIG.enableLiquidityCheck = false;
      bot.sendMessage(msg.chat.id, '⚠️ Liquidity checks DISABLED');
      console.log('\n⚠️ Liquidity checks DISABLED via Telegram\n');
    } else {
      bot.sendMessage(msg.chat.id, '❌ Invalid option. Use: /liquidity on OR /liquidity off');
    }
  });

  bot.onText(/\/restart/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    bot.sendMessage(msg.chat.id, '🔄 Restarting bot in 3 seconds...');
    console.log('\n🔄 RESTART requested via Telegram\n');

    setTimeout(() => {
      process.exit(0);
    }, 3000);
  });

  bot.onText(/\/stop/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    isStopped = true;
    CONFIG.autoTrade = false;
    
    if (scanInterval) {
      clearInterval(scanInterval);
    }
    
    bot.sendMessage(msg.chat.id,
      '⏸️ <b>Bot Paused</b>\n\n' +
      'Paper Trades: ' + stats.paperTrades + '\n' +
      'Live Trades: ' + stats.tradesExecuted + '\n' +
      'Total P&L: ₦' + stats.totalProfitNGN.toFixed(2) + ' / $' + stats.totalProfitUSDT.toFixed(2) + '\n\n' +
      '✅ Scanning stopped\n' +
      '✅ Trading disabled\n\n' +
      'Use /start to resume.',
      { parse_mode: 'HTML' }
    );
    
    console.log('\n⏸️  Bot paused via Telegram\n');
    printStats();
  });

  bot.onText(/\/start/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    if (!isStopped) {
      bot.sendMessage(msg.chat.id, '✅ Bot is already running!');
      return;
    }

    isStopped = false;
    
    bot.sendMessage(msg.chat.id, 
      '▶️ <b>Resuming Bot</b>\n\n' +
      'Scanning will restart in 5 seconds...\n' +
      'Mode: ' + (CONFIG.autoTrade ? '🟢 Live' : '📝 Paper'),
      { parse_mode: 'HTML' }
    );
    
    console.log('\n▶️  Bot resumed via Telegram\n');
    
    setTimeout(() => {
      scan();
      scanInterval = setInterval(scan, CONFIG.scanInterval);
    }, 5000);
  });

  bot.onText(/\/help/, (msg) => {
    if (!isAuthorized(msg.chat.id)) return;

    const helpText =
      '🤖 <b>BOT COMMANDS</b>\n\n' +
      '<b>Status & Info:</b>\n' +
      '/status - View bot statistics\n' +
      '/balance - Check Luno balances\n' +
      '/decimals - View decimal precision cache\n' +
      '/minimums - View minimum order sizes\n' +
      '/opportunities - Show recent opportunities\n\n' +
      '<b>Control:</b>\n' +
      '/start - Resume bot (if paused)\n' +
      '/stop - Pause bot (stops scanning)\n' +
      '/restart - Full restart (requires PM2)\n' +
      '/mode live - Enable LIVE trading ⚠️\n' +
      '/mode paper - Enable paper trading\n' +
      '/liquidity on - Enable liquidity checks\n' +
      '/liquidity off - Disable liquidity checks\n\n' +
      '<b>Settings:</b>\n' +
      '/threshold 3.0 - Set profit threshold\n' +
      '/spread 7.0 - Set max spread\n\n' +
      '<b>Help:</b>\n' +
      '/help - Show this help';

    bot.sendMessage(msg.chat.id, helpText, { parse_mode: 'HTML' });
  });

  console.log('✅ Telegram bot commands initialized');
}

const FEES = {
  standard_taker: 0.006,
  standard_maker: 0.004,
  stablecoin_taker: 0.001,
  stablecoin_maker: -0.0001,
  withdrawal: 0,
  deposit: 0,
};

let isTrading = false;
let isStopped = false;
let scanInterval;

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

function parseLunoPair(pair) {
  if (pair.endsWith('NGN')) return { base: pair.slice(0, -3), quote: 'NGN' };
  if (pair.endsWith('USDT')) return { base: pair.slice(0, -4), quote: 'USDT' };

  if (pair.startsWith('XBT')) {
    const quote = pair.slice(3);
    if (quote === 'NGN' || quote === 'USDT') {
      return { base: 'XBT', quote: quote };
    }
  }

  if (pair.endsWith('XBT')) {
    return { base: pair.slice(0, -3), quote: 'XBT' };
  }

  return null;
}

function getFeeForPair(pair) {
  if (pair.includes('USDT')) {
    return FEES.stablecoin_taker;
  }
  return FEES.standard_taker;
}

async function getDecimalPrecision(pair, volumeType) {
  if (volumeType === 'counter' && decimalCache.counter[pair]) {
    return decimalCache.counter[pair];
  }
  if (volumeType === 'base' && decimalCache.base[pair]) {
    return decimalCache.base[pair];
  }

  try {
    const book = await new Promise((resolve, reject) => {
      const options = {
        hostname: 'api.luno.com',
        path: '/api/1/orderbook_top?pair=' + pair,
        method: 'GET',
      };

      https.get(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (error) {
            reject(error);
          }
        });
      }).on('error', reject);
    });

    if (book.asks && book.asks.length > 0) {
      const volumes = book.asks.slice(0, 5).map(a => a.volume);
      let maxDecimals = 0;
      volumes.forEach(vol => {
        const parts = vol.toString().split('.');
        if (parts.length > 1) {
          maxDecimals = Math.max(maxDecimals, parts[1].length);
        }
      });

      const parsed = parseLunoPair(pair);
      let cappedDecimals = maxDecimals;

      if (volumeType === 'base') {
        if (parsed.base === 'XBT' || parsed.base === 'ETH') {
          cappedDecimals = Math.min(maxDecimals, 8);
        } else if (parsed.base === 'XRP') {
          cappedDecimals = Math.min(maxDecimals, 6);
        } else if (parsed.base === 'LTC' || parsed.base === 'SOL' || parsed.base === 'ZEC') {
          cappedDecimals = Math.min(maxDecimals, 8);
        }
      } else {
        if (parsed.quote === 'NGN' || parsed.quote === 'USDT' || parsed.quote === 'USDC') {
          cappedDecimals = Math.min(maxDecimals, 2);
        } else if (parsed.quote === 'XBT') {
          cappedDecimals = Math.min(maxDecimals, 8);
        }
      }

      if (volumeType === 'counter') {
        decimalCache.counter[pair] = cappedDecimals;
      } else {
        decimalCache.base[pair] = cappedDecimals;
      }

      console.log('   📐 Detected ' + maxDecimals + ' decimals, using ' + cappedDecimals + ' for ' + pair + ' (' + volumeType + ' volume)');
      return cappedDecimals;
    }
  } catch (error) {
    console.log('   ⚠️  Could not detect decimals for ' + pair + ', using safe default');
  }

  const parsed = parseLunoPair(pair);
  if (volumeType === 'counter') {
    if (parsed.quote === 'NGN' || parsed.quote === 'USDT' || parsed.quote === 'USDC') {
      return 2;
    } else if (parsed.quote === 'XBT') {
      return 8;
    }
    return 4;
  } else {
    if (parsed.base === 'XBT' || parsed.base === 'ETH') {
      return 8;
    } else if (parsed.base === 'XRP') {
      return 6;
    } else if (parsed.base === 'LTC' || parsed.base === 'SOL' || parsed.base === 'ZEC') {
      return 8;
    } else if (parsed.base === 'ADA' || parsed.base === 'DOGE' || parsed.base === 'TRX') {
      return 2;
    }
    return 6;
  }
}

function lunoAPI(endpoint, method = 'GET', params = {}) {
  return new Promise((resolve, reject) => {
    const auth = Buffer.from(CONFIG.apiKey + ':' + CONFIG.apiSecret).toString('base64');

    let path = '/api/1/' + endpoint;
    let postData = '';

    if (method === 'POST') {
      postData = new URLSearchParams(params).toString();
    }

    const options = {
      hostname: 'api.luno.com',
      path: path,
      method: method,
      headers: {
        'Authorization': 'Basic ' + auth,
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
            reject(new Error('Luno API: ' + parsed.error));
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

function checkPairLiquidity(pair) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'api.luno.com',
      path: '/api/1/orderbook_top?pair=' + pair,
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

            const askDepth = top5Asks.reduce((sum, a) => sum + parseFloat(a.volume), 0);
            const bidDepth = top5Bids.reduce((sum, b) => sum + parseFloat(b.volume), 0);

            const bestAsk = parseFloat(top5Asks[0].price);
            const bestBid = parseFloat(top5Bids[0].price);
            const spread = ((bestAsk - bestBid) / bestBid * 100);

            const isLiquid = (
              (askDepth >= CONFIG.minAskDepth || bidDepth >= CONFIG.minBidDepth) &&
              spread <= CONFIG.maxSpreadForTrade
            );

            resolve({
              pair: pair,
              liquid: isLiquid,
              askDepth: askDepth,
              bidDepth: bidDepth,
              spread: spread,
            });
          } else {
            resolve({
              pair: pair,
              liquid: false,
              askDepth: 0,
              bidDepth: 0,
              spread: 999,
            });
          }
        } catch (error) {
          resolve({
            pair: pair,
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
        pair: pair,
        liquid: false,
        askDepth: 0,
        bidDepth: 0,
        spread: 999,
        error: error.message,
      });
    });
  });
}

async function checkPathLiquidity(pairs) {
  const [pair1, pair2, pair3] = pairs;

  console.log('  🔍 Checking liquidity...');

  const liq1 = await checkPairLiquidity(pair1);
  const liq2 = await checkPairLiquidity(pair2);
  const liq3 = await checkPairLiquidity(pair3);

  const allLiquid = liq1.liquid && liq2.liquid && liq3.liquid;

  console.log('    ' + pair1 + ': ' + (liq1.liquid ? '✅' : '❌') + ' (Ask=' + liq1.askDepth.toFixed(2) + ', Bid=' + liq1.bidDepth.toFixed(2) + ', Spread=' + liq1.spread.toFixed(2) + '%)');
  console.log('    ' + pair2 + ': ' + (liq2.liquid ? '✅' : '❌') + ' (Ask=' + liq2.askDepth.toFixed(2) + ', Bid=' + liq2.bidDepth.toFixed(2) + ', Spread=' + liq2.spread.toFixed(2) + '%)');
  console.log('    ' + pair3 + ': ' + (liq3.liquid ? '✅' : '❌') + ' (Ask=' + liq3.askDepth.toFixed(2) + ', Bid=' + liq3.bidDepth.toFixed(2) + ', Spread=' + liq3.spread.toFixed(2) + '%)');

  if (allLiquid) {
    console.log('  ✅ All pairs have sufficient liquidity');
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

function fetchLunoPrices() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.luno.com',
      path: '/api/1/tickers',
      method: 'GET',
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const prices = {};

          const nigeriaPairs = [
            'AAVENGN', 'ADANGN', 'ALGONGN', 'ATOMNGN', 'AVAXNGN',
            'XBTNGN', 'CRVNGN', 'DOGENGN', 'DOTNGN', 'ETHNGN',
            'FTMNGN', 'GRTNGN', 'LINKNGN', 'LTCNGN', 'MATICNGN',
            'NEARNGN', 'SANDNGN', 'SKYNGN', 'SNXNGN', 'SOLNGN',
            'TRXNGN', 'UNINGN', 'USDCNGN', 'USDTNGN', 'XLMNGN',
            'XRPNGN', 'ZECNGN',

            'XBTUSDT', 'ETHUSDT', 'AAVEUSDT', 'ADAUSDT', 'ALGOUSDT',
            'ATOMUSDT', 'AVAXUSDT', 'CRVUSDT', 'DOGEUSDT', 'DOTUSDT',
            'FTMUSDT', 'GRTUSDT', 'LINKUSDT', 'LTCUSDT', 'MATICUSDT',
            'NEARUSDT', 'SANDUSDT', 'SKYUSDT', 'SNXUSDT', 'SOLUSDT',
            'TRXUSDT', 'UNIUSDT', 'XLMUSDT', 'XRPUSDT', 'ZECUSDT',

            'XBTUSDC', 'ETHUSDC',

            'ETHXBT', 'AAVEXBT', 'ADAXBT', 'ALGOXBT', 'ATOMXBT',
            'AVAXBT', 'BCHXBT', 'CRVXBT', 'DOGEXBT', 'DOTXBT',
            'FTMXBT', 'GRTXBT', 'LINKXBT', 'LTCXBT', 'MATICXBT',
            'NEARXBT', 'SANDXBT', 'SKYXBT', 'SNXXBT', 'SOLXBT',
            'TRXXBT', 'UNIXBT', 'XLMXBT', 'XRPXBT', 'ZECXBT',
          ];

          if (parsed.tickers) {
            parsed.tickers.forEach(ticker => {
              const pair = ticker.pair;

              if (!nigeriaPairs.includes(pair)) {
                return;
              }

              const ask = parseFloat(ticker.ask);
              const bid = parseFloat(ticker.bid);
              const last = parseFloat(ticker.last_trade);

              if (ask > 0 && bid > 0) {
                prices[pair] = {
                  ask: ask,
                  bid: bid,
                  last: last,
                  spread: ((ask - bid) / bid * 100),
                  volume: parseFloat(ticker.rolling_24_hour_volume || 0),
                };
              }
            });
          }

          console.log('✅ Loaded ' + Object.keys(prices).length + ' Nigeria pairs (NGN/USDT/USDC only)');
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
    const balance = await lunoAPI('balance');
    const balances = {};

    if (balance.balance) {
      balance.balance.forEach(b => {
        const total = parseFloat(b.balance);
        const reserved = parseFloat(b.reserved);
        const available = total - reserved;

        balances[b.asset] = {
          available: available,
          reserved: reserved,
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

async function placeOrder(pair, type, volume) {
  let params = {};
  const volumeType = type.toUpperCase() === 'BID' ? 'counter' : 'base';
  const volumeField = type.toUpperCase() === 'BID' ? 'counter_volume' : 'base_volume';

  const parsed = parseLunoPair(pair);
  const currency = volumeType === 'base' ? parsed.base : parsed.quote;
  const knownMinimum = minimumOrderSizes[currency];

  if (knownMinimum && volume < knownMinimum) {
    console.log('   ⚠️  Volume ' + volume.toFixed(8) + ' ' + currency + ' is below known minimum ' + knownMinimum);
    console.log('   💡 Skipping order placement - would be rejected by API');
    throw new Error('Volume ' + volume.toFixed(8) + ' ' + currency + ' below minimum ' + knownMinimum +
                    '. Increase maxTrade' + (currency === 'NGN' || currency === 'USDT' || currency === 'USDC' ? currency : '') +
                    ' or wait for larger opportunity.');
  }

  let decimals;
  if (workingDecimalCache[volumeType][pair]) {
    decimals = workingDecimalCache[volumeType][pair];
    console.log('   ✅ Using cached working decimals: ' + decimals + ' for ' + pair + ' (' + volumeType + ')');
  } else {
    decimals = await getDecimalPrecision(pair, volumeType);
    console.log('   🔍 Starting with detected decimals: ' + decimals + ' for ' + pair + ' (' + volumeType + ')');
  }

  const startingDecimals = decimals;
  const MIN_DECIMALS = 0;
  const MAX_ATTEMPTS = decimals + 1;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    try {
      params = {
        pair: pair,
        type: type.toUpperCase(),
      };

      params[volumeField] = volume.toFixed(decimals);

      const retryNote = attempt > 0 ? ', retry #' + attempt : '';
      console.log('   💰 ' + volumeField + ': ' + params[volumeField] + ' (' + decimals + ' decimals' + retryNote + ')');
      console.log('   📤 Placing order:', JSON.stringify(params, null, 2));

      const result = await lunoAPI('marketorder', 'POST', params);
      console.log('   ✅ Order placed:', result.order_id);

      if (!workingDecimalCache[volumeType][pair] || workingDecimalCache[volumeType][pair] !== decimals) {
        const wasLearned = !workingDecimalCache[volumeType][pair];
        workingDecimalCache[volumeType][pair] = decimals;
        saveWorkingDecimals();
        if (wasLearned) {
          console.log('   🎓 LEARNED: ' + pair + ' ' + volumeType + ' uses ' + decimals + ' decimals (tried ' + (attempt + 1) + ' attempt(s))');
        } else {
          console.log('   📚 Updated cache: ' + pair + ' ' + volumeType + ' = ' + decimals + ' decimals');
        }
      }

      return result;

    } catch (error) {
      if (error.message.includes('minimum') ||
          error.message.includes('too small') ||
          error.message.includes('below minimum')) {

        const learned = extractMinimumFromError(error.message, currency);

        if (learned) {
          console.log('   📚 Updated minimum order size cache for ' + currency);
          console.log('   💡 Next trade will need at least ' + learned + ' ' + currency);
        }
      }

      if (error.message.includes('too many decimal places') && decimals > MIN_DECIMALS) {
        decimals--;
        console.log('   ⚠️  Too many decimals! Reducing to ' + decimals + ' and retrying...');
        continue;
      }

      console.error('   ❌ Order failed:', error.message);
      console.error('   Failed params:', JSON.stringify(params, null, 2));

      const errorDetails = {
        timestamp: new Date().toISOString(),
        pair: pair,
        type: type,
        rawVolume: volume,
        startingDecimals: startingDecimals,
        attemptedDecimals: decimals,
        formattedVolume: params[volumeField],
        attempt: attempt + 1,
        totalAttempts: attempt + 1,
        error: error.message,
        fullParams: params
      };
      fs.appendFileSync('luno-order-errors.log', JSON.stringify(errorDetails, null, 2) + '\n---\n');

      throw error;
    }
  }

  throw new Error('Failed to place order after ' + MAX_ATTEMPTS + ' attempts (decimals ' + startingDecimals + ' down to 0)');
}

function simulatePaperTrade(opportunity) {
  const startCurrency = opportunity.startCurrency;
  const tradeSize = startCurrency === 'NGN' ? CONFIG.maxTradeNGN : CONFIG.maxTradeUSDT;

  const netProfitPercent = parseFloat(opportunity.netProfit);
  const grossProfitPercent = parseFloat(opportunity.grossProfit);

  const slippagePercent = 1.0;
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
    pairs: opportunity.pairs,
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

async function checkCurrentSpreads(pairs) {
  console.log('  🔍 Verifying current spreads before execution...');

  const spreads = [];

  for (const pair of pairs) {
    try {
      const book = await new Promise((resolve, reject) => {
        const options = {
          hostname: 'api.luno.com',
          path: '/api/1/orderbook_top?pair=' + pair,
          method: 'GET',
        };

        https.get(options, (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (error) {
              reject(error);
            }
          });
        }).on('error', reject);
      });

      if (book.asks && book.bids && book.asks.length > 0 && book.bids.length > 0) {
        const bestAsk = parseFloat(book.asks[0].price);
        const bestBid = parseFloat(book.bids[0].price);
        const spread = ((bestAsk - bestBid) / bestBid * 100);

        spreads.push({
          pair: pair,
          spread: spread,
          ask: bestAsk,
          bid: bestBid
        });

        console.log('    ' + pair + ': ' + spread.toFixed(2) + '% (Ask=' + bestAsk + ', Bid=' + bestBid + ')');
      } else {
        spreads.push({ pair: pair, spread: 999 });
        console.log('    ' + pair + ': ❌ No data');
      }
    } catch (error) {
      spreads.push({ pair: pair, spread: 999 });
      console.log('    ' + pair + ': ❌ Error - ' + error.message);
    }
  }

  return spreads;
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

  const MAX_WAIT_MS = 10000;
  const POLL_INTERVAL_MS = 500;
  const MIN_EXPECTED_RATIO = 0.90;

  async function waitForBalance(currency, expectedAmount, startingBalance, tradeName, isFinalTrade = false) {
    console.log('   ⏳ Waiting for settlement (checking every ' + POLL_INTERVAL_MS + 'ms)...');
    const startTime = Date.now();
    let attempts = 0;

    while (Date.now() - startTime < MAX_WAIT_MS) {
      attempts++;
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));

      const balanceCheck = await getBalance();
      const actualBalance = balanceCheck[currency]?.available || 0;

      let proceeds;
      if (isFinalTrade) {
        proceeds = actualBalance;
      } else {
        proceeds = actualBalance - startingBalance;
      }

      if (attempts % 2 === 0) {
        console.log('   📊 Check #' + attempts + ': ' + proceeds.toFixed(8) + ' ' + currency +
                    ' (expecting ~' + expectedAmount.toFixed(8) + ')');
      }

      if (isFinalTrade) {
        if (actualBalance > 0) {
          const waitedMs = Date.now() - startTime;
          console.log('   ✅ Funds available! Waited ' + waitedMs + 'ms (' + attempts + ' checks)');
          return { actualBalance, proceeds: actualBalance };
        }
      } else {
        if (proceeds >= expectedAmount * MIN_EXPECTED_RATIO) {
          const waitedMs = Date.now() - startTime;
          console.log('   ✅ Funds available! Waited ' + waitedMs + 'ms (' + attempts + ' checks)');
          return { actualBalance, proceeds };
        }
      }
    }

    const finalBalance = await getBalance();
    const finalActual = finalBalance[currency]?.available || 0;
    const finalProceeds = isFinalTrade ? finalActual : (finalActual - startingBalance);

    throw new Error('Timeout waiting for ' + tradeName + ': Expected ~' + expectedAmount.toFixed(8) +
                    ' ' + currency + ', only got ' + finalProceeds.toFixed(8) +
                    ' after ' + MAX_WAIT_MS + 'ms');
  }

  try {
    console.log('\n🚀 EXECUTING TRADE: ' + opportunity.path);
    console.log('Expected profit: ' + opportunity.netProfit + '%');

    const currentSpreads = await checkCurrentSpreads(opportunity.pairs);

    const maxAllowedSpread = 4.0;
    const badSpread = currentSpreads.find(s => s.spread > maxAllowedSpread);

    if (badSpread) {
      throw new Error('Spread too wide on ' + badSpread.pair + ': ' + badSpread.spread.toFixed(2) +
                      '% (max: ' + maxAllowedSpread + '%). Opportunity disappeared, aborting trade.');
    }

    const scanSpreads = [
      parseFloat(opportunity.spread1),
      parseFloat(opportunity.spread2),
      parseFloat(opportunity.spread3)
    ];

    let spreadIncrease = 0;
    currentSpreads.forEach((current, i) => {
      const increase = current.spread - scanSpreads[i];
      if (increase > spreadIncrease) {
        spreadIncrease = increase;
      }
    });

    if (spreadIncrease > 2.0) {
      throw new Error('Spreads widened by ' + spreadIncrease.toFixed(2) +
                      '% since scan (max allowed: 2%). Market moved, aborting trade.');
    }

    console.log('  ✅ Spread check passed - proceeding with execution\n');

    const [pair1, pair2, pair3] = opportunity.pairs;
    const startCurrency = opportunity.startCurrency;

    const balanceBefore = await getBalance();
    console.log('Balance before:', JSON.stringify(balanceBefore, null, 2));

    const startingBalances = {};
    ['NGN', 'USDT', 'USDC', 'XRP', 'ETH', 'LTC', 'SOL', 'XBT', 'ZEC', 'ADA', 'DOGE', 'TRX', 'MATIC', 'LINK', 'AAVE', 'ALGO', 'ATOM', 'AVAX', 'CRV', 'DOT', 'FTM', 'GRT', 'NEAR', 'SAND', 'SKY', 'SNX', 'UNI', 'XLM', 'BCH'].forEach(curr => {
      startingBalances[curr] = balanceBefore[curr]?.available || 0;
    });

    console.log('📊 Starting balances stored for all currencies');
    console.log('⚡ Smart polling enabled: checks every ' + POLL_INTERVAL_MS + 'ms, max wait ' + (MAX_WAIT_MS/1000) + 's');

    const availableBalance = balanceBefore[startCurrency]?.available || 0;

    let maxTrade = startCurrency === 'NGN' ? CONFIG.maxTradeNGN : CONFIG.maxTradeUSDT;
    let minReserve = startCurrency === 'NGN' ? CONFIG.minBalanceReserveNGN : CONFIG.minBalanceReserveUSDT;

    const requiredBalance = maxTrade + minReserve;
    if (availableBalance < requiredBalance) {
      throw new Error('Insufficient balance: Have ' + availableBalance.toFixed(2) + ' ' + startCurrency +
                      ', need ' + requiredBalance.toFixed(2) + ' (trade: ' + maxTrade + ' + reserve: ' + minReserve + ')');
    }

    let startAmount = Math.min(maxTrade * 0.95, availableBalance - minReserve);
    tradeLog.startBalance = startAmount;

    console.log('Trading with: ' + startAmount.toFixed(2) + ' ' + startCurrency + ' (95% of max for slippage buffer)');
    console.log('Reserved: ' + minReserve.toFixed(2) + ' ' + startCurrency);

    let currentAmount = startAmount;
    let currentCurrency = startCurrency;

    // ============ TRADE 1 ============
    console.log('\n--- TRADE 1: ' + pair1 + ' ---');
    const p1 = parseLunoPair(pair1);
    if (!p1) throw new Error('Invalid pair: ' + pair1);

    const fee1 = getFeeForPair(pair1);

    let trade1Type, trade1Volume, expectedAmount1;
    if (currentCurrency === p1.quote) {
      trade1Type = 'BID';
      trade1Volume = currentAmount;
      expectedAmount1 = (currentAmount / prices[pair1].ask) * (1 - fee1);
      currentCurrency = p1.base;
      console.log('   Buying ~' + expectedAmount1.toFixed(8) + ' ' + p1.base + ' with ' + trade1Volume.toFixed(2) + ' ' + p1.quote);
    } else {
      trade1Type = 'ASK';
      trade1Volume = currentAmount;
      expectedAmount1 = (currentAmount * prices[pair1].bid) * (1 - fee1);
      currentCurrency = p1.quote;
      console.log('   Selling ' + trade1Volume.toFixed(8) + ' ' + p1.base + ' for ~' + expectedAmount1.toFixed(2) + ' ' + p1.quote);
    }

    console.log('   📊 Expected after fees: ' + expectedAmount1.toFixed(8) + ' ' + currentCurrency);

    const order1 = await placeOrder(pair1, trade1Type, trade1Volume);
    tradeLog.trades.push({ pair: pair1, type: trade1Type, volume: trade1Volume, fee: fee1, orderId: order1.order_id });

    const result1 = await waitForBalance(currentCurrency, expectedAmount1, startingBalances[currentCurrency], 'Trade 1', false);
    const actualBalance1 = result1.actualBalance;
    const proceedsFromTrade1 = result1.proceeds;

    console.log('   📊 Starting ' + currentCurrency + ' balance: ' + startingBalances[currentCurrency].toFixed(8));
    console.log('   📊 Current ' + currentCurrency + ' balance: ' + actualBalance1.toFixed(8));
    console.log('   💰 Proceeds from trade: ' + proceedsFromTrade1.toFixed(8) + ' ' + currentCurrency);
    console.log('   📉 Expected: ' + expectedAmount1.toFixed(8) + ' ' + currentCurrency);

    const expectedWithBuffer1 = expectedAmount1 * 0.98;
    currentAmount = Math.min(expectedWithBuffer1, proceedsFromTrade1);

    console.log('   ✅ Using for next trade: ' + currentAmount.toFixed(8) + ' ' + currentCurrency);

    const slippage1 = ((expectedAmount1 - proceedsFromTrade1) / expectedAmount1) * 100;
    console.log('   📊 Slippage: ' + slippage1.toFixed(2) + '%');
    if (slippage1 > 5) {
      console.log('   ⚠️  WARNING: High slippage detected!');
    }

    // ============ TRADE 2 ============
    console.log('\n--- TRADE 2: ' + pair2 + ' ---');
    const p2 = parseLunoPair(pair2);
    if (!p2) throw new Error('Invalid pair: ' + pair2);

    const fee2 = getFeeForPair(pair2);
    const trade2Amount = currentAmount * 0.99;

    let trade2Type, trade2Volume, expectedAmount2;
    if (currentCurrency === p2.quote) {
      trade2Type = 'BID';
      trade2Volume = trade2Amount;
      expectedAmount2 = (trade2Amount / prices[pair2].ask) * (1 - fee2);
      currentCurrency = p2.base;
      console.log('   Buying ~' + expectedAmount2.toFixed(8) + ' ' + p2.base + ' with ' + trade2Volume.toFixed(2) + ' ' + p2.quote);
    } else {
      trade2Type = 'ASK';
      trade2Volume = trade2Amount;
      expectedAmount2 = (trade2Amount * prices[pair2].bid) * (1 - fee2);
      currentCurrency = p2.quote;
      console.log('   Selling ' + trade2Volume.toFixed(8) + ' ' + p2.base + ' for ~' + expectedAmount2.toFixed(2) + ' ' + p2.quote);
    }

    console.log('   📊 Expected after fees: ' + expectedAmount2.toFixed(8) + ' ' + currentCurrency);
    console.log('   💡 Using 99% of available (' + currentAmount.toFixed(8) + ') = ' + trade2Amount.toFixed(8));

    const order2 = await placeOrder(pair2, trade2Type, trade2Volume);
    tradeLog.trades.push({ pair: pair2, type: trade2Type, volume: trade2Volume, fee: fee2, orderId: order2.order_id });

    const result2 = await waitForBalance(currentCurrency, expectedAmount2, startingBalances[currentCurrency], 'Trade 2', false);
    const actualBalance2 = result2.actualBalance;
    const proceedsFromTrade2 = result2.proceeds;

    console.log('   📊 Starting ' + currentCurrency + ' balance: ' + startingBalances[currentCurrency].toFixed(8));
    console.log('   📊 Current ' + currentCurrency + ' balance: ' + actualBalance2.toFixed(8));
    console.log('   💰 Proceeds from trade: ' + proceedsFromTrade2.toFixed(8) + ' ' + currentCurrency);
    console.log('   📉 Expected: ' + expectedAmount2.toFixed(8) + ' ' + currentCurrency);

    const expectedWithBuffer2 = expectedAmount2 * 0.98;
    currentAmount = Math.min(expectedWithBuffer2, proceedsFromTrade2);

    console.log('   ✅ Using for next trade: ' + currentAmount.toFixed(8) + ' ' + currentCurrency);

    const slippage2 = ((expectedAmount2 - proceedsFromTrade2) / expectedAmount2) * 100;
    console.log('   📊 Slippage: ' + slippage2.toFixed(2) + '%');
    if (slippage2 > 5) {
      console.log('   ⚠️  WARNING: High slippage detected!');
    }

    // ============ TRADE 3 ============
    console.log('\n--- TRADE 3: ' + pair3 + ' ---');
    const p3 = parseLunoPair(pair3);
    if (!p3) throw new Error('Invalid pair: ' + pair3);

    const fee3 = getFeeForPair(pair3);
    const trade3Amount = currentAmount * 0.99;

    let trade3Type, trade3Volume, expectedAmount3;
    if (currentCurrency === p3.quote) {
      trade3Type = 'BID';
      trade3Volume = trade3Amount;
      expectedAmount3 = (trade3Amount / prices[pair3].ask) * (1 - fee3);
      currentCurrency = p3.base;
      console.log('   Buying ~' + expectedAmount3.toFixed(8) + ' ' + p3.base + ' with ' + trade3Volume.toFixed(2) + ' ' + p3.quote);
    } else {
      trade3Type = 'ASK';
      trade3Volume = trade3Amount;
      expectedAmount3 = (trade3Amount * prices[pair3].bid) * (1 - fee3);
      currentCurrency = p3.quote;
      console.log('   Selling ' + trade3Volume.toFixed(8) + ' ' + p3.base + ' for ~' + expectedAmount3.toFixed(2) + ' ' + p3.quote);
    }

    console.log('   📊 Expected after fees: ' + expectedAmount3.toFixed(8) + ' ' + currentCurrency);
    console.log('   💡 Using 99% of available (' + currentAmount.toFixed(8) + ') = ' + trade3Amount.toFixed(8));

    const order3 = await placeOrder(pair3, trade3Type, trade3Volume);
    tradeLog.trades.push({ pair: pair3, type: trade3Type, volume: trade3Volume, fee: fee3, orderId: order3.order_id });

    const result3 = await waitForBalance(startCurrency, expectedAmount3, startingBalances[startCurrency], 'Trade 3', true);

    const balanceAfter = await getBalance();
    const endAmount = balanceAfter[startCurrency]?.available || 0;
    const profit = endAmount - availableBalance;
    const profitPercent = (profit / startAmount) * 100;

    console.log('\n📊 FINAL SETTLEMENT:');
    console.log('   Started with: ' + availableBalance.toFixed(2) + ' ' + startCurrency);
    console.log('   Ended with: ' + endAmount.toFixed(2) + ' ' + startCurrency);
    console.log('   Profit: ' + profit.toFixed(2) + ' ' + startCurrency + ' (' + profitPercent.toFixed(2) + '%)');

    const totalSlippage = slippage1 + slippage2;
    console.log('   Total slippage: ' + totalSlippage.toFixed(2) + '%');

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

    const currencySymbol = startCurrency === 'NGN' ? '₦' : '$';
    const message = '✅ <b>LIVE TRADE SUCCESSFUL!</b> [LUNO]\n\n' +
                   '<b>Path:</b> ' + opportunity.path + '\n' +
                   '<b>Expected:</b> ' + opportunity.netProfit + '%\n' +
                   '<b>Actual:</b> ' + profitPercent.toFixed(2) + '%\n' +
                   '<b>Profit:</b> ' + currencySymbol + profit.toFixed(2) + '\n' +
                   '<b>Slippage:</b> ' + totalSlippage.toFixed(2) + '%\n' +
                   '<b>Time:</b> ' + tradeLog.timestampET + ' ET\n\n' +
                   '🟢 <i>AUTO-TRADING ENABLED</i>';

    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');

  } catch (error) {
    console.error('\n❌ TRADE FAILED:', error.message);
    tradeLog.error = error.message;
    tradeLog.success = false;
    stats.tradesFailed++;

    const message = '❌ <b>LIVE TRADE FAILED</b> [LUNO]\n\n' +
                   '<b>Path:</b> ' + opportunity.path + '\n' +
                   '<b>Error:</b> ' + error.message + '\n' +
                   '<b>Time:</b> ' + tradeLog.timestampET + ' ET\n\n' +
                   '🟢 <i>AUTO-TRADING ENABLED</i>';

    sendTelegramAlert(message);
    fs.appendFileSync(CONFIG.tradeLogFile, JSON.stringify(tradeLog, null, 2) + '\n');
  } finally {
    stats.tradesExecuted++;
    isTrading = false;
    console.log('  🔓 Trade lock released');
  }
}

function generateArbitragePaths(prices) {
  const paths = [];
  const pairList = Object.keys(prices);

  const pairMap = {};
  pairList.forEach(p => {
    const parsed = parseLunoPair(p);
    if (parsed) {
      pairMap[parsed.base + '-' + parsed.quote] = p;
      pairMap[parsed.quote + '-' + parsed.base] = p;
    }
  });

  const baseCurrencies = ['USDT', 'NGN'];

  baseCurrencies.forEach(startCurrency => {
    const startPairs = pairList.filter(p => {
      const parsed = parseLunoPair(p);
      return parsed && (parsed.base === startCurrency || parsed.quote === startCurrency);
    });

    startPairs.forEach(pair1 => {
      const p1 = parseLunoPair(pair1);
      if (!p1) return;

      const cryptoA = p1.base === startCurrency ? p1.quote : p1.base;
      if (cryptoA === startCurrency) return;

      pairList.forEach(pair2 => {
        const p2 = parseLunoPair(pair2);
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

      const fee1 = getFeeForPair(pair1);
      const fee2 = getFeeForPair(pair2);
      const fee3 = getFeeForPair(pair3);

      let startAmount = path.startCurrency === 'NGN' ? 100000 : 1000;

      let amount = startAmount;
      let holding = path.startCurrency;

      const p1 = parseLunoPair(pair1);
      if (!p1) return;
      if (!prices[pair1].ask || !prices[pair1].bid || prices[pair1].ask <= 0 || prices[pair1].bid <= 0) return;

      if (holding === p1.quote) {
        amount = (amount / prices[pair1].ask) * (1 - fee1);
        holding = p1.base;
      } else if (holding === p1.base) {
        amount = (amount * prices[pair1].bid) * (1 - fee1);
        holding = p1.quote;
      } else {
        return;
      }

      const p2 = parseLunoPair(pair2);
      if (!p2) return;
      if (!prices[pair2].ask || !prices[pair2].bid || prices[pair2].ask <= 0 || prices[pair2].bid <= 0) return;

      if (holding === p2.quote) {
        amount = (amount / prices[pair2].ask) * (1 - fee2);
        holding = p2.base;
      } else if (holding === p2.base) {
        amount = (amount * prices[pair2].bid) * (1 - fee2);
        holding = p2.quote;
      } else {
        return;
      }

      const p3 = parseLunoPair(pair3);
      if (!p3) return;
      if (!prices[pair3].ask || !prices[pair3].bid || prices[pair3].ask <= 0 || prices[pair3].bid <= 0) return;

      if (holding === p3.quote) {
        amount = (amount / prices[pair3].ask) * (1 - fee3);
        holding = p3.base;
      } else if (holding === p3.base) {
        amount = (amount * prices[pair3].bid) * (1 - fee3);
        holding = p3.quote;
      } else {
        return;
      }

      if (holding !== path.startCurrency) return;

      const finalAmount = amount;
      if (!isFinite(finalAmount) || finalAmount <= 0 || isNaN(finalAmount)) return;

      const avgFee = (fee1 + fee2 + fee3) / 3;
      const grossProfit = ((finalAmount / Math.pow(1 - avgFee, 3) - startAmount) / startAmount) * 100;
      const netProfit = ((finalAmount - startAmount) / startAmount) * 100;

      if (!isFinite(grossProfit) || !isFinite(netProfit) || isNaN(grossProfit) || isNaN(netProfit)) return;

      if (netProfit > CONFIG.minProfitThreshold) {
        opportunities.push({
          path: path.name,
          grossProfit: grossProfit.toFixed(4),
          netProfit: netProfit.toFixed(4),
          avgSpread: avgSpread.toFixed(3),
          avgFee: (avgFee * 100).toFixed(3) + '%',
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

async function logOpportunity(opp, prices) {
  const netProfitNum = parseFloat(opp.netProfit);
  const alert = netProfitNum >= 3.0 ? 'HIGH PROFIT!' : 'Opportunity';

  let message = '\n' + alert + ' [LUNO] ' + opp.path + '\n';
  message += '  Gross: ' + opp.grossProfit + '% (before fees)\n';
  message += '  Net: ' + opp.netProfit + '% (after fees)\n';
  message += '  Avg Fee: ' + opp.avgFee + '\n';
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
      liquidityCheck = await checkPathLiquidity(opp.pairs);

      if (!liquidityCheck.passed) {
        message = '  ⚠️  SKIPPED - Failed liquidity check\n';
        message += '======================================================================\n';
        console.log(message);
        if (CONFIG.logToFile) fs.appendFileSync(CONFIG.logFile, message);
        return;
      }
    }

    if (CONFIG.autoTrade && canTrade(opp.startCurrency)) {
      if (isTrading) {
        console.log('  ⚠️  Trade already in progress - Skipping');
        return;
      }

      isTrading = true;
      console.log('  🔒 Trade lock acquired');

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

      let telegramMsg = '📝 <b>PAPER TRADE OPPORTUNITY</b> [LUNO]\n\n' +
                       '<b>Path:</b> ' + opp.path + '\n' +
                       '<b>Pairs:</b> ' + opp.pairs.join(' → ') + '\n\n' +
                       '<b>Gross Profit:</b> ' + opp.grossProfit + '%\n' +
                       '<b>Net Profit:</b> ' + opp.netProfit + '%\n' +
                       '<b>Est. After Slippage:</b> ' + paperLog.estimatedNetProfit.toFixed(2) + '%\n\n' +
                       '<b>Avg Spread:</b> ' + opp.avgSpread + '%\n' +
                       '<b>Spreads:</b> ' + opp.spread1 + '%, ' + opp.spread2 + '%, ' + opp.spread3 + '%\n\n';

      if (CONFIG.enableLiquidityCheck && liquidityCheck.passed) {
        telegramMsg += '<b>Liquidity Check:</b> ✅ PASSED\n';
        liquidityCheck.details.forEach((liq, i) => {
          telegramMsg += '  ' + opp.pairs[i] + ': Ask=' + liq.askDepth.toFixed(2) + ', Bid=' + liq.bidDepth.toFixed(2) + '\n';
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
    sendTelegramAlert('🛑 LUNO TRADING STOPPED - NGN daily loss limit: ₦' + stats.dailyProfitNGN.toFixed(2));
    return false;
  }

  if (currency === 'USDT' && stats.dailyProfitUSDT <= -CONFIG.maxDailyLossUSDT) {
    console.log('⚠️ USDT daily loss limit reached');
    sendTelegramAlert('🛑 LUNO TRADING STOPPED - USDT daily loss limit: $' + stats.dailyProfitUSDT.toFixed(2));
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
  console.log('STATISTICS [LUNO NIGERIA]');
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

    const prices = await fetchLunoPrices();

    if (PATHS.length === 0) {
      PATHS = generateArbitragePaths(prices);
      console.log('\n🇳🇬 Found ' + PATHS.length + ' Nigeria-only paths (USDT/NGN)!\n');

      const ngnPaths = PATHS.filter(p => p.startCurrency === 'NGN').length;
      const usdtPaths = PATHS.filter(p => p.startCurrency === 'USDT').length;
      console.log('NGN paths: ' + ngnPaths);
      console.log('USDT paths: ' + usdtPaths);
      console.log('Fees: USDT pairs 0.1% taker, NGN pairs 0.6% taker\n');
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
console.log('LUNO AUTO-TRADING BOT - NIGERIA 🇳🇬');
console.log('======================================================================');
console.log('Mode: ' + (CONFIG.autoTrade ? '🟢 LIVE TRADING ENABLED' : '📝 PAPER TRADING MODE'));
console.log('Liquidity Check: ' + (CONFIG.enableLiquidityCheck ? '✅ ENABLED' : '❌ DISABLED'));
console.log('Strategy: Triangular arbitrage (USDT/NGN only)');
console.log('Fees: USDT 0.1% taker / NGN 0.6% taker');
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

loadWorkingDecimals();
loadMinimumSizes();

if (!CONFIG.autoTrade) {
  console.log('📝 PAPER TRADING MODE - Simulating trades without execution');
  console.log('Telegram alerts will show estimated profits');
  console.log('Liquidity checks: ' + (CONFIG.enableLiquidityCheck ? 'ENABLED ✅' : 'DISABLED ❌'));
  console.log('Set autoTrade: true to enable LIVE trading\n');

  const startMsg = '📝 <b>Luno Bot Started - PAPER TRADING MODE</b>\n\n' +
                  '<b>Pairs:</b> USDT/NGN only\n' +
                  '<b>Min profit:</b> ' + CONFIG.minProfitThreshold + '%\n' +
                  '<b>Paper trade alert:</b> ' + CONFIG.paperTradeThreshold + '%\n' +
                  '<b>Max spread:</b> ' + CONFIG.maxSpread + '%\n' +
                  '<b>Liquidity check:</b> ' + (CONFIG.enableLiquidityCheck ? '✅ Enabled' : '❌ Disabled') + '\n' +
                  '<b>Fees:</b> USDT 0.1% / NGN 0.6%\n\n' +
                  '🔴 <i>AUTO-TRADING DISABLED</i>';
  sendTelegramAlert(startMsg);

  scan();
  scanInterval = setInterval(scan, CONFIG.scanInterval);
} else {
  console.log('⚠️  WARNING: LIVE TRADING IS ENABLED!');
  console.log('⚠️  The bot will execute REAL trades on LUNO!');
  console.log('⚠️  Trade size: ₦' + CONFIG.maxTradeNGN + ' / $' + CONFIG.maxTradeUSDT);
  console.log('⚠️  Liquidity checks: ' + (CONFIG.enableLiquidityCheck ? 'ENABLED ✅' : 'DISABLED ❌'));
  console.log('⚠️  Press Ctrl+C within 10 seconds to cancel...\n');

  setTimeout(() => {
    console.log('🤖 Live trading started on Luno Nigeria!\n');

    const startMsg = '🟢 <b>Luno Bot Started - LIVE TRADING ENABLED</b>\n\n' +
                    '<b>Pairs:</b> USDT/NGN only\n' +
                    '<b>Min profit:</b> ' + CONFIG.minProfitThreshold + '%\n' +
                    '<b>Max spread:</b> ' + CONFIG.maxSpread + '%\n' +
                    '<b>Trade size:</b> ₦' + CONFIG.maxTradeNGN + ' / $' + CONFIG.maxTradeUSDT + '\n' +
                    '<b>Daily limit:</b> ' + CONFIG.maxDailyTrades + ' trades\n' +
                    '<b>Liquidity check:</b> ' + (CONFIG.enableLiquidityCheck ? '✅ Enabled' : '❌ Disabled') + '\n' +
                    '<b>Fees:</b> USDT 0.1% / NGN 0.6%\n\n' +
                    '🟢 <b>REAL TRADES WILL BE EXECUTED!</b>';
    sendTelegramAlert(startMsg);

    scan();
    scanInterval = setInterval(scan, CONFIG.scanInterval);
  }, 10000);
}

process.on('SIGINT', () => {
  const mode = CONFIG.autoTrade ? 'LIVE TRADING' : 'PAPER TRADING';
  const finalMsg = '🛑 <b>Luno Bot Stopped (' + mode + ')</b>\n\n' +
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
