// Busha API Test Script - VPS Version
// Run: node test-busha.js

const https = require('https');

const results = { passed: 0, failed: 0, tests: [] };

function logTest(name, success, message) {
  const status = success ? '✅ PASS' : '❌ FAIL';
  console.log(`${status} - ${name}`);
  if (message) console.log(`   ${message}`);
  results.tests.push({ name, success, message });
  if (success) results.passed++;
  else results.failed++;
}

// Test 1: Fetch all trading products/pairs
function testFetchProducts() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 1: Fetching Trading Products...');
    console.log('   Endpoint: https://api.pro.busha.co/api/v1/products/\n');
    
    const options = {
      hostname: 'api.pro.busha.co',
      path: '/api/v1/products/',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      console.log(`   Status Code: ${res.statusCode}`);
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          // Check if HTML or JSON
          if (data.trim().startsWith('<')) {
            console.log('   ❌ ERROR: Received HTML instead of JSON');
            console.log('   First 200 chars:', data.substring(0, 200));
            logTest('Fetch Products', false, 'API returned HTML instead of JSON');
            resolve(null);
            return;
          }

          const parsed = JSON.parse(data);
          
          if (parsed.error || parsed.message) {
            logTest('Fetch Products', false, `API Error: ${JSON.stringify(parsed)}`);
            resolve(null);
            return;
          }

          if (Array.isArray(parsed)) {
            console.log(`   ✅ Found ${parsed.length} trading pairs`);
            
            // Show NGN pairs
            const ngnPairs = parsed.filter(p => p.id && p.id.includes('NGN'));
            const usdtPairs = parsed.filter(p => p.id && p.id.includes('USDT'));
            
            console.log(`   NGN pairs: ${ngnPairs.length}`);
            console.log(`   Examples: ${ngnPairs.slice(0, 5).map(p => p.id).join(', ')}`);
            
            console.log(`   USDT pairs: ${usdtPairs.length}`);
            console.log(`   Examples: ${usdtPairs.slice(0, 5).map(p => p.id).join(', ')}`);
            
            if (ngnPairs.length > 0) {
              const example = ngnPairs[0];
              console.log(`\n   Sample pair: ${example.id}`);
              console.log(`   Base: ${example.base_currency}, Quote: ${example.quote_currency}`);
              console.log(`   Min size: ${example.base_min_size}, Max size: ${example.base_max_size}`);
            }
            
            logTest('Fetch Products', true, `Successfully loaded ${parsed.length} trading pairs`);
            resolve(parsed);
          } else {
            logTest('Fetch Products', false, 'Unexpected response format');
            resolve(null);
          }
        } catch (error) {
          logTest('Fetch Products', false, `Parse Error: ${error.message}`);
          resolve(null);
        }
      });
    });

    req.on('error', (error) => {
      logTest('Fetch Products', false, `Network Error: ${error.message}`);
      resolve(null);
    });

    req.setTimeout(10000, () => {
      req.abort();
      logTest('Fetch Products', false, 'Request timeout');
      resolve(null);
    });

    req.end();
  });
}

// Test 2: Fetch ticker for BTC-NGN
function testFetchTicker() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 2: Fetching BTC-NGN Ticker...');
    console.log('   Endpoint: https://api.pro.busha.co/api/v1/products/BTC-NGN/ticker/\n');
    
    const options = {
      hostname: 'api.pro.busha.co',
      path: '/api/v1/products/BTC-NGN/ticker/',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      console.log(`   Status Code: ${res.statusCode}`);
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          if (data.trim().startsWith('<')) {
            logTest('Fetch Ticker', false, 'API returned HTML instead of JSON');
            resolve(null);
            return;
          }

          const parsed = JSON.parse(data);
          
          if (parsed.error || parsed.message) {
            logTest('Fetch Ticker', false, `API Error: ${JSON.stringify(parsed)}`);
            resolve(null);
            return;
          }

          if (parsed.price || parsed.bid || parsed.ask) {
            console.log(`   Trade ID: ${parsed.trade_id || 'N/A'}`);
            console.log(`   Price: ₦${parsed.price || 'N/A'}`);
            console.log(`   Bid: ₦${parsed.bid || 'N/A'}`);
            console.log(`   Ask: ₦${parsed.ask || 'N/A'}`);
            console.log(`   Volume (24h): ${parsed.volume || 'N/A'} BTC`);
            console.log(`   Time: ${parsed.time || 'N/A'}`);
            
            // Calculate spread
            if (parsed.bid && parsed.ask) {
              const spread = ((parsed.ask - parsed.bid) / parsed.bid * 100).toFixed(2);
              console.log(`   Spread: ${spread}%`);
            }
            
            logTest('Fetch Ticker', true, 'Successfully fetched ticker data');
            resolve(parsed);
          } else {
            logTest('Fetch Ticker', false, 'Invalid ticker format');
            resolve(null);
          }
        } catch (error) {
          logTest('Fetch Ticker', false, `Parse Error: ${error.message}`);
          resolve(null);
        }
      });
    });

    req.on('error', (error) => {
      logTest('Fetch Ticker', false, `Network Error: ${error.message}`);
      resolve(null);
    });

    req.setTimeout(10000, () => {
      req.abort();
      logTest('Fetch Ticker', false, 'Request timeout');
      resolve(null);
    });

    req.end();
  });
}

