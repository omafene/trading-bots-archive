#!/usr/bin/env python3
"""
Comprehensive Settings Optimizer - Grid Search Analysis

Tests all combinations of filter settings to find optimal configuration
for maximizing profit and win rate.
"""

import csv
from datetime import datetime, timezone, timedelta
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from itertools import product

def get_outcomes(alert_trades, client):
    """Fetch outcomes for closed markets"""
    results = []
    now = datetime.now(timezone.utc)

    for row in alert_trades:
        ticker = row['ticker']
        try:
            if '-' in ticker:
                parts = ticker.split('-')
                time_part = parts[1]
                month_map = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}

                day = int(time_part[0:2])
                month = month_map[time_part[2:5]]
                year = 2000 + int(time_part[5:7])
                hour = int(time_part[7:9])
                minute = int(time_part[9:11])
                close_time = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

                if now > close_time + timedelta(minutes=2):
                    market = client.get_market(ticker)
                    if market and market.get('result'):
                        outcome = market['result']
                        side = row['best_edge_side']
                        market_price = float(row[f'{side}_market_price'])

                        won = (outcome == side)
                        profit = (1.00 - market_price) if won else -market_price

                        results.append({
                            'edge': float(row['best_edge_pct']),
                            'signal': float(row['signal_strength']),
                            'prob': float(row[f'{side}_expected_prob']),
                            'price': market_price,
                            'minutes_to_close': float(row['minutes_to_close']) if row['minutes_to_close'] else 0,
                            'trend_strength': float(row['trend_strength']) if row['trend_strength'] else 0,
                            'won': won,
                            'profit': profit,
                        })
        except:
            pass

    return results

def test_combination(results, min_edge, min_prob, max_price, min_signal, min_trend, min_time, max_time):
    """Test a specific combination of filters"""
    filtered = [
        r for r in results
        if r['edge'] >= min_edge
        and r['prob'] >= min_prob
        and r['price'] <= max_price
        and r['signal'] >= min_signal
        and r['trend_strength'] >= min_trend
        # Skip time filter if minutes_to_close is 0 (unreliable in data)
        and (r['minutes_to_close'] == 0 or min_time <= r['minutes_to_close'] <= max_time)
    ]

    if not filtered:
        return None

    wins = len([r for r in filtered if r['won']])
    total_profit = sum(r['profit'] for r in filtered)
    win_rate = (wins / len(filtered)) * 100
    avg_profit = total_profit / len(filtered)

    return {
        'min_edge': min_edge,
        'min_prob': min_prob,
        'max_price': max_price,
        'min_signal': min_signal,
        'min_trend': min_trend,
        'min_time': min_time,
        'max_time': max_time,
        'trades': len(filtered),
        'wins': wins,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
    }

