#!/usr/bin/env python3
"""Analyze why faded edges changed from Feb 12 to now"""

import pandas as pd
from datetime import datetime
import pytz

# Read all skipped trades
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter to contrarian bets only
contrarian = df[df['skip_reason'] == 'Contrarian Bet'].copy()

print("\n" + "="*80)
print("🔍 ANALYZING FADED EDGE EVOLUTION")
print("="*80 + "\n")

# Split by date
feb_12 = contrarian[contrarian['timestamp'].dt.date == pd.to_datetime('2026-02-12').date()]
feb_4_11 = contrarian[(contrarian['timestamp'].dt.date >= pd.to_datetime('2026-02-04').date()) &
                       (contrarian['timestamp'].dt.date <= pd.to_datetime('2026-02-11').date())]
feb_13 = contrarian[contrarian['timestamp'].dt.date == pd.to_datetime('2026-02-13').date()]

print(f"📅 DATE BREAKDOWN:")
print(f"  Feb 4-11:  {len(feb_4_11):4d} contrarian bets")
print(f"  Feb 12:    {len(feb_12):4d} contrarian bets")
print(f"  Feb 13:    {len(feb_13):4d} contrarian bets")
print(f"  Total:     {len(contrarian):4d} contrarian bets")

def analyze_period(data, label):
    """Analyze edge characteristics for a period"""
    if len(data) == 0:
        print(f"\n⚠️ No data for {label}")
        return

    print(f"\n" + "="*80)
    print(f"📊 {label}")
    print("="*80)

    # Original edge (what bot calculated)
    print(f"\n🔢 ORIGINAL Edge (contrarian side):")
    print(f"  Mean:   {data['best_edge_pct'].mean():+7.2f}%")
    print(f"  Median: {data['best_edge_pct'].median():+7.2f}%")
    print(f"  Min:    {data['best_edge_pct'].min():+7.2f}%")
    print(f"  Max:    {data['best_edge_pct'].max():+7.2f}%")

    # Calculate faded edge (opposite side)
    # If bot wanted YES (best_edge_side='yes'), faded edge is NO edge
    # If bot wanted NO (best_edge_side='no'), faded edge is YES edge
    data['faded_edge'] = data.apply(
        lambda row: row['no_edge_pct'] if row['best_edge_side'] == 'yes' else row['yes_edge_pct'],
        axis=1
    )

    print(f"\n🔄 FADED Edge (opposite side):")
    print(f"  Mean:   {data['faded_edge'].mean():+7.2f}%")
    print(f"  Median: {data['faded_edge'].median():+7.2f}%")
    print(f"  Min:    {data['faded_edge'].min():+7.2f}%")
    print(f"  Max:    {data['faded_edge'].max():+7.2f}%")

    # Market prices
    print(f"\n💰 MARKET PRICES:")
    print(f"  YES price - Mean: ${data['yes_market_price'].mean():.3f}, Median: ${data['yes_market_price'].median():.3f}")
    print(f"  NO price  - Mean: ${data['no_market_price'].mean():.3f}, Median: ${data['no_market_price'].median():.3f}")

    # Probabilities
    print(f"\n🎲 BOT PROBABILITIES:")
    print(f"  YES prob - Mean: {data['yes_expected_prob'].mean():.3f}, Median: {data['yes_expected_prob'].median():.3f}")
    print(f"  NO prob  - Mean: {data['no_expected_prob'].mean():.3f}, Median: {data['no_expected_prob'].median():.3f}")

    # Direction breakdown
    print(f"\n🧭 MOMENTUM DIRECTION:")
    print(data['momentum_direction'].value_counts())

    print(f"\n📍 CONTRARIAN BET DIRECTION:")
    print(data['best_edge_side'].value_counts())

    # Symbol breakdown
    print(f"\n💎 BY SYMBOL:")
    for symbol in data['symbol'].unique():
        symbol_data = data[data['symbol'] == symbol]
        symbol_faded_avg = symbol_data['faded_edge'].mean()
        print(f"  {symbol:3s}: {len(symbol_data):4d} trades, avg faded edge: {symbol_faded_avg:+7.2f}%")

    return data

# Analyze each period
data_feb_4_11 = analyze_period(feb_4_11, "FEB 4-11 (Early Period)")
data_feb_12 = analyze_period(feb_12, "FEB 12 (Reference Day - Should be -22.6% avg)")
data_feb_13 = analyze_period(feb_13, "FEB 13 (Today - Currently seeing -110% avg)")

# Compare key metrics
print("\n" + "="*80)
print("📈 COMPARISON SUMMARY")
print("="*80 + "\n")

periods = [
    ("Feb 4-11", data_feb_4_11),
    ("Feb 12", data_feb_12),
    ("Feb 13", data_feb_13)
]

print(f"{'Period':<15} {'Count':>8} {'Orig Edge':>12} {'Faded Edge':>13} {'YES Price':>11} {'NO Price':>10}")
print("-" * 80)

for label, data in periods:
    if data is not None and len(data) > 0:
        orig_edge_avg = data['best_edge_pct'].mean()
        faded_edge_avg = data['faded_edge'].mean()
        yes_price_avg = data['yes_market_price'].mean()
        no_price_avg = data['no_market_price'].mean()

        print(f"{label:<15} {len(data):8d} {orig_edge_avg:+11.2f}% {faded_edge_avg:+12.2f}% ${yes_price_avg:9.3f} ${no_price_avg:8.3f}")

print("\n" + "="*80 + "\n")
