const https = require('https');

function checkOrderbook(pair) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.luno.com',
      path: '/api/1/orderbook_top?pair=' + pair,
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

async function analyzeDepth() {
  // Check LTC path pairs
  const pairs = ['LTCNGN', 'LTCXBT', 'XBTNGN'];
  
  for (const pair of pairs) {
    console.log('\n=== ' + pair + ' ORDER BOOK ===');
    const book = await checkOrderbook(pair);
    
    if (book.asks && book.bids) {
      // Top 5 asks (sell orders)
      console.log('\nTop 5 ASKS (prices you pay):');
      book.asks.slice(0, 5).forEach((ask, i) => {
        console.log('  ' + (i+1) + '. Price: ' + ask.price + ', Volume: ' + ask.volume);
      });
      
      // Top 5 bids (buy orders)
      console.log('\nTop 5 BIDS (prices you get):');
      book.bids.slice(0, 5).forEach((bid, i) => {
        console.log('  ' + (i+1) + '. Price: ' + bid.price + ', Volume: ' + bid.volume);
      });
      
      // Calculate depth
      const askDepth = book.asks.slice(0, 5).reduce((sum, a) => sum + parseFloat(a.volume), 0);
      const bidDepth = book.bids.slice(0, 5).reduce((sum, b) => sum + parseFloat(b.volume), 0);
      
      console.log('\nTop 5 Depth: Ask=' + askDepth.toFixed(4) + ', Bid=' + bidDepth.toFixed(4));
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

analyzeDepth();
