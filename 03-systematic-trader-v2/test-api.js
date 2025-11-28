require('dotenv').config();
const ccxt = require('ccxt');

console.log('🔍 Testing Coinbase API Connection...\n');

const exchange = new ccxt.coinbase({
    apiKey: process.env.EXCHANGE_API_KEY,
    secret: process.env.EXCHANGE_API_SECRET,
    enableRateLimit: true
});

async function testAPI() {
    try {
        console.log('1️⃣ Checking API credentials format...');
        
        if (!process.env.EXCHANGE_API_KEY) {
            throw new Error('EXCHANGE_API_KEY not found in .env file');
        }
        if (!process.env.EXCHANGE_API_SECRET) {
            throw new Error('EXCHANGE_API_SECRET not found in .env file');
        }
        
        console.log('✅ API credentials loaded from .env\n');
        
        console.log('2️⃣ Testing connection to Coinbase...');
        
        // Fetch account balance
        const balance = await exchange.fetchBalance();
        
        console.log('✅ API connection successful!\n');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('📊 YOUR ACCOUNT BALANCES:');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
        
        let hasBalance = false;
        for (const [currency, amount] of Object.entries(balance.free)) {
            if (amount > 0) {
                console.log(`   ${currency}: ${amount}`);
                hasBalance = true;
            }
        }
        
        if (!hasBalance) {
            console.log('   No balances found (account may be empty)');
        }
        
        console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('✅ API TEST PASSED - Your keys are working!');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
        
        // Test market data access
        console.log('3️⃣ Testing market data access...');
        const ticker = await exchange.fetchTicker('BTC/USD');
        console.log(`✅ Current BTC price: $${ticker.last}\n`);
        
        console.log('🎉 All tests passed! You can proceed with backtesting.\n');
        
    } catch (error) {
        console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('❌ API TEST FAILED');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
        console.log('Error:', error.message);
        console.log('\n🔧 TROUBLESHOOTING:\n');
        
        if (error.message.includes('Invalid API Key')) {
            console.log('❌ Your API key is invalid or incorrectly formatted');
            console.log('   • Check for typos in .env file');
            console.log('   • Make sure you copied the ENTIRE key');
            console.log('   • Verify no extra spaces before/after the key\n');
        } else if (error.message.includes('not found')) {
            console.log('❌ API credentials not found in .env file');
            console.log('   • Run: cat .env');
            console.log('   • Verify EXCHANGE_API_KEY and EXCHANGE_API_SECRET exist\n');
        } else if (error.message.includes('permission')) {
            console.log('❌ API key lacks required permissions');
            console.log('   • Go to Coinbase.com → Settings → API');
            console.log('   • Edit your API key');
            console.log('   • Enable "View" and "Trade" permissions\n');
        } else {
            console.log('❌ Unexpected error - check your .env file format');
            console.log('   • Run: cat .env');
            console.log('   • Verify keys are on correct lines\n');
        }
        
        process.exit(1);
    }
}

testAPI();
