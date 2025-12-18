"""
Volume Impact Analysis
Checks if high-volume markets have better win rates than low-volume markets
"""

import json
import pandas as pd
from collections import defaultdict

print("="*80)
print("VOLUME IMPACT ANALYSIS - Does Volume Matter?")
print("="*80)
print("\n⚙️  CURRENT SETTING: min_volume: 100 (very permissive)")
print("📊 Testing if higher thresholds would improve performance...")
print("="*80)

# Load data
with open('analysis/trades.json', 'r') as f:
    fills = json.load(f)

with open('analysis/settlements.json', 'r') as f:
    settlements = json.load(f)

# Get market details with volume
from kalshi_client import KalshiClient
import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

client = KalshiClient(config)
client.authenticate()

print("\nFetching market volume data...")

# Build ticker -> volume map
volume_map = {}
tickers = list(set([s.get('ticker') for s in settlements if s.get('ticker')]))

print(f"Fetching volume for {len(tickers)} unique markets...")

for i, ticker in enumerate(tickers[:100]):  # Limit to avoid too many API calls
    if i % 20 == 0:
        print(f"  Progress: {i}/{min(100, len(tickers))}...")
    
    try:
        market = client.get_market(ticker)
        if market:
            volume = market.get('volume', 0)
            volume_map[ticker] = volume
    except:
        volume_map[ticker] = 0

# Process outcomes (reuse logic from sweet spot finder)
buys = [f for f in fills if f.get('action') == 'buy']
buy_map = defaultdict(list)

for buy in buys:
    ticker = buy.get('ticker') or buy.get('market_ticker')
    side = buy.get('side', 'yes')
    
    if side == 'yes':
        entry_price = buy.get('yes_price', 0) / 100
    else:
        entry_price = buy.get('no_price', 0) / 100
    
    buy_map[ticker].append({
        'entry_price': entry_price,
        'side': side
    })

# Analyze settlements with volume
results = []

for settlement in settlements:
    ticker = settlement.get('ticker')
    market_result = settlement.get('market_result')
    
    if ticker not in buy_map:
        continue
    
    yes_count = settlement.get('yes_count', 0)
    no_count = settlement.get('no_count', 0)
    yes_cost = settlement.get('yes_total_cost', 0)
    no_cost = settlement.get('no_total_cost', 0)
    revenue = settlement.get('revenue', 0)
    
    if yes_count > 0:
        side = 'yes'
        won = (market_result == 'yes')
    elif no_count > 0:
        side = 'no'
        won = (market_result == 'no')
    else:
        continue
    
    # Get entry price
    buys_for_ticker = buy_map.get(ticker, [])
    if buys_for_ticker:
        avg_entry = sum(b['entry_price'] for b in buys_for_ticker) / len(buys_for_ticker)
    else:
        continue
    
    # Get volume
    volume = volume_map.get(ticker, 0)
    
    results.append({
        'ticker': ticker,
        'entry_price': avg_entry,
        'won': won,
        'volume': volume
    })

print(f"\nAnalyzed {len(results)} trades with volume data\n")

if not results:
    print("⚠️ No volume data available")
    exit()

df = pd.DataFrame(results)

# Create probability buckets
prob_bins = [0, 0.75, 0.80, 0.85, 0.90, 0.95, 1.01]
prob_labels = ['<75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%']
df['prob_bucket'] = pd.cut(df['entry_price'], bins=prob_bins, labels=prob_labels)

# Create volume buckets
df['volume_bucket'] = pd.cut(df['volume'], 
    bins=[0, 1000, 5000, 10000, 50000, float('inf')],
    labels=['<$1k', '$1k-$5k', '$5k-$10k', '$10k-$50k', '>$50k']
)

# Overall analysis
print("="*80)
print("OVERALL: Win Rate by Volume")
print("="*80)

volume_stats = df.groupby('volume_bucket').agg({
    'won': ['count', 'sum', 'mean']
}).round(3)

volume_stats.columns = ['Total', 'Wins', 'Win_Rate']

