#!/usr/bin/env python3
"""
Comprehensive analysis of skipped trades from 2026-02-08 to 2026-02-10
"""

import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict

# Read the CSV file
df = pd.read_csv('data/negative_edges/skipped_trades.csv')

# Filter for the date range
df['timestamp'] = pd.to_datetime(df['timestamp'])
df_filtered = df[(df['timestamp'] >= '2026-02-08') & (df['timestamp'] <= '2026-02-10 23:59:59')].copy()

print("=" * 100)
print("SKIPPED TRADES ANALYSIS: February 8-10, 2026")
print("=" * 100)
print()

# =============================================================================
# 1. OVERALL PERFORMANCE
# =============================================================================
print("1. OVERALL PERFORMANCE")
print("-" * 100)
print()

total_opportunities = len(df_filtered)
print(f"Total Opportunities Evaluated: {total_opportunities:,}")
print()

# Skip reasons breakdown
print("Skip Reasons Breakdown:")
skip_reasons = df_filtered['skip_reason'].value_counts().sort_values(ascending=False)
for reason, count in skip_reasons.items():
    pct = (count / total_opportunities) * 100
    print(f"  {reason:50s}: {count:5,} ({pct:5.1f}%)")
print()

# Outcomes
outcome_checked = df_filtered['outcome_checked'].sum()
print(f"Outcomes Checked (verified results): {outcome_checked:,} ({(outcome_checked/total_opportunities)*100:.1f}%)")
print()

# Win/loss breakdown for checked outcomes
checked_df = df_filtered[df_filtered['outcome_checked'] == True].copy()
if len(checked_df) > 0:
    wins = checked_df['would_have_won'].sum()
    losses = len(checked_df) - wins
    win_rate = (wins / len(checked_df)) * 100
    print(f"Would Have Won:  {wins:5,} ({win_rate:.1f}%)")
    print(f"Would Have Lost: {losses:5,} ({100-win_rate:.1f}%)")
    print()

    # Theoretical P&L
    total_pnl = checked_df['theoretical_pnl'].sum()
    avg_pnl = checked_df['theoretical_pnl'].mean()
    winning_pnl = checked_df[checked_df['would_have_won'] == True]['theoretical_pnl'].sum()
    losing_pnl = checked_df[checked_df['would_have_won'] == False]['theoretical_pnl'].sum()

    print(f"Theoretical P&L (if all trades taken):")
    print(f"  Total P&L:     ${total_pnl:10.2f}")
    print(f"  Average P&L:   ${avg_pnl:10.2f}")
    print(f"  Winning P&L:   ${winning_pnl:10.2f}")
    print(f"  Losing P&L:    ${losing_pnl:10.2f}")
    print()

# =============================================================================
# 2. WIN RATE ANALYSIS BY CONDITIONS
# =============================================================================
print("\n")
print("=" * 100)
print("2. WIN RATE ANALYSIS BY CONDITIONS")
print("=" * 100)
print()

def analyze_condition(df, column_name, title, bins=None, labels=None):
    """Analyze win rate by a specific condition"""
    print(f"{title}")
    print("-" * 100)

    if bins is not None:
        # Bin continuous variables
        df_copy = df.copy()
        df_copy['binned'] = pd.cut(df_copy[column_name], bins=bins, labels=labels, include_lowest=True)
        grouped = df_copy.groupby('binned')
    else:
        grouped = df.groupby(column_name)

    results = []
    for name, group in grouped:
        count = len(group)
        if count == 0:
            continue
        wins = group['would_have_won'].sum()
        win_rate = (wins / count) * 100 if count > 0 else 0
        avg_pnl = group['theoretical_pnl'].mean()
        total_pnl = group['theoretical_pnl'].sum()

        results.append({
            'condition': name,
            'count': count,
            'wins': wins,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl
        })

    # Sort by count descending
    results = sorted(results, key=lambda x: x['count'], reverse=True)

    print(f"{'Condition':<40} {'Count':>8} {'Wins':>8} {'Win Rate':>10} {'Avg P&L':>12} {'Total P&L':>12}")
    print("-" * 100)
    for r in results:
        print(f"{str(r['condition']):<40} {r['count']:8,} {r['wins']:8,} {r['win_rate']:9.1f}% ${r['avg_pnl']:10.2f} ${r['total_pnl']:11.2f}")
    print()

# 2a. Skip Reason Analysis
analyze_condition(checked_df, 'skip_reason', '2a. Win Rate by Skip Reason')

