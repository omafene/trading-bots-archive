#!/usr/bin/env python3
"""
Two analyses:
1. Fine-grained timing (1-min buckets) to determine if 6-min window is safe
2. Low-momentum backfill: fetch Kalshi settlement for 0.20-0.30 momentum trades
   to determine if threshold can be safely lowered
"""

import pandas as pd
import numpy as np
import re
import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, '/root/kalshi_15m_bot')
from kalshi_client import KalshiClient
from config_loader import load_config_with_env

# ─────────────────────────────────────────────
# PART 1: FINE-GRAINED TIMING ANALYSIS
# ─────────────────────────────────────────────
print("=" * 65)
print("PART 1: TIMING — Win Rate by 1-min bucket (skipped trades)")
print("=" * 65)

df = pd.read_csv('/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv')
df = df[df['outcome_checked'] == True].copy()
df['won'] = df['would_have_won'].astype(str).map({'True': True, 'False': False})
df['minutes_to_close'] = pd.to_numeric(df['minutes_to_close'], errors='coerce')
df['best_edge_pct'] = pd.to_numeric(df['best_edge_pct'], errors='coerce')
df['momentum_abs'] = pd.to_numeric(df['momentum_pct'], errors='coerce').abs()
df['yes_expected_prob'] = pd.to_numeric(df['yes_expected_prob'], errors='coerce')
df['entry_price'] = pd.to_numeric(df['yes_market_price'], errors='coerce')

# Filter to the quality bar that matches actual bot trades:
# edge > 15%, entry < 0.50, momentum passed (>=0.30), in 0-10 min window
quality = df[
    (df['best_edge_pct'] >= 15) &
    (df['entry_price'] <= 0.50) &
    (df['momentum_abs'] >= 0.30) &
    (df['minutes_to_close'] >= 0) &
    (df['minutes_to_close'] <= 10)
].copy()

print(f"\nQuality-filtered trades (edge>=15%, entry<=50c, mom>=0.30): {len(quality):,}")
print()
print(f"{'Window':<12} {'WR':>8} {'n':>6} {'note'}")
print("-" * 45)

bins  = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
labels = ['0-1','1-2','2-3','3-4','4-5','5-6','6-7','7-8','8-9','9-10']
quality['bin'] = pd.cut(quality['minutes_to_close'], bins=bins, labels=labels)
g = quality.groupby('bin', observed=True)['won'].agg(['mean', 'count'])

for idx, row in g.iterrows():
    n   = int(row['count'])
    wr  = round(row['mean'] * 100, 1) if n > 0 else 0
    note = ''
    if idx in ('4-5', '5-6', '6-7'):
        note = '← region of interest'
    if n < 20:
        note += ' (low n)'
    print(f"  {idx} min  {wr:>6.1f}%  {n:>6}  {note}")

# Also show without momentum filter to include low-momentum data
print()
print("Same but WITHOUT momentum filter (includes all momentum levels):")
quality2 = df[
    (df['best_edge_pct'] >= 15) &
    (df['entry_price'] <= 0.50) &
    (df['minutes_to_close'] >= 0) &
    (df['minutes_to_close'] <= 10)
].copy()
quality2['bin'] = pd.cut(quality2['minutes_to_close'], bins=bins, labels=labels)
g2 = quality2.groupby('bin', observed=True)['won'].agg(['mean', 'count'])
for idx, row in g2.iterrows():
    n  = int(row['count'])
    wr = round(row['mean'] * 100, 1) if n > 0 else 0
    note = '← region of interest' if idx in ('4-5','5-6','6-7') else ''
    if n < 20: note += ' (low n)'
    print(f"  {idx} min  {wr:>6.1f}%  {n:>6}  {note}")


# ─────────────────────────────────────────────
# PART 2: LOW MOMENTUM BACKFILL FROM KALSHI
# ─────────────────────────────────────────────
print()
print("=" * 65)
print("PART 2: MOMENTUM THRESHOLD — Backfill Kalshi outcomes")
print("        for trades skipped at momentum 0.20–0.30")
print("=" * 65)

LOG_PATH = '/root/kalshi_15m_bot/logs/edge_bot.log'

print(f"\nParsing log for Low Momentum skips (0.20–0.30)...")

# Parse: timestamp, ticker, momentum value, minutes_to_close
# Line example:
#   2026-02-24 06:40:01,746 - edge_detector_advanced - INFO - ⏭️ KXXRP15M-26FEB240645-45 skip: Low Momentum (0.284 < 0.300)
pattern = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?'
    r'(KX[\w-]+)\s+skip: Low Momentum \(([0-9.]+) < ([0-9.]+)\)'
)

records = defaultdict(list)  # ticker → list of (ts, momentum, mtc)

with open(LOG_PATH, 'r') as f:
    for line in f:
        m = pattern.search(line)
        if not m:
            continue
        ts_str, ticker, mom_val, threshold = m.groups()
        mom = float(mom_val)
        if mom < 0.20:
            continue  # only care about 0.20-0.30

        ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
        # Parse close time from ticker
        cm = re.search(r'(\d{4})-\d+$', ticker)
        if not cm:
            continue
        hhmm = cm.group(1)
        close_total = int(hhmm[:2]) * 60 + int(hhmm[2:])
        trade_total = ts.hour * 60 + ts.minute + ts.second / 60
        mtc = close_total - trade_total
        if not (0 <= mtc <= 10):
            continue

        records[ticker].append((ts, mom, mtc))

