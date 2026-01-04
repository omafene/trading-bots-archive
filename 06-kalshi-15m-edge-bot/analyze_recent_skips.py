#!/usr/bin/env python3
"""Analyze skipped trades from the past 3 hours"""

import pandas as pd
from datetime import datetime, timedelta

# Read the CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Get trades from past 3 hours
import pytz
utc = pytz.UTC
three_hours_ago = datetime.now(utc) - timedelta(hours=3)
recent = df[df['timestamp'] >= three_hours_ago].copy()

print(f"\n📊 SKIPPED TRADES ANALYSIS - PAST 3 HOURS")
print(f"=" * 70)
print(f"Time range: {three_hours_ago.strftime('%Y-%m-%d %H:%M')} to now")
print(f"Total skipped trades: {len(recent)}")

# 1. Skip reasons summary
print(f"\n\n🚫 SKIP REASONS BREAKDOWN:")
print(f"-" * 70)
skip_reasons = recent['skip_reason'].value_counts()
for reason, count in skip_reasons.items():
    pct = (count / len(recent)) * 100
    print(f"{reason:30s}: {count:4d} ({pct:5.1f}%)")

# 2. Outcomes analysis (only for checked trades)
checked = recent[recent['outcome_checked'] == True].copy()
print(f"\n\n✅ OUTCOME ANALYSIS:")
print(f"-" * 70)
print(f"Trades with known outcomes: {len(checked)} / {len(recent)}")

if len(checked) > 0:
    winners = checked[checked['would_have_won'] == True]
    losers = checked[checked['would_have_won'] == False]

    win_rate = (len(winners) / len(checked)) * 100 if len(checked) > 0 else 0

    print(f"\nWould have WON:  {len(winners):4d} ({win_rate:5.1f}%)")
    print(f"Would have LOST: {len(losers):4d} ({100-win_rate:5.1f}%)")

    # Total theoretical P&L
    total_pnl = checked['theoretical_pnl'].sum()
    avg_pnl = checked['theoretical_pnl'].mean()

    print(f"\nTheoretical P&L: ${total_pnl:+.2f}")
    print(f"Average per trade: ${avg_pnl:+.2f}")

    # Break down by skip reason
    print(f"\n\n🎯 WINNERS BY SKIP REASON:")
    print(f"-" * 70)
    for reason in skip_reasons.index[:10]:  # Top 10 skip reasons
        reason_checked = checked[checked['skip_reason'] == reason]
        if len(reason_checked) > 0:
            reason_winners = reason_checked[reason_checked['would_have_won'] == True]
            reason_win_rate = (len(reason_winners) / len(reason_checked)) * 100
            reason_pnl = reason_checked['theoretical_pnl'].sum()

            print(f"\n{reason}:")
            print(f"  Checked: {len(reason_checked):3d} | Won: {len(reason_winners):3d} ({reason_win_rate:5.1f}%) | P&L: ${reason_pnl:+.2f}")

            if len(reason_winners) > 0:
                # Show a few examples
                examples = reason_winners.head(3)[['ticker', 'symbol', 'best_edge_side', 'best_edge_pct', 'theoretical_pnl', 'actual_outcome']]
                for _, row in examples.iterrows():
                    print(f"    ✓ {row['ticker']:30s} {row['symbol']:3s} {row['best_edge_side']:3s} edge={row['best_edge_pct']:+6.1f}% pnl=${row['theoretical_pnl']:+6.1f}")

    # Check for drift calibration
    print(f"\n\n⚙️  DRIFT CALIBRATION CHECK:")
    print(f"-" * 70)
    print("Searching for v2 drift calibration events in logs...")

else:
    print("\nNo outcomes checked yet (markets may still be open)")

print("\n" + "=" * 70)
