// Quidax API Diagnostic Script
// Run: node diagnose-quidax.js

const https = require('https');

console.log('═══════════════════════════════════════════════════════════');
console.log('🔍 QUIDAX API DIAGNOSTIC TOOL');
console.log('═══════════════════════════════════════════════════════════\n');

// Test 1: Check what the tickers endpoint returns
function testTickersEndpoint() {
  return new Promise((resolve) => {
    console.log('📡 Testing: https://www.quidax.com/api/v2/tickers\n');
    
    const options = {
      hostname: 'www.quidax.com',
      path: '/api/v2/tickers',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      console.log(`✅ Connection successful!`);
      console.log(`📊 Status Code: ${res.statusCode}`);
      console.log(`📋 Headers:`, JSON.stringify(res.headers, null, 2));
      console.log(`\n📄 Response Body (first 500 chars):\n`);
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        console.log('─────────────────────────────────────────────────────');
        console.log(data.substring(0, 500));
        console.log('─────────────────────────────────────────────────────\n');
        
        // Try to detect the issue
        if (data.trim().startsWith('<')) {
          console.log('❌ PROBLEM: API returned HTML instead of JSON');
          console.log('   This usually means:');
          console.log('   1. Wrong URL or endpoint changed');
          console.log('   2. API is redirecting (check for 301/302)');
          console.log('   3. API is showing an error page');
          console.log('   4. Cloudflare or WAF blocking the request\n');
          
          if (data.includes('cloudflare') || data.includes('Cloudflare')) {
            console.log('🔒 Detected: Cloudflare protection page');
            console.log('   Solution: Try adding proper headers or use browser simulation\n');
          }
          
          if (data.includes('403') || data.includes('Forbidden')) {
            console.log('🚫 Detected: Access forbidden (403)');
            console.log('   Your VPS IP might be blocked\n');
          }
        } else {
          try {
            const parsed = JSON.parse(data);
            console.log('✅ Valid JSON received!');
            console.log(`📦 Found ${Object.keys(parsed).length} items in response\n`);
          } catch (e) {
            console.log('❌ Invalid JSON format\n');
          }
        }
        
        resolve(data);
      });
    });

    req.on('error', (error) => {
      console.log(`❌ Connection Error: ${error.message}\n`);
      resolve(null);
    });

    req.setTimeout(15000, () => {
      req.abort();
      console.log('❌ Request timeout\n');
      resolve(null);
    });

    req.end();
  });
}

// Test 2: Try alternative Quidax endpoints
function testAlternativeEndpoints() {
  console.log('\n🔄 Testing Alternative Endpoints:\n');
  
  const endpoints = [
    'https://www.quidax.com/api/v2/markets',
    'https://www.quidax.com/api/v1/markets/tickers',
    'https://api.quidax.com/api/v2/tickers',
    'https://quidax.com/api/v2/tickers',
  ];
  
  endpoints.forEach((url, index) => {
    setTimeout(() => {
      console.log(`\n📍 Endpoint ${index + 1}: ${url}`);
      
      https.get(url, (res) => {
        console.log(`   Status: ${res.statusCode}`);
        
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          if (data.trim().startsWith('{') || data.trim().startsWith('[')) {
            console.log('   ✅ Returns JSON!');
            console.log(`   Sample: ${data.substring(0, 100)}...`);
          } else if (data.trim().startsWith('<')) {
            console.log('   ❌ Returns HTML');
          } else {
            console.log('   ⚠️  Unknown format');
          }
        });
      }).on('error', (e) => {
        console.log(`   ❌ Error: ${e.message}`);
      });
    }, index * 2000); // Delay 2 seconds between each test
  });
}

// Test 3: Check if DNS resolution works
function testDNS() {
  return new Promise((resolve) => {
    console.log('\n🌐 Testing DNS Resolution:\n');
    
    const dns = require('dns');
    dns.resolve4('www.quidax.com', (err, addresses) => {
      if (err) {
        console.log(`❌ DNS Resolution Failed: ${err.message}\n`);
        resolve(false);
      } else {
        console.log(`✅ DNS Resolution Successful!`);
        console.log(`   IP Addresses: ${addresses.join(', ')}\n`);
        resolve(true);
      }
    });
  });
}

// Test 4: Test with curl-like request
function testWithHeaders() {
  return new Promise((resolve) => {
    console.log('\n🔧 Testing with Enhanced Headers:\n');
    
    const options = {
      hostname: 'www.quidax.com',
      path: '/api/v2/tickers',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.quidax.com/',
        'Origin': 'https://www.quidax.com'
      }
    };

    const req = https.request(options, (res) => {
      console.log(`Status: ${res.statusCode}`);
      
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (data.trim().startsWith('{') || data.trim().startsWith('[')) {
          console.log('✅ Enhanced headers worked! Returns JSON\n');
          resolve(true);
        } else {
          console.log('❌ Still getting HTML with enhanced headers\n');
          resolve(false);
        }
      });
    });

    req.on('error', (error) => {
      console.log(`❌ Error: ${error.message}\n`);
      resolve(false);
    });

    req.end();
  });
}

// Run all diagnostics
async function runDiagnostics() {
  await testDNS();
  await testTickersEndpoint();
  await testWithHeaders();
  testAlternativeEndpoints();
  
  setTimeout(() => {
    console.log('\n═══════════════════════════════════════════════════════════');
    console.log('💡 RECOMMENDATIONS:');
    console.log('═══════════════════════════════════════════════════════════\n');
    console.log('1. Check the actual Quidax API documentation at:');
    console.log('   https://docs.quidax.io/\n');
    console.log('2. Try accessing Quidax from your VPS browser/curl:');
    console.log('   curl -v https://www.quidax.com/api/v2/tickers\n');
    console.log('3. If getting Cloudflare pages, you may need to:');
    console.log('   - Add proper User-Agent headers (already in bot)');
    console.log('   - Use a proxy service');
    console.log('   - Contact Quidax support to whitelist your VPS IP\n');
    console.log('4. Check if Quidax API is operational:');
    console.log('   https://status.quidax.com/ (if exists)\n');
    console.log('5. Try the bot from a different network to isolate issue\n');
    console.log('═══════════════════════════════════════════════════════════\n');
  }, 10000); // Wait 10 seconds for all alternative endpoint tests
}

runDiagnostics();
