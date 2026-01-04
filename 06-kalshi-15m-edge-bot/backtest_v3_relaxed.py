"""
Backtest V3 with RELAXED Settings

Testing more practical v3 configuration that actually trades
"""

import pandas as pd
import numpy as np
import sys

# Import the v3 probability calculation from backtest_v3.py
from backtest_v3 import calculate_v3_probability

def apply_v3_filters_relaxed(row, v3_config):
    """Apply v3 filters with relaxed settings"""

    # Parse market type
    market_type = row.get('market_type', '').lower()
    if market_type not in ['up', 'down', 'above', 'below']:
        return False, None, "Invalid market type", None

    # Calculate distance to threshold
    spot_price = row.get('spot_price', 0)
    threshold = row.get('threshold', 0)

    if spot_price <= 0 or threshold <= 0:
        return False, None, "Invalid price/threshold data", None

    distance_pct = ((threshold - spot_price) / spot_price) * 100

    # Get momentum and quality metrics
    momentum_pct = row.get('momentum_pct', 0)
    trend_strength = row.get('trend_strength', 0.5)

    # Approximate r_squared from trend_strength
    if abs(momentum_pct) > 0.1:
        r_squared = min(trend_strength / (abs(momentum_pct) / 2.0), 1.0)
    else:
        r_squared = 0.5

    # Calculate v3 probability
    v3_prob = calculate_v3_probability(distance_pct, momentum_pct, r_squared, market_type)

    if v3_prob is None:
        return False, None, "V3 prob calculation failed", None

    # Get market prices
    yes_price = row.get('yes_market_price', 0.5)
    no_price = row.get('no_market_price', 0.5)

    # Calculate edges
    slippage = 0.02
    fee = 7.0

    edge_yes = ((v3_prob - yes_price - slippage) * 100) - fee
    edge_no = ((1 - v3_prob - no_price - slippage) * 100) - fee

    # Determine best side
    best_side = 'yes' if edge_yes > edge_no else 'no'
    best_edge = edge_yes if best_side == 'yes' else edge_no
    best_prob = v3_prob if best_side == 'yes' else (1 - v3_prob)
    best_price = yes_price if best_side == 'yes' else no_price

    # Apply v3 filters
    filters = v3_config

    # Min edge
    if best_edge < filters['min_edge_percent']:
        return False, best_side, f"Edge {best_edge:.1f}% < min {filters['min_edge_percent']}%", v3_prob

    # Min/max probability
    if best_prob < filters['min_expected_probability']:
        return False, best_side, f"Prob {best_prob:.2%} < min {filters['min_expected_probability']:.2%}", v3_prob
    if best_prob > filters['max_expected_probability']:
        return False, best_side, f"Prob {best_prob:.2%} > max {filters['max_expected_probability']:.2%}", v3_prob

    # Price filters (more relaxed)
    if filters['price_floor_enabled']:
        if best_price < filters['min_entry_price']:
            return False, best_side, f"Price ${best_price:.2f} < min ${filters['min_entry_price']:.2f}", v3_prob
        if best_price > filters['max_entry_price']:
            return False, best_side, f"Price ${best_price:.2f} > max ${filters['max_entry_price']:.2f}", v3_prob

    # R² filter (relaxed)
    if filters.get('r_squared_filter_enabled', False):
        if r_squared < filters['min_r_squared']:
            return False, best_side, f"R² {r_squared:.2f} < min {filters['min_r_squared']:.2f}", v3_prob

    # Momentum filter (relaxed)
    if abs(momentum_pct) < filters['min_momentum_pct']:
        return False, best_side, f"Momentum {abs(momentum_pct):.2%} < min {filters['min_momentum_pct']:.2%}", v3_prob

    # Time window
    mins_to_close = row.get('minutes_to_close', 0)
    if mins_to_close < filters['min_minutes_to_close']:
        return False, best_side, f"Time {mins_to_close:.1f}m < min {filters['min_minutes_to_close']}m", v3_prob
    if mins_to_close > filters['max_minutes_to_close']:
        return False, best_side, f"Time {mins_to_close:.1f}m > max {filters['max_minutes_to_close']}m", v3_prob

    # All filters passed
    return True, best_side, f"PASS (Edge: {best_edge:.1f}%, Prob: {best_prob:.1%})", v3_prob


