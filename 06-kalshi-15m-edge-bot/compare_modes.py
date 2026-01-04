#!/usr/bin/env python3
"""Compare contrarian-only mode vs normal mode"""

import pandas as pd
from datetime import datetime, timedelta
import pytz

# Read CSV
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Identify contrarian pattern
df['is_contrarian'] = (
    ((df['momentum_direction'] == 'up') & (df['best_edge_side'] == 'no')) |
    ((df['momentum_direction'] == 'down') & (df['best_edge_side'] == 'yes'))
)

# Past 24h with outcomes
utc = pytz.UTC
day_ago = datetime.now(utc) - timedelta(hours=24)
recent = df[(df['timestamp'] >= day_ago) & (df['outcome_checked'] == True)].copy()

print('='*80)
print('CONTRARIAN-ONLY vs NORMAL MODE COMPARISON (Past 24h)')
print('='*80)
print()

# Split into contrarian and non-contrarian
contrarian = recent[recent['is_contrarian'] == True]
non_contrarian = recent[recent['is_contrarian'] == False]

print(f'Total trades with outcomes: {len(recent):,}')
print(f'  Contrarian pattern: {len(contrarian):,}')
print(f'  Non-contrarian: {len(non_contrarian):,}')
print()

# ===== CONTRARIAN-ONLY MODE =====
print('='*80)
print('MODE 1: CONTRARIAN-ONLY (Faded Contrarian Trades Only)')
print('='*80)
print()

contr_faded_won = 0
contr_faded_wr = 0
contr_faded_pnl = 0

if len(contrarian) > 0:
    # Faded performance
    contr_faded_won = len(contrarian) - contrarian['would_have_won'].sum()
    contr_faded_wr = (contr_faded_won / len(contrarian)) * 100
    contr_faded_pnl = -contrarian['theoretical_pnl'].sum()

    print(f'Trades: {len(contrarian):,}')
    print(f'Win Rate: {contr_faded_wr:.1f}%')
    print(f'Total P&L: ${contr_faded_pnl:+,.2f}')
    print(f'Avg per trade: ${contr_faded_pnl/len(contrarian):+.2f}')

# ===== NON-CONTRARIAN TRADES =====
print()
print('='*80)
print('MODE 2: NON-CONTRARIAN TRADES (Regular Momentum Trades)')
print('='*80)
print()

non_contr_won = 0
non_contr_wr = 0
non_contr_pnl = 0

if len(non_contrarian) > 0:
    # Original performance (what bot would have taken)
    non_contr_won = non_contrarian['would_have_won'].sum()
    non_contr_wr = (non_contr_won / len(non_contrarian)) * 100
    non_contr_pnl = non_contrarian['theoretical_pnl'].sum()

    print(f'Trades: {len(non_contrarian):,}')
    print(f'Win Rate: {non_contr_wr:.1f}%')
    print(f'Total P&L: ${non_contr_pnl:+,.2f}')
    print(f'Avg per trade: ${non_contr_pnl/len(non_contrarian):+.2f}')

# ===== COMBINED (NORMAL MODE) =====
print()
print('='*80)
print('MODE 3: NORMAL MODE (Faded Contrarians + Non-Contrarian)')
print('='*80)
print()

if len(contrarian) > 0 and len(non_contrarian) > 0:
    combined_trades = len(contrarian) + len(non_contrarian)
    combined_won = contr_faded_won + non_contr_won
    combined_wr = (combined_won / combined_trades) * 100
    combined_pnl = contr_faded_pnl + non_contr_pnl

    print(f'Trades: {combined_trades:,}')
    print(f'  Faded contrarian: {len(contrarian):,}')
    print(f'  Regular: {len(non_contrarian):,}')
    print(f'Win Rate: {combined_wr:.1f}%')
    print(f'Total P&L: ${combined_pnl:+,.2f}')
    print(f'Avg per trade: ${combined_pnl/combined_trades:+.2f}')

# ===== COMPARISON TABLE =====
print()
print('='*80)
print('📊 COMPARISON SUMMARY')
print('='*80)
print()

header = f"{'Mode':<30} {'Trades':>10} {'Win Rate':>10} {'Total P&L':>15} {'Avg/Trade':>12}"
print(header)
print('-'*80)

if len(contrarian) > 0:
    line1 = f"{'Contrarian-Only (Fades)':<30} {len(contrarian):>10,} {contr_faded_wr:>9.1f}% ${contr_faded_pnl:>13,.2f} ${contr_faded_pnl/len(contrarian):>10.2f}"
    print(line1)

if len(non_contrarian) > 0:
    line2 = f"{'Non-Contrarian Only':<30} {len(non_contrarian):>10,} {non_contr_wr:>9.1f}% ${non_contr_pnl:>13,.2f} ${non_contr_pnl/len(non_contrarian):>10.2f}"
    print(line2)

if len(contrarian) > 0 and len(non_contrarian) > 0:
    line3 = f"{'Combined (Normal Mode)':<30} {combined_trades:>10,} {combined_wr:>9.1f}% ${combined_pnl:>13,.2f} ${combined_pnl/combined_trades:>10.2f}"
    print(line3)

# ===== RECOMMENDATION =====
print()
print('='*80)
print('💡 RECOMMENDATION')
print('='*80)
print()

if len(contrarian) > 0 and len(non_contrarian) > 0:
    if contr_faded_pnl > combined_pnl:
        diff = contr_faded_pnl - combined_pnl
        diff_pct = (diff / combined_pnl) * 100 if combined_pnl != 0 else 0
        print(f'✅ CONTRARIAN-ONLY MODE is MORE PROFITABLE')
        print(f'   Advantage: ${diff:+,.2f} ({diff_pct:+.1f}%)')
        print(f'   Reason: Non-contrarian trades are dragging down performance')
    elif combined_pnl > contr_faded_pnl:
        diff = combined_pnl - contr_faded_pnl
        diff_pct = (diff / contr_faded_pnl) * 100 if contr_faded_pnl != 0 else 0
        print(f'✅ NORMAL MODE (Combined) is MORE PROFITABLE')
        print(f'   Advantage: ${diff:+,.2f} ({diff_pct:+.1f}%)')
        print(f'   Reason: Non-contrarian trades add value')
    else:
        print(f'⚖️  EQUAL PERFORMANCE')

    # Trade volume consideration
    print()
    print(f'📈 Volume Consideration:')
    print(f'   Contrarian-only: {len(contrarian):,} trades')
    print(f'   Normal mode: {combined_trades:,} trades')
    if len(contrarian) < combined_trades:
        print(f'   Normal mode has {combined_trades - len(contrarian):,} more trades')

print()
print('='*80)
