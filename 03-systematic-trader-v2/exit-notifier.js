#!/usr/bin/env node
/**
 * BACKUP EXIT NOTIFICATION SYSTEM
 * Monitors trade-history.json and sends Telegram alerts for exits
 */
require('dotenv').config();
const fs = require('fs');
const https = require('https');

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const TRADE_HISTORY_FILE = './trade-history.json';
const LAST_NOTIFIED_FILE = './last-notified-trade.txt';

// Read last notified trade ID
function getLastNotifiedId() {
    try {
        if (fs.existsSync(LAST_NOTIFIED_FILE)) {
            return parseInt(fs.readFileSync(LAST_NOTIFIED_FILE, 'utf8'));
        }
    } catch (error) {
        console.log('No previous notification record found');
    }
    return 0;
}

// Save last notified trade ID
function saveLastNotifiedId(id) {
    fs.writeFileSync(LAST_NOTIFIED_FILE, id.toString());
}

// Send Telegram message
async function sendTelegram(message) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({
            chat_id: TELEGRAM_CHAT_ID,
            text: message,
            parse_mode: 'HTML'
        });

        const options = {
            hostname: 'api.telegram.org',
            path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': data.length
            }
        };

        const req = https.request(options, (res) => {
            let responseData = '';
            res.on('data', (chunk) => responseData += chunk);
            res.on('end', () => {
                if (res.statusCode === 200) {
                    resolve(JSON.parse(responseData));
                } else {
                    reject(new Error(`Telegram API error: ${res.statusCode}`));
                }
            });
        });

        req.on('error', reject);
        req.write(data);
        req.end();
    });
}

// Check for new exits
async function checkForNewExits() {
    try {
        if (!fs.existsSync(TRADE_HISTORY_FILE)) {
            console.log('⏳ Waiting for trade history file...');
            return;
        }

        const trades = JSON.parse(fs.readFileSync(TRADE_HISTORY_FILE, 'utf8'));
        const lastNotified = getLastNotifiedId();
        
        // Find new trades since last notification
        const newTrades = trades.filter(t => t.id > lastNotified);
        
        if (newTrades.length === 0) {
            console.log(`✓ No new exits (last ID: ${lastNotified})`);
            return;
        }

        console.log(`🔔 Found ${newTrades.length} new exit(s)!`);

        // Send notification for each new exit
        for (const trade of newTrades) {
            const pnl = parseFloat(trade.pnl);
            const pnlPercent = parseFloat(trade.pnlPercent);
            const emoji = pnl >= 0 ? '✅' : '❌';
            const reason = trade.exitReason.toUpperCase().replace('_', '-');
            
            const message = 
                `🚪 <b>${trade.mode.toUpperCase()} EXIT: ${reason}</b>\n\n` +
                `${trade.pair} ${emoji}\n` +
                `Entry: ${trade.entryPrice}\n` +
                `Exit: ${trade.exitPrice}\n` +
                `PnL: $${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)\n` +
                `Duration: ${formatDuration(trade.duration)}\n` +
                `Strategy: ${trade.strategy}`;

            try {
                await sendTelegram(message);
                console.log(`✅ Notified: ${trade.pair} exit (${reason})`);
                saveLastNotifiedId(trade.id);
            } catch (error) {
                console.error(`❌ Failed to send notification:`, error.message);
            }

            // Wait 1 second between notifications
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    } catch (error) {
        console.error('❌ Error checking exits:', error.message);
    }
}

// Format duration
function formatDuration(ms) {
    const minutes = Math.floor(ms / 60000);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    return `${minutes}m`;
}

// Main loop
async function main() {
    console.log('╔════════════════════════════════════════╗');
    console.log('║  BACKUP EXIT NOTIFICATION SYSTEM      ║');
    console.log('║  Monitoring trade-history.json        ║');
    console.log('╚════════════════════════════════════════╝\n');

    if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
        console.error('❌ Missing Telegram credentials in .env file!');
        process.exit(1);
    }

    console.log('✅ Backup notifier started');
    console.log(`📁 Watching: ${TRADE_HISTORY_FILE}`);
    console.log(`⏱️  Checking every 10 seconds\n`);

    // Check every 10 seconds
    setInterval(checkForNewExits, 10000);
    
    // Initial check
    checkForNewExits();
}

main();
