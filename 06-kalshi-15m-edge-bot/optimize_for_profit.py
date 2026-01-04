"""
Optimize V3 for MAXIMUM WEEKLY PROFIT

Formula: Weekly Profit = Volume × (Win Rate - Loss Rate) × $100
                       = Volume × (2 × WR - 1) × $100

We want to maximize Volume × Edge, not just Win Rate.
"""

import pandas as pd
import numpy as np
from backtest_v3 import calculate_v3_probability

def test_config_for_profit(df, config):
    """Test a configuration and return expected weekly profit"""
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

        if abs(momentum_pct) > 0.1:
            r_squared = min(trend_strength / (abs(momentum_pct) / 2.0), 1.0)
        else:
            r_squared = 0.5

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

        # Apply filters
        if best_prob < config.get('min_expected_probability', 0.40):
            continue
        if best_prob > config.get('max_expected_probability', 0.99):
            continue
        if config.get('price_floor_enabled', True):
            if best_price < config.get('min_entry_price', 0.20):
                continue
            if best_price > config.get('max_entry_price', 0.90):
                continue
        if abs(momentum_pct) < config.get('min_momentum_pct', 0.05):
            continue

        mins_to_close = row.get('minutes_to_close', 0)
        if mins_to_close < config.get('min_minutes_to_close', 3):
            continue
        if mins_to_close > config.get('max_minutes_to_close', 12):
            continue

        results.append({
            'side': best_side,
            'outcome': row.get('actual_outcome'),
            'yes_price': yes_price,
        })

    if len(results) == 0:
        return None

    trades = pd.DataFrame(results)
    trades['won'] = trades.apply(lambda r:
        (r['outcome'] == 'yes' and r['side'] == 'yes') or
        (r['outcome'] == 'no' and r['side'] == 'no'), axis=1)

    wins = trades['won'].sum()
    volume = len(trades)
    win_rate = wins / volume

    # Calculate actual PnL based on prices
    avg_price = trades['yes_price'].mean()
    avg_win = (1 - avg_price) * 100 - 7  # Win pays (1 - entry) per contract
    avg_loss = -avg_price * 100 - 7      # Loss costs entry price

    total_pnl = (wins * avg_win) + ((volume - wins) * avg_loss)
    pnl_per_trade = total_pnl / volume

    # Expected weekly profit (assuming 833 markets ≈ 1 week)
    weekly_profit = total_pnl

    return {
        'volume': volume,
        'win_rate': win_rate,
        'weekly_profit': weekly_profit,
        'pnl_per_trade': pnl_per_trade,
        'edge': (2 * win_rate - 1),  # Simplified edge metric
        'profit_score': volume * (2 * win_rate - 1),  # Volume × Edge
    }


