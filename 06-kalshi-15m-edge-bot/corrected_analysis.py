#!/usr/bin/env python3
"""
CORRECTED Analysis - Using UNIQUE markets only (not duplicate scans)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

print("="*80)
print("CORRECTED ANALYSIS - UNIQUE MARKETS ONLY")
print("="*80)
print()

# Load data
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

print(f"📊 Raw Data:")
print(f"   Total scan records: {len(df):,}")
print(f"   Unique markets (tickers): {df['ticker'].nunique():,}")
print(f"   Inflation factor: {len(df) / df['ticker'].nunique():.1f}x")
print()

# CRITICAL: Keep only ONE record per unique market (use last scan - most recent data)
df_unique = df.drop_duplicates(subset='ticker', keep='last').copy()
print(f"✅ Deduplicated to {len(df_unique):,} unique markets")
print()

# Calculate outcomes on UNIQUE markets
df_unique['entry_price'] = df_unique['yes_market_price']
df_unique['pnl'] = df_unique.apply(
    lambda row: (1.0 - row['entry_price']) * 100 if row['actual_outcome'] == 'yes'
    else -row['entry_price'] * 100 if pd.notna(row['actual_outcome']) else 0,
    axis=1
)
df_unique['won'] = (df_unique['pnl'] > 0).astype(int)

# Filter to completed markets only
df_completed = df_unique[pd.notna(df_unique['actual_outcome'])].copy()
print(f"📈 Completed markets with outcomes: {len(df_completed):,}")
print()

print("="*80)
print("SECTION 1: OVERALL PERFORMANCE (CORRECTED)")
print("="*80)
print()

overall_wr = df_completed['won'].mean() * 100
total_pnl = df_completed['pnl'].sum()
avg_pnl = df_completed['pnl'].mean()

print(f"🎯 Overall Performance:")
print(f"   Unique markets: {len(df_completed):,}")
print(f"   Win Rate: {overall_wr:.1f}%")
print(f"   Total PnL: ${total_pnl:.2f}")
print(f"   Avg PnL/Trade: ${avg_pnl:.2f}")
print()

print("="*80)
print("SECTION 2: FILTER EFFECTIVENESS (CORRECTED)")
print("="*80)
print()

# Analyze each filter on UNIQUE markets
for filter_name in ['Low Win Prob', 'Low Edge', 'Low Signal', 'Contrarian Bet']:
    filtered = df_completed[df_completed['skip_reason'] == filter_name]
    if len(filtered) > 0:
        wr = filtered['won'].mean() * 100
        total = filtered['pnl'].sum()
        avg = filtered['pnl'].mean()

        print(f"📊 Filter: {filter_name}")
        print(f"   Unique markets blocked: {len(filtered):,}")
        print(f"   Would-be win rate: {wr:.1f}%")
        print(f"   Would-be total PnL: ${total:.2f}")
        print(f"   Would-be avg PnL: ${avg:.2f}")
        print()

print("="*80)
print("SECTION 3: PROBABILITY CALIBRATION (CORRECTED)")
print("="*80)
print()

# Probability calibration on UNIQUE markets
df_with_prob = df_completed[pd.notna(df_completed['yes_expected_prob'])].copy()
prob_bins = [0, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
df_with_prob['prob_bin'] = pd.cut(df_with_prob['yes_expected_prob'], bins=prob_bins)

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
print("SECTION 4: EDGE CALCULATION (CORRECTED)")
print("="*80)
print()

df_with_edge = df_completed[pd.notna(df_completed['yes_edge_pct'])].copy()
edge_bins = [-200, -50, -20, -10, -5, 0, 5, 10, 20, 50, 200]
df_with_edge['edge_bin'] = pd.cut(df_with_edge['yes_edge_pct'], bins=edge_bins)

print(f"{'Edge Range (%)':<20} {'Count':<10} {'Win Rate':<12} {'Avg PnL':<12} {'Edge Accuracy':<15}")
print("-" * 80)

for edge_bin in df_with_edge['edge_bin'].cat.categories:
    bin_data = df_with_edge[df_with_edge['edge_bin'] == edge_bin]
    if len(bin_data) > 0:
        wr = bin_data['won'].mean()
        avg_pnl = bin_data['pnl'].mean()
        avg_edge = bin_data['yes_edge_pct'].mean()

        edge_correct = (avg_edge > 0 and avg_pnl > 0) or (avg_edge < 0 and avg_pnl < 0)
        accuracy = "✅" if edge_correct else "❌"

        print(f"{str(edge_bin):<20} {len(bin_data):<10} {wr*100:>6.1f}%     "
              f"${avg_pnl:>8.2f}   {accuracy} Edge: {avg_edge:>+6.1f}%")

print()

print("="*80)
print("SECTION 5: ASSET PERFORMANCE (CORRECTED)")
print("="*80)
print()

for symbol in df_completed['symbol'].dropna().unique():
    symbol_data = df_completed[df_completed['symbol'] == symbol]
    wr = symbol_data['won'].mean() * 100
    total = symbol_data['pnl'].sum()
    avg = symbol_data['pnl'].mean()
    avg_entry = symbol_data['entry_price'].mean()

    print(f"🔸 {symbol}")
    print(f"   Markets: {len(symbol_data):,}")
    print(f"   Win Rate: {wr:.1f}%")
    print(f"   Total PnL: ${total:.2f}")
    print(f"   Avg PnL: ${avg:.2f}")
    print(f"   Avg Entry: ${avg_entry:.3f}")

    # Direction breakdown
    for direction in ['up', 'down']:
        dir_data = symbol_data[symbol_data['momentum_direction'] == direction]
        if len(dir_data) >= 3:
            dir_wr = dir_data['won'].mean() * 100
            dir_pnl = dir_data['pnl'].sum()
            print(f"   └─ {direction.upper()}: {len(dir_data)} markets, {dir_wr:.1f}% WR, ${dir_pnl:.2f} PnL")
    print()

print("="*80)
print("SECTION 6: ENTRY PRICE SENSITIVITY (CORRECTED)")
print("="*80)
print()

price_bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
df_completed['price_bin'] = pd.cut(df_completed['entry_price'], bins=price_bins)

print(f"{'Entry Price':<20} {'Count':<10} {'Win Rate':<12} {'Avg PnL':<12} {'Total PnL':<12}")
print("-" * 80)

for price_bin in df_completed['price_bin'].cat.categories:
    bin_data = df_completed[df_completed['price_bin'] == price_bin]
    if len(bin_data) > 0:
        wr = bin_data['won'].mean() * 100
        avg_pnl = bin_data['pnl'].mean()
        total = bin_data['pnl'].sum()

        print(f"{str(price_bin):<20} {len(bin_data):<10} {wr:>6.1f}%     ${avg_pnl:>8.2f}   ${total:>9.2f}")

print()

print("="*80)
print("SECTION 7: TIME WINDOW ANALYSIS (CORRECTED)")
print("="*80)
print()

time_bins = [0, 3, 5, 8, 10, 15]
df_completed['time_bin'] = pd.cut(df_completed['minutes_to_close'], bins=time_bins)

for time_bin in df_completed['time_bin'].cat.categories:
    bin_data = df_completed[df_completed['time_bin'] == time_bin]
    if len(bin_data) > 0:
        wr = bin_data['won'].mean() * 100
        total = bin_data['pnl'].sum()
        avg = bin_data['pnl'].mean()
        print(f"   {str(time_bin):<15} Count: {len(bin_data):>6,}  WR: {wr:>5.1f}%  "
              f"Total: ${total:>9.2f}  Avg: ${avg:>6.2f}")

print()

print("="*80)
print("COMPARISON: MY ORIGINAL (WRONG) vs CORRECTED ANALYSIS")
print("="*80)
print()

print("❌ Original Analysis (counting duplicate scans):")
print(f"   Sample size: 18,941 'trades'")
print(f"   Overall WR: ~47.4%")
print(f"   'Low Win Prob' blocked: 10,019 with 59.2% WR")
print()

print("✅ Corrected Analysis (unique markets only):")
print(f"   Sample size: {len(df_completed):,} unique markets")
print(f"   Overall WR: {overall_wr:.1f}%")

# Recalculate Low Win Prob filter
low_prob = df_completed[df_completed['skip_reason'] == 'Low Win Prob']
print(f"   'Low Win Prob' blocked: {len(low_prob):,} with {low_prob['won'].mean()*100:.1f}% WR")
print()

print("🔍 Impact of Correction:")
print(f"   Sample size changed by: {18941 / len(df_completed):.1f}x (inflated)")
print(f"   Win rate changed by: {47.4 - overall_wr:+.1f}pp")
print()

print("="*80)
print("ANALYSIS COMPLETE - CORRECTED VERSION")
print("="*80)
