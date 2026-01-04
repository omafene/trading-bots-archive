"""
Find Optimal V3 Configuration

Test configurations between Moderate and Conservative to maximize:
- Win rate > 45%
- Volume > 50 trades (in this sample)
- Positive expected value
"""

import pandas as pd
import numpy as np
from backtest_v3 import calculate_v3_probability

def apply_v3_filters(row, v3_config):
    """Apply v3 filters"""
    market_type = row.get('market_type', '').lower()
    if market_type not in ['up', 'down', 'above', 'below']:
        return False, None, None

    spot_price = row.get('spot_price', 0)
    threshold = row.get('threshold', 0)
    if spot_price <= 0 or threshold <= 0:
        return False, None, None

    distance_pct = ((threshold - spot_price) / spot_price) * 100

    momentum_pct = row.get('momentum_pct', 0)
    trend_strength = row.get('trend_strength', 0.5)

    if abs(momentum_pct) > 0.1:
        r_squared = min(trend_strength / (abs(momentum_pct) / 2.0), 1.0)
    else:
        r_squared = 0.5

    v3_prob = calculate_v3_probability(distance_pct, momentum_pct, r_squared, market_type)
    if v3_prob is None:
        return False, None, None

    yes_price = row.get('yes_market_price', 0.5)
    no_price = row.get('no_market_price', 0.5)

    slippage = 0.02
    fee = 7.0
    edge_yes = ((v3_prob - yes_price - slippage) * 100) - fee
    edge_no = ((1 - v3_prob - no_price - slippage) * 100) - fee

    best_side = 'yes' if edge_yes > edge_no else 'no'
    best_edge = edge_yes if best_side == 'yes' else edge_no
    best_prob = v3_prob if best_side == 'yes' else (1 - v3_prob)
    best_price = yes_price if best_side == 'yes' else no_price

    # Apply filters
    if best_edge < v3_config.get('min_edge_percent', 0):
        return False, None, None
    if best_prob < v3_config.get('min_expected_probability', 0.40):
        return False, None, None
    if best_prob > v3_config.get('max_expected_probability', 0.99):
        return False, None, None
    if v3_config.get('price_floor_enabled', True):
        if best_price < v3_config.get('min_entry_price', 0.20):
            return False, None, None
        if best_price > v3_config.get('max_entry_price', 0.90):
            return False, None, None
    if abs(momentum_pct) < v3_config.get('min_momentum_pct', 0.05):
        return False, None, None

    mins_to_close = row.get('minutes_to_close', 0)
    if mins_to_close < v3_config.get('min_minutes_to_close', 3):
        return False, None, None
    if mins_to_close > v3_config.get('max_minutes_to_close', 12):
        return False, None, None

    return True, best_side, v3_prob


def test_config(df, config):
    """Test a configuration and return results"""
    results = []
    for idx, row in df.iterrows():
        would_take, side, v3_prob = apply_v3_filters(row, config)
        if would_take:
            results.append({
                'side': side,
                'outcome': row.get('actual_outcome'),
                'momentum_pct': row.get('momentum_pct', 0),
                'yes_price': row.get('yes_market_price', 0.5),
            })

    if len(results) == 0:
        return None

    trades_df = pd.DataFrame(results)
    trades_df['won'] = trades_df.apply(lambda r:
        (r['outcome'] == 'yes' and r['side'] == 'yes') or
        (r['outcome'] == 'no' and r['side'] == 'no'), axis=1)

    wins = trades_df['won'].sum()
    win_rate = wins / len(trades_df)

    avg_price = trades_df['yes_price'].mean()
    avg_win = (1 - avg_price) * 100 - 7
    avg_loss = -avg_price * 100 - 7
    expected_pnl = (wins * avg_win) + ((len(trades_df) - wins) * avg_loss)
    pnl_per_trade = expected_pnl / len(trades_df)

    return {
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'expected_pnl': expected_pnl,
        'pnl_per_trade': pnl_per_trade,
    }


