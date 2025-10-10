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

async function getBalance() {
  try {
    const balance = await lunoAPI('balance');
    const balances = {};

    if (balance.balance) {
      balance.balance.forEach(b => {
        const total = parseFloat(b.balance);
        const reserved = parseFloat(b.reserved);
        const available = total - reserved;
        
        balances[b.asset] = {
          available: available,
          reserved: reserved,
          total: total,
        };
      });
    }

    return balances;
  } catch (error) {
    console.error('Error:', error.message);
    return {};
  }
}

async function test() {
  const balances = await getBalance();
  
  console.log('\n✅ FIXED BALANCE:');
  console.log('==================');
  Object.keys(balances).forEach(asset => {
    const b = balances[asset];
    if (b.total > 0) {
      console.log(asset + ':');
      console.log('  Available: ' + b.available.toFixed(2));
      console.log('  Reserved: ' + b.reserved.toFixed(2));
      console.log('  Total: ' + b.total.toFixed(2));
    }
  });
  console.log('==================\n');
}

test();