print(f"Unique tickers with momentum 0.20–0.30: {len(records)}")

# For each ticker, take the observation with the HIGHEST momentum
# (most likely to trade if threshold was lowered)
candidates = {}
for ticker, obs in records.items():
    best = max(obs, key=lambda x: x[1])  # highest momentum
    candidates[ticker] = {'ts': best[0], 'momentum': best[1], 'mtc': best[2]}

# Bucket by momentum
buckets = {'0.20-0.23': [], '0.23-0.25': [], '0.25-0.27': [], '0.27-0.28': [], '0.28-0.30': []}
for ticker, info in candidates.items():
    m = info['momentum']
    if   0.20 <= m < 0.23: buckets['0.20-0.23'].append(ticker)
    elif 0.23 <= m < 0.25: buckets['0.23-0.25'].append(ticker)
    elif 0.25 <= m < 0.27: buckets['0.25-0.27'].append(ticker)
    elif 0.27 <= m < 0.28: buckets['0.27-0.28'].append(ticker)
    elif 0.28 <= m <= 0.30: buckets['0.28-0.30'].append(ticker)

print("Distribution by momentum bucket:")
for b, tickers in buckets.items():
    print(f"  {b}: {len(tickers)} tickers")

# Fetch Kalshi outcomes
print(f"\nFetching Kalshi settlement results...")
config = load_config_with_env()
client = KalshiClient(config)

# Also load existing skipped trades to check if we already have some outcomes
# Check which tickers we need to fetch (to avoid re-fetching)
results = {}
total = len(candidates)
fetched = 0
errors  = 0

for i, (ticker, info) in enumerate(candidates.items()):
    if i % 50 == 0 and i > 0:
        print(f"  Progress: {i}/{total} ({fetched} fetched, {errors} errors)...")

    result = client.get_market(ticker)
    if result:
        market = result.get('market', result)
        status = market.get('status', '')
        outcome = market.get('result', None)
        if status == 'finalized' and outcome in ('yes', 'no'):
            # Determine if the bot's intended trade (YES momentum = YES bet) would have won
            # For UP markets with momentum UP: bot would bet YES
            # We need to know what side the bot would have bet
            # The ticker is an "up" market, momentum was positive → bot would bet YES
            won = (outcome == 'yes')
            results[ticker] = {
                'outcome': outcome,
                'won': won,
                'momentum': info['momentum'],
                'mtc': info['mtc'],
                'ts': info['ts']
            }
            fetched += 1
    else:
        errors += 1

print(f"  Done: {fetched} settled results, {errors} errors, {total - fetched - errors} not finalized")

if not results:
    print("No results to analyze.")
    sys.exit(0)

res_df = pd.DataFrame(results.values())
res_df['mom_bucket'] = pd.cut(
    res_df['momentum'],
    bins=[0.20, 0.23, 0.25, 0.27, 0.28, 0.30],
    labels=['0.20-0.23', '0.23-0.25', '0.25-0.27', '0.27-0.28', '0.28-0.30'],
    include_lowest=True
)

print()
print(f"{'Momentum':<14} {'WR':>8} {'n':>6}  {'vs current 0.30+ threshold'}")
print("-" * 60)

# Also show current 0.30+ baseline from actual trades
out = pd.read_csv('/root/kalshi_15m_bot/data/position_outcomes.csv')
out['won'] = out['won'].astype(str).map({'True': True, 'False': False})
baseline_wr = out['won'].mean() * 100
baseline_n  = len(out)
print(f"  {'≥0.30 (actual)':<14} {baseline_wr:>6.1f}%  {baseline_n:>6}  ← current bot baseline")
print()

g = res_df.groupby('mom_bucket', observed=True)['won'].agg(['mean', 'count'])
for idx, row in g.iterrows():
    n  = int(row['count'])
    wr = round(row['mean'] * 100, 1) if n > 0 else 0
    delta = wr - baseline_wr
    arrow = f"{'↑' if delta > 0 else '↓'} {abs(delta):.1f}pp vs baseline"
    low_n = ' (low n)' if n < 15 else ''
    print(f"  {str(idx):<14} {wr:>6.1f}%  {n:>6}  {arrow}{low_n}")

print()
print("MTC breakdown for 0.28-0.30 range (timing quality):")
near_thresh = res_df[res_df['momentum'] >= 0.28]
if len(near_thresh) > 0:
    bins2 = [0,1,2,3,4,5,6,7]; labels2 = ['0-1','1-2','2-3','3-4','4-5','5-6','6-7']
    near_thresh = near_thresh.copy()
    near_thresh['tbin'] = pd.cut(near_thresh['mtc'], bins=bins2, labels=labels2)
    g3 = near_thresh.groupby('tbin', observed=True)['won'].agg(['mean','count'])
    for idx, row in g3.iterrows():
        n = int(row['count'])
        if n > 0:
            print(f"  {idx} min  WR={round(row['mean']*100,1)}%  n={n}")

print()
print("Done.")
