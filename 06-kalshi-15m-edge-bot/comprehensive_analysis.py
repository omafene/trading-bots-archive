#!/usr/bin/env python3
"""
Comprehensive Bot Performance Analysis - Fresh Review
Analyzes all available data to understand why the bot is not profitable
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

print("="*80)
print("COMPREHENSIVE BOT PERFORMANCE ANALYSIS")
print("="*80)
print()

# Load skipped trades data
print("📊 Loading data...")
df = pd.read_csv('/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv')
print(f"   Total records: {len(df):,}")

# Parse timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['date'] = df['timestamp'].dt.date
df['hour'] = df['timestamp'].dt.hour

# Calculate theoretical outcomes
df['entry_price'] = df['yes_market_price']  # Assuming we'd bet YES side
df['pnl'] = df.apply(lambda row: (1.0 - row['entry_price']) * 100 if row['actual_outcome'] == 'yes' else -row['entry_price'] * 100
                     if pd.notna(row['actual_outcome']) else 0, axis=1)
df['won'] = (df['pnl'] > 0).astype(int)

# Filter to only trades with known outcomes
df_completed = df[pd.notna(df['actual_outcome'])].copy()
print(f"   Completed trades with outcomes: {len(df_completed):,}")
print()

# Load bot state to see actual trades
try:
    with open('/root/kalshi_15m_bot/data/bot_state.json', 'r') as f:
        bot_state = json.load(f)
    total_trades = bot_state.get('trades_today', 0)
    positions = bot_state.get('positions', {})
    print(f"📈 Actual Bot Activity:")
    print(f"   Total trades executed: {total_trades}")
    print(f"   Current positions: {len(positions)}")
    print()
except Exception as e:
    print(f"   Could not load bot state: {e}")
    print()

print("="*80)
print("SECTION 1: DATA QUALITY & COVERAGE")
print("="*80)
print()

# Time range
print(f"📅 Data Coverage:")
print(f"   First record: {df['timestamp'].min()}")
print(f"   Last record: {df['timestamp'].max()}")
print(f"   Days covered: {(df['timestamp'].max() - df['timestamp'].min()).days}")
print()

# Outcome coverage
print(f"🎯 Outcome Tracking:")
print(f"   Total opportunities: {len(df):,}")
print(f"   With outcomes: {len(df_completed):,} ({len(df_completed)/len(df)*100:.1f}%)")
print(f"   Missing outcomes: {len(df) - len(df_completed):,}")
print()

# Skip reasons
print("🚫 Skip Reasons Distribution:")
skip_counts = df['skip_reason'].value_counts()
for reason, count in skip_counts.head(10).items():
    pct = count / len(df) * 100
    print(f"   {reason}: {count:,} ({pct:.1f}%)")
print()

print("="*80)
print("SECTION 2: CURRENT FILTER EFFECTIVENESS")
print("="*80)
print()

# Analyze each major filter
filters_to_test = [
    ('Low Edge', 'yes_edge_pct'),
    ('Low Win Prob', 'yes_expected_prob'),
    ('Low Signal', 'signal_strength'),
    ('Min Time Window', 'minutes_to_close'),
]

for filter_name, field in filters_to_test:
    if field not in df_completed.columns:
        continue

    filtered_out = df_completed[df_completed['skip_reason'] == filter_name]
    if len(filtered_out) > 0:
        win_rate = filtered_out['won'].mean() * 100
        total_pnl = filtered_out['pnl'].sum()
        avg_pnl = filtered_out['pnl'].mean()

        print(f"📊 Filter: {filter_name}")
        print(f"   Trades blocked: {len(filtered_out):,}")
        print(f"   Would-be win rate: {win_rate:.1f}%")
        print(f"   Would-be total PnL: ${total_pnl:.2f}")
        print(f"   Would-be avg PnL: ${avg_pnl:.2f}")

        # Show threshold if available
        if field in filtered_out.columns:
            values = filtered_out[field].dropna()
            if len(values) > 0:
                print(f"   Avg {field}: {values.mean():.3f}")
                print(f"   Range: {values.min():.3f} to {values.max():.3f}")
        print()

print("="*80)
print("SECTION 3: PROBABILITY MODEL ACCURACY")
print("="*80)
print()

# Bin by expected probability and check actual win rates
df_with_prob = df_completed[pd.notna(df_completed['yes_expected_prob'])].copy()

prob_bins = [0, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
df_with_prob['prob_bin'] = pd.cut(df_with_prob['yes_expected_prob'], bins=prob_bins)

print("📈 Model Calibration (Expected vs Actual Win Rates):")
print()
print(f"{'Expected Prob':<20} {'Count':<10} {'Actual WR':<15} {'Avg PnL':<12} {'Calibration':<15}")
print("-" * 80)

for prob_bin in df_with_prob['prob_bin'].cat.categories:
    bin_data = df_with_prob[df_with_prob['prob_bin'] == prob_bin]
    if len(bin_data) > 0:
        actual_wr = bin_data['won'].mean()
        avg_prob = bin_data['yes_expected_prob'].mean()
        avg_pnl = bin_data['pnl'].mean()
        calibration_error = (avg_prob - actual_wr) * 100

        print(f"{str(prob_bin):<20} {len(bin_data):<10} {actual_wr*100:>6.1f}% ({avg_prob*100:.1f}%)  "
              f"${avg_pnl:>8.2f}   {calibration_error:>+6.1f}pp {'❌ Over' if calibration_error > 5 else '✅ Good' if abs(calibration_error) <= 5 else '⚠️ Under'}")

print()

print("="*80)
print("SECTION 4: EDGE CALCULATION ACCURACY")
print("="*80)
print()

# Bin by calculated edge and check actual performance
df_with_edge = df_completed[pd.notna(df_completed['yes_edge_pct'])].copy()

edge_bins = [-200, -50, -20, -10, -5, 0, 5, 10, 20, 50, 200]
df_with_edge['edge_bin'] = pd.cut(df_with_edge['yes_edge_pct'], bins=edge_bins)

print("💰 Edge Calculation Accuracy:")
print()
print(f"{'Edge Range (%)':<20} {'Count':<10} {'Win Rate':<12} {'Avg PnL':<12} {'Edge Accuracy':<15}")
print("-" * 80)

for edge_bin in df_with_edge['edge_bin'].cat.categories:
    bin_data = df_with_edge[df_with_edge['edge_bin'] == edge_bin]
    if len(bin_data) > 0:
        win_rate = bin_data['won'].mean()
        avg_pnl = bin_data['pnl'].mean()
        avg_edge = bin_data['yes_edge_pct'].mean()

        # Edge should predict positive PnL
        edge_correct = (avg_edge > 0 and avg_pnl > 0) or (avg_edge < 0 and avg_pnl < 0)
        accuracy_indicator = "✅" if edge_correct else "❌"

        print(f"{str(edge_bin):<20} {len(bin_data):<10} {win_rate*100:>6.1f}%     "
              f"${avg_pnl:>8.2f}   {accuracy_indicator} Edge: {avg_edge:>+6.1f}%")

print()

print("="*80)
print("SECTION 5: ASSET PERFORMANCE BREAKDOWN")
print("="*80)
print()

for symbol in df_completed['symbol'].dropna().unique():
    symbol_data = df_completed[df_completed['symbol'] == symbol]

    win_rate = symbol_data['won'].mean() * 100
    total_pnl = symbol_data['pnl'].sum()
    avg_pnl = symbol_data['pnl'].mean()
    avg_entry = symbol_data['entry_price'].mean()

    print(f"🔸 {symbol}")
    print(f"   Trades: {len(symbol_data):,}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Total PnL: ${total_pnl:.2f}")
    print(f"   Avg PnL/Trade: ${avg_pnl:.2f}")
    print(f"   Avg Entry Price: ${avg_entry:.3f}")

    # Best/worst conditions for this symbol
    if len(symbol_data) > 10:
        # By momentum direction
        for direction in ['up', 'down']:
            dir_data = symbol_data[symbol_data['momentum_direction'] == direction]
            if len(dir_data) > 5:
                dir_wr = dir_data['won'].mean() * 100
                dir_pnl = dir_data['pnl'].sum()
                print(f"   └─ {direction.upper()}: {len(dir_data)} trades, {dir_wr:.1f}% WR, ${dir_pnl:.2f} PnL")
    print()

print("="*80)
print("SECTION 6: TIME-BASED PATTERNS")
print("="*80)
print()

# By minutes to close
print("⏰ Performance by Time to Close:")
time_bins = [0, 3, 5, 8, 10, 15]
df_completed['time_bin'] = pd.cut(df_completed['minutes_to_close'], bins=time_bins)

for time_bin in df_completed['time_bin'].cat.categories:
    bin_data = df_completed[df_completed['time_bin'] == time_bin]
    if len(bin_data) > 0:
        wr = bin_data['won'].mean() * 100
        total_pnl = bin_data['pnl'].sum()
        avg_pnl = bin_data['pnl'].mean()
        print(f"   {str(time_bin):<15} Count: {len(bin_data):>6,}  WR: {wr:>5.1f}%  "
              f"Total: ${total_pnl:>9.2f}  Avg: ${avg_pnl:>6.2f}")

print()

# By hour of day
print("🕐 Performance by Hour of Day (Top 10):")
hourly_perf = df_completed.groupby('hour').agg({
    'won': ['count', 'mean'],
    'pnl': 'sum'
}).round(3)
hourly_perf.columns = ['count', 'win_rate', 'total_pnl']
hourly_perf = hourly_perf.sort_values('total_pnl', ascending=False).head(10)

for hour, row in hourly_perf.iterrows():
    print(f"   Hour {hour:02d}:00  Count: {row['count']:>6.0f}  WR: {row['win_rate']*100:>5.1f}%  PnL: ${row['total_pnl']:>9.2f}")

print()

print("="*80)
print("SECTION 7: ENTRY PRICE SENSITIVITY")
print("="*80)
print()

price_bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
df_completed['price_bin'] = pd.cut(df_completed['entry_price'], bins=price_bins)

print("💵 Performance by Entry Price:")
print()
print(f"{'Entry Price':<20} {'Count':<10} {'Win Rate':<12} {'Avg PnL':<12} {'Total PnL':<12}")
print("-" * 80)

for price_bin in df_completed['price_bin'].cat.categories:
    bin_data = df_completed[df_completed['price_bin'] == price_bin]
    if len(bin_data) > 0:
        wr = bin_data['won'].mean() * 100
        avg_pnl = bin_data['pnl'].mean()
        total_pnl = bin_data['pnl'].sum()

        print(f"{str(price_bin):<20} {len(bin_data):<10} {wr:>6.1f}%     ${avg_pnl:>8.2f}   ${total_pnl:>9.2f}")

print()

print("="*80)
print("SECTION 8: CRITICAL INSIGHTS")
print("="*80)
print()

# Find the most profitable subset
print("🎯 Most Profitable Combinations:")
print()

# Test various combinations
combinations = [
    ('Entry < $0.50', df_completed[df_completed['entry_price'] < 0.50]),
    ('Entry < $0.50 + 3-5min window', df_completed[(df_completed['entry_price'] < 0.50) &
                                                     (df_completed['minutes_to_close'].between(3, 5))]),
    ('High prob (>0.65) + Entry < $0.50', df_completed[(df_completed['yes_expected_prob'] > 0.65) &
                                                         (df_completed['entry_price'] < 0.50)]),
    ('Strong trend (strength>0.20) + Entry < $0.50', df_completed[(df_completed['trend_strength'] > 0.20) &
                                                                    (df_completed['entry_price'] < 0.50)]),
]

best_combo = None
best_wr = 0

for name, subset in combinations:
    if len(subset) > 10:  # Need sufficient sample
        wr = subset['won'].mean() * 100
        total_pnl = subset['pnl'].sum()
        avg_pnl = subset['pnl'].mean()

        print(f"   {name}")
        print(f"      Trades: {len(subset):,}  |  Win Rate: {wr:.1f}%  |  Total PnL: ${total_pnl:.2f}  |  Avg: ${avg_pnl:.2f}")

        if wr > best_wr and len(subset) > 20:
            best_wr = wr
            best_combo = (name, subset)

print()

if best_combo:
    print(f"✅ Best Strategy Found: {best_combo[0]}")
    print(f"   Win Rate: {best_wr:.1f}%")
    print(f"   Sample Size: {len(best_combo[1]):,} trades")
    print()

print("="*80)
print("SECTION 9: KEY PROBLEMS IDENTIFIED")
print("="*80)
print()

# Identify major issues
issues = []

# Issue 1: Overall win rate
overall_wr = df_completed['won'].mean() * 100
if overall_wr < 50:
    issues.append(f"❌ CRITICAL: Overall win rate only {overall_wr:.1f}% (need >52% for profitability)")

# Issue 2: Probability calibration
high_prob_trades = df_completed[df_completed['yes_expected_prob'] > 0.70]
if len(high_prob_trades) > 10:
    high_prob_wr = high_prob_trades['won'].mean() * 100
    calibration_error = high_prob_trades['yes_expected_prob'].mean() - high_prob_trades['won'].mean()
    if calibration_error > 0.10:  # 10pp overconfigent
        issues.append(f"❌ Probability Model is overconfident by {calibration_error*100:.1f}pp on high-confidence trades")

# Issue 3: Positive edge but negative PnL
positive_edge = df_completed[df_completed['yes_edge_pct'] > 0]
if len(positive_edge) > 10:
    pos_edge_pnl = positive_edge['pnl'].sum()
    if pos_edge_pnl < 0:
        issues.append(f"❌ Edge calculation broken: Positive edge trades have NEGATIVE PnL (${pos_edge_pnl:.2f})")

# Issue 4: Filter blocking profitable trades
for filter_name in ['Low Signal', 'Low Win Prob', 'Low Edge']:
    filtered = df_completed[df_completed['skip_reason'] == filter_name]
    if len(filtered) > 20:
        filtered_wr = filtered['won'].mean() * 100
        if filtered_wr > 55:
            filtered_pnl = filtered['pnl'].sum()
            issues.append(f"⚠️ '{filter_name}' filter blocking {len(filtered)} trades with {filtered_wr:.1f}% WR (${filtered_pnl:.2f} PnL)")

# Issue 5: Wrong time window
for start, end in [(3, 5), (5, 8), (8, 10)]:
    window_data = df_completed[df_completed['minutes_to_close'].between(start, end)]
    if len(window_data) > 20:
        window_wr = window_data['won'].mean() * 100
        window_pnl = window_data['pnl'].sum()
        if window_wr > 60 and window_pnl > 100:
            issues.append(f"💡 OPPORTUNITY: {start}-{end} minute window has {window_wr:.1f}% WR and ${window_pnl:.2f} PnL")

for i, issue in enumerate(issues, 1):
    print(f"{i}. {issue}")

if not issues:
    print("✅ No critical issues detected in this analysis")

print()
print("="*80)
print("ANALYSIS COMPLETE")
print("="*80)
