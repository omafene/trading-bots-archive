// Telegram Test
const https = require('https');

const telegramBotToken = '123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
const telegramChatId = '123456789';

function sendTelegramAlert(message) {
  const url = 'https://api.telegram.org/bot' + telegramBotToken + '/sendMessage';
  const postData = JSON.stringify({
    chat_id: telegramChatId,
    text: message,
    parse_mode: 'HTML'
  });

  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': postData.length
    }
  };

  console.log('Sending to Telegram...');
  console.log('URL:', url);
  console.log('Chat ID:', telegramChatId);

  const req = https.request(url, options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      console.log('\nResponse Status:', res.statusCode);
      console.log('Response:', data);
      
      if (res.statusCode === 200) {
        console.log('\n✅ SUCCESS! Check your Telegram!');
      } else {
        console.log('\n❌ FAILED! Check the error above.');
      }
    });
  });

  req.on('error', (error) => {
    console.error('❌ Connection Error:', error.message);
  });

  req.write(postData);
  req.end();
}

console.log('Testing Telegram connection...\n');
sendTelegramAlert('🧪 Test Message from Luno Bot!\n\nIf you see this, Telegram is working! ✅');
