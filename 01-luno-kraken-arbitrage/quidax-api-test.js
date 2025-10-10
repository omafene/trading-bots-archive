// Quidax API Connection Test - Correct API
// Run: node quidax-api-test.js

const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

// Quidax OpenAPI Authentication
function quidaxSignature(params) {
  // Sort parameters alphabetically
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  // Create signature string
  const signString = querystring.stringify(sortedParams) + '&secret_key=' + CONFIG.apiSecret;
  const signature = crypto.createHash('md5').update(signString).digest('hex').toUpperCase();
  
  return signature;
}

// Quidax API call
function quidaxAPI(endpoint, params = {}) {
  return new Promise((resolve, reject) => {
    // Add API key and timestamp
    params.api_key = CONFIG.apiKey;
    params.time = Date.now();
    
    // Generate signature
    params.sign = quidaxSignature(params);
    
    const queryString = querystring.stringify(params);
    const path = '/open/api' + endpoint + '?' + queryString;
    
    const options = {
      hostname: 'openapi.quidax.io',
      path: path,
      method: 'GET',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      }
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.code !== '0' && parsed.code !== 0) {
            reject(new Error('Quidax API: ' + (parsed.msg || parsed.message || 'Error code ' + parsed.code)));
          } else {
            resolve(parsed);
          }
        } catch (error) {
          reject(error);
        }
      });
    }).on('error', reject);
  });
}

// Public API call (no auth)
function quidaxPublicAPI(endpoint) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'openapi.quidax.io',
      path: '/open/api' + endpoint,
      method: 'GET',
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(parsed);
        } catch (error) {
          reject(error);
        }
      });
    }).on('error', reject);
  });
}

