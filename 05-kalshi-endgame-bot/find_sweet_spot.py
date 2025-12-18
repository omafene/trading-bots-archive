"""
Find Your Trading Sweet Spot
Analyzes win rates by probability to identify optimal trading range
"""

import json
import pandas as pd
from collections import defaultdict

print("="*80)
print("FINDING YOUR SWEET SPOT - WIN RATE BY PROBABILITY")
print("="*80)

# Load data
with open('analysis/trades.json', 'r') as f:
    fills = json.load(f)

with open('analysis/settlements.json', 'r') as f:
    settlements = json.load(f)

# Separate buys and sells
buys = [f for f in fills if f.get('action') == 'buy']
sells = [f for f in fills if f.get('action') == 'sell']

print(f"\nTotal Buys: {len(buys)}")
print(f"Total Sells (manual): {len(sells)}")
print(f"Total Settlements (auto): {len(settlements)}")

# Build buy position map: ticker -> list of buys
buy_map = defaultdict(list)
for buy in buys:
    ticker = buy.get('ticker') or buy.get('market_ticker')
    side = buy.get('side', 'yes')
    
    # Get entry price
    if side == 'yes':
        entry_price = buy.get('yes_price', 0) / 100
    else:
        entry_price = buy.get('no_price', 0) / 100
    
    buy_map[ticker].append({
        'count': buy.get('count', 0),
        'entry_price': entry_price,
        'side': side,
        'time': buy.get('created_time')
    })

# Build sell map: ticker -> list of sells
sell_map = defaultdict(list)
for sell in sells:
    ticker = sell.get('ticker') or sell.get('market_ticker')
    side = sell.get('side', 'yes')
    
    # Get exit price
    if side == 'yes':
        exit_price = sell.get('yes_price', 0) / 100
    else:
        exit_price = sell.get('no_price', 0) / 100
    
    sell_map[ticker].append({
        'count': sell.get('count', 0),
        'exit_price': exit_price,
        'side': side,
        'time': sell.get('created_time')
    })

# Analyze outcomes
results = []

# 1. Process settlements (positions held to expiration)
for settlement in settlements:
    ticker = settlement.get('ticker')
    market_result = settlement.get('market_result')  # 'yes' or 'no'
    
    if ticker not in buy_map:
        continue
    
    # Get position details
    yes_count = settlement.get('yes_count', 0)
    no_count = settlement.get('no_count', 0)
    yes_cost = settlement.get('yes_total_cost', 0)
    no_cost = settlement.get('no_total_cost', 0)
    revenue = settlement.get('revenue', 0)
    
    # Calculate total cost
    total_cost = yes_cost + no_cost
    
    # Determine if won
    if yes_count > 0:
        side = 'yes'
        count = yes_count
        won = (market_result == 'yes')
        cost = yes_cost
    elif no_count > 0:
        side = 'no'
        count = no_count
        won = (market_result == 'no')
        cost = no_cost
    else:
        continue  # No position
    
    # Get entry price from buys
    buys_for_ticker = buy_map.get(ticker, [])
    if buys_for_ticker:
        # Use average entry price
        avg_entry = sum(b['entry_price'] for b in buys_for_ticker) / len(buys_for_ticker)
    else:
        avg_entry = 0.50  # Default
    
    # Calculate P&L
    pnl = revenue - cost
    
    results.append({
        'ticker': ticker,
        'side': side,
        'entry_price': avg_entry,
        'count': count,
        'cost': cost,
        'revenue': revenue,
        'pnl': pnl,
        'won': won,
        'outcome_type': 'settlement'
    })

# 2. Process manual sells (match to buys)
for ticker, sells_list in sell_map.items():
    if ticker not in buy_map:
        continue
    
    buys_list = buy_map[ticker]
    
    # Match sells to buys (FIFO)
    for sell in sells_list:
        sell_count = sell['count']
        sell_price = sell['exit_price']
        sell_side = sell['side']
        
        # Find matching buy
        for buy in buys_list:
            if buy['side'] == sell_side and buy['count'] > 0:
                # Calculate for this match
                matched_count = min(sell_count, buy['count'])
                
                entry_price = buy['entry_price']
                
                # P&L calculation
                cost = matched_count * entry_price
                revenue = matched_count * sell_price
                pnl = revenue - cost
                won = (pnl > 0)
                
                results.append({
                    'ticker': ticker,
                    'side': sell_side,
                    'entry_price': entry_price,
                    'count': matched_count,
                    'cost': cost,
                    'revenue': revenue,
                    'pnl': pnl,
                    'won': won,
                    'outcome_type': 'manual_sell'
                })
                
                # Update remaining
                buy['count'] -= matched_count
                sell_count -= matched_count
                
                if sell_count <= 0:
                    break

print(f"\nProcessed {len(results)} completed trades with outcomes\n")

