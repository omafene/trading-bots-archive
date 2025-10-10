// Paste YOUR ACTUAL keys here
const apiKey = 'YOUR_API_KEY_HERE';
const apiSecret = 'YOUR_API_SECRET_HERE';

console.log('\n=== KEY FORMAT CHECK ===\n');

console.log('API Key:');
console.log('  Length:', apiKey.length);
console.log('  First 10 chars:', apiKey.substring(0, 10));
console.log('  Last 10 chars:', apiKey.substring(apiKey.length - 10));
console.log('  Has spaces?', apiKey.includes(' ') ? '❌ YES (BAD!)' : '✅ No');
console.log('  Has newlines?', apiKey.includes('\n') ? '❌ YES (BAD!)' : '✅ No');

console.log('\nAPI Secret (Private Key):');
console.log('  Length:', apiSecret.length);
console.log('  First 10 chars:', apiSecret.substring(0, 10));
console.log('  Last 10 chars:', apiSecret.substring(apiSecret.length - 10));
console.log('  Has spaces?', apiSecret.includes(' ') ? '❌ YES (BAD!)' : '✅ No');
console.log('  Has newlines?', apiSecret.includes('\n') ? '❌ YES (BAD!)' : '✅ No');
console.log('  Looks like base64?', /^[A-Za-z0-9+/=]+$/.test(apiSecret) ? '✅ Yes' : '❌ No');

console.log('\n=== EXPECTED FORMAT ===');
console.log('API Key: 50-60 characters, alphanumeric');
console.log('API Secret: 80-90 characters, base64 (includes +, /, =)');
console.log('\n=== COMMON ISSUES ===');
console.log('- Keys swapped (shorter one should be API Key)');
console.log('- Extra spaces at start/end');
console.log('- Truncated (not fully copied)');
console.log('- Missing permissions on Kraken');