# 2b. Momentum Direction & Strength
print("2b. Win Rate by Momentum Direction")
print("-" * 100)
for direction in checked_df['momentum_direction'].unique():
    if pd.isna(direction):
        continue
    direction_df = checked_df[checked_df['momentum_direction'] == direction]

    # Analyze by momentum strength ranges
    bins = [0, 0.5, 1.0, 1.5, 2.0, 100]
    labels = ['0.0-0.5%', '0.5-1.0%', '1.0-1.5%', '1.5-2.0%', '2.0%+']

    print(f"\nMomentum Direction: {direction}")
    print(f"{'Strength Range':<40} {'Count':>8} {'Wins':>8} {'Win Rate':>10} {'Avg P&L':>12} {'Total P&L':>12}")
    print("-" * 100)

    direction_df_copy = direction_df.copy()
    direction_df_copy['mom_binned'] = pd.cut(abs(direction_df_copy['momentum_pct']), bins=bins, labels=labels, include_lowest=True)

    for name, group in direction_df_copy.groupby('mom_binned'):
        count = len(group)
        if count == 0:
            continue
        wins = group['would_have_won'].sum()
        win_rate = (wins / count) * 100
        avg_pnl = group['theoretical_pnl'].mean()
        total_pnl = group['theoretical_pnl'].sum()
        print(f"{str(name):<40} {count:8,} {wins:8,} {win_rate:9.1f}% ${avg_pnl:10.2f} ${total_pnl:11.2f}")
print()

# 2c. Trend Strength Ranges
trend_bins = [0, 0.1, 0.2, 0.3, 100]
trend_labels = ['0.0-0.1', '0.1-0.2', '0.2-0.3', '0.3+']
analyze_condition(checked_df, 'trend_strength', '2c. Win Rate by Trend Strength', bins=trend_bins, labels=trend_labels)

# 2d. Signal Strength Ranges
signal_bins = [0, 1, 2, 3, 4, 100]
signal_labels = ['0-1', '1-2', '2-3', '3-4', '4+']
analyze_condition(checked_df, 'signal_strength', '2d. Win Rate by Signal Strength', bins=signal_bins, labels=signal_labels)

# 2e. Time to Close
time_bins = [0, 5, 10, 15, 20, 100]
time_labels = ['0-5min', '5-10min', '10-15min', '15-20min', '20min+']
analyze_condition(checked_df, 'minutes_to_close', '2e. Win Rate by Time to Close', bins=time_bins, labels=time_labels)

# 2f. Market Type
analyze_condition(checked_df, 'market_type', '2f. Win Rate by Market Type')

# 2g. Symbol
analyze_condition(checked_df, 'symbol', '2g. Win Rate by Symbol')

# 2h. Price Level
analyze_condition(checked_df, 'price_level_bucket', '2h. Win Rate by Price Level')

# =============================================================================
# 3. PROFITABILITY ANALYSIS
# =============================================================================
print("\n")
print("=" * 100)
print("3. PROFITABILITY ANALYSIS")
print("=" * 100)
print()

# 3a. Average P&L by skip reason (already shown above, but let's highlight top/bottom)
print("3a. Most Profitable Skip Reasons (Theoretical P&L if taken)")
print("-" * 100)
skip_pnl = checked_df.groupby('skip_reason').agg({
    'theoretical_pnl': ['sum', 'mean', 'count'],
    'would_have_won': 'sum'
})
skip_pnl.columns = ['Total P&L', 'Avg P&L', 'Count', 'Wins']
skip_pnl['Total P&L'] = skip_pnl['Total P&L'].astype(float).round(2)
skip_pnl['Avg P&L'] = skip_pnl['Avg P&L'].astype(float).round(2)
skip_pnl['Count'] = skip_pnl['Count'].astype(int)
skip_pnl['Wins'] = skip_pnl['Wins'].astype(int)
skip_pnl['Win Rate %'] = ((skip_pnl['Wins'] / skip_pnl['Count']) * 100).round(1)
skip_pnl = skip_pnl.sort_values('Total P&L', ascending=False)
print(skip_pnl.to_string())
print()

# 3b. Best performing conditions
print("3b. Best Performing Conditions (by Total P&L)")
print("-" * 100)

