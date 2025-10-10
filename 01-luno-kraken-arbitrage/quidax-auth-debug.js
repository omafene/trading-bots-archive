// Quidax Auth Debug - Try Different Methods
const https = require('https');
const crypto = require('crypto');
const querystring = require('querystring');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',  // Your key
  apiSecret: 'YOUR_API_SECRET_HERE',  // Add your secret
};

console.log('Testing different signature methods...\n');

// Method 1: Timestamp in seconds
function test1() {
  console.log('=== TEST 1: Timestamp in SECONDS ===');
  
  const params = {
    api_key: CONFIG.apiKey,
    time: Math.floor(Date.now() / 1000),
  };
  
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  const signString = querystring.stringify(sortedParams) + '&secret_key=' + CONFIG.apiSecret;
  const signature = crypto.createHash('md5').update(signString).digest('hex').toUpperCase();
  
  params.sign = signature;
  
  console.log('Params:', params);
  console.log('Sign string:', signString);
  console.log('Signature:', signature);
  
  const queryString = querystring.stringify(params);
  const path = '/open/api/user/account?' + queryString;
  
  return new Promise((resolve) => {
    https.get('https://openapi.quidax.io' + path, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log('Response:', data);
        try {
          const parsed = JSON.parse(data);
          if (parsed.code === '0' || parsed.code === 0) {
            console.log('✅ SUCCESS!\n');
          } else {
            console.log('❌ Failed with code:', parsed.code, '\n');
          }
        } catch (e) {}
        resolve();
      });
    }).on('error', () => resolve());
  });
}

// Method 2: No secret_key in sign string
function test2() {
  console.log('=== TEST 2: Without secret_key suffix ===');
  
  const params = {
    api_key: CONFIG.apiKey,
    time: Math.floor(Date.now() / 1000),
  };
  
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  const signString = querystring.stringify(sortedParams);
  const signature = crypto.createHash('md5').update(signString + CONFIG.apiSecret).digest('hex').toUpperCase();
  
  params.sign = signature;
  
  console.log('Params:', params);
  console.log('Sign string:', signString + CONFIG.apiSecret);
  console.log('Signature:', signature);
  
  const queryString = querystring.stringify(params);
  const path = '/open/api/user/account?' + queryString;
  
  return new Promise((resolve) => {
    https.get('https://openapi.quidax.io' + path, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log('Response:', data);
        try {
          const parsed = JSON.parse(data);
          if (parsed.code === '0' || parsed.code === 0) {
            console.log('✅ SUCCESS!\n');
          } else {
            console.log('❌ Failed with code:', parsed.code, '\n');
          }
        } catch (e) {}
        resolve();
      });
    }).on('error', () => resolve());
  });
}

// Method 3: HMAC-SHA256 instead of MD5
function test3() {
  console.log('=== TEST 3: HMAC-SHA256 ===');
  
  const params = {
    api_key: CONFIG.apiKey,
    time: Math.floor(Date.now() / 1000),
  };
  
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  const signString = querystring.stringify(sortedParams);
  const signature = crypto.createHmac('sha256', CONFIG.apiSecret).update(signString).digest('hex').toUpperCase();
  
  params.sign = signature;
  
  console.log('Params:', params);
  console.log('Sign string:', signString);
  console.log('Signature:', signature);
  
  const queryString = querystring.stringify(params);
  const path = '/open/api/user/account?' + queryString;
  
  return new Promise((resolve) => {
    https.get('https://openapi.quidax.io' + path, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log('Response:', data);
        try {
          const parsed = JSON.parse(data);
          if (parsed.code === '0' || parsed.code === 0) {
            console.log('✅ SUCCESS!\n');
          } else {
            console.log('❌ Failed with code:', parsed.code, '\n');
          }
        } catch (e) {}
        resolve();
      });
    }).on('error', () => resolve());
  });
}

async function runTests() {
  await test1();
  await test2();
  await test3();
  
  console.log('=== All tests complete ===');
  console.log('If all failed, the issue might be:');
  console.log('1. API secret is incorrect');
  console.log('2. IP not properly whitelisted');
  console.log('3. API key lacks permissions');
  console.log('4. Need to contact Quidax support for correct format');
}

runTests();
