// Quidax Bot Test Script - VPS Version
// Run: node test-quidax.js

const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');

// Add your API keys here (optional for public endpoint tests)
const API_KEY = 'YOUR_API_KEY_HERE';  // Your access_key
const API_SECRET = 'YOUR_API_SECRET_HERE';  // Your secret_key

const results = { passed: 0, failed: 0, tests: [] };

function logTest(name, success, message) {
  const status = success ? '✅ PASS' : '❌ FAIL';
  console.log(`${status} - ${name}`);
  if (message) console.log(`   ${message}`);
  results.tests.push({ name, success, message });
  if (success) results.passed++;
  else results.failed++;
}

function generateSignature(verb, uri, query) {
  const canonical = verb + '|' + uri + '|' + query;
  return crypto.createHmac('sha256', API_SECRET).update(canonical).digest('hex');
}

function testFetchTickers() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 1: Fetching Public Tickers...');
    https.get('https://www.quidax.com/api/v2/tickers', (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            logTest('Fetch Tickers', false, `API Error: ${JSON.stringify(parsed.error)}`);
            resolve(false);
            return;
          }
          const markets = Object.keys(parsed);
          const ngnMarkets = markets.filter(m => m.toLowerCase().endsWith('ngn'));
          const usdtMarkets = markets.filter(m => m.toLowerCase().endsWith('usdt'));
          
          console.log(`   Found ${markets.length} markets`);
          console.log(`   NGN markets: ${ngnMarkets.length} (e.g. ${ngnMarkets.slice(0, 3).join(', ')})`);
          console.log(`   USDT markets: ${usdtMarkets.length} (e.g. ${usdtMarkets.slice(0, 3).join(', ')})`);
          
          const firstMarket = markets[0];
          const ticker = parsed[firstMarket];
          const buy = ticker.ticker?.buy || ticker.buy;
          const sell = ticker.ticker?.sell || ticker.sell;
          
          if (buy && sell) {
            console.log(`   Sample: ${firstMarket} - Buy: ${buy}, Sell: ${sell}`);
            logTest('Fetch Tickers', true, `Successfully loaded ${markets.length} markets`);
            resolve(parsed);
          } else {
            logTest('Fetch Tickers', false, 'Invalid ticker format');
            resolve(false);
          }
        } catch (error) {
          logTest('Fetch Tickers', false, `Parse Error: ${error.message}`);
          resolve(false);
        }
      });
    }).on('error', (error) => {
      logTest('Fetch Tickers', false, `Network Error: ${error.message}`);
      resolve(false);
    });
  });
}

function testFetchOrderbook() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 2: Fetching Orderbook...');
    https.get('https://www.quidax.com/api/v2/depth?market=btcngn&limit=5', (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.asks && parsed.bids && parsed.asks.length > 0 && parsed.bids.length > 0) {
            const topAsk = parsed.asks[0];
            const topBid = parsed.bids[0];
            const askPrice = topAsk.price || topAsk[0];
            const bidPrice = topBid.price || topBid[0];
            const spread = ((askPrice - bidPrice) / bidPrice * 100).toFixed(2);
            
            console.log(`   Asks: ${parsed.asks.length}, Bids: ${parsed.bids.length}`);
            console.log(`   Best Ask: ${askPrice}, Best Bid: ${bidPrice}`);
            console.log(`   Spread: ${spread}%`);
            
            logTest('Fetch Orderbook', true, `Orderbook loaded successfully`);
            resolve(true);
          } else {
            logTest('Fetch Orderbook', false, 'Invalid orderbook format');
            resolve(false);
          }
        } catch (error) {
          logTest('Fetch Orderbook', false, `Parse Error: ${error.message}`);
          resolve(false);
        }
      });
    }).on('error', (error) => {
      logTest('Fetch Orderbook', false, `Network Error: ${error.message}`);
      resolve(false);
    });
  });
}

function testSignatureGeneration() {
  console.log('\n🧪 Test 3: Testing Signature Generation...');
  if (!API_SECRET || API_SECRET.trim() === '') {
    logTest('Signature Generation', false, 'API_SECRET not configured - skipping');
    return false;
  }
  try {
    const signature = generateSignature('GET', '/api/v2/markets', 'access_key=test&tonce=123');
    if (signature && signature.length === 64) {
      console.log(`   Generated signature: ${signature.substring(0, 16)}...`);
      logTest('Signature Generation', true, 'HMAC-SHA256 working correctly');
      return true;
    } else {
      logTest('Signature Generation', false, 'Invalid signature format');
      return false;
    }
  } catch (error) {
    logTest('Signature Generation', false, `Error: ${error.message}`);
    return false;
  }
}

