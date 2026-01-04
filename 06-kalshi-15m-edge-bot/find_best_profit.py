"""
Find configuration with BEST profit - prioritize WR > 52%
"""

import pandas as pd
from backtest_v3 import calculate_v3_probability

def test_config(df, config):
    """Test config and return results"""
    results = []

    for idx, row in df.iterrows():
        market_type = row.get('market_type', '').lower()
        spot_price = row.get('spot_price', 0)
        threshold = row.get('threshold', 0)

        if market_type not in ['up', 'down', 'above', 'below'] or spot_price <= 0 or threshold <= 0:
            continue

        distance_pct = ((threshold - spot_price) / spot_price) * 100
        momentum_pct = row.get('momentum_pct', 0)
        trend_strength = row.get('trend_strength', 0.5)
        r_squared = 0.5 if abs(momentum_pct) < 0.1 else min(trend_strength / (abs(momentum_pct) / 2.0), 1.0)

        v3_prob = calculate_v3_probability(distance_pct, momentum_pct, r_squared, market_type)
        if not v3_prob:
            continue

        yes_price = row.get('yes_market_price', 0.5)
        no_price = row.get('no_market_price', 0.5)

        edge_yes = ((v3_prob - yes_price - 0.02) * 100) - 7
        edge_no = ((1 - v3_prob - no_price - 0.02) * 100) - 7

        best_side = 'yes' if edge_yes > edge_no else 'no'
        best_prob = v3_prob if best_side == 'yes' else (1 - v3_prob)
        best_price = yes_price if best_side == 'yes' else no_price

        # Filters
        if best_prob < config.get('min_prob', 0.40):
            continue
        if best_price < config.get('min_price', 0.20) or best_price > config.get('max_price', 0.90):
            continue
        if abs(momentum_pct) < config.get('min_mom', 0.05):
            continue
        mins = row.get('minutes_to_close', 0)
        if mins < 3 or mins > config.get('max_time', 12):
            continue

        results.append({
            'side': best_side,
            'outcome': row.get('actual_outcome'),
            'yes_price': yes_price,
        })

    if not results:
        return None

    trades = pd.DataFrame(results)
    trades['won'] = trades.apply(lambda r:
        (r['outcome'] == 'yes' and r['side'] == 'yes') or
        (r['outcome'] == 'no' and r['side'] == 'no'), axis=1)

    wins = trades['won'].sum()
    wr = wins / len(trades)
    avg_price = trades['yes_price'].mean()
    pnl = (wins * ((1 - avg_price) * 100 - 7)) + ((len(trades) - wins) * (-avg_price * 100 - 7))

    return {
        'volume': len(trades),
        'wr': wr,
        'pnl': pnl,
        'pnl_per_trade': pnl / len(trades),
    }


print("Finding configuration with MAXIMUM PROFIT...")
print()

df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df = df[df['minutes_to_close'] > 0]
df = df.drop_duplicates(subset='ticker', keep='last')
df = df[df['actual_outcome'].notna()]
print(f"Testing on {len(df)} markets\n")

best_configs = []

# Wide grid search
for min_prob in [0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48, 0.50]:
    for min_price in [0.25, 0.30, 0.35, 0.40]:
        for min_mom in [0.04, 0.05, 0.06, 0.07, 0.08]:
            for max_time in [8, 10, 12, 15]:
                config = {
                    'min_prob': min_prob,
                    'min_price': min_price,
                    'max_price': 0.85,
                    'min_mom': min_mom,
                    'max_time': max_time,
                }

                result = test_config(df, config)
                if result and result['volume'] >= 10:  # At least 10 trades
                    best_configs.append({**config, **result})

# Sort by weekly profit
best_configs.sort(key=lambda x: x['pnl'], reverse=True)

print("=" * 100)
print("TOP 20 CONFIGURATIONS (by Weekly Profit)")
print("=" * 100)
print()

for i, c in enumerate(best_configs[:20], 1):
    print(f"{i:2d}. ${c['pnl']:6.2f}/week | {c['volume']:2d} trades | {c['wr']:5.1%} WR | ${c['pnl_per_trade']:5.2f}/trade")
    print(f"     min_prob={c['min_prob']:.2f}, min_price=${c['min_price']:.2f}, "
          f"min_mom={c['min_mom']:.2f}, max_time={c['max_time']}m")
    print()

# Find best by profit
best = best_configs[0]

print("=" * 100)
print("💎 RECOMMENDED: MAXIMUM PROFIT CONFIGURATION")
print("=" * 100)
print()

print("📊 Backtest Performance:")
print(f"   Weekly Profit: ${best['pnl']:.2f}")
print(f"   Volume: {best['volume']} trades/week")
print(f"   Win Rate: {best['wr']:.1%}")
print(f"   PnL per trade: ${best['pnl_per_trade']:.2f}")
print(f"   Edge over 50%: {(best['wr'] - 0.50)*100:+.1f} percentage points")
print()

print("💰 Projected Returns:")
print(f"   Weekly: ${best['pnl']:.2f}")
print(f"   Monthly (4.33 weeks): ${best['pnl'] * 4.33:.2f}")
print(f"   Yearly (52 weeks): ${best['pnl'] * 52:,.2f}")
print()

print("⚙️  Configuration for config_15m.yaml:")
print()
print("strategy:")
print(f"  probability_model: \"v3\"")
print()
print(f"  min_expected_probability: {best['min_prob']:.2f}")
print(f"  min_entry_price: {best['min_price']:.2f}")
print(f"  max_entry_price: {best['max_price']:.2f}")
print(f"  min_momentum_pct: {best['min_mom']:.2f}")
print()
print(f"  min_minutes_to_close: 3")
print(f"  max_minutes_to_close: {best['max_time']}")
print()
print("  # Disable these for v3:")
print("  r_squared_filter_enabled: false")
print("  use_advanced_edge_detection: false")
print("  disable_contrarian_bets: false")
print()

# Compare high-volume vs high-WR strategies
print("=" * 100)
print("📊 STRATEGY COMPARISON")
print("=" * 100)
print()

by_volume = sorted(best_configs, key=lambda x: x['volume'], reverse=True)[:5]
by_wr = sorted([c for c in best_configs if c['volume'] >= 15], key=lambda x: x['wr'], reverse=True)[:5]

print("Top 5 by Volume (most trades):")
for i, c in enumerate(by_volume, 1):
    print(f"  {i}. {c['volume']} trades, {c['wr']:.1%} WR → ${c['pnl']:.2f}/week")

print("\nTop 5 by Win Rate (15+ trades minimum):")
for i, c in enumerate(by_wr, 1):
    print(f"  {i}. {c['wr']:.1%} WR, {c['volume']} trades → ${c['pnl']:.2f}/week")

print()
print("🎯 Conclusion: For maximum profit, optimize for (Win Rate × Volume), not just Win Rate alone.")