# By symbol
print("\nBy Symbol:")
symbol_pnl = checked_df.groupby('symbol').agg({
    'theoretical_pnl': ['sum', 'mean', 'count'],
    'would_have_won': 'sum'
})
symbol_pnl.columns = ['Total P&L', 'Avg P&L', 'Count', 'Wins']
symbol_pnl['Total P&L'] = symbol_pnl['Total P&L'].astype(float).round(2)
symbol_pnl['Avg P&L'] = symbol_pnl['Avg P&L'].astype(float).round(2)
symbol_pnl['Count'] = symbol_pnl['Count'].astype(int)
symbol_pnl['Wins'] = symbol_pnl['Wins'].astype(int)
symbol_pnl['Win Rate %'] = ((symbol_pnl['Wins'] / symbol_pnl['Count']) * 100).round(1)
print(symbol_pnl.sort_values('Total P&L', ascending=False).to_string())

# By market type
print("\nBy Market Type:")
market_pnl = checked_df.groupby('market_type').agg({
    'theoretical_pnl': ['sum', 'mean', 'count'],
    'would_have_won': 'sum'
})
market_pnl.columns = ['Total P&L', 'Avg P&L', 'Count', 'Wins']
market_pnl['Total P&L'] = market_pnl['Total P&L'].astype(float).round(2)
market_pnl['Avg P&L'] = market_pnl['Avg P&L'].astype(float).round(2)
market_pnl['Count'] = market_pnl['Count'].astype(int)
market_pnl['Wins'] = market_pnl['Wins'].astype(int)
market_pnl['Win Rate %'] = ((market_pnl['Wins'] / market_pnl['Count']) * 100).round(1)
print(market_pnl.sort_values('Total P&L', ascending=False).to_string())

# By momentum direction
print("\nBy Momentum Direction:")
mom_pnl = checked_df.groupby('momentum_direction').agg({
    'theoretical_pnl': ['sum', 'mean', 'count'],
    'would_have_won': 'sum'
})
mom_pnl.columns = ['Total P&L', 'Avg P&L', 'Count', 'Wins']
mom_pnl['Total P&L'] = mom_pnl['Total P&L'].astype(float).round(2)
mom_pnl['Avg P&L'] = mom_pnl['Avg P&L'].astype(float).round(2)
mom_pnl['Count'] = mom_pnl['Count'].astype(int)
mom_pnl['Wins'] = mom_pnl['Wins'].astype(int)
mom_pnl['Win Rate %'] = ((mom_pnl['Wins'] / mom_pnl['Count']) * 100).round(1)
print(mom_pnl.sort_values('Total P&L', ascending=False).to_string())

print()

# 3c. Identify filters blocking profitable trades
print("3c. Filters Blocking Profitable Trades")
print("-" * 100)

# Find skip reasons with positive total P&L and >50% win rate
profitable_filters = skip_pnl[(skip_pnl['Total P&L'] > 0) & (skip_pnl['Win Rate %'] > 50)]
if len(profitable_filters) > 0:
    print("WARNING: These filters are blocking profitable trades:")
    print(profitable_filters.to_string())
    print()
else:
    print("No filters are blocking consistently profitable trades (>50% win rate, positive P&L)")
    print()

# Show filters with high win rate but negative total P&L (small positions)
high_winrate_filters = skip_pnl[skip_pnl['Win Rate %'] > 55].sort_values('Win Rate %', ascending=False)
print("Filters with >55% Win Rate:")
print(high_winrate_filters.to_string())
print()

# =============================================================================
# 4. RECOMMENDATIONS
# =============================================================================
print("\n")
print("=" * 100)
print("4. RECOMMENDATIONS")
print("=" * 100)
print()

# Calculate key metrics for recommendations
total_winrate = (checked_df['would_have_won'].sum() / len(checked_df) * 100) if len(checked_df) > 0 else 0
total_roi = (checked_df['theoretical_pnl'].sum() / len(checked_df)) if len(checked_df) > 0 else 0

print(f"Current Overall Performance (Skipped Trades):")
print(f"  Win Rate: {total_winrate:.1f}%")
print(f"  Avg P&L per Trade: ${total_roi:.2f}")
print()

print("Recommendations based on data analysis:")
print()

# Recommendation 1: High win rate filters
high_wr_filters = skip_pnl[skip_pnl['Win Rate %'] > total_winrate].sort_values('Win Rate %', ascending=False)
if len(high_wr_filters) > 0:
    print("1. FILTERS TO RELAX (Higher win rate than average):")
    for idx, row in high_wr_filters.head(5).iterrows():
        print(f"   - {idx}: {row['Win Rate %']:.1f}% win rate, ${row['Avg P&L']:.2f} avg P&L ({int(row['Count'])} opportunities)")
    print()

