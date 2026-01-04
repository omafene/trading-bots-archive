#!/usr/bin/env python3
"""Analyze which skipped trades would have won"""

import pandas as pd
from datetime import datetime, timedelta
import pytz

# Read the CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter to recently checked outcomes (past 6 hours)
utc = pytz.UTC
six_hours_ago = datetime.now(utc) - timedelta(hours=6)
recent = df[df['timestamp'] >= six_hours_ago].copy()

# Get only checked outcomes
checked = recent[recent['outcome_checked'] == True]

print("\n" + "="*80)
print("📊 SKIPPED TRADES ANALYSIS - WOULD HAVE WON?")
print("="*80 + "\n")

print(f"Time Range: {six_hours_ago.strftime('%Y-%m-%d %H:%M')} to now")
print(f"Total skipped trades: {len(recent):,}")
print(f"Outcomes checked: {len(checked):,}\n")

if len(checked) == 0:
    print("⚠️ No outcomes available yet\n")
    print("="*80 + "\n")
    exit(0)

winners = checked[checked['would_have_won'] == True]
losers = checked[checked['would_have_won'] == False]
win_rate = (len(winners) / len(checked)) * 100

print("="*80)
print("📈 OVERALL RESULTS")
print("="*80)
print(f"Would have WON:  {len(winners):4d} trades ({win_rate:5.1f}%)")
print(f"Would have LOST: {len(losers):4d} trades ({100-win_rate:5.1f}%)")

total_pnl = checked['theoretical_pnl'].sum()
avg_pnl = checked['theoretical_pnl'].mean()

print(f"\nTheoretical P&L:   ${total_pnl:+,.2f}")
print(f"Average per trade: ${avg_pnl:+.2f}")

print("\n" + "="*80)
print("🎯 BREAKDOWN BY SKIP REASON")
print("="*80 + "\n")

skip_reasons = checked['skip_reason'].value_counts()
for reason in skip_reasons.index:
    reason_checked = checked[checked['skip_reason'] == reason]
    reason_winners = reason_checked[reason_checked['would_have_won'] == True]
    reason_win_rate = (len(reason_winners) / len(reason_checked)) * 100
    reason_pnl = reason_checked['theoretical_pnl'].sum()

    print(f"{reason:30s}")
    print(f"  Total:  {len(reason_checked):3d} trades")
    print(f"  Won:    {len(reason_winners):3d} trades ({reason_win_rate:5.1f}%)")
    print(f"  P&L:    ${reason_pnl:+,.2f}")
    print()

print("="*80)
print("💰 TOP 10 BIGGEST WINNERS (Should Have Taken)")
print("="*80 + "\n")

if len(winners) > 0:
    top_winners = winners.nlargest(10, 'theoretical_pnl')[
        ['ticker', 'symbol', 'best_edge_side', 'best_edge_pct', 'skip_reason',
         'yes_market_price', 'no_market_price', 'theoretical_pnl']
    ]

    for idx, row in top_winners.iterrows():
        print(f"✓ {row['ticker']}")
        print(f"   {row['symbol']:3s} {row['best_edge_side'].upper():3s} @ ${row['yes_market_price']:.2f}Y/${row['no_market_price']:.2f}N")
        print(f"   Edge: {row['best_edge_pct']:+6.1f}% | Skipped: {row['skip_reason']}")
        print(f"   Would have made: ${row['theoretical_pnl']:+.2f}\n")

print("="*80)
print("❌ TOP 10 BIGGEST LOSERS (Good We Skipped)")
print("="*80 + "\n")

if len(losers) > 0:
    top_losers = losers.nsmallest(10, 'theoretical_pnl')[
        ['ticker', 'symbol', 'best_edge_side', 'best_edge_pct', 'skip_reason',
         'yes_market_price', 'no_market_price', 'theoretical_pnl']
    ]

    for idx, row in top_losers.iterrows():
        print(f"✗ {row['ticker']}")
        print(f"   {row['symbol']:3s} {row['best_edge_side'].upper():3s} @ ${row['yes_market_price']:.2f}Y/${row['no_market_price']:.2f}N")
        print(f"   Edge: {row['best_edge_pct']:+6.1f}% | Skipped: {row['skip_reason']}")
        print(f"   Would have lost: ${row['theoretical_pnl']:+.2f}\n")

print("="*80 + "\n")