def main():
    print("=" * 80)
    print("OPTIMIZING V3 FOR MAXIMUM WEEKLY PROFIT")
    print("=" * 80)
    print()

    # Load data
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    df = df[df['minutes_to_close'] > 0].copy()
    df = df.drop_duplicates(subset='ticker', keep='last')
    df = df[df['actual_outcome'].notna()].copy()
    print(f"📂 Analyzing {len(df):,} unique markets with outcomes")
    print()

    # Grid search with wider parameter ranges
    print("🔍 Testing configurations for maximum profit...")
    print()

    configs = []

    # Test more aggressive settings to capture volume
    for min_prob in [0.38, 0.40, 0.42, 0.44, 0.46, 0.48]:
        for min_price in [0.20, 0.25, 0.30, 0.35]:
            for min_mom in [0.04, 0.05, 0.06, 0.08]:
                for max_time in [8, 10, 12, 15]:
                    config = {
                        'min_expected_probability': min_prob,
                        'max_expected_probability': 0.99,
                        'price_floor_enabled': True,
                        'min_entry_price': min_price,
                        'max_entry_price': 0.85,
                        'min_momentum_pct': min_mom,
                        'min_minutes_to_close': 3,
                        'max_minutes_to_close': max_time,
                    }

                    result = test_config_for_profit(df, config)
                    if result and result['volume'] >= 15 and result['win_rate'] > 0.45:
                        configs.append({
                            'min_prob': min_prob,
                            'min_price': min_price,
                            'min_mom': min_mom,
                            'max_time': max_time,
                            **result
                        })

    if len(configs) == 0:
        print("❌ No configurations met minimum criteria (volume ≥ 15, WR > 45%)")
        return

    # Sort by weekly profit
    configs_sorted = sorted(configs, key=lambda x: x['weekly_profit'], reverse=True)

    print("=" * 80)
    print("TOP 15 CONFIGURATIONS (by Weekly Profit)")
    print("=" * 80)
    print()

    for i, config in enumerate(configs_sorted[:15], 1):
        print(f"{i}. Weekly Profit: ${config['weekly_profit']:.2f}")
        print(f"   Volume: {config['volume']} trades, Win Rate: {config['win_rate']:.1%}, "
              f"PnL/trade: ${config['pnl_per_trade']:.2f}")
        print(f"   Config: min_prob={config['min_prob']:.2f}, min_price=${config['min_price']:.2f}, "
              f"min_mom={config['min_mom']:.2f}, max_time={config['max_time']}m")
        print()

    # Analyze top config in detail
    best = configs_sorted[0]

    print("=" * 80)
    print("💎 OPTIMAL CONFIGURATION FOR MAXIMUM PROFIT")
    print("=" * 80)
    print()

    print(f"📊 Performance Metrics:")
    print(f"   Weekly Profit: ${best['weekly_profit']:.2f}")
    print(f"   Volume: {best['volume']} trades/week")
    print(f"   Win Rate: {best['win_rate']:.1%}")
    print(f"   PnL per trade: ${best['pnl_per_trade']:.2f}")
    print(f"   Edge: {best['edge']:.1%} (WR - 50%)")
    print()

    print(f"⚙️  Configuration:")
    print(f"   min_expected_probability: {best['min_prob']:.2f}")
    print(f"   min_entry_price: ${best['min_price']:.2f}")
    print(f"   max_entry_price: $0.85")
    print(f"   min_momentum_pct: {best['min_mom']:.2f}")
    print(f"   min_minutes_to_close: 3")
    print(f"   max_minutes_to_close: {best['max_time']}")
    print()

    # Extrapolate to monthly/yearly
    monthly_profit = best['weekly_profit'] * 4.33
    yearly_profit = best['weekly_profit'] * 52

    print(f"💰 Projected Returns:")
    print(f"   Weekly: ${best['weekly_profit']:.2f}")
    print(f"   Monthly: ${monthly_profit:.2f}")
    print(f"   Yearly: ${yearly_profit:,.2f}")
    print()

    # Compare to other strategies
    print("=" * 80)
    print("📊 COMPARISON: Volume vs Win Rate Strategies")
    print("=" * 80)
    print()

    # Show top 3 by different metrics
    by_wr = sorted(configs, key=lambda x: x['win_rate'], reverse=True)[:3]
    by_volume = sorted(configs, key=lambda x: x['volume'], reverse=True)[:3]
    by_profit = configs_sorted[:3]

    print("Top 3 by Win Rate:")
    for i, c in enumerate(by_wr, 1):
        print(f"  {i}. WR: {c['win_rate']:.1%}, Volume: {c['volume']}, Profit: ${c['weekly_profit']:.2f}")

    print("\nTop 3 by Volume:")
    for i, c in enumerate(by_volume, 1):
        print(f"  {i}. Volume: {c['volume']}, WR: {c['win_rate']:.1%}, Profit: ${c['weekly_profit']:.2f}")

    print("\nTop 3 by Profit:")
    for i, c in enumerate(by_profit, 1):
        print(f"  {i}. Profit: ${c['weekly_profit']:.2f}, Volume: {c['volume']}, WR: {c['win_rate']:.1%}")

    print()
    print("🎯 Key Insight: The most profitable strategy balances volume and win rate,")
    print("   not just maximizing either metric alone.")
    print()

    # Risk analysis
    print("=" * 80)
    print("⚠️  RISK ANALYSIS")
    print("=" * 80)
    print()

    # Calculate drawdown risk
    volume = best['volume']
    wr = best['win_rate']

    # Probability of losing streak
    lose_2_in_row = (1 - wr) ** 2
    lose_3_in_row = (1 - wr) ** 3
    lose_5_in_row = (1 - wr) ** 5

    avg_trade = abs(best['pnl_per_trade'])
    max_dd_5_losses = 5 * avg_trade

    print(f"Drawdown Risk:")
    print(f"   Probability of 2 losses in a row: {lose_2_in_row:.1%}")
    print(f"   Probability of 3 losses in a row: {lose_3_in_row:.1%}")
    print(f"   Probability of 5 losses in a row: {lose_5_in_row:.1%}")
    print(f"   Max drawdown (5 losses): ~${max_dd_5_losses:.2f}")
    print()

    # Kelly criterion check
    edge = best['edge']
    kelly_fraction = edge if edge > 0 else 0
    print(f"Position Sizing:")
    print(f"   Edge: {edge:.1%}")
    print(f"   Full Kelly: {kelly_fraction:.1%} of bankroll per trade")
    print(f"   Half Kelly (recommended): {kelly_fraction/2:.1%}")
    print()


if __name__ == '__main__':
    main()
