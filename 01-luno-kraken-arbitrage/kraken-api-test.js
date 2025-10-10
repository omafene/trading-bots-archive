// Kraken API Connection Test
// Run: node kraken-api-test.js

const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

// Kraken API signature
function getKrakenSignature(path, request, secret) {
  const message = querystring.stringify(request);
  const secret_buffer = Buffer.from(secret, 'base64');
  const hash = crypto.createHash('sha256');
  const hmac = crypto.createHmac('sha512', secret_buffer);
  const hash_digest = hash.update(request.nonce + message).digest('binary');
  const hmac_digest = hmac.update(path + hash_digest, 'binary').digest('base64');
  return hmac_digest;
}

// Kraken API call
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

async function testAPI() {
  console.log('\n======================================================================');
  console.log('KRAKEN API CONNECTION TEST');
  console.log('======================================================================\n');

  try {
    // Test 1: Get Balance
    console.log('TEST 1: Getting account balance...');
    const balance = await krakenAPI('Balance');
    console.log('✅ Success! Your balance:');
    
    // Filter out zero balances and format nicely
    const nonZeroBalances = {};
    for (let [currency, amount] of Object.entries(balance)) {
      if (parseFloat(amount) > 0) {
        nonZeroBalances[currency] = parseFloat(amount).toFixed(8);
      }
    }
    
    if (Object.keys(nonZeroBalances).length === 0) {
      console.log('   (No balances found - account might be empty)');
    } else {
      console.log(JSON.stringify(nonZeroBalances, null, 2));
    }
    
    console.log('\n');

    // Test 2: Get Trade Balance (USD equivalent)
    console.log('TEST 2: Getting trade balance (USD equivalent)...');
    const tradeBalance = await krakenAPI('TradeBalance', { asset: 'ZUSD' });
    console.log('✅ Success! Trade balance:');
    console.log('   Equivalent Balance (USD): $' + parseFloat(tradeBalance.eb).toFixed(2));
    console.log('   Total Balance (USD): $' + parseFloat(tradeBalance.tb).toFixed(2));
    console.log('   Margin Amount: $' + parseFloat(tradeBalance.m || 0).toFixed(2));
    console.log('\n');

    // Test 3: Get Open Orders
    console.log('TEST 3: Getting open orders...');
    const openOrders = await krakenAPI('OpenOrders');
    const orderCount = Object.keys(openOrders.open || {}).length;
    console.log('✅ Success! Open orders: ' + orderCount);
    if (orderCount > 0) {
      console.log(JSON.stringify(openOrders, null, 2));
    }
    console.log('\n');

    // Summary
    console.log('======================================================================');
    console.log('✅ ALL TESTS PASSED!');
    console.log('======================================================================');
    console.log('Your API keys are working correctly.');
    console.log('You can now proceed with trading setup.\n');
    console.log('⚠️  IMPORTANT: Before enabling auto-trading:');
    console.log('   1. Make sure you have funds in your account');
    console.log('   2. Start with very small amounts ($100-500)');
    console.log('   3. Test manually first before enabling auto-trade');
    console.log('======================================================================\n');

  } catch (error) {
    console.log('\n======================================================================');
    console.log('❌ TEST FAILED!');
    console.log('======================================================================');
    console.log('Error:', error.message);
    console.log('\n');
    
    if (error.message.includes('Invalid key')) {
      console.log('⚠️  Your API key is invalid or incorrect.');
      console.log('   → Check that you copied the key correctly');
      console.log('   → Make sure the key is not expired');
    } else if (error.message.includes('Invalid signature')) {
      console.log('⚠️  Your API secret is invalid or incorrect.');
      console.log('   → Check that you copied the secret correctly');
      console.log('   → Secrets are case-sensitive!');
    } else if (error.message.includes('Permission denied')) {
      console.log('⚠️  Your API key does not have required permissions.');
      console.log('   → Go to Kraken Settings → API');
      console.log('   → Make sure these permissions are enabled:');
      console.log('      ✓ Query Funds');
      console.log('      ✓ Query Open Orders & Trades');
      console.log('      ✓ Query Closed Orders & Trades');
      console.log('      ✓ Create & Modify Orders (for trading)');
    }
    
    console.log('======================================================================\n');
  }
}

// Run the test
testAPI();
