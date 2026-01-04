#!/usr/bin/env python3
"""
Skipped trades analysis for BNB, DOGE, HYPE — March 21-23, 2026
Focuses on: what would have won if filters hadn't blocked them?
"""
import pandas as pd
import numpy as np
from datetime import datetime

df = pd.read_csv('data/negative_edges/skipped_trades.csv', low_memory=False)
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

# Extract real symbol from ticker prefix (KXBNB15M → BNB, etc.)
def extract_sym(ticker):
    for s in ['BNB', 'DOGE', 'HYPE', 'BTC', 'ETH', 'SOL', 'XRP']:
        if f'KX{s}' in str(ticker):
            return s
    return ticker
df['sym'] = df['ticker'].apply(extract_sym)

# Filter: target symbols, target date range, outcome known
mask = (
    df['sym'].isin(['BNB', 'DOGE', 'HYPE']) &
    (df['timestamp'] >= '2026-03-21') &
    (df['timestamp'] < '2026-03-24') &
    (df['outcome_checked'] == True)
)
df = df[mask].copy()
df['symbol'] = df['sym']  # use extracted symbol going forward
print(f"Total rows (with outcomes): {len(df):,}")

# Deduplicate: keep the row closest to entry (largest minutes_to_close per ticker)
# This represents "best chance at entry" per market window
df_best = df.sort_values('minutes_to_close', ascending=False).drop_duplicates(
    subset=['ticker', 'best_edge_side'], keep='first'
).copy()
print(f"Unique ticker+side opportunities: {len(df_best):,}")
print()

# ─────────────────────────────────────────────────────────
# 1. OVERALL SUMMARY
# ─────────────────────────────────────────────────────────
print("=" * 80)
print("1. OVERALL SUMMARY  (one best entry per market window per side)")
print("=" * 80)
total = len(df_best)
wins = df_best['would_have_won'].sum()
losses = total - wins
win_rate = wins / total * 100 if total else 0
total_pnl = df_best['theoretical_pnl'].sum()
avg_pnl = df_best['theoretical_pnl'].mean()
print(f"  Opportunities : {total}")
print(f"  Would have WON: {wins}  ({win_rate:.1f}%)")
print(f"  Would have LOST:{losses}  ({100-win_rate:.1f}%)")
print(f"  Total theo P&L: ${total_pnl:.2f}  (avg ${avg_pnl:.2f}/trade)")
print()

# ─────────────────────────────────────────────────────────
# 2. BY SYMBOL
# ─────────────────────────────────────────────────────────
print("=" * 80)
print("2. BY SYMBOL")
print("=" * 80)
print(f"{'Symbol':<8} {'Opps':>6} {'Wins':>6} {'WR%':>7} {'TotalPnL':>10} {'AvgPnL':>9}")
print("-" * 80)
for sym, g in df_best.groupby('symbol'):
    w = g['would_have_won'].sum()
    wr = w / len(g) * 100
    tpnl = g['theoretical_pnl'].sum()
    apnl = g['theoretical_pnl'].mean()
    print(f"{sym:<8} {len(g):>6} {w:>6} {wr:>6.1f}% {tpnl:>10.2f} {apnl:>9.2f}")
print()

# ─────────────────────────────────────────────────────────
# 3. BY SKIP REASON
# ─────────────────────────────────────────────────────────
print("=" * 80)
print("3. BY SKIP REASON")
print("=" * 80)
print(f"{'Skip Reason':<35} {'Opps':>6} {'Wins':>6} {'WR%':>7} {'TotalPnL':>10} {'AvgPnL':>9}")
print("-" * 80)
for reason, g in df_best.groupby('skip_reason'):
    w = g['would_have_won'].sum()
    wr = w / len(g) * 100
    tpnl = g['theoretical_pnl'].sum()
    apnl = g['theoretical_pnl'].mean()
    print(f"{str(reason):<35} {len(g):>6} {w:>6} {wr:>6.1f}% {tpnl:>10.2f} {apnl:>9.2f}")
print()

# ─────────────────────────────────────────────────────────
# 4. BY SYMBOL × SKIP REASON
# ─────────────────────────────────────────────────────────
print("=" * 80)
print("4. BY SYMBOL × SKIP REASON")
print("=" * 80)
print(f"{'Symbol':<8} {'Skip Reason':<35} {'Opps':>6} {'Wins':>6} {'WR%':>7} {'TotalPnL':>10}")
print("-" * 80)
for (sym, reason), g in df_best.groupby(['symbol', 'skip_reason']):
    w = g['would_have_won'].sum()
    wr = w / len(g) * 100
    tpnl = g['theoretical_pnl'].sum()
    print(f"{sym:<8} {str(reason):<35} {len(g):>6} {w:>6} {wr:>6.1f}% {tpnl:>10.2f}")
print()

