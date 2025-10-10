// Mock Kraken response
const mockKrakenResponse = {
  error: [],
  result: {
    ZUSD: "1500.5000",
    XXBT: "0.05000000",
    XETH: "2.5000",
    USDT: "500.00"
  }
};

// OLD BROKEN VERSION
function oldGetBalance(balanceData) {
  return balanceData;  // Just returns raw data!
}

// NEW FIXED VERSION
function newGetBalance(balanceData) {
  if (balanceData.error && balanceData.error.length > 0) {
    throw new Error('Kraken API error: ' + balanceData.error.join(', '));
  }

  const balances = {};
  
  if (balanceData.result) {
    Object.keys(balanceData.result).forEach(asset => {
      const balance = parseFloat(balanceData.result[asset]);
      if (balance === 0) return;
      
      let cleanAsset = asset;
      if (asset.startsWith('Z') || asset.startsWith('X')) {
        cleanAsset = asset.substring(1);
      }
      
      if (cleanAsset === 'XBT') cleanAsset = 'BTC';
      
      balances[cleanAsset] = {
        available: balance,
        total: balance,
      };
    });
  }

  return balances;
}

console.log('\n=== OLD BROKEN VERSION ===');
console.log(oldGetBalance(mockKrakenResponse));

console.log('\n=== NEW FIXED VERSION ===');
const fixed = newGetBalance(mockKrakenResponse);
console.log(fixed);

console.log('\n=== CHECKS ===');
console.log('Can access USD balance?', fixed.USD ? '✅ YES: $' + fixed.USD.available : '❌ NO');
console.log('Can access BTC balance?', fixed.BTC ? '✅ YES: ' + fixed.BTC.available + ' BTC' : '❌ NO');
console.log('Can access ETH balance?', fixed.ETH ? '✅ YES: ' + fixed.ETH.available + ' ETH' : '❌ NO');
console.log('Can access USDT balance?', fixed.USDT ? '✅ YES: $' + fixed.USDT.available : '❌ NO');
console.log('\n');
