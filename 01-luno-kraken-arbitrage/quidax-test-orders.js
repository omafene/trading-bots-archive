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
    
    const sortedKeys = Object.keys(params).sort();
    let signString = '';
    sortedKeys.forEach(key => {
      signString += key + '=' + params[key] + '&';
    });
    signString += 'secret_key=' + CONFIG.apiSecret;
    
    const sign = crypto.createHash('md5').update(signString).digest('hex').toUpperCase();
    params.sign = sign;
    
    const queryParts = [];
    Object.keys(params).forEach(key => {
      queryParts.push(key + '=' + encodeURIComponent(params[key]));
    });
    const queryString = queryParts.join('&');
    
    const options = {
      hostname: 'openapi.quidax.io',
      path: '/open/api' + endpoint + '?' + queryString,
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
}

async function test() {
  console.log('\nTrying different endpoints:\n');
  
  // Try current orders
  console.log('1. Testing /new_order...');
  let result = await quidaxAPI('/new_order', { symbol: 'btcusdt', pageSize: 10 });
  console.log('   Result:', result.code, result.msg || 'No message');
  
  // Try order history
  console.log('2. Testing /all_order...');
  result = await quidaxAPI('/all_order', { symbol: 'btcusdt', pageSize: 10 });
  console.log('   Result:', result.code, result.msg || 'No message');
  
  // Try account again
  console.log('3. Testing /user/account...');
  result = await quidaxAPI('/user/account');
  console.log('   Result:', result.code, result.msg || 'No message');
}

test();
