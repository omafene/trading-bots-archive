const trades = require('./trade-history.json');

console.log('\n🏆 ANALYZING WINNING TRADES\n');
console.log('='.repeat(60));

const winners = trades.filter(t => t.pnl > 0);
const losers = trades.filter(t => t.pnl <= 0);

console.log(`\nTotal Winners: ${winners.length} / ${trades.length}`);
console.log(`Total Losers: ${losers.length}`);

// Sort winners by profit
const sortedWinners = winners.sort((a, b) => b.pnl - a.pnl);

console.log('\n📊 TOP 10 WINNING TRADES:\n');
sortedWinners.slice(0, 10).forEach((t, i) => {
    const duration = t.duration / 3600000;
    console.log(`${i+1}. ${t.pair} ${t.side.toUpperCase()}`);
    console.log(`   P&L: $${t.pnl.toFixed(2)} (${t.pnlPercent.toFixed(2)}%)`);
    console.log(`   Entry: $${t.entryPrice} → Exit: $${t.exitPrice}`);
    console.log(`   Confidence: ${(t.confidence*100).toFixed(1)}%`);
    console.log(`   Duration: ${duration.toFixed(1)}h`);
    console.log(`   Exit: ${t.exitReason}`);
    console.log('');
});

// Analyze patterns in winners
console.log('\n🔍 WINNING TRADE PATTERNS:\n');

const avgWinnerConfidence = winners.reduce((sum, t) => sum + t.confidence, 0) / winners.length;
const avgLoserConfidence = losers.reduce((sum, t) => sum + t.confidence, 0) / losers.length;

console.log(`Average Confidence:`);
console.log(`  Winners: ${(avgWinnerConfidence*100).toFixed(1)}%`);
console.log(`  Losers:  ${(avgLoserConfidence*100).toFixed(1)}%`);

const avgWinnerDuration = winners.reduce((sum, t) => sum + t.duration, 0) / winners.length / 3600000;
const avgLoserDuration = losers.reduce((sum, t) => sum + t.duration, 0) / losers.length / 3600000;

console.log(`\nAverage Hold Time:`);
console.log(`  Winners: ${avgWinnerDuration.toFixed(1)}h`);
console.log(`  Losers:  ${avgLoserDuration.toFixed(1)}h`);

// Exit reasons
console.log(`\nExit Reasons:`);
const winnerExits = {};
winners.forEach(t => {
    winnerExits[t.exitReason] = (winnerExits[t.exitReason] || 0) + 1;
});
Object.entries(winnerExits).forEach(([reason, count]) => {
    console.log(`  ${reason}: ${count} (${(count/winners.length*100).toFixed(1)}%)`);
});

// Pair performance
console.log(`\nWinners by Pair:`);
const pairWins = {};
winners.forEach(t => {
    pairWins[t.pair] = (pairWins[t.pair] || 0) + 1;
});
Object.entries(pairWins).sort((a, b) => b[1] - a[1]).forEach(([pair, count]) => {
    const total = trades.filter(t => t.pair === pair).length;
    console.log(`  ${pair}: ${count}/${total} (${(count/total*100).toFixed(1)}%)`);
});

// Side analysis
const longWins = winners.filter(t => t.side === 'buy').length;
const shortWins = winners.filter(t => t.side === 'sell').length;
const longTotal = trades.filter(t => t.side === 'buy').length;
const shortTotal = trades.filter(t => t.side === 'sell').length;

console.log(`\nWinners by Side:`);
console.log(`  LONG (buy):  ${longWins}/${longTotal} (${(longWins/longTotal*100).toFixed(1)}%)`);
console.log(`  SHORT (sell): ${shortWins}/${shortTotal} (${(shortWins/shortTotal*100).toFixed(1)}%)`);

// Confidence distribution
console.log(`\nConfidence Distribution:`);
const confBuckets = { '60-70%': 0, '70-80%': 0, '80-90%': 0, '90-100%': 0, '>100%': 0 };
const confBucketsTotal = { '60-70%': 0, '70-80%': 0, '80-90%': 0, '90-100%': 0, '>100%': 0 };

trades.forEach(t => {
    const conf = t.confidence * 100;
    const bucket = conf < 70 ? '60-70%' : conf < 80 ? '70-80%' : conf < 90 ? '80-90%' : conf < 100 ? '90-100%' : '>100%';
    confBucketsTotal[bucket]++;
    if (t.pnl > 0) confBuckets[bucket]++;
});

Object.entries(confBucketsTotal).forEach(([bucket, total]) => {
    const wins = confBuckets[bucket];
    console.log(`  ${bucket}: ${wins}/${total} wins (${(wins/total*100).toFixed(1)}% win rate)`);
});

console.log('\n' + '='.repeat(60) + '\n');