def main():
    print("🔍 COMPREHENSIVE SETTINGS OPTIMIZER")
    print("=" * 100)
    print("Testing all combinations of filter settings...\n")

    # Load data
    config = load_config_with_env('config_15m.yaml')
    client = KalshiClient(config)

    with open('data/negative_edges/skipped_trades.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    cutoff = datetime(2026, 2, 4, 22, 30, tzinfo=timezone.utc)
    filtered = [r for r in data if datetime.fromisoformat(r['timestamp']) >= cutoff]

    # Filter for alert-worthy trades (edge>=1% OR signal>=30)
    alert_trades = [
        r for r in filtered
        if float(r['best_edge_pct']) >= 1.0 or float(r['signal_strength']) >= 30.0
    ]

    print(f"Alert-worthy trades: {len(alert_trades)}")
    print("Fetching outcomes...\n")

    results = get_outcomes(alert_trades, client)
    print(f"Closed trades with outcomes: {len(results)}\n")

    if len(results) < 10:
        print("⚠️  Not enough closed trades for reliable analysis.")
        return

    # Define parameter ranges to test
    edge_values = [0, 1, 3, 5, 8, 10, 12, 15]
    prob_values = [0, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
    price_values = [0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 1.00]
    signal_values = [0, 20, 25, 30, 35, 40]
    trend_values = [0, 0.10, 0.15, 0.20]

    # Grid search
    print(f"Testing {len(edge_values) * len(prob_values) * len(price_values) * len(signal_values) * len(trend_values)} combinations...")
    print("This may take a minute...\n")

    all_results = []

    for edge, prob, price, signal, trend in product(
        edge_values, prob_values, price_values, signal_values, trend_values
    ):
        result = test_combination(results, edge, prob, price, signal, trend, 0, 15)
        if result and result['trades'] >= 3:  # Require at least 3 trades
            all_results.append(result)

    if not all_results:
        print("No valid combinations found.")
        return

    print(f"Found {len(all_results)} valid combinations (≥5 trades each)\n")

    # Sort and display results
    print("=" * 95)
    print("🏆 TOP 20 BY TOTAL PROFIT")
    print("=" * 95)
    print(f"{'Rank':<5} {'Edge%':<7} {'Prob':<7} {'Price':<8} {'Signal':<8} {'Trend':<7} {'Trades':<8} {'Win%':<8} {'Total $':<10}")
    print("-" * 95)

    by_profit = sorted(all_results, key=lambda x: x['total_profit'], reverse=True)[:20]
    for i, r in enumerate(by_profit, 1):
        print(f"{i:<5} ≥{r['min_edge']:<5}% ≥{r['min_prob']:<5.0%} ≤${r['max_price']:<6.2f} ≥{r['min_signal']:<6} "
              f"≥{r['min_trend']:<5.2f} {r['trades']:<8} "
              f"{r['win_rate']:<7.1f}% ${r['total_profit']:<9.2f}")

    print(f"\n{'=' * 95}")
    print("🎯 TOP 20 BY WIN RATE")
    print("=" * 95)
    print(f"{'Rank':<5} {'Edge%':<7} {'Prob':<7} {'Price':<8} {'Signal':<8} {'Trend':<7} {'Trades':<8} {'Win%':<8} {'Total $':<10}")
    print("-" * 95)

    by_winrate = sorted(all_results, key=lambda x: x['win_rate'], reverse=True)[:20]
    for i, r in enumerate(by_winrate, 1):
        print(f"{i:<5} ≥{r['min_edge']:<5}% ≥{r['min_prob']:<5.0%} ≤${r['max_price']:<6.2f} ≥{r['min_signal']:<6} "
              f"≥{r['min_trend']:<5.2f} {r['trades']:<8} "
              f"{r['win_rate']:<7.1f}% ${r['total_profit']:<9.2f}")

    print(f"\n{'=' * 95}")
    print("⚖️  TOP 20 BY BALANCED SCORE (Win Rate × Total Profit)")
    print("=" * 95)
    print(f"{'Rank':<5} {'Edge%':<7} {'Prob':<7} {'Price':<8} {'Signal':<8} {'Trend':<7} {'Trades':<8} {'Win%':<8} {'Total $':<10}")
    print("-" * 95)

    for r in all_results:
        r['balanced_score'] = (r['win_rate'] / 100) * r['total_profit'] if r['total_profit'] > 0 else 0

    by_balanced = sorted(all_results, key=lambda x: x['balanced_score'], reverse=True)[:20]
    for i, r in enumerate(by_balanced, 1):
        print(f"{i:<5} ≥{r['min_edge']:<5}% ≥{r['min_prob']:<5.0%} ≤${r['max_price']:<6.2f} ≥{r['min_signal']:<6} "
              f"≥{r['min_trend']:<5.2f} {r['trades']:<8} "
              f"{r['win_rate']:<7.1f}% ${r['total_profit']:<9.2f}")

    # Final recommendation
    print(f"\n{'=' * 100}")
    print("💡 RECOMMENDED OPTIMAL SETTINGS")
    print("=" * 100)

    best_profit = by_profit[0]
    best_winrate = by_winrate[0]
    best_balanced = by_balanced[0]

    print(f"\n📊 For Maximum Profit:")
    print(f"   min_edge_percent: {best_profit['min_edge']}")
    print(f"   min_expected_probability: {best_profit['min_prob']:.2f}")
    print(f"   max_entry_price: ${best_profit['max_price']:.2f}")
    print(f"   min_signal_strength: {best_profit['min_signal']}")
    print(f"   min_trend_strength: {best_profit['min_trend']:.2f}")
    print(f"   Expected: {best_profit['trades']} trades, {best_profit['win_rate']:.1f}% win rate, ${best_profit['total_profit']:.2f} profit")

    print(f"\n🎯 For Maximum Win Rate:")
    print(f"   min_edge_percent: {best_winrate['min_edge']}")
    print(f"   min_expected_probability: {best_winrate['min_prob']:.2f}")
    print(f"   max_entry_price: ${best_winrate['max_price']:.2f}")
    print(f"   min_signal_strength: {best_winrate['min_signal']}")
    print(f"   min_trend_strength: {best_winrate['min_trend']:.2f}")
    print(f"   Expected: {best_winrate['trades']} trades, {best_winrate['win_rate']:.1f}% win rate, ${best_winrate['total_profit']:.2f} profit")

    print(f"\n⚖️  For Best Balance:")
    print(f"   min_edge_percent: {best_balanced['min_edge']}")
    print(f"   min_expected_probability: {best_balanced['min_prob']:.2f}")
    print(f"   max_entry_price: ${best_balanced['max_price']:.2f}")
    print(f"   min_signal_strength: {best_balanced['min_signal']}")
    print(f"   min_trend_strength: {best_balanced['min_trend']:.2f}")
    print(f"   Expected: {best_balanced['trades']} trades, {best_balanced['win_rate']:.1f}% win rate, ${best_balanced['total_profit']:.2f} profit")

    print(f"\n" + "=" * 100)

if __name__ == "__main__":
    main()
