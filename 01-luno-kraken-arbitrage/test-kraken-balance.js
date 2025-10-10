const https = require('https');
const crypto = require('crypto');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

function krakenAPI(endpoint, params = {}) {
  return new Promise((resolve, reject) => {
    const path = '/0/private/' + endpoint;
    const nonce = Date.now() * 1000;
    
    const postData = new URLSearchParams({
      nonce: nonce.toString(),
      ...params
    }).toString();

    const signature = crypto
      .createHmac('sha512', Buffer.from(CONFIG.apiSecret, 'base64'))
      .update(path + crypto.createHash('sha256').update(nonce + postData).digest())
      .digest('base64');

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
          resolve(JSON.parse(data));
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

async function testKrakenBalance() {
  try {
    console.log('\n========================================');
    console.log('TESTING KRAKEN BALANCE...');
    console.log('========================================\n');

    const result = await krakenAPI('Balance');
    
    console.log('RAW KRAKEN RESPONSE:');
    console.log(JSON.stringify(result, null, 2));
    console.log('\n========================================');
    
    if (result.error && result.error.length > 0) {
      console.log('❌ ERROR:', result.error);
      return;
    }
    
    if (result.result) {
      console.log('\n✅ PARSED BALANCES:');
      console.log('========================================');
      
      Object.keys(result.result).forEach(asset => {
        const balance = parseFloat(result.result[asset]);
        if (balance > 0) {
          // Kraken uses prefixes: ZUSD = USD, XXBT = BTC, etc.
          const cleanAsset = asset.replace(/^[ZX]/, ''); // Remove Z or X prefix
          console.log(cleanAsset + ': ' + balance.toFixed(8));
        }
      });
      console.log('========================================\n');
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

testKrakenBalance();