// Test 3: Fetch orderbook for BTC-NGN
function testFetchOrderbook() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 3: Fetching BTC-NGN Orderbook...');
    console.log('   Endpoint: https://api.pro.busha.co/api/v1/products/BTC-NGN/book/?level=2\n');
    
    const options = {
      hostname: 'api.pro.busha.co',
      path: '/api/v1/products/BTC-NGN/book/?level=2',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      console.log(`   Status Code: ${res.statusCode}`);
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          if (data.trim().startsWith('<')) {
            logTest('Fetch Orderbook', false, 'API returned HTML instead of JSON');
            resolve(null);
            return;
          }

          const parsed = JSON.parse(data);
          
          if (parsed.error || parsed.message) {
            logTest('Fetch Orderbook', false, `API Error: ${JSON.stringify(parsed)}`);
            resolve(null);
            return;
          }

          if (parsed.bids && parsed.asks) {
            const askCount = parsed.asks.length;
            const bidCount = parsed.bids.length;
            
            console.log(`   Sequence: ${parsed.sequence || 'N/A'}`);
            console.log(`   Bids: ${bidCount}, Asks: ${askCount}`);
            
            if (askCount > 0 && bidCount > 0) {
              const topAsk = parsed.asks[0];
              const topBid = parsed.bids[0];
              
              const askPrice = parseFloat(topAsk.price || topAsk[0]);
              const bidPrice = parseFloat(topBid.price || topBid[0]);
              const askSize = parseFloat(topAsk.size || topAsk[1]);
              const bidSize = parseFloat(topBid.size || topBid[1]);
              
              console.log(`\n   Best Bid: ₦${bidPrice.toLocaleString()} (${bidSize} BTC)`);
              console.log(`   Best Ask: ₦${askPrice.toLocaleString()} (${askSize} BTC)`);
              
              const spread = ((askPrice - bidPrice) / bidPrice * 100).toFixed(2);
              console.log(`   Spread: ${spread}%`);
              
              // Calculate liquidity
              const top5Bids = parsed.bids.slice(0, 5);
              const top5Asks = parsed.asks.slice(0, 5);
              
              const bidDepth = top5Bids.reduce((sum, b) => {
                const size = parseFloat(b.size || b[1]);
                return sum + size;
              }, 0);
              
              const askDepth = top5Asks.reduce((sum, a) => {
                const size = parseFloat(a.size || a[1]);
                return sum + size;
              }, 0);
              
              console.log(`\n   Top 5 Bid Depth: ${bidDepth.toFixed(4)} BTC`);
              console.log(`   Top 5 Ask Depth: ${askDepth.toFixed(4)} BTC`);
              
              logTest('Fetch Orderbook', true, `Orderbook loaded with ${bidCount} bids and ${askCount} asks`);
              resolve(parsed);
            } else {
              logTest('Fetch Orderbook', false, 'Empty orderbook');
              resolve(null);
            }
          } else {
            logTest('Fetch Orderbook', false, 'Invalid orderbook format');
            resolve(null);
          }
        } catch (error) {
          logTest('Fetch Orderbook', false, `Parse Error: ${error.message}`);
          resolve(null);
        }
      });
    });

    req.on('error', (error) => {
      logTest('Fetch Orderbook', false, `Network Error: ${error.message}`);
      resolve(null);
    });

    req.setTimeout(10000, () => {
      req.abort();
      logTest('Fetch Orderbook', false, 'Request timeout');
      resolve(null);
    });

    req.end();
  });
}

// Test 4: Test multiple pairs
function testMultiplePairs(products) {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 4: Testing Multiple Trading Pairs...');
    
    if (!products || !Array.isArray(products) || products.length === 0) {
      logTest('Multiple Pairs', false, 'No products available to test');
      resolve(false);
      return;
    }

    const ngnPairs = products.filter(p => p.id && p.id.includes('NGN')).slice(0, 3);
    
    if (ngnPairs.length === 0) {
      logTest('Multiple Pairs', false, 'No NGN pairs found');
      resolve(false);
      return;
    }

    let successCount = 0;
    let tested = 0;

    console.log(`   Testing ${ngnPairs.length} pairs: ${ngnPairs.map(p => p.id).join(', ')}\n`);

    ngnPairs.forEach((pair, index) => {
      setTimeout(() => {
        const options = {
          hostname: 'api.pro.busha.co',
          path: `/api/v1/products/${pair.id}/ticker/`,
          method: 'GET',
          headers: {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'application/json'
          }
        };

        https.request(options, (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              if (!data.trim().startsWith('<')) {
                const parsed = JSON.parse(data);
                if (parsed.price || parsed.bid || parsed.ask) {
                  console.log(`   ✅ ${pair.id}: Bid=₦${parsed.bid || 'N/A'}, Ask=₦${parsed.ask || 'N/A'}`);
                  successCount++;
                } else {
                  console.log(`   ❌ ${pair.id}: Invalid data`);
                }
              } else {
                console.log(`   ❌ ${pair.id}: Got HTML`);
              }
            } catch (e) {
              console.log(`   ❌ ${pair.id}: Parse error`);
            }
            
            tested++;
            if (tested === ngnPairs.length) {
              if (successCount === ngnPairs.length) {
                logTest('Multiple Pairs', true, `All ${successCount} pairs working`);
              } else if (successCount > 0) {
                logTest('Multiple Pairs', true, `${successCount}/${ngnPairs.length} pairs working`);
              } else {
                logTest('Multiple Pairs', false, 'No pairs working');
              }
              resolve(successCount > 0);
            }
          });
        }).on('error', () => {
          console.log(`   ❌ ${pair.id}: Network error`);
          tested++;
          if (tested === ngnPairs.length) {
            logTest('Multiple Pairs', successCount > 0, `${successCount}/${ngnPairs.length} pairs working`);
            resolve(successCount > 0);
          }
        }).end();
      }, index * 1000); // 1 second delay between requests
    });
  });
}

