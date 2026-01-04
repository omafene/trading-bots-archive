#!/usr/bin/env python3
"""Analyze why fade trades aren't being taken"""

import pandas as pd
from datetime import datetime, timedelta
import pytz

# Read CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter recent
utc = pytz.UTC
three_hours_ago = datetime.now(utc) - timedelta(hours=3)
recent = df[df['timestamp'] >= three_hours_ago].copy()

# Look at contrarian and faded trades
contrarian = recent[recent['skip_reason'] == 'Contrarian Bet']
faded_negative = recent[recent['skip_reason'].str.contains('Faded edge too negative', na=False)]

print("\n" + "="*80)
print("🔍 FADE MODE ISSUE ANALYSIS")
print("="*80 + "\n")

print(f"Time range: Past 3 hours")
print(f"Total skipped: {len(recent):,}")
print(f"Contrarian Bets detected: {len(contrarian)}")
print(f"Faded but rejected (edge too negative): {len(faded_negative)}")

if len(faded_negative) > 0:
    print(f"\n" + "="*80)
    print("❌ FADED TRADES REJECTED (Edge Too Negative)")
    print("="*80 + "\n")

    print("Current threshold: min_fade_edge = -80.0%")
    print(f"Rejected faded trades: {len(faded_negative)}\n")

    # Parse edge from skip reason
    edges = []
    for reason in faded_negative['skip_reason']:
        try:
            # Extract edge from "Faded edge too negative (-108.7% < -80.0%)"
            edge_str = reason.split('(')[1].split('%')[0]
            edges.append(float(edge_str))
        except:
            pass

    if edges:
        print(f"Faded edge statistics:")
        print(f"  Min:    {min(edges):.1f}%")
        print(f"  Max:    {max(edges):.1f}%")
        print(f"  Mean:   {sum(edges)/len(edges):.1f}%")
        print(f"  Median: {sorted(edges)[len(edges)//2]:.1f}%")

        # Count how many would pass different thresholds
        thresholds = [-80, -90, -100, -110, -120, -130, -140, -150]
        print(f"\n📊 Trades that would pass at different thresholds:")
        for thresh in thresholds:
            count = sum(1 for e in edges if e >= thresh)
            pct = (count / len(edges)) * 100
            print(f"  min_fade_edge = {thresh:4d}%: {count:3d} trades ({pct:5.1f}%)")

# Check historical contrarian fade performance
print(f"\n" + "="*80)
print("📈 HISTORICAL CONTRARIAN BET OUTCOMES")
print("="*80 + "\n")

all_contrarian = df[df['skip_reason'] == 'Contrarian Bet'].copy()
contrarian_checked = all_contrarian[all_contrarian['outcome_checked'] == True]

if len(contrarian_checked) > 0:
    print(f"Total contrarian bets: {len(all_contrarian):,}")
    print(f"Outcomes verified: {len(contrarian_checked):,}")

    # If we had taken the ORIGINAL contrarian bet (what bot wanted)
    original_winners = contrarian_checked[contrarian_checked['would_have_won'] == True]
    original_wr = (len(original_winners) / len(contrarian_checked)) * 100
    original_pnl = contrarian_checked['theoretical_pnl'].sum()

    print(f"\n📉 If we took ORIGINAL contrarian bets (what bot calculated):")
    print(f"  Win rate: {original_wr:.1f}%")
    print(f"  P&L: ${original_pnl:+,.2f}")

    # If we FADED (took opposite)
    contrarian_checked['faded_would_win'] = ~contrarian_checked['would_have_won']
    faded_winners = contrarian_checked[contrarian_checked['faded_would_win'] == True]
    faded_wr = (len(faded_winners) / len(contrarian_checked)) * 100
    faded_pnl = -contrarian_checked['theoretical_pnl'].sum()  # Flip P&L

    print(f"\n📈 If we FADED (took opposite side):")
    print(f"  Win rate: {faded_wr:.1f}%")
    print(f"  P&L: ${faded_pnl:+,.2f}")

    # Analyze by edge ranges
    print(f"\n📊 Fade performance by edge bucket:")
    contrarian_checked['best_edge_rounded'] = (contrarian_checked['best_edge_pct'] // 20) * 20

    for edge_bucket in sorted(contrarian_checked['best_edge_rounded'].unique()):
        bucket_data = contrarian_checked[contrarian_checked['best_edge_rounded'] == edge_bucket]
        bucket_faded_wr = (bucket_data['faded_would_win'].sum() / len(bucket_data)) * 100
        bucket_faded_pnl = -bucket_data['theoretical_pnl'].sum()

        print(f"  Edge {edge_bucket:+4.0f}% to {edge_bucket+20:+4.0f}%: "
              f"{len(bucket_data):3d} trades, {bucket_faded_wr:5.1f}% WR, ${bucket_faded_pnl:+,.2f}")

else:
    print("No historical contrarian bet outcomes available")

print("\n" + "="*80)
print("💡 RECOMMENDATION")
print("="*80 + "\n")

if edges and len(contrarian_checked) > 0:
    avg_faded_edge = sum(edges) / len(edges)

    print(f"Current situation:")
    print(f"  • Fade mode is ACTIVE and detecting contrarians")
    print(f"  • Faded trades have average edge: {avg_faded_edge:.1f}%")
    print(f"  • Current min_fade_edge threshold: -80.0%")
    print(f"  • Historical fade win rate: {faded_wr:.1f}%")
    print(f"  • Historical fade P&L: ${faded_pnl:+,.2f}")

    if faded_wr > 50 and faded_pnl > 0:
        suggested_threshold = sorted(edges)[int(len(edges) * 0.75)]  # 75th percentile
        print(f"\n✅ Fading works! Consider lowering min_fade_edge to: {suggested_threshold:.0f}%")
        print(f"   This would allow ~75% of current faded trades")
    else:
        print(f"\n⚠️ Historical fade performance is poor")
        print(f"   Keep current threshold or disable fade mode")

print("\n" + "="*80 + "\n")
