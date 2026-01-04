"""
Backtest V3 Model on Historical Data

Simulates what v3 would have done on the same markets that v1/v2 saw.
Shows if v3 settings would actually improve win rate and profitability.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import sys

# V3 probability model logic (simplified for backtesting)
def calculate_v3_probability(distance_pct, momentum_pct, r_squared, market_type):
    """
    Replicate v3 probability model from momentum_analyzer_v3.py

    Args:
        distance_pct: % distance to threshold (negative = above for UP markets)
        momentum_pct: Trend % from regression
        r_squared: Trend quality (0-1)
        market_type: 'up', 'down', 'above', 'below'

    Returns:
        Probability (0.05-0.95)
    """

    # --- BASE PROBABILITY (Distance-Based) ---
    if market_type in ['up', 'above']:
        # YES wins if price >= threshold at close
        if distance_pct < -2.0:  # >2% above threshold
            base_prob = 0.70
        elif distance_pct < -1.0:  # 1-2% above
            base_prob = 0.62
        elif distance_pct < -0.5:  # 0.5-1% above
            base_prob = 0.56
        elif distance_pct < 0:  # Slightly above
            base_prob = 0.52
        elif distance_pct < 0.5:  # Slightly below
            base_prob = 0.48
        elif distance_pct < 1.0:  # 0.5-1% below
            base_prob = 0.42
        elif distance_pct < 2.0:  # 1-2% below
            base_prob = 0.35
        else:  # >2% below
            base_prob = 0.25

    elif market_type in ['down', 'below']:
        # YES wins if price < threshold (inverted)
        if distance_pct > 2.0:  # >2% below threshold
            base_prob = 0.70
        elif distance_pct > 1.0:
            base_prob = 0.62
        elif distance_pct > 0.5:
            base_prob = 0.56
        elif distance_pct > 0:
            base_prob = 0.52
        elif distance_pct > -0.5:
            base_prob = 0.48
        elif distance_pct > -1.0:
            base_prob = 0.42
        elif distance_pct > -2.0:
            base_prob = 0.35
        else:
            base_prob = 0.25
    else:
        return None

    # --- MEAN REVERSION ADJUSTMENT ---
    momentum_abs = abs(momentum_pct)

    if momentum_abs > 0.8:  # Very strong momentum
        mean_reversion_penalty = -0.12
    elif momentum_abs > 0.5:  # Strong momentum
        mean_reversion_penalty = -0.08
    elif momentum_abs > 0.3:  # Moderate momentum
        mean_reversion_penalty = -0.04
    else:  # Weak momentum
        mean_reversion_penalty = 0

    # --- QUALITY ADJUSTMENT (R²) ---
    if r_squared > 0.7:  # Very clean trend
        quality_bonus = 0.03
    elif r_squared > 0.5:
        quality_bonus = 0.02
    else:
        quality_bonus = 0

    # --- FINAL PROBABILITY ---
    final_prob = base_prob + mean_reversion_penalty + quality_bonus

    # Clamp to safe range
    return max(0.05, min(0.95, final_prob))


def apply_v3_filters(row, v3_config):
    """
    Apply v3 config filters to determine if trade would be taken

    Returns: (would_take, side, reason, v3_prob)
    """

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

    # Approximate r_squared from trend_strength (we don't have exact r_squared in data)
    # trend_strength = r_squared * min(abs(momentum) / 2.0, 1.0)
    # So: r_squared ≈ trend_strength / (abs(momentum)/2.0)
    if abs(momentum_pct) > 0.1:
        r_squared = min(trend_strength / (abs(momentum_pct) / 2.0), 1.0)
    else:
        r_squared = 0.5  # Default assumption

    # Calculate v3 probability
    v3_prob = calculate_v3_probability(distance_pct, momentum_pct, r_squared, market_type)

    if v3_prob is None:
        return False, None, "V3 prob calculation failed", None

    # Get market prices
    yes_price = row.get('yes_market_price', 0.5)
    no_price = row.get('no_market_price', 0.5)

    # Calculate edges (simplified - no multi-factor adjustments in v3)
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

    # Price filters
    if filters['price_floor_enabled']:
        if best_price < filters['min_entry_price']:
            return False, best_side, f"Price ${best_price:.2f} < min ${filters['min_entry_price']:.2f}", v3_prob
        if best_price > filters['max_entry_price']:
            return False, best_side, f"Price ${best_price:.2f} > max ${filters['max_entry_price']:.2f}", v3_prob

    # R² filter (approximate)
    if filters['r_squared_filter_enabled']:
        if r_squared < filters['min_r_squared']:
            return False, best_side, f"R² {r_squared:.2f} < min {filters['min_r_squared']:.2f}", v3_prob

    # Momentum filter
    if abs(momentum_pct) < filters['min_momentum_pct']:
        return False, best_side, f"Momentum {abs(momentum_pct):.2%} < min {filters['min_momentum_pct']:.2%}", v3_prob

    # Bid-ask spread filter
    if filters['max_spread_filter_enabled']:
        spread = abs(yes_price + no_price - 1.0)
        if spread > filters['max_bid_ask_spread']:
            return False, best_side, f"Spread {spread:.2f} > max {filters['max_bid_ask_spread']:.2f}", v3_prob

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
    print("V3 MODEL BACKTEST")
    print("=" * 80)
    print()

    # Load data
    print("📂 Loading historical data...")
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    print(f"   Loaded {len(df):,} scan records")

    # Filter for markets that were actually tradeable (positive minutes to close)
    df = df[df['minutes_to_close'] > 0].copy()
    print(f"   Filtered to {len(df):,} tradeable markets (minutes_to_close > 0)")

    # Deduplicate (keep last scan per ticker)
    df = df.drop_duplicates(subset='ticker', keep='last')
    print(f"   Deduplicated to {len(df):,} unique markets")

    # Filter for markets with outcomes
    df = df[df['actual_outcome'].notna()].copy()
    print(f"   Filtered to {len(df):,} markets with known outcomes")
    print()

    if len(df) == 0:
        print("❌ No valid data to backtest!")
        return

    # V3 configuration
    v3_config = {
        'min_edge_percent': 0,
        'min_expected_probability': 0.48,
        'max_expected_probability': 0.99,
        'price_floor_enabled': True,
        'min_entry_price': 0.35,
        'max_entry_price': 0.85,
        'r_squared_filter_enabled': True,
        'min_r_squared': 0.30,
        'min_momentum_pct': 0.08,
        'max_spread_filter_enabled': True,
        'max_bid_ask_spread': 0.12,
        'min_minutes_to_close': 3,
        'max_minutes_to_close': 8,
    }

    print("⚙️  V3 Configuration:")
    for key, val in v3_config.items():
        print(f"   {key}: {val}")
    print()

    # Apply v3 filters to each market
    print("🔍 Applying v3 filters...")
    results = []
    for idx, row in df.iterrows():
        would_take, side, reason, v3_prob = apply_v3_filters(row, v3_config)
        results.append({
            'ticker': row['ticker'],
            'would_take': would_take,
            'side': side,
            'reason': reason,
            'v3_prob': v3_prob,
            'outcome': row.get('actual_outcome'),
            'model_prob': row.get('yes_expected_prob', 0.5),
            'yes_price': row.get('yes_market_price', 0.5),
            'no_price': row.get('no_market_price', 0.5),
            'momentum_pct': row.get('momentum_pct', 0),
        })

    results_df = pd.DataFrame(results)

    # Calculate statistics
    print()
    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print()

    # Overall stats
    total_markets = len(results_df)
    would_trade = results_df['would_take'].sum()
    would_skip = total_markets - would_trade

    print(f"📊 Overall Statistics:")
    print(f"   Total markets analyzed: {total_markets:,}")
    print(f"   Would TRADE with v3: {would_trade:,} ({would_trade/total_markets*100:.1f}%)")
    print(f"   Would SKIP with v3: {would_skip:,} ({would_skip/total_markets*100:.1f}%)")
    print()

    # Performance on trades that would be taken
    trades = results_df[results_df['would_take'] == True].copy()

    if len(trades) == 0:
        print("❌ No trades would pass v3 filters!")
        print()
        print("🔍 Analyzing why trades were skipped...")
        skipped = results_df[results_df['would_take'] == False]
        if len(skipped) > 0:
            print(f"\n🚫 Top Reasons for Skipping ({len(skipped):,} markets):")
            skip_reasons = skipped['reason'].value_counts().head(10)
            for reason, count in skip_reasons.items():
                pct = count / len(skipped) * 100
                print(f"   {reason}: {count:,} ({pct:.1f}%)")
        return

    # Calculate wins
    trades['won'] = trades.apply(lambda r:
        (r['outcome'] == 'yes' and r['side'] == 'yes') or
        (r['outcome'] == 'no' and r['side'] == 'no'), axis=1)

    wins = trades['won'].sum()
    losses = len(trades) - wins
    win_rate = wins / len(trades) if len(trades) > 0 else 0

    # Calculate PnL (simplified)
    avg_price = trades['yes_price'].mean() if 'yes_price' in trades.columns else 0.50
    avg_win = (1 - avg_price) * 100 - 7  # Contract pays $1, minus fee
    avg_loss = -avg_price * 100 - 7  # Lose entry price plus fee

    expected_pnl = (wins * avg_win) + (losses * avg_loss)
    pnl_per_trade = expected_pnl / len(trades)

    print(f"🎯 V3 Performance:")
    print(f"   Trades taken: {len(trades):,}")
    print(f"   Wins: {wins:,}")
    print(f"   Losses: {losses:,}")
    print(f"   Win Rate: {win_rate:.1%}")
    print(f"   Estimated PnL: ${expected_pnl:,.2f}")
    print(f"   PnL per trade: ${pnl_per_trade:.2f}")
    print()

    # Compare to "would have won" from current model
    current_model_wins = df['would_have_won'].sum()
    current_model_wr = current_model_wins / len(df)

    print(f"📈 Comparison to Current Model:")
    print(f"   Current model (on same data): {current_model_wr:.1%} WR")
    print(f"   V3 win rate: {win_rate:.1%}")
    print(f"   Improvement: {(win_rate - current_model_wr)*100:+.1f} percentage points")
    print()

    # Breakdown by side
    print(f"📊 Breakdown by Side:")
    for side in ['yes', 'no']:
        side_trades = trades[trades['side'] == side]
        if len(side_trades) > 0:
            side_wins = side_trades['won'].sum()
            side_wr = side_wins / len(side_trades)
            print(f"   {side.upper()}: {len(side_trades):,} trades, {side_wr:.1%} WR")
    print()

    # Breakdown by momentum direction
    print(f"📊 Breakdown by Momentum:")
    trades['momentum_dir'] = trades['momentum_pct'].apply(lambda x: 'UP' if x > 0 else 'DOWN')
    for direction in ['UP', 'DOWN']:
        dir_trades = trades[trades['momentum_dir'] == direction]
        if len(dir_trades) > 0:
            dir_wins = dir_trades['won'].sum()
            dir_wr = dir_wins / len(dir_trades)
            print(f"   {direction}: {len(dir_trades):,} trades, {dir_wr:.1%} WR")
    print()

    # Top skip reasons
    skipped = results_df[results_df['would_take'] == False]
    if len(skipped) > 0:
        print(f"🚫 Top Reasons for Skipping ({len(skipped):,} markets):")
        skip_reasons = skipped['reason'].value_counts().head(10)
        for reason, count in skip_reasons.items():
            pct = count / len(skipped) * 100
            print(f"   {reason}: {count:,} ({pct:.1f}%)")
        print()

    # Sample of trades that would be taken
    print("✅ Sample of Trades V3 Would Take:")
    print()
    sample_trades = trades.head(10)
    for idx, row in sample_trades.iterrows():
        outcome_emoji = "✅" if row['won'] else "❌"
        print(f"   {outcome_emoji} {row['ticker'][:40]}")
        print(f"      Side: {row['side'].upper()}, Outcome: {row['outcome'].upper()}, Mom: {row['momentum_pct']:+.2f}%")
        print(f"      V3 Prob: {row['v3_prob']:.1%}, {row['reason']}")
        print()


if __name__ == '__main__':
    main()