async function testQuidaxAPI() {
  console.log('\n======================================================================');
  console.log('QUIDAX API CONNECTION TEST (OpenAPI)');
  console.log('======================================================================\n');

  try {
    // Test 1: Get All Trading Pairs (public)
    console.log('TEST 1: Getting all trading pairs (no auth)...');
    const symbols = await quidaxPublicAPI('/common/symbols');
    
    if (symbols.data && symbols.data.length > 0) {
      console.log('✅ Success! Found ' + symbols.data.length + ' trading pairs');
      
      // Show USDT and NGN pairs
      const usdtPairs = symbols.data.filter(s => s.symbol.includes('usdt'));
      const ngnPairs = symbols.data.filter(s => s.symbol.includes('ngn'));
      
      console.log('   USDT pairs: ' + usdtPairs.length);
      console.log('   NGN pairs: ' + ngnPairs.length);
      
      console.log('\n   Example pairs:');
      symbols.data.slice(0, 5).forEach(s => {
        console.log('      ' + s.symbol + ' - Base: ' + s.base_coin + ', Quote: ' + s.count_coin);
      });
    } else {
      console.log('⚠️  No trading pair data returned');
    }
    
    console.log('\n');

    // Test 2: Get Market Prices (public)
    console.log('TEST 2: Getting current market prices...');
    const market = await quidaxPublicAPI('/market');
    
    if (market.data && market.data.length > 0) {
      console.log('✅ Success! Market data retrieved');
      
      console.log('\n   Sample prices with spreads:');
      market.data.slice(0, 5).forEach(m => {
        const ask = parseFloat(m.sell);
        const bid = parseFloat(m.buy);
        const spread = bid > 0 ? (((ask - bid) / bid) * 100).toFixed(2) : 'N/A';
        console.log('      ' + m.symbol + ' - Last: ' + parseFloat(m.close).toFixed(2) + 
                   ' (Spread: ' + spread + '%)');
      });
    }
    
    console.log('\n');

    // Test 3: Get Account Balance (requires auth)
    console.log('TEST 3: Getting your account balance (requires auth)...');
    try {
      const account = await quidaxAPI('/user/account');
      
      if (account.data && account.data.total_asset) {
        console.log('✅ Success! Your account balances:');
        
        const coinList = account.data.coin_list || [];
        let hasBalance = false;
        
        coinList.forEach(coin => {
          const normal = parseFloat(coin.normal || 0);
          const locked = parseFloat(coin.locked || 0);
          const total = normal + locked;
          
          if (total > 0) {
            hasBalance = true;
            console.log('   ' + coin.coin.toUpperCase() + ':');
            console.log('      Available: ' + normal.toFixed(8));
            console.log('      Locked: ' + locked.toFixed(8));
            console.log('      Total: ' + total.toFixed(8));
          }
        });
        
        if (!hasBalance) {
          console.log('   (No balances found - account is empty)');
          console.log('   Total asset value: ' + account.data.total_asset);
        }
      } else {
        console.log('   Account data structure:', JSON.stringify(account, null, 2));
      }
    } catch (error) {
      console.log('❌ Failed: ' + error.message);
      console.log('   This could mean:');
      console.log('   - API key is invalid');
      console.log('   - API secret is incorrect');
      console.log('   - IP address not whitelisted');
      console.log('   - Trading permission not enabled');
      throw error;
    }
    
    console.log('\n');

    // Test 4: Analyze Spreads for Arbitrage
    console.log('TEST 4: Analyzing spreads for triangular arbitrage...');
    
    if (market.data && market.data.length > 0) {
      let totalSpread = 0;
      let pairCount = 0;
      let wideSpreads = [];
      let goodSpreads = [];
      
      market.data.forEach(m => {
        const ask = parseFloat(m.sell);
        const bid = parseFloat(m.buy);
        
        if (bid > 0 && ask > 0) {
          const spread = ((ask - bid) / bid) * 100;
          
          if (spread > 0 && spread < 20) {
            totalSpread += spread;
            pairCount++;
            
            if (spread > 2) {
              wideSpreads.push({ pair: m.symbol, spread: spread.toFixed(2) });
            } else if (spread < 1) {
              goodSpreads.push({ pair: m.symbol, spread: spread.toFixed(2) });
            }
          }
        }
      });
      
      const avgSpread = totalSpread / pairCount;
      console.log('✅ Average spread: ' + avgSpread.toFixed(2) + '%');
      console.log('   Pairs analyzed: ' + pairCount);
      
      if (goodSpreads.length > 0) {
        console.log('\n   ✅ Good spreads (<1%) - Best for arbitrage:');
        goodSpreads.slice(0, 5).forEach(p => {
          console.log('      ' + p.pair + ': ' + p.spread + '%');
        });
      }
      
      if (wideSpreads.length > 0) {
        console.log('\n   ⚠️  Wide spreads (>2%) - Lower liquidity:');
        wideSpreads.slice(0, 5).forEach(p => {
          console.log('      ' + p.pair + ': ' + p.spread + '%');
        });
      }
      
      // Calculate profitability threshold
      const totalFees = 0.3; // 0.1% × 3 trades
      const estimatedSpreadLoss = avgSpread * 3;
      const minGrossProfit = totalFees + estimatedSpreadLoss;
      
      console.log('\n   💡 Profitability estimate:');
      console.log('      Fees (3 trades): ' + totalFees.toFixed(1) + '%');
      console.log('      Spread loss (est): ' + estimatedSpreadLoss.toFixed(1) + '%');
      console.log('      Min gross profit needed: ' + minGrossProfit.toFixed(1) + '%');
      
      if (minGrossProfit > 3) {
        console.log('\n   ⚠️  WARNING: Need >' + minGrossProfit.toFixed(1) + '% gross profit to be profitable');
        console.log('      This is HIGH - opportunities may be rare');
      } else {
        console.log('\n   ✅ Target >' + minGrossProfit.toFixed(1) + '% gross profit seems achievable');
      }
    }
    
    console.log('\n');

    // Summary
    console.log('======================================================================');
    console.log('✅ ALL TESTS PASSED!');
    console.log('======================================================================');
    console.log('Your Quidax API connection is working!');
    console.log('\n📊 KEY METRICS:');
    console.log('   - API Endpoint: openapi.quidax.io');
    console.log('   - Trading pairs: ' + (symbols.data?.length || 'N/A'));
    console.log('   - Average spread: ' + (market.data ? (totalSpread / pairCount).toFixed(2) + '%' : 'N/A'));
    console.log('   - Fees: 0.1% per trade (0.3% total)');
    console.log('   - Authentication: ✅ Working');
    
    console.log('\n⚠️  RECOMMENDATIONS:');
    console.log('   1. Fund account with $100-200 USDT or ₦50k-100k NGN');
    console.log('   2. Run bot in monitoring mode for 24-48 hours');
    console.log('   3. Check if opportunities exceed ' + minGrossProfit.toFixed(1) + '% gross profit');
    console.log('   4. Start with $50-100 trades to test execution');
    console.log('   5. Monitor actual profit vs expected');
    console.log('======================================================================\n');

  } catch (error) {
    console.log('\n======================================================================');
    console.log('❌ TEST FAILED!');
    console.log('======================================================================');
    console.log('Error:', error.message);
    console.log('\n');
    
    if (error.message.includes('Illegal')) {
      console.log('⚠️  IP address not whitelisted or API key invalid.');
      console.log('   → Add your VPS IP to Quidax API whitelist');
      console.log('   → Your VPS IP should be the one you found earlier');
      console.log('   → Double-check API key and secret are correct');
    } else if (error.message.includes('sign')) {
      console.log('⚠️  Signature verification failed.');
      console.log('   → Check that API secret is copied correctly');
      console.log('   → Secrets are case-sensitive!');
    } else if (error.message.includes('ENOTFOUND')) {
      console.log('⚠️  Cannot connect to Quidax.');
      console.log('   → Check internet connection');
      console.log('   → Quidax may be down');
    }
    
    console.log('======================================================================\n');
  }
}

// Run the test
testQuidaxAPI();