// Test 5: Check API response time
function testAPISpeed() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 5: Testing API Response Time...');
    
    const startTime = Date.now();
    
    const options = {
      hostname: 'api.pro.busha.co',
      path: '/api/v1/products/BTC-NGN/ticker/',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json'
      }
    };

    https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        console.log(`   Response time: ${responseTime}ms`);
        
        if (responseTime < 500) {
          console.log(`   ⚡ Excellent! (< 500ms)`);
          logTest('API Speed', true, `Fast response: ${responseTime}ms`);
        } else if (responseTime < 1500) {
          console.log(`   ✅ Good (< 1.5s)`);
          logTest('API Speed', true, `Acceptable response: ${responseTime}ms`);
        } else {
          console.log(`   ⚠️  Slow (> 1.5s)`);
          logTest('API Speed', false, `Slow response: ${responseTime}ms`);
        }
        
        resolve(true);
      });
    }).on('error', (error) => {
      logTest('API Speed', false, `Error: ${error.message}`);
      resolve(false);
    }).end();
  });
}

// Test 6: Check DNS resolution
function testDNS() {
  return new Promise((resolve) => {
    console.log('\n🧪 Test 6: Testing DNS Resolution...');
    
    const dns = require('dns');
    dns.resolve4('api.pro.busha.co', (err, addresses) => {
      if (err) {
        console.log(`   ❌ DNS Failed: ${err.message}`);
        logTest('DNS Resolution', false, err.message);
        resolve(false);
      } else {
        console.log(`   ✅ Resolved to: ${addresses.join(', ')}`);
        logTest('DNS Resolution', true, `Resolved to ${addresses.length} IP(s)`);
        resolve(true);
      }
    });
  });
}

// Main test runner
async function runTests() {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('🧪 BUSHA API TEST SUITE - VPS VERSION');
  console.log('═══════════════════════════════════════════════════════════');
  console.log('Testing: Busha Pro API (https://api.pro.busha.co)');
  console.log('═══════════════════════════════════════════════════════════\n');

  await testDNS();
  const products = await testFetchProducts();
  await testFetchTicker();
  await testFetchOrderbook();
  
  if (products) {
    await testMultiplePairs(products);
  }
  
  await testAPISpeed();

  // Print summary
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('📊 TEST RESULTS');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`✅ Passed: ${results.passed}`);
  console.log(`❌ Failed: ${results.failed}`);
  console.log(`📝 Total:  ${results.passed + results.failed}`);
  
  const passRate = ((results.passed / (results.passed + results.failed)) * 100).toFixed(0);
  console.log(`\n📈 Pass Rate: ${passRate}%`);
  
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('🎯 VERDICT');
  console.log('═══════════════════════════════════════════════════════════');
  
  if (results.failed === 0) {
    console.log('🎉 ALL TESTS PASSED!');
    console.log('\n✅ Busha API is fully accessible from your VPS!');
    console.log('✅ Ready to build arbitrage bot!');
    console.log('\nNext steps:');
    console.log('1. Get Busha API keys (if you want authenticated trading)');
    console.log('2. Create Busha arbitrage bot');
    console.log('3. Start paper trading!');
  } else if (passRate >= 60) {
    console.log('⚠️  MOSTLY WORKING');
    console.log(`\n${results.passed} tests passed, ${results.failed} failed`);
    console.log('The bot may work, but review failed tests above.');
  } else {
    console.log('❌ MANY TESTS FAILED');
    console.log('\nBusha API may not be accessible from your VPS.');
    console.log('Possible issues:');
    console.log('- VPS IP blocked');
    console.log('- Network connectivity issues');
    console.log('- API endpoint changed');
    console.log('\nTry running from a different location.');
  }
  
  console.log('═══════════════════════════════════════════════════════════\n');
}

// Run the tests
runTests().catch(error => {
  console.error('\n❌ FATAL ERROR:', error.message);
  process.exit(1);
});