if not results:
    print("⚠️ No completed trades yet - need more settlements!")
    print("Most of your 411 trades are still open or just opened.")
    exit()

# Convert to DataFrame
df = pd.DataFrame(results)

# Create probability buckets
prob_bins = [0, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.01]
prob_labels = ['<70%', '70-75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%']

df['prob_bucket'] = pd.cut(df['entry_price'], bins=prob_bins, labels=prob_labels)

# Group by probability bucket
print("WIN RATES BY PROBABILITY BUCKET:")
print("="*80)
print(f"{'Bucket':<12} {'Trades':<8} {'Wins':<8} {'Losses':<8} {'Win Rate':<10} {'Total P&L':<12} {'Avg P&L'}")
print("-"*80)

for bucket in prob_labels:
    bucket_df = df[df['prob_bucket'] == bucket]
    
    if len(bucket_df) == 0:
        continue
    
    total = len(bucket_df)
    wins = bucket_df['won'].sum()
    losses = total - wins
    win_rate = wins / total if total > 0 else 0
    total_pnl = bucket_df['pnl'].sum()
    avg_pnl = bucket_df['pnl'].mean()
    
    # Mark sweet spot (best win rate with 5+ trades)
    marker = "🎯" if total >= 5 and win_rate >= 0.70 else "  "
    
    print(f"{marker} {bucket:<10} {total:<8} {wins:<8} {losses:<8} {win_rate*100:>6.1f}%    "
          f"${total_pnl:>8.2f}    ${avg_pnl:>6.2f}")

# Find sweet spot
valid_buckets = df[df.groupby('prob_bucket')['prob_bucket'].transform('count') >= 5]

if len(valid_buckets) > 0:
    bucket_stats = valid_buckets.groupby('prob_bucket').agg({
        'won': 'mean',
        'pnl': ['sum', 'mean', 'count']
    }).round(3)
    
    bucket_stats.columns = ['win_rate', 'total_pnl', 'avg_pnl', 'count']
    best_bucket = bucket_stats['win_rate'].idxmax()
    
    print("\n" + "="*80)
    print(f"🎯 YOUR SWEET SPOT: {best_bucket}")
    print("="*80)
    
    best_stats = bucket_stats.loc[best_bucket]
    print(f"Win Rate: {best_stats['win_rate']*100:.1f}%")
    print(f"Sample Size: {int(best_stats['count'])} trades")
    print(f"Total P&L: ${best_stats['total_pnl']:.2f}")
    print(f"Avg P&L per trade: ${best_stats['avg_pnl']:.2f}")
    
    # Recommendation
    bucket_ranges = {
        '<70%': (0.65, 0.70),
        '70-75%': (0.70, 0.75),
        '75-80%': (0.75, 0.80),
        '80-85%': (0.80, 0.85),
        '85-90%': (0.85, 0.90),
        '90-95%': (0.90, 0.95),
        '95-100%': (0.95, 0.99)
    }
    
    if best_bucket in bucket_ranges:
        min_rec, max_rec = bucket_ranges[best_bucket]
        
        print(f"\n💡 RECOMMENDED CONFIG:")
        print("-"*80)
        print(f"strategy:")
        print(f"  min_probability: {min_rec:.2f}")
        print(f"  max_probability: {max_rec:.2f}")
        
        # Additional recommendations based on data
        print(f"\nWhy this works for you:")
        sweet_df = df[df['prob_bucket'] == best_bucket]
        print(f"  • {int(best_stats['count'])} trades in this range")
        print(f"  • {best_stats['win_rate']*100:.1f}% win rate")
        print(f"  • Avg profit per winner: ${sweet_df[sweet_df['won']]['pnl'].mean():.2f}")
        if (sweet_df['won'] == False).any():
            print(f"  • Avg loss per loser: ${sweet_df[~sweet_df['won']]['pnl'].mean():.2f}")

# Overall stats
print("\n" + "="*80)
print("OVERALL PERFORMANCE")
print("="*80)
print(f"Total Trades Analyzed: {len(df)}")
print(f"Overall Win Rate: {df['won'].mean()*100:.1f}%")
print(f"Total P&L: ${df['pnl'].sum():.2f}")
print(f"Average P&L per trade: ${df['pnl'].mean():.2f}")
print(f"Best Trade: ${df['pnl'].max():.2f}")
print(f"Worst Trade: ${df['pnl'].min():.2f}")

# Side comparison
print(f"\nPERFORMANCE BY SIDE:")
print("-"*80)
for side in ['yes', 'no']:
    side_df = df[df['side'] == side]
    if len(side_df) > 0:
        print(f"{side.upper()}:")
        print(f"  Trades: {len(side_df)}")
        print(f"  Win Rate: {side_df['won'].mean()*100:.1f}%")
        print(f"  Total P&L: ${side_df['pnl'].sum():.2f}")
        print(f"  Avg P&L: ${side_df['pnl'].mean():.2f}")

