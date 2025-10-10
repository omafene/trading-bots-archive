// Simulate Kraken API response format
const mockKrakenResponse = {
  "error": [],
  "result": {
    "ZUSD": "1500.5000",      // USD with Z prefix
    "XXBT": "0.05000000",     // Bitcoin (XBT) with X prefix
    "XETH": "2.50000000",     // Ethereum with X prefix
    "USDT": "500.0000"        // USDT (no prefix)
  }
};

// Your bot's getBalance logic
function parseKrakenBalance(balanceData) {
  const balances = {};
  
  if (balanceData.result) {
    Object.keys(balanceData.result).forEach(asset => {
      const balance = parseFloat(balanceData.result[asset]);
      
      // Remove Kraken's Z/X prefix
      let cleanAsset = asset;
      if (asset.startsWith('Z') || asset.startsWith('X')) {
        cleanAsset = asset.substring(1);
      }
      
      // Normalize XBT to BTC
      if (cleanAsset === 'XBT') cleanAsset = 'BTC';
      
      balances[cleanAsset] = {
        available: balance,
        total: balance,
      };
    });
  }
  
  return balances;
}

// TEST IT
console.log('\n========================================');
console.log('TESTING KRAKEN BALANCE PARSING');
console.log('========================================\n');

console.log('Mock Kraken API Response:');
console.log(JSON.stringify(mockKrakenResponse, null, 2));

console.log('\n========================================');
console.log('PARSED RESULT:');
console.log('========================================\n');

const parsed = parseKrakenBalance(mockKrakenResponse);

Object.keys(parsed).forEach(asset => {
  console.log(asset + ':');
  console.log('  Available: ' + parsed[asset].available.toFixed(2));
  console.log('  Total: ' + parsed[asset].total.toFixed(2));
});

console.log('\n========================================');
console.log('CHECKS:');
console.log('========================================');
console.log('✓ ZUSD → USD:', parsed.USD ? '✅ PASS' : '❌ FAIL');
console.log('✓ XXBT → BTC:', parsed.BTC ? '✅ PASS' : '❌ FAIL');
console.log('✓ XETH → ETH:', parsed.ETH ? '✅ PASS' : '❌ FAIL');
console.log('✓ USDT stays USDT:', parsed.USDT ? '✅ PASS' : '❌ FAIL');
console.log('✓ Balance is number:', typeof parsed.USD.available === 'number' ? '✅ PASS' : '❌ FAIL');
console.log('========================================\n');
