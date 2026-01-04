#!/usr/bin/env python3
"""Analyze all unique contrarian trades from today"""

import pandas as pd
from datetime import datetime, date
import pytz

# Read CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter to today only
utc = pytz.UTC
today = date.today()
today_data = df[df['timestamp'].dt.date == today].copy()

print("\n" + "="*80)
print(f"📊 CONTRARIAN TRADE ANALYSIS - {today}")
print("="*80 + "\n")

print(f"Total trades today: {len(today_data):,}")

# Find all contrarian-related trades
contrarian_today = today_data[
    (today_data['skip_reason'] == 'Contrarian Bet') |
    (today_data['skip_reason'].str.contains('Faded edge', na=False)) |
    (today_data['skip_reason'].str.contains('contrarian', case=False, na=False))
]

print(f"Contrarian-related trades: {len(contrarian_today):,}")

if len(contrarian_today) == 0:
    print("\n⚠️ No contrarian trades recorded in CSV today")
    print("\nPossible reasons:")
    print("  1. Markets haven't triggered contrarian conditions today")
    print("  2. Contrarian bets are being detected but faded (not logged as 'Contrarian Bet')")
    print("  3. Trade data hasn't been written to CSV yet")

    # Check for any skip reasons that mention contrarian
    print("\n📋 All skip reasons from today:")
    print(today_data['skip_reason'].value_counts())

    print("\n" + "="*80 + "\n")
    exit(0)

# Analyze contrarian trades
print(f"\n📋 SKIP REASON BREAKDOWN:")
print(contrarian_today['skip_reason'].value_counts())

# Group by unique market
print(f"\n🎯 UNIQUE MARKETS:")
unique_markets = contrarian_today.groupby('ticker').agg({
    'timestamp': 'first',
    'symbol': 'first',
    'market_type': 'first',
    'threshold': 'first',
    'skip_reason': 'first',
    'best_edge_side': 'first',
    'best_edge_pct': 'first',
    'momentum_direction': 'first',
    'outcome_checked': 'first',
    'actual_outcome': 'first',
    'would_have_won': 'first',
    'theoretical_pnl': 'first'
}).reset_index()

print(f"Total unique markets: {len(unique_markets)}\n")

# Separate by outcome status
with_outcomes = unique_markets[unique_markets['outcome_checked'] == True]
without_outcomes = unique_markets[unique_markets['outcome_checked'] == False]

print(f"Markets with outcomes: {len(with_outcomes)}")
print(f"Markets still pending: {len(without_outcomes)}")

if len(with_outcomes) > 0:
    print("\n" + "="*80)
    print("✅ CONTRARIAN TRADES WITH OUTCOMES")
    print("="*80 + "\n")

    # Calculate faded win rate (opposite of what bot wanted)
    with_outcomes['faded_would_win'] = ~with_outcomes['would_have_won']

    # Original contrarian bet performance
    original_won = with_outcomes['would_have_won'].sum()
    original_wr = (original_won / len(with_outcomes)) * 100
    original_pnl = with_outcomes['theoretical_pnl'].sum()

    print(f"📉 ORIGINAL Contrarian Bets (what bot calculated):")
    print(f"  Wins: {original_won} / {len(with_outcomes)}")
    print(f"  Win Rate: {original_wr:.1f}%")
    print(f"  Theoretical P&L: ${original_pnl:+,.2f}")

    # Faded performance (opposite)
    faded_won = with_outcomes['faded_would_win'].sum()
    faded_wr = (faded_won / len(with_outcomes)) * 100
    faded_pnl = -original_pnl

    print(f"\n📈 FADED (opposite side):")
    print(f"  Wins: {faded_won} / {len(with_outcomes)}")
    print(f"  Win Rate: {faded_wr:.1f}%")
    print(f"  Theoretical P&L: ${faded_pnl:+,.2f}")

    # Show each trade
    print(f"\n" + "-"*80)
    print(f"DETAILED BREAKDOWN:")
    print(f"-"*80 + "\n")

    for idx, row in with_outcomes.iterrows():
        outcome_emoji = "✅" if row['actual_outcome'] == 'yes' else "❌"
        original_result = "WON" if row['would_have_won'] else "LOST"
        faded_result = "LOST" if row['would_have_won'] else "WON"

        print(f"{outcome_emoji} {row['ticker']}")
        print(f"   Symbol: {row['symbol']} | Type: {row['market_type']} | Threshold: {row['threshold']}")
        print(f"   Momentum: {row['momentum_direction'].upper()} | Bot wanted: {row['best_edge_side'].upper()} (edge: {row['best_edge_pct']:+.1f}%)")
        print(f"   Actual outcome: {row['actual_outcome'].upper()}")
        print(f"   Original bet would have: {original_result} (P&L: ${row['theoretical_pnl']:+.2f})")
        print(f"   Faded bet would have: {faded_result} (P&L: ${-row['theoretical_pnl']:+.2f})")
        print(f"   Skip reason: {row['skip_reason']}")
        print()

    # By symbol breakdown
    print("="*80)
    print("BY SYMBOL:")
    print("="*80 + "\n")

    for symbol in with_outcomes['symbol'].unique():
        symbol_data = with_outcomes[with_outcomes['symbol'] == symbol]
        symbol_faded_won = symbol_data['faded_would_win'].sum()
        symbol_faded_wr = (symbol_faded_won / len(symbol_data)) * 100
        symbol_faded_pnl = -symbol_data['theoretical_pnl'].sum()

        print(f"{symbol}:")
        print(f"  Trades: {len(symbol_data)}")
        print(f"  Faded WR: {symbol_faded_wr:.1f}%")
        print(f"  Faded P&L: ${symbol_faded_pnl:+,.2f}")
        print()

else:
    print("\n⚠️ No outcomes available yet for today's contrarian trades")
    print("Markets are likely still open or haven't settled yet")

if len(without_outcomes) > 0:
    print("\n" + "="*80)
    print("⏳ PENDING CONTRARIAN TRADES (No outcome yet)")
    print("="*80 + "\n")

    for idx, row in without_outcomes.head(10).iterrows():
        print(f"⏳ {row['ticker']}")
        print(f"   {row['symbol']} | Momentum: {row['momentum_direction']} | Bot wanted: {row['best_edge_side']} ({row['best_edge_pct']:+.1f}%)")
        print(f"   Reason: {row['skip_reason']}")
        print()

print("="*80 + "\n")
