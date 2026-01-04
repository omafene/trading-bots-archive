#!/usr/bin/env python3
"""
Analyze specific combinations of conditions in skipped trades
"""

import pandas as pd
import numpy as np

# Read and filter data
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df_filtered = df[(df['timestamp'] >= '2026-02-08') & (df['timestamp'] <= '2026-02-10 23:59:59')].copy()
checked_df = df_filtered[df_filtered['outcome_checked'] == True].copy()

print("=" * 100)
print("COMBINATION ANALYSIS: High-Value Skipped Trade Patterns")
print("=" * 100)
print()

# 1. SOL + Low Signal combination
print("1. SOL Markets with 'Low Signal' Skip Reason")
print("-" * 100)
sol_low_signal = checked_df[(checked_df['symbol'] == 'SOL') & (checked_df['skip_reason'] == 'Low Signal')]
if len(sol_low_signal) > 0:
    wins = sol_low_signal['would_have_won'].sum()
    win_rate = (wins / len(sol_low_signal)) * 100
    total_pnl = sol_low_signal['theoretical_pnl'].sum()
    avg_pnl = sol_low_signal['theoretical_pnl'].mean()
    print(f"  Count: {len(sol_low_signal)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
    print(f"  Signal Strength Range: {sol_low_signal['signal_strength'].min():.2f} - {sol_low_signal['signal_strength'].max():.2f}")
    print(f"  Edge Range: {sol_low_signal['best_edge_pct'].min():.2f}% - {sol_low_signal['best_edge_pct'].max():.2f}%")
else:
    print("  No trades found")
print()

# 2. Cheap contracts + Low Signal
print("2. Cheap Contracts with 'Low Signal' Skip Reason")
print("-" * 100)
cheap_low_signal = checked_df[(checked_df['price_level_bucket'] == 'cheap') & (checked_df['skip_reason'] == 'Low Signal')]
if len(cheap_low_signal) > 0:
    wins = cheap_low_signal['would_have_won'].sum()
    win_rate = (wins / len(cheap_low_signal)) * 100
    total_pnl = cheap_low_signal['theoretical_pnl'].sum()
    avg_pnl = cheap_low_signal['theoretical_pnl'].mean()
    print(f"  Count: {len(cheap_low_signal)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
else:
    print("  No trades found")
print()

# 3. 5-10 min window + Low Signal
print("3. 5-10 Minute Window with 'Low Signal' Skip Reason")
print("-" * 100)
optimal_time_low_signal = checked_df[(checked_df['minutes_to_close'] >= 5) & (checked_df['minutes_to_close'] < 10) & (checked_df['skip_reason'] == 'Low Signal')]
if len(optimal_time_low_signal) > 0:
    wins = optimal_time_low_signal['would_have_won'].sum()
    win_rate = (wins / len(optimal_time_low_signal)) * 100
    total_pnl = optimal_time_low_signal['theoretical_pnl'].sum()
    avg_pnl = optimal_time_low_signal['theoretical_pnl'].mean()
    print(f"  Count: {len(optimal_time_low_signal)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
else:
    print("  No trades found")
print()

# 4. SOL + 5-10 min + Low Signal (GOLDEN COMBINATION)
print("4. SOL + 5-10 Min Window + 'Low Signal' (GOLDEN COMBINATION)")
print("-" * 100)
golden = checked_df[
    (checked_df['symbol'] == 'SOL') &
    (checked_df['minutes_to_close'] >= 5) &
    (checked_df['minutes_to_close'] < 10) &
    (checked_df['skip_reason'] == 'Low Signal')
]
if len(golden) > 0:
    wins = golden['would_have_won'].sum()
    win_rate = (wins / len(golden)) * 100
    total_pnl = golden['theoretical_pnl'].sum()
    avg_pnl = golden['theoretical_pnl'].mean()
    print(f"  Count: {len(golden)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
    print()
    print("  Sample trades:")
    for idx, row in golden.head(5).iterrows():
        print(f"    {row['timestamp']} | {row['ticker']} | Signal: {row['signal_strength']:.2f} | Edge: {row['best_edge_pct']:.1f}% | Won: {row['would_have_won']} | P&L: ${row['theoretical_pnl']:.2f}")
else:
    print("  No trades found")
print()

# 5. Flat momentum + Low Signal
print("5. Flat Momentum + 'Low Signal' Skip Reason")
print("-" * 100)
flat_low_signal = checked_df[(checked_df['momentum_direction'] == 'flat') & (checked_df['skip_reason'] == 'Low Signal')]
if len(flat_low_signal) > 0:
    wins = flat_low_signal['would_have_won'].sum()
    win_rate = (wins / len(flat_low_signal)) * 100
    total_pnl = flat_low_signal['theoretical_pnl'].sum()
    avg_pnl = flat_low_signal['theoretical_pnl'].mean()
    print(f"  Count: {len(flat_low_signal)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
else:
    print("  No trades found")
print()

# 6. High trend strength (0.3+) + Low Signal
print("6. High Trend Strength (0.3+) + 'Low Signal' Skip Reason")
print("-" * 100)
high_trend_low_signal = checked_df[(checked_df['trend_strength'] >= 0.3) & (checked_df['skip_reason'] == 'Low Signal')]
if len(high_trend_low_signal) > 0:
    wins = high_trend_low_signal['would_have_won'].sum()
    win_rate = (wins / len(high_trend_low_signal)) * 100
    total_pnl = high_trend_low_signal['theoretical_pnl'].sum()
    avg_pnl = high_trend_low_signal['theoretical_pnl'].mean()
    print(f"  Count: {len(high_trend_low_signal)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
else:
    print("  No trades found")
print()

# 7. Signal strength analysis for "Low Signal" trades
print("7. Signal Strength Distribution in 'Low Signal' Skipped Trades")
print("-" * 100)
low_signal_trades = checked_df[checked_df['skip_reason'] == 'Low Signal']
if len(low_signal_trades) > 0:
    bins = [0, 2, 3, 4, 5, 100]
    labels = ['0-2', '2-3', '3-4', '4-5', '5+']
    low_signal_trades_copy = low_signal_trades.copy()
    low_signal_trades_copy['signal_bin'] = pd.cut(low_signal_trades_copy['signal_strength'], bins=bins, labels=labels, include_lowest=True)

    print(f"{'Signal Range':<15} {'Count':>8} {'Wins':>8} {'Win Rate':>10} {'Avg P&L':>12} {'Total P&L':>12}")
    print("-" * 100)

    for name, group in low_signal_trades_copy.groupby('signal_bin', observed=True):
        count = len(group)
        if count == 0:
            continue
        wins = group['would_have_won'].sum()
        win_rate = (wins / count) * 100
        avg_pnl = group['theoretical_pnl'].mean()
        total_pnl = group['theoretical_pnl'].sum()
        print(f"{str(name):<15} {count:8,} {wins:8,} {win_rate:9.1f}% ${avg_pnl:10.2f} ${total_pnl:11.2f}")
print()

# 8. Edge percentage analysis for "Low Edge" trades with high win rate
print("8. 'Low Edge' Trades That Had High Win Rate")
print("-" * 100)
low_edge_trades = checked_df[checked_df['skip_reason'] == 'Low Edge']
if len(low_edge_trades) > 0:
    bins = [0, 2, 3, 4, 5, 100]
    labels = ['0-2%', '2-3%', '3-4%', '4-5%', '5%+']
    low_edge_trades_copy = low_edge_trades.copy()
    low_edge_trades_copy['edge_bin'] = pd.cut(low_edge_trades_copy['best_edge_pct'], bins=bins, labels=labels, include_lowest=True)

    print(f"{'Edge Range':<15} {'Count':>8} {'Wins':>8} {'Win Rate':>10} {'Avg P&L':>12} {'Total P&L':>12}")
    print("-" * 100)

    for name, group in low_edge_trades_copy.groupby('edge_bin', observed=True):
        count = len(group)
        if count == 0:
            continue
        wins = group['would_have_won'].sum()
        win_rate = (wins / count) * 100
        avg_pnl = group['theoretical_pnl'].mean()
        total_pnl = group['theoretical_pnl'].sum()
        print(f"{str(name):<15} {count:8,} {wins:8,} {win_rate:9.1f}% ${avg_pnl:10.2f} ${total_pnl:11.2f}")

    print()
    print("Note: Edge ranges 4-5% show good win rates. Consider lowering MIN_EDGE threshold to 4%.")
print()

# 9. Best individual trades we missed
print("9. Top 10 Missed Opportunities (by P&L)")
print("-" * 100)
winners = checked_df[checked_df['would_have_won'] == True].sort_values('theoretical_pnl', ascending=False).head(10)
print(f"{'Timestamp':<20} {'Symbol':<6} {'Skip Reason':<15} {'Signal':>8} {'Edge %':>8} {'Time Left':>10} {'P&L':>10}")
print("-" * 100)
for idx, row in winners.iterrows():
    print(f"{str(row['timestamp']):<20} {row['symbol']:<6} {row['skip_reason']:<15} {row['signal_strength']:8.2f} {row['best_edge_pct']:8.1f} {row['minutes_to_close']:10.1f} ${row['theoretical_pnl']:9.2f}")
print()

# 10. Worst trades that were correctly skipped
print("10. Worst Avoided Losses (Correctly Skipped)")
print("-" * 100)
losers = checked_df[checked_df['would_have_won'] == False].sort_values('theoretical_pnl', ascending=True).head(10)
print(f"{'Timestamp':<20} {'Symbol':<6} {'Skip Reason':<15} {'Signal':>8} {'Edge %':>8} {'Time Left':>10} {'P&L':>10}")
print("-" * 100)
for idx, row in losers.iterrows():
    print(f"{str(row['timestamp']):<20} {row['symbol']:<6} {row['skip_reason']:<15} {row['signal_strength']:8.2f} {row['best_edge_pct']:8.1f} {row['minutes_to_close']:10.1f} ${row['theoretical_pnl']:9.2f}")
print()

print("=" * 100)
print("KEY TAKEAWAY: Focus on 'Low Signal' trades, especially SOL in 5-10 min window")
print("=" * 100)