print(f"{'Volume':<15} {'Trades':<10} {'Wins':<10} {'Win Rate'}")
print("-"*80)
for idx, row in volume_stats.iterrows():
    if row['Total'] > 0:
        marker = "🎯" if row['Win_Rate'] > 0.85 else "  "
        print(f"{marker} {idx:<13} {int(row['Total']):<10} {int(row['Wins']):<10} {row['Win_Rate']*100:>6.1f}%")

# Focus on 85-90% range (the critical range)
print("\n" + "="*80)
print("CRITICAL RANGE (85-90%): High Volume vs Low Volume")
print("="*80)

range_85_90 = df[df['prob_bucket'] == '85-90%']

if len(range_85_90) > 0:
    high_vol = range_85_90[range_85_90['volume'] >= 5000]
    low_vol = range_85_90[range_85_90['volume'] < 5000]
    
    print(f"\nHIGH VOLUME (≥$5k):")
    if len(high_vol) > 0:
        print(f"  Trades: {len(high_vol)}")
        print(f"  Wins: {high_vol['won'].sum()}")
        print(f"  Win Rate: {high_vol['won'].mean()*100:.1f}%")
        print(f"  Avg Volume: ${high_vol['volume'].mean():,.0f}")
    else:
        print(f"  No trades in this range")
    
    print(f"\nLOW VOLUME (<$5k):")
    if len(low_vol) > 0:
        print(f"  Trades: {len(low_vol)}")
        print(f"  Wins: {low_vol['won'].sum()}")
        print(f"  Win Rate: {low_vol['won'].mean()*100:.1f}%")
        print(f"  Avg Volume: ${low_vol['volume'].mean():,.0f}")
    else:
        print(f"  No trades in this range")
    
    if len(high_vol) > 0 and len(low_vol) > 0:
        diff = high_vol['won'].mean() - low_vol['won'].mean()
        print(f"\n📊 DIFFERENCE: {diff*100:+.1f}% win rate improvement with high volume")
        
        if diff > 0.05:  # 5% improvement
            print("\n✅ RECOMMENDATION: ADD VOLUME FILTER")
            print("   High-volume markets perform significantly better!")
        else:
            print("\n⚠️ No significant difference - volume filter may not help")
else:
    print("No trades in 85-90% range")

# Detailed breakdown by probability AND volume
print("\n" + "="*80)
print("FULL BREAKDOWN: Win Rate by Probability AND Volume")
print("="*80)

pivot = pd.crosstab(
    df['prob_bucket'],
    df['volume_bucket'],
    values=df['won'],
    aggfunc=['count', 'mean']
).round(3)

print("\nTRADE COUNT by Probability x Volume:")
print(pivot['count'].fillna(0).astype(int))

print("\n\nWIN RATE (%) by Probability x Volume:")
print((pivot['mean'] * 100).round(1))

# Generate recommendation
print("\n" + "="*80)
print("💡 VOLUME THRESHOLD COMPARISON")
print("="*80)

# Test different thresholds
thresholds = [100, 500, 1000, 2000, 5000, 10000]

print(f"\n{'Threshold':<12} {'Trades':<10} {'Win Rate':<12} {'Trades Lost'}")
print("-"*80)

for threshold in thresholds:
    filtered = df[df['volume'] >= threshold]
    if len(filtered) > 0:
        wr = filtered['won'].mean() * 100
        count = len(filtered)
        lost = len(df) - count
        
        marker = "⚙️" if threshold == 100 else "🎯" if wr >= 88 and count >= 20 else "  "
        print(f"{marker} ≥${threshold:<9,} {count:<10} {wr:>6.1f}%       -{lost}")

print("\n" + "="*80)
print("💡 RECOMMENDATIONS")
print("="*80)

# Check if volume makes a difference across all probabilities
high_vol_all = df[df['volume'] >= 5000]
low_vol_all = df[df['volume'] < 5000]

