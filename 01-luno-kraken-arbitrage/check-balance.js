const https = require('https');

const CONFIG = {
  apiKey: 'YOUR_API_KEY_HERE',
  apiSecret: 'YOUR_API_SECRET_HERE',
};

function lunoAPI(endpoint) {
  return new Promise((resolve, reject) => {
    const auth = Buffer.from(CONFIG.apiKey + ':' + CONFIG.apiSecret).toString('base64');

    const options = {
      hostname: 'api.luno.com',
      path: '/api/1/' + endpoint,
      method: 'GET',
      headers: { 'Authorization': 'Basic ' + auth }
    };

    https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject).end();
  });
}

async function checkBalance() {
  try {
    const balance = await lunoAPI('balance');
    
    console.log('\n========================================');
    console.log('RAW BALANCE DATA:');
    console.log('========================================');
    console.log(JSON.stringify(balance, null, 2));
    console.log('========================================\n');
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

checkBalance();