def main():
    print("=" * 80)
    print("FINDING OPTIMAL V3 CONFIGURATION")
    print("=" * 80)
    print()

    # Load data
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    df = df[df['minutes_to_close'] > 0].copy()
    df = df.drop_duplicates(subset='ticker', keep='last')
    df = df[df['actual_outcome'].notna()].copy()
    print(f"📂 Analyzing {len(df):,} unique markets with outcomes")
    print()

    # Grid search over key parameters
    print("🔍 Testing configurations...")
    print()

    configs_to_test = []

    # Vary key parameters
    for min_prob in [0.42, 0.44, 0.46, 0.48]:
        for min_price in [0.25, 0.30, 0.35]:
            for min_mom in [0.06, 0.08]:
                for max_time in [8, 10, 12]:
                    config = {
                        'min_edge_percent': 0,
                        'min_expected_probability': min_prob,
                        'max_expected_probability': 0.99,
                        'price_floor_enabled': True,
                        'min_entry_price': min_price,
                        'max_entry_price': 0.85,
                        'min_momentum_pct': min_mom,
                        'min_minutes_to_close': 3,
                        'max_minutes_to_close': max_time,
                    }
                    result = test_config(df, config)
                    if result and result['num_trades'] >= 20:  # Minimum volume
                        configs_to_test.append({
                            'min_prob': min_prob,
                            'min_price': min_price,
                            'min_mom': min_mom,
                            'max_time': max_time,
                            **result
                        })

    if len(configs_to_test) == 0:
        print("❌ No configurations met minimum criteria")
        return

    # Sort by win rate
    configs_sorted = sorted(configs_to_test, key=lambda x: x['win_rate'], reverse=True)

    print("=" * 80)
    print("TOP 10 CONFIGURATIONS (by Win Rate)")
    print("=" * 80)
    print()

    for i, config in enumerate(configs_sorted[:10], 1):
        print(f"{i}. Win Rate: {config['win_rate']:.1%}, Volume: {config['num_trades']}, "
              f"PnL/trade: ${config['pnl_per_trade']:.2f}")
        print(f"   min_prob={config['min_prob']:.2f}, min_price=${config['min_price']:.2f}, "
              f"min_mom={config['min_mom']:.2f}, max_time={config['max_time']}")
        print(f"   Total PnL: ${config['expected_pnl']:.2f}")
        print()

    print("=" * 80)
    print("TOP 10 CONFIGURATIONS (by Total PnL)")
    print("=" * 80)
    print()

    configs_by_pnl = sorted(configs_to_test, key=lambda x: x['expected_pnl'], reverse=True)

    for i, config in enumerate(configs_by_pnl[:10], 1):
        print(f"{i}. Total PnL: ${config['expected_pnl']:.2f}, Win Rate: {config['win_rate']:.1%}, "
              f"Volume: {config['num_trades']}")
        print(f"   min_prob={config['min_prob']:.2f}, min_price=${config['min_price']:.2f}, "
              f"min_mom={config['min_mom']:.2f}, max_time={config['max_time']}")
        print(f"   PnL/trade: ${config['pnl_per_trade']:.2f}")
        print()

    # Recommend balanced config
    print("=" * 80)
    print("💎 RECOMMENDED CONFIGURATION")
    print("=" * 80)
    print()

    # Find config with best balance: WR > 40%, volume > 40, positive PnL
    balanced = [c for c in configs_to_test if
                c['win_rate'] > 0.40 and
                c['num_trades'] > 40 and
                c['expected_pnl'] > 0]

    if balanced:
        # Sort by PnL per trade
        balanced_sorted = sorted(balanced, key=lambda x: x['pnl_per_trade'], reverse=True)
        best = balanced_sorted[0]

        print(f"✅ Balanced Config:")
        print(f"   Win Rate: {best['win_rate']:.1%}")
        print(f"   Volume: {best['num_trades']} trades")
        print(f"   Total PnL: ${best['expected_pnl']:.2f}")
        print(f"   PnL per trade: ${best['pnl_per_trade']:.2f}")
        print()
        print(f"⚙️  Settings:")
        print(f"   min_expected_probability: {best['min_prob']:.2f}")
        print(f"   min_entry_price: {best['min_price']:.2f}")
        print(f"   min_momentum_pct: {best['min_mom']:.2f}")
        print(f"   max_minutes_to_close: {best['max_time']}")
    else:
        print("❌ No configuration met balanced criteria (WR > 40%, volume > 40, PnL > 0)")


if __name__ == '__main__':
    main()