if len(high_vol_all) > 5 and len(low_vol_all) > 5:
    high_wr = high_vol_all['won'].mean()
    low_wr = low_vol_all['won'].mean()
    diff_all = high_wr - low_wr
    
    print(f"\nOverall win rates:")
    print(f"  High volume (≥$5k): {high_wr*100:.1f}% ({len(high_vol_all)} trades)")
    print(f"  Low volume (<$5k): {low_wr*100:.1f}% ({len(low_vol_all)} trades)")
    print(f"  Difference: {diff_all*100:+.1f}%")
    
    if diff_all > 0.03:  # 3%+ improvement
        print(f"\n✅ STRONG RECOMMENDATION: Add volume filter")
        print(f"\nSuggested config:")
        print(f"```yaml")
        print(f"filters:")
        print(f"  min_volume: 5000  # Only trade markets with $5k+ volume")
        print(f"  # Especially important for 85-90% probability range")
        print(f"```")
        
        print(f"\n📈 Expected impact:")
        print(f"  • Improves win rate by {diff_all*100:.1f}%")
        print(f"  • Filters out {len(low_vol_all)} low-quality trades")
        print(f"  • Keeps {len(high_vol_all)} high-quality trades")
    elif diff_all > 0:
        print(f"\n⚠️ MODERATE: Small benefit from volume filter")
        print(f"   Consider adding min_volume: 2000 as a lighter filter")
    else:
        print(f"\n❌ Volume filter NOT helpful for your strategy")
        print(f"   Low-volume markets performing equally well or better")

# Show some examples of manipulated markets (lost despite high probability)
print("\n" + "="*80)
print("🚩 POTENTIAL 'FALSE FAVORITES' (Lost despite high probability)")
print("="*80)

false_favs = df[(df['entry_price'] >= 0.85) & (df['won'] == False)]
false_favs = false_favs.sort_values('volume')

if len(false_favs) > 0:
    print(f"\nFound {len(false_favs)} losses in high-probability markets:\n")
    print(f"{'Ticker':<30} {'Entry %':<10} {'Volume':<12} {'Result'}")
    print("-"*80)
    
    for _, trade in false_favs.head(10).iterrows():
        ticker = trade['ticker']
        entry = trade['entry_price'] * 100
        vol = trade['volume']
        
        vol_flag = "⚠️ LOW" if vol < 5000 else "✅ HIGH"
        print(f"{ticker:<30} {entry:>6.1f}%    ${vol:>8,.0f}  {vol_flag}")
    
    low_vol_losses = len(false_favs[false_favs['volume'] < 5000])
    high_vol_losses = len(false_favs[false_favs['volume'] >= 5000])
    
    print(f"\nBreakdown of losses:")
    print(f"  Low volume (<$5k): {low_vol_losses} losses")
    print(f"  High volume (≥$5k): {high_vol_losses} losses")
    
    if low_vol_losses > high_vol_losses * 2:
        print(f"\n🚨 ALERT: Most losses are in LOW-VOLUME markets!")
        print(f"   Volume filter would have prevented {low_vol_losses} losses")
else:
    print("No losses in high-probability trades - perfect record!")

# Final summary
print("\n" + "="*80)
print("📋 SUMMARY vs CURRENT SETTING (min_volume: 100)")
print("="*80)

current_trades = df[df['volume'] >= 100]
recommended_trades = df[df['volume'] >= 5000]

print(f"\nCURRENT (min_volume: 100):")
print(f"  Total trades: {len(current_trades)}")
print(f"  Win rate: {current_trades['won'].mean()*100:.1f}%")
print(f"  Trades filtered out: {len(df) - len(current_trades)}")

print(f"\nRECOMMENDED (min_volume: 5000):")
print(f"  Total trades: {len(recommended_trades)}")
if len(recommended_trades) > 0:
    print(f"  Win rate: {recommended_trades['won'].mean()*100:.1f}%")
    print(f"  Trades filtered out: {len(df) - len(recommended_trades)}")
    
    improvement = (recommended_trades['won'].mean() - current_trades['won'].mean()) * 100
    print(f"\n📊 Impact of raising to 5000:")
    print(f"  Win rate change: {improvement:+.1f}%")
    print(f"  Opportunity reduction: {len(current_trades) - len(recommended_trades)} trades")
    
    if improvement > 3:
        print(f"\n✅ STRONG CASE: Raising min_volume significantly improves quality")
    elif improvement > 0:
        print(f"\n⚠️ MODERATE: Slight improvement, test with 2000-3000 first")
    else:
        print(f"\n❌ Current setting (100) is fine - no benefit from higher threshold")
