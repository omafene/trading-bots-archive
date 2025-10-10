const https = require('https');
const crypto = require('crypto');

// YOUR ACTUAL KEYS HERE
const apiKey = 'YOUR_API_KEY_HERE';
const apiSecret = 'YOUR_API_SECRET_HERE';

function krakenAPI() {
  return new Promise((resolve, reject) => {
    const path = '/0/private/Balance';
    const nonce = Date.now() * 1000;
    const postData = 'nonce=' + nonce;

    const signature = crypto
      .createHmac('sha512', Buffer.from(apiSecret, 'base64'))
      .update(path + crypto.createHash('sha256').update(nonce + postData).digest())
      .digest('base64');

    const options = {
      hostname: 'api.kraken.com',  // ← KRAKEN.COM (not .us)
      path: path,
      method: 'POST',
      port: 443,
      headers: {
        'API-Key': apiKey,
        'API-Sign': signature,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': postData.length,
        'User-Agent': 'Kraken-Bot/1.0'
      }
    };

    console.log('Connecting to: api.kraken.com');
    console.log('API Key starts with:', apiKey.substring(0, 5) + '...');
    console.log('Sending request...\n');

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          console.log('✅ SUCCESS! Response:');
          console.log(JSON.stringify(parsed, null, 2));
          resolve(parsed);
        } catch (e) {
          console.log('Raw response:', data);
          reject(e);
        }
      });
    });

    req.on('error', (e) => {
      console.error('❌ Connection error:', e.message);
      reject(e);
    });

    req.write(postData);
    req.end();
  });
}

krakenAPI();
