// Luno API Connection Test
// Run: node luno-api-test.js

const https = require('https');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

// Luno API call with Basic Auth
function lunoAPI(endpoint, method = 'GET') {
  return new Promise((resolve, reject) => {
    const auth = Buffer.from(CONFIG.apiKey + ':' + CONFIG.apiSecret).toString('base64');
    
    const options = {
      hostname: 'api.luno.com',
      path: '/api/1/' + endpoint,
      method: method,
      headers: {
        'Authorization': 'Basic ' + auth,
      }
    };

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
    req.end();
  });
}

async function testLunoAPI() {
  console.log('\n======================================================================');
  console.log('LUNO API CONNECTION TEST');
  console.log('======================================================================\n');

  try {
    // Test 1: Get Balance
    console.log('TEST 1: Getting account balance...');
    const balance = await lunoAPI('balance');
    console.log('✅ Success! Your balance:');
    
    if (balance.balance && balance.balance.length > 0) {
      balance.balance.forEach(b => {
        const available = parseFloat(b.available);
        const reserved = parseFloat(b.reserved);
        const total = parseFloat(b.balance);
        
        if (total > 0) {
          console.log('   ' + b.asset + ':');
          console.log('      Available: ' + available.toFixed(8));
          console.log('      Reserved: ' + reserved.toFixed(8));
          console.log('      Total: ' + total.toFixed(8));
        }
      });
    } else {
      console.log('   (No balances found - account might be empty)');
    }
    
    console.log('\n');

    // Test 2: Get Tickers (public endpoint, no auth needed)
    console.log('TEST 2: Getting market tickers...');
    const tickers = await lunoAPI('tickers');
    
    if (tickers.tickers) {
      console.log('✅ Success! Found ' + tickers.tickers.length + ' trading pairs');
      
      // Show USDT and NGN pairs
      const usdtPairs = tickers.tickers.filter(t => t.pair.includes('USDT'));
      const ngnPairs = tickers.tickers.filter(t => t.pair.includes('NGN'));
      
      console.log('   USDT pairs: ' + usdtPairs.length);
      console.log('   NGN pairs: ' + ngnPairs.length);
      
      // Show some example pairs
      console.log('\n   Example USDT pairs:');
      usdtPairs.slice(0, 5).forEach(t => {
        console.log('      ' + t.pair + ' - Last: $' + parseFloat(t.last_trade).toFixed(2));
      });
      
      console.log('\n   Example NGN pairs:');
      ngnPairs.slice(0, 5).forEach(t => {
        console.log('      ' + t.pair + ' - Last: ₦' + parseFloat(t.last_trade).toFixed(2));
      });
    }
    
    console.log('\n');

    // Test 3: Get Account Info
    console.log('TEST 3: Getting account information...');
    try {
      const orders = await lunoAPI('listorders');
      console.log('✅ Success! Account active.');
      console.log('   Open orders: ' + (orders.orders ? orders.orders.length : 0));
    } catch (error) {
      // This might fail if no trading permission, but that's okay
      console.log('⚠️  Could not get orders (might need trading permission enabled)');
    }
    
    console.log('\n');

    // Summary
    console.log('======================================================================');
    console.log('✅ ALL CRITICAL TESTS PASSED!');
    console.log('======================================================================');
    console.log('Your Luno API keys are working correctly.');
    console.log('You can now proceed with trading setup.\n');
    console.log('⚠️  IMPORTANT: Before enabling auto-trading:');
    console.log('   1. Fund your account with USDT or NGN');
    console.log('   2. Start with very small amounts (₦50k or $100)');
    console.log('   3. Run in monitoring mode first (autoTrade: false)');
    console.log('   4. Watch for opportunities for 1-2 days');
    console.log('   5. Only then enable auto-trade');
    console.log('======================================================================\n');

  } catch (error) {
    console.log('\n======================================================================');
    console.log('❌ TEST FAILED!');
    console.log('======================================================================');
    console.log('Error:', error.message);
    console.log('\n');
    
    if (error.message.includes('ErrNoAuth') || error.message.includes('Unauthorized')) {
      console.log('⚠️  Your API key or secret is invalid.');
      console.log('   → Check that you copied both key and secret correctly');
      console.log('   → Keys are case-sensitive!');
      console.log('   → Make sure the key is not expired');
    } else if (error.message.includes('Permission')) {
      console.log('⚠️  Your API key does not have required permissions.');
      console.log('   → Go to Luno Settings → API Keys');
      console.log('   → Make sure "Trading" permission is enabled');
      console.log('   → May need to create a new key with correct permissions');
    }
    
    console.log('======================================================================\n');
  }
}

// Run the test
testLunoAPI();
