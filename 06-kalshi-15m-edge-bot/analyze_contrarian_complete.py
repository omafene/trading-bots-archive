#!/usr/bin/env python3
"""Complete contrarian analysis: skipped and unskipped, with outcomes from Kalshi API"""

import pandas as pd
from datetime import datetime, date, timedelta
import pytz
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from outcome_checker import OutcomeChecker
from negative_edge_tracker import NegativeEdgeTracker

print("\n" + "="*80)
print("🔍 COMPLETE CONTRARIAN ANALYSIS - SKIPPED & UNSKIPPED")
print("="*80 + "\n")

# Load config and API client
config = load_config_with_env("config_15m.yaml")
client = KalshiClient(config)

# Read CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Identify contrarian pattern: momentum ≠ bet direction
df['is_contrarian_pattern'] = (
    ((df['momentum_direction'] == 'up') & (df['best_edge_side'] == 'no')) |
    ((df['momentum_direction'] == 'down') & (df['best_edge_side'] == 'yes'))
)

# Focus on good data range (past 24 hours)
utc = pytz.UTC
twenty_four_hours_ago = datetime.now(utc) - timedelta(hours=24)
recent = df[df['timestamp'] >= twenty_four_hours_ago].copy()

print(f"📅 Analysis Period: Past 24 hours")
print(f"Total trades: {len(recent):,}")

# Get contrarian trades
contrarian = recent[recent['is_contrarian_pattern'] == True].copy()
print(f"Contrarian pattern trades: {len(contrarian):,}\n")

# Group by unique ticker
print("🎯 Checking outcomes for unique markets...")
unique_markets = contrarian.drop_duplicates('ticker')
print(f"Unique contrarian markets: {len(unique_markets)}")

# Check outcomes via API
tracker = NegativeEdgeTracker(data_dir="data/negative_edges")
outcome_checker = OutcomeChecker(client, tracker)

print("\n📡 Fetching outcomes from Kalshi API...")
checked_count = 0
for idx, row in unique_markets.iterrows():
    ticker = row['ticker']

    # Only check if not already checked
    if pd.isna(row['outcome_checked']) or not row['outcome_checked']:
        outcome = outcome_checker.get_market_result(ticker)
        if outcome:
            tracker.update_outcome(ticker, outcome)
            checked_count += 1

print(f"✅ Checked {checked_count} new outcomes\n")

# Reload data
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['is_contrarian_pattern'] = (
    ((df['momentum_direction'] == 'up') & (df['best_edge_side'] == 'no')) |
    ((df['momentum_direction'] == 'down') & (df['best_edge_side'] == 'yes'))
)

recent = df[df['timestamp'] >= twenty_four_hours_ago].copy()
contrarian = recent[recent['is_contrarian_pattern'] == True].copy()

# Analyze outcomes
with_outcomes = contrarian[contrarian['outcome_checked'] == True]
without_outcomes = contrarian[contrarian['outcome_checked'] == False]

print("="*80)
print("📊 CONTRARIAN TRADE RESULTS (Past 24h)")
print("="*80 + "\n")

print(f"Total contrarian trades: {len(contrarian):,}")
print(f"With outcomes: {len(with_outcomes):,}")
print(f"Pending: {len(without_outcomes):,}\n")

if len(with_outcomes) > 0:
    # Original (what bot calculated)
    original_won = with_outcomes['would_have_won'].sum()
    original_wr = (original_won / len(with_outcomes)) * 100
    original_pnl = with_outcomes['theoretical_pnl'].sum()

    print("📉 ORIGINAL Contrarian Bets (bot's calculation):")
    print(f"  Win Rate: {original_wr:.1f}% ({original_won}/{len(with_outcomes)})")
    print(f"  Theoretical P&L: ${original_pnl:+,.2f}\n")

    # Faded (opposite side)
    faded_won = len(with_outcomes) - original_won
    faded_wr = (faded_won / len(with_outcomes)) * 100
    faded_pnl = -original_pnl

    print("🔄 FADED (opposite side - momentum aligned):")
    print(f"  Win Rate: {faded_wr:.1f}% ({faded_won}/{len(with_outcomes)})")
    print(f"  Theoretical P&L: ${faded_pnl:+,.2f}\n")

    # By skip reason
    print("="*80)
    print("BY SKIP REASON:")
    print("="*80 + "\n")

    for skip_reason in with_outcomes['skip_reason'].value_counts().index[:5]:
        reason_data = with_outcomes[with_outcomes['skip_reason'] == skip_reason]
        reason_faded_won = len(reason_data) - reason_data['would_have_won'].sum()
        reason_faded_wr = (reason_faded_won / len(reason_data)) * 100
        reason_faded_pnl = -reason_data['theoretical_pnl'].sum()

        print(f"{skip_reason}:")
        print(f"  Count: {len(reason_data)}")
        print(f"  Faded WR: {reason_faded_wr:.1f}%")
        print(f"  Faded P&L: ${reason_faded_pnl:+,.2f}\n")

    # By symbol
    print("="*80)
    print("BY SYMBOL:")
    print("="*80 + "\n")

    for symbol in with_outcomes['symbol'].value_counts().index:
        symbol_data = with_outcomes[with_outcomes['symbol'] == symbol]
        symbol_faded_won = len(symbol_data) - symbol_data['would_have_won'].sum()
        symbol_faded_wr = (symbol_faded_won / len(symbol_data)) * 100
        symbol_faded_pnl = -symbol_data['theoretical_pnl'].sum()

        print(f"{symbol}:")
        print(f"  Count: {len(symbol_data)}")
        print(f"  Faded WR: {symbol_faded_wr:.1f}%")
        print(f"  Faded P&L: ${symbol_faded_pnl:+,.2f}\n")

    # Sample trades
    print("="*80)
    print("SAMPLE CONTRARIAN TRADES (First 10 with outcomes):")
    print("="*80 + "\n")

    for idx, row in with_outcomes.head(10).iterrows():
        outcome_emoji = "✅" if row['actual_outcome'] == 'yes' else "❌"
        faded_won = (row['actual_outcome'] == 'yes' and row['best_edge_side'] == 'no') or \
                    (row['actual_outcome'] == 'no' and row['best_edge_side'] == 'yes')
        faded_result = "WON" if faded_won else "LOST"

        print(f"{outcome_emoji} {row['ticker']}")
        print(f"   {row['symbol']} | Momentum: {row['momentum_direction'].upper()} | Bot wanted: {row['best_edge_side'].upper()}")
        print(f"   Edge: {row['best_edge_pct']:+.1f}% | Outcome: {row['actual_outcome'].upper()}")
        print(f"   Faded would have: {faded_result}")
        print(f"   Skip reason: {row['skip_reason']}\n")

else:
    print("⚠️ No outcomes available yet for past 24h contrarian trades")

print("="*80 + "\n")
