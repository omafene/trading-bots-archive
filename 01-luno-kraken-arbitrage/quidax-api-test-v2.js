// Quidax API Test - Alternative Signature Method
// Run: node quidax-api-test-v2.js

const https = require('https');
const crypto = require('crypto');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

function quidaxAPI(endpoint, params = {}) {
  return new Promise((resolve, reject) => {
    params.api_key = CONFIG.apiKey;
    params.time = Date.now();
    
    // Sort params and create sign string
    const sortedKeys = Object.keys(params).sort();
    let signString = '';
    sortedKeys.forEach(key => {
      signString += key + '=' + params[key] + '&';
    });
    signString += 'secret_key=' + CONFIG.apiSecret;
    
    // Create MD5 signature
    const sign = crypto.createHash('md5').update(signString).digest('hex').toUpperCase();
    params.sign = sign;
    
    // Build query string
    const queryParts = [];
    Object.keys(params).forEach(key => {
      queryParts.push(key + '=' + encodeURIComponent(params[key]));
    });
    const queryString = queryParts.join('&');
    
    console.log('DEBUG: Calling endpoint:', endpoint);
    console.log('DEBUG: Query string:', queryString.substring(0, 100) + '...');
    
    const options = {
      hostname: 'openapi.quidax.io',
      path: '/open/api' + endpoint + '?' + queryString,
      method: 'GET',
    };

    https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log('DEBUG: Response:', data.substring(0, 200));
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

async function test() {
  console.log('\n=== Testing Quidax Authentication ===\n');
  
  try {
    console.log('Attempting to get account balance...\n');
    const result = await quidaxAPI('/user/account');
    
    console.log('\n✅ SUCCESS!');
    console.log('Response code:', result.code);
    console.log('Full response:', JSON.stringify(result, null, 2));
    
  } catch (error) {
    console.log('\n❌ FAILED:', error.message);
  }
}

test();