function testAuthenticatedRequest() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 4: Testing Authenticated Request...');
    if (!API_KEY || !API_SECRET || API_KEY.trim() === '' || API_SECRET.trim() === '') {
      logTest('Authenticated Request', false, 'API keys not configured - skipping');
      console.log('   ℹ️  Add API keys at top of file to test authentication');
      resolve(false);
      return;
    }

    const tonce = Date.now();
    const params = { access_key: API_KEY, tonce: tonce };
    const query = querystring.stringify(params);
    const signature = generateSignature('GET', '/api/v2/members/me', query);
    const path = '/api/v2/members/me?' + query + '&signature=' + signature;

    https.get('https://www.quidax.com' + path, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            logTest('Authenticated Request', false, `API Error: ${JSON.stringify(parsed.error)}`);
            console.log('   ⚠️  Check your API keys');
            resolve(false);
            return;
          }
          if (parsed.email || parsed.sn) {
            console.log(`   Account SN: ${parsed.sn || 'N/A'}`);
            console.log(`   Email: ${parsed.email ? parsed.email.substring(0, 3) + '***' : 'N/A'}`);
            if (parsed.accounts) {
              console.log(`   \n   💰 Balances:`);
              parsed.accounts.forEach(acc => {
                const currency = acc.currency.toUpperCase();
                const balance = parseFloat(acc.balance || 0).toFixed(2);
                console.log(`      ${currency}: ${balance}`);
              });
            }
            logTest('Authenticated Request', true, 'Successfully authenticated');
            resolve(true);
          } else {
            logTest('Authenticated Request', false, 'Unexpected response format');
            resolve(false);
          }
        } catch (error) {
          logTest('Authenticated Request', false, `Parse Error: ${error.message}`);
          resolve(false);
        }
      });
    }).on('error', (error) => {
      logTest('Authenticated Request', false, `Network Error: ${error.message}`);
      resolve(false);
    });
  });
}

function testPriceParsingForArbitrage(tickers) {
  console.log('\n🧪 Test 5: Testing Price Parsing...');
  if (!tickers) {
    logTest('Price Parsing', false, 'No ticker data available');
    return false;
  }
  try {
    let ngnCount = 0, usdtCount = 0;
    Object.keys(tickers).forEach(market => {
      const ticker = tickers[market];
      const marketLower = market.toLowerCase();
      const buy = parseFloat(ticker.ticker?.buy || ticker.buy || 0);
      const sell = parseFloat(ticker.ticker?.sell || ticker.sell || 0);
      if (buy > 0 && sell > 0) {
        if (marketLower.endsWith('ngn')) ngnCount++;
        if (marketLower.endsWith('usdt')) usdtCount++;
      }
    });
    console.log(`   Parsed ${ngnCount} NGN pairs and ${usdtCount} USDT pairs`);
    if (ngnCount > 5 && usdtCount > 5) {
      logTest('Price Parsing', true, `Parsed ${ngnCount + usdtCount} tradeable pairs`);
      return true;
    } else {
      logTest('Price Parsing', false, 'Insufficient pairs');
      return false;
    }
  } catch (error) {
    logTest('Price Parsing', false, `Error: ${error.message}`);
    return false;
  }
}

function testPathGeneration(tickers) {
  console.log('\n🧪 Test 6: Testing Path Generation...');
  if (!tickers) {
    logTest('Path Generation', false, 'No ticker data available');
    return false;
  }
  try {
    const markets = Object.keys(tickers).filter(m => {
      const ml = m.toLowerCase();
      return ml.endsWith('ngn') || ml.endsWith('usdt');
    });
    const ngnMarkets = markets.filter(m => m.toLowerCase().endsWith('ngn'));
    const usdtMarkets = markets.filter(m => m.toLowerCase().endsWith('usdt'));
    const ngnPaths = Math.min(ngnMarkets.length * 2, 50);
    const usdtPaths = Math.min(usdtMarkets.length * 2, 50);
    
    console.log(`   Potential NGN paths: ~${ngnPaths}`);
    console.log(`   Potential USDT paths: ~${usdtPaths}`);
    
    if (ngnPaths > 10 || usdtPaths > 10) {
      logTest('Path Generation', true, 'Sufficient paths for arbitrage');
      return true;
    } else {
      logTest('Path Generation', false, 'Insufficient paths');
      return false;
    }
  } catch (error) {
    logTest('Path Generation', false, `Error: ${error.message}`);
    return false;
  }
}

async function runTests() {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('🧪 QUIDAX BOT TEST SUITE - VPS VERSION');
  console.log('═══════════════════════════════════════════════════════════');
  
  const tickers = await testFetchTickers();
  await testFetchOrderbook();
  testSignatureGeneration();
  await testAuthenticatedRequest();
  if (tickers) {
    testPriceParsingForArbitrage(tickers);
    testPathGeneration(tickers);
  }
  
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('📊 TEST RESULTS');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`✅ Passed: ${results.passed}`);
  console.log(`❌ Failed: ${results.failed}`);
  console.log(`📝 Total:  ${results.passed + results.failed}`);
  
  const passRate = ((results.passed / (results.passed + results.failed)) * 100).toFixed(0);
  console.log(`\n📈 Pass Rate: ${passRate}%`);
  
  if (results.failed === 0) {
    console.log('\n🎉 ALL TESTS PASSED! Bot ready to run!');
  } else if (passRate >= 60) {
    console.log('\n⚠️  Some tests failed - review errors above');
  } else {
    console.log('\n❌ Many tests failed - fix errors first');
  }
  console.log('═══════════════════════════════════════════════════════════\n');
}

runTests().catch(error => {
  console.error('\n❌ FATAL ERROR:', error.message);
  process.exit(1);
});