# Recommendation 2: Profitable filters
profitable = skip_pnl[skip_pnl['Total P&L'] > 50].sort_values('Total P&L', ascending=False)
if len(profitable) > 0:
    print("2. MOST PROFITABLE SKIPPED CATEGORIES (Total P&L > $50):")
    for idx, row in profitable.head(5).iterrows():
        print(f"   - {idx}: ${row['Total P&L']:.2f} total, ${row['Avg P&L']:.2f} avg, {row['Win Rate %']:.1f}% WR ({int(row['Count'])} trades)")
    print()

# Recommendation 3: Symbol/Market analysis
print("3. OPTIMAL MARKET CONDITIONS:")
print(f"   Best Symbol: {symbol_pnl.sort_values('Total P&L', ascending=False).index[0]} (${symbol_pnl.sort_values('Total P&L', ascending=False)['Total P&L'].iloc[0]:.2f} total P&L)")
print(f"   Best Market Type: {market_pnl.sort_values('Win Rate %', ascending=False).index[0]} ({market_pnl.sort_values('Win Rate %', ascending=False)['Win Rate %'].iloc[0]:.1f}% WR)")
print()

# Recommendation 4: Signal strength analysis
print("4. SIGNAL STRENGTH THRESHOLD RECOMMENDATIONS:")
checked_df_copy = checked_df.copy()
signal_bins_rec = [0, 1, 2, 3, 4, 100]
signal_labels_rec = ['0-1', '1-2', '2-3', '3-4', '4+']
checked_df_copy['signal_binned'] = pd.cut(checked_df_copy['signal_strength'], bins=signal_bins_rec, labels=signal_labels_rec, include_lowest=True)
signal_analysis = checked_df_copy.groupby('signal_binned').agg({
    'theoretical_pnl': ['sum', 'mean'],
    'would_have_won': 'sum',
    'signal_strength': 'count'
}).round(2)
signal_analysis.columns = ['Total P&L', 'Avg P&L', 'Wins', 'Count']
signal_analysis['Total P&L'] = signal_analysis['Total P&L'].astype(float).round(2)
signal_analysis['Avg P&L'] = signal_analysis['Avg P&L'].astype(float).round(2)
signal_analysis['Wins'] = signal_analysis['Wins'].astype(int)
signal_analysis['Count'] = signal_analysis['Count'].astype(int)
signal_analysis['Win Rate %'] = ((signal_analysis['Wins'] / signal_analysis['Count']) * 100).round(1)
print(signal_analysis.to_string())
print()

# Find optimal signal threshold
if len(signal_analysis) > 0:
    best_signal = signal_analysis[signal_analysis['Win Rate %'] == signal_analysis['Win Rate %'].max()]
    if len(best_signal) > 0:
        print(f"   Optimal Signal Strength Range: {best_signal.index[0]} ({best_signal['Win Rate %'].iloc[0]:.1f}% WR)")
print()

# Recommendation 5: Timing
print("5. OPTIMAL TIMING:")
time_analysis = checked_df.copy()
time_bins_rec = [0, 5, 10, 15, 20, 100]
time_labels_rec = ['0-5min', '5-10min', '10-15min', '15-20min', '20min+']
time_analysis['time_binned'] = pd.cut(time_analysis['minutes_to_close'], bins=time_bins_rec, labels=time_labels_rec, include_lowest=True)
time_results = time_analysis.groupby('time_binned').agg({
    'theoretical_pnl': ['sum', 'mean'],
    'would_have_won': 'sum',
    'minutes_to_close': 'count'
}).round(2)
time_results.columns = ['Total P&L', 'Avg P&L', 'Wins', 'Count']
time_results['Total P&L'] = time_results['Total P&L'].astype(float).round(2)
time_results['Avg P&L'] = time_results['Avg P&L'].astype(float).round(2)
time_results['Wins'] = time_results['Wins'].astype(int)
time_results['Count'] = time_results['Count'].astype(int)
time_results['Win Rate %'] = ((time_results['Wins'] / time_results['Count']) * 100).round(1)
print(time_results.to_string())
if len(time_results) > 0:
    best_time = time_results[time_results['Win Rate %'] == time_results['Win Rate %'].max()]
    if len(best_time) > 0:
        print(f"   Best Time Window: {best_time.index[0]} ({best_time['Win Rate %'].iloc[0]:.1f}% WR, ${best_time['Avg P&L'].iloc[0]:.2f} avg P&L)")
print()

print("=" * 100)
print("END OF ANALYSIS")
print("=" * 100)