# ─────────────────────────────────────────────────────────
# 5. CONTRARIAN BETS DETAIL
# ─────────────────────────────────────────────────────────
contrarian = df_best[df_best['skip_reason'] == 'Contrarian Bet'].copy()
if len(contrarian) > 0:
    print("=" * 80)
    print("5. CONTRARIAN BETS — what would have happened if taken?")
    print("   (Bot skipped because it wanted to bet WITH momentum but market only offered AGAINST)")
    print("=" * 80)
    print(f"{'Symbol':<8} {'Direction':<10} {'Best Side':<10} {'Outcome':<10} {'Won?':<6} {'ThrPnL':>8}")
    print("-" * 80)
    # Show a sample
    for _, row in contrarian.sort_values('symbol').iterrows():
        won_str = "✓ WIN" if row['would_have_won'] else "✗ LOSS"
        print(f"{row['symbol']:<8} {str(row['momentum_direction']):<10} {str(row['best_edge_side']):<10} "
              f"{str(row['actual_outcome']):<10} {won_str:<6} ${row['theoretical_pnl']:>7.2f}")
    print()
    # Summary
    cw = contrarian['would_have_won'].sum()
    print(f"  Contrarian wins: {cw}/{len(contrarian)} ({cw/len(contrarian)*100:.1f}%) — "
          f"Total P&L ${contrarian['theoretical_pnl'].sum():.2f}")
    print()

# ─────────────────────────────────────────────────────────
# 6. LOW MOMENTUM / LOW R² DETAIL
# ─────────────────────────────────────────────────────────
low_filters = df_best[df_best['skip_reason'].isin(['Low Momentum', 'Low R²'])].copy()
if len(low_filters) > 0:
    print("=" * 80)
    print("6. LOW MOMENTUM / LOW R² — momentum direction vs. actual outcome")
    print("=" * 80)
    print(f"{'Symbol':<8} {'Filter':<15} {'MomDir':<8} {'MomPct':>8} {'R²':>6} {'BestSide':<10} {'Outcome':<10} {'Won?':<6} {'ThrPnL':>8}")
    print("-" * 80)
    for _, row in low_filters.sort_values(['symbol', 'skip_reason']).iterrows():
        won_str = "✓" if row['would_have_won'] else "✗"
        print(f"{row['symbol']:<8} {str(row['skip_reason']):<15} {str(row['momentum_direction']):<8} "
              f"{row['momentum_pct']:>7.3f}% {row.get('trend_strength', 0):>6.2f} "
              f"{str(row['best_edge_side']):<10} {str(row['actual_outcome']):<10} {won_str:<6} ${row['theoretical_pnl']:>7.2f}")
    lw = low_filters['would_have_won'].sum()
    print(f"\n  Wins: {lw}/{len(low_filters)} ({lw/len(low_filters)*100:.1f}%)  Total P&L ${low_filters['theoretical_pnl'].sum():.2f}")
    print()

# ─────────────────────────────────────────────────────────
# 7. WINNING OPPORTUNITIES MISSED
# ─────────────────────────────────────────────────────────
missed_wins = df_best[df_best['would_have_won'] == True].sort_values('theoretical_pnl', ascending=False)
if len(missed_wins) > 0:
    print("=" * 80)
    print("7. ALL WINNING OPPORTUNITIES MISSED (sorted by P&L)")
    print("=" * 80)
    print(f"{'Ticker':<35} {'Symbol':<6} {'Side':<5} {'SkipReason':<30} {'MomDir':<8} {'PnL':>8}")
    print("-" * 80)
    for _, row in missed_wins.iterrows():
        print(f"{str(row['ticker']):<35} {row['symbol']:<6} {str(row['best_edge_side']):<5} "
              f"{str(row['skip_reason']):<30} {str(row['momentum_direction']):<8} ${row['theoretical_pnl']:>7.2f}")
    print(f"\n  Total missed profit: ${missed_wins['theoretical_pnl'].sum():.2f} across {len(missed_wins)} trades")
    print()

# ─────────────────────────────────────────────────────────
# 8. KEY INSIGHT: Would relaxing filters help?
# ─────────────────────────────────────────────────────────
print("=" * 80)
print("8. KEY INSIGHT: Filter relaxation impact")
print("=" * 80)
for sym in ['BNB', 'DOGE', 'HYPE']:
    sym_df = df_best[df_best['symbol'] == sym]
    if len(sym_df) == 0:
        continue
    wins_sym = sym_df['would_have_won'].sum()
    wr = wins_sym / len(sym_df) * 100
    pnl = sym_df['theoretical_pnl'].sum()
    print(f"\n  {sym}: {wins_sym}/{len(sym_df)} would-win ({wr:.1f}% WR), ${pnl:.2f} total")
    for reason, g in sym_df.groupby('skip_reason'):
        rw = g['would_have_won'].sum()
        rwr = rw / len(g) * 100
        rpnl = g['theoretical_pnl'].sum()
        verdict = "✓ PROFITABLE" if rpnl > 0 and rwr > 50 else ("⚠ MARGINAL" if rwr > 45 else "✗ LOSING")
        print(f"    {verdict}  [{reason}]: {rw}/{len(g)} ({rwr:.1f}% WR) = ${rpnl:.2f}")

print()
print("=" * 80)
print("END OF ANALYSIS")
print("=" * 80)