def main():
    print("=" * 80)
    print("V3 MODEL BACKTEST - RELAXED SETTINGS")
    print("=" * 80)
    print()

    # Load data
    print("📂 Loading historical data...")
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    print(f"   Loaded {len(df):,} scan records")

    # Filter for tradeable markets
    df = df[df['minutes_to_close'] > 0].copy()
    print(f"   Filtered to {len(df):,} tradeable markets")

    # Deduplicate
    df = df.drop_duplicates(subset='ticker', keep='last')
    print(f"   Deduplicated to {len(df):,} unique markets")

    # Filter for known outcomes
    df = df[df['actual_outcome'].notna()].copy()
    print(f"   Filtered to {len(df):,} markets with known outcomes")
    print()

    # Test multiple v3 configurations
    configs_to_test = [
        {
            'name': 'V3 Aggressive (Low Barriers)',
            'settings': {
                'min_edge_percent': -5,  # Allow small negative edge
                'min_expected_probability': 0.40,  # Lower threshold
                'max_expected_probability': 0.99,
                'price_floor_enabled': True,
                'min_entry_price': 0.20,  # Much lower
                'max_entry_price': 0.90,
                'r_squared_filter_enabled': False,  # Disabled
                'min_r_squared': 0.20,
                'min_momentum_pct': 0.05,  # Lower
                'min_minutes_to_close': 3,
                'max_minutes_to_close': 12,  # Wider window
            }
        },
        {
            'name': 'V3 Moderate (Balanced)',
            'settings': {
                'min_edge_percent': 0,
                'min_expected_probability': 0.45,
                'max_expected_probability': 0.95,
                'price_floor_enabled': True,
                'min_entry_price': 0.25,
                'max_entry_price': 0.85,
                'r_squared_filter_enabled': False,
                'min_r_squared': 0.25,
                'min_momentum_pct': 0.06,
                'min_minutes_to_close': 3,
                'max_minutes_to_close': 10,
            }
        },
        {
            'name': 'V3 Conservative (Original)',
            'settings': {
                'min_edge_percent': 0,
                'min_expected_probability': 0.48,
                'max_expected_probability': 0.99,
                'price_floor_enabled': True,
                'min_entry_price': 0.35,
                'max_entry_price': 0.85,
                'r_squared_filter_enabled': True,
                'min_r_squared': 0.30,
                'min_momentum_pct': 0.08,
                'min_minutes_to_close': 3,
                'max_minutes_to_close': 8,
            }
        },
    ]

    for config_test in configs_to_test:
        print("=" * 80)
        print(f"Testing: {config_test['name']}")
        print("=" * 80)
        print()

        v3_config = config_test['settings']

        # Apply filters
        results = []
        for idx, row in df.iterrows():
            would_take, side, reason, v3_prob = apply_v3_filters_relaxed(row, v3_config)
            results.append({
                'would_take': would_take,
                'side': side,
                'reason': reason,
                'v3_prob': v3_prob,
                'outcome': row.get('actual_outcome'),
                'momentum_pct': row.get('momentum_pct', 0),
                'yes_price': row.get('yes_market_price', 0.5),
                'no_price': row.get('no_market_price', 0.5),
            })

        results_df = pd.DataFrame(results)

        # Stats
        total_markets = len(results_df)
        would_trade = results_df['would_take'].sum()

        print(f"📊 Results:")
        print(f"   Markets analyzed: {total_markets:,}")
        print(f"   Would TRADE: {would_trade:,} ({would_trade/total_markets*100:.1f}%)")
        print()

        if would_trade == 0:
            print("❌ No trades passed filters")
            print()
            continue

        # Performance
        trades = results_df[results_df['would_take'] == True].copy()

        trades['won'] = trades.apply(lambda r:
            (r['outcome'] == 'yes' and r['side'] == 'yes') or
            (r['outcome'] == 'no' and r['side'] == 'no'), axis=1)

        wins = trades['won'].sum()
        losses = len(trades) - wins
        win_rate = wins / len(trades)

        # PnL
        avg_price = trades['yes_price'].mean()
        avg_win = (1 - avg_price) * 100 - 7
        avg_loss = -avg_price * 100 - 7
        expected_pnl = (wins * avg_win) + (losses * avg_loss)
        pnl_per_trade = expected_pnl / len(trades)

        print(f"🎯 Performance:")
        print(f"   Win Rate: {win_rate:.1%}")
        print(f"   Wins: {wins:,}, Losses: {losses:,}")
        print(f"   Estimated PnL: ${expected_pnl:,.2f}")
        print(f"   PnL per trade: ${pnl_per_trade:.2f}")
        print()

        # Breakdown by side
        print(f"📊 By Side:")
        for side in ['yes', 'no']:
            side_trades = trades[trades['side'] == side]
            if len(side_trades) > 0:
                side_wins = side_trades['won'].sum()
                side_wr = side_wins / len(side_trades)
                print(f"   {side.upper()}: {len(side_trades):,} trades, {side_wr:.1%} WR")

        # Breakdown by momentum
        trades['momentum_dir'] = trades['momentum_pct'].apply(lambda x: 'UP' if x > 0 else 'DOWN')
        print(f"\n📊 By Momentum:")
        for direction in ['UP', 'DOWN']:
            dir_trades = trades[trades['momentum_dir'] == direction]
            if len(dir_trades) > 0:
                dir_wins = dir_trades['won'].sum()
                dir_wr = dir_wins / len(dir_trades)
                print(f"   {direction}: {len(dir_trades):,} trades, {dir_wr:.1%} WR")

        print()
        print()


if __name__ == '__main__':
    main()
