#!/usr/bin/env python3
"""
Analyze detected edges since a specific time to optimize settings

Determines which threshold combinations provide:
1. Best win rate
2. Highest ROI potential
3. Optimal signal/edge/probability settings
"""

import csv
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import statistics

def get_market_outcome(client, ticker):
    """Get actual outcome of a closed market"""
    try:
        market = client.get_market(ticker)
        if market and market.get('result') in ['yes', 'no']:
            return market['result']
    except:
        pass
    return None

def analyze_edges(since_time_str):
    """Analyze edges detected since specified time"""

    # Parse cutoff time
    if 'T' in since_time_str:
        cutoff = datetime.fromisoformat(since_time_str.replace('Z', '+00:00'))
    else:
        # Parse as "HH:MM" and assume today
        from datetime import datetime, timezone
        import pytz
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
        hour, minute = map(int, since_time_str.split(':'))
        cutoff = et.localize(datetime(now.year, now.month, now.day, hour, minute))
        cutoff = cutoff.astimezone(timezone.utc)

    # Load data
    csv_path = Path('data/negative_edges/skipped_trades.csv')
    if not csv_path.exists():
        print(f"❌ No data file found: {csv_path}")
        return

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        all_data = list(reader)

    # Filter since cutoff
    data = []
    for row in all_data:
        ts = datetime.fromisoformat(row['timestamp'])
        if ts >= cutoff:
            data.append(row)

    print(f"\n📊 Edge Analysis Since {cutoff.astimezone(pytz.timezone('US/Eastern')).strftime('%I:%M %p ET')}")
    print(f"=" * 80)
    print(f"Total opportunities analyzed: {len(data)}\n")

    if not data:
        print("No data in time range.")
        return

    # Get Kalshi client to check outcomes
    from config_loader import load_config_with_env
    from kalshi_client import KalshiClient

    config = load_config_with_env('config_15m.yaml')
    client = KalshiClient(config)

    # Check outcomes for closed markets
    print("⏳ Checking outcomes for closed markets...")
    now = datetime.now(timezone.utc)

    for row in data:
        # Skip if already checked
        if row.get('outcome_checked') == 'True':
            continue

        ticker = row['ticker']

        # Extract close time from ticker format: KXBTC15M-26FEB041800-00
        # Format: KXSYM15M-DDMMMYYHHММ-XX where HHMM is close time
        try:
            if '-' in ticker:
                parts = ticker.split('-')
                if len(parts) >= 2:
                    time_part = parts[1]  # e.g., "26FEB041800"
                    if len(time_part) >= 11:
                        day = int(time_part[0:2])
                        month_map = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                                   'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
                        month = month_map.get(time_part[2:5])
                        year = 2000 + int(time_part[5:7])
                        hour = int(time_part[7:9])
                        minute = int(time_part[9:11])

                        close_time = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

                        # Only check if market closed >2 minutes ago
                        if now > close_time + timedelta(minutes=2):
                            outcome = get_market_outcome(client, ticker)
                            row['actual_outcome'] = outcome or ''
                            row['outcome_checked'] = 'True' if outcome else 'False'

                            # Determine if trade would have won
                            if outcome:
                                best_side = row['best_edge_side']
                                row['would_have_won'] = 'True' if outcome == best_side else 'False'
        except Exception as e:
            pass

    # Count outcomes
    checked = [r for r in data if r.get('outcome_checked') == 'True']
    won = [r for r in checked if r.get('would_have_won') == 'True']
    lost = [r for r in checked if r.get('would_have_won') == 'False']

    print(f"✅ Outcomes available: {len(checked)} / {len(data)} markets")
    if checked:
        win_rate = len(won) / len(checked) * 100
        print(f"   Win rate: {len(won)}/{len(checked)} = {win_rate:.1f}%\n")

    # Analyze by threshold combinations
    print(f"\n{'='*80}")
    print("🎯 OPTIMAL SETTINGS ANALYSIS")
    print(f"{'='*80}\n")

    if len(checked) < 10:
        print("⚠️  Not enough closed markets yet for statistical analysis.")
        print(f"   Need at least 10, have {len(checked)}.")
        print("\n💡 Run this script again in 30-60 minutes for better insights.\n")
        return

    # Test different threshold combinations
    thresholds_to_test = [
        # (min_edge, min_prob, min_signal, name)
        (5, 0.30, 0, "Very Aggressive"),
        (8, 0.35, 20, "Aggressive"),
        (10, 0.40, 30, "Current (Moderate)"),
        (12, 0.45, 40, "Conservative"),
        (15, 0.50, 50, "Very Conservative"),
    ]

    results = []

    for min_edge, min_prob, min_signal, name in thresholds_to_test:
        # Filter opportunities that would pass this threshold
        qualified = []
        for row in checked:
            edge = float(row['best_edge_pct'])
            prob = float(row[f"{row['best_edge_side']}_expected_prob"])
            signal = float(row['signal_strength'])

            if edge >= min_edge and prob >= min_prob and signal >= min_signal:
                qualified.append(row)

        if not qualified:
            continue

        # Calculate win rate
        wins = [r for r in qualified if r['would_have_won'] == 'True']
        win_rate = len(wins) / len(qualified) * 100 if qualified else 0

        # Calculate theoretical ROI
        total_roi = 0
        for row in qualified:
            edge = float(row['best_edge_pct'])
            won = row['would_have_won'] == 'True'

            # Simplified ROI calculation
            if won:
                # Won: gained edge%
                total_roi += edge
            else:
                # Lost: lost ~100% (simplified)
                total_roi -= 100

        avg_roi_per_trade = total_roi / len(qualified) if qualified else 0

        results.append({
            'name': name,
            'min_edge': min_edge,
            'min_prob': min_prob,
            'min_signal': min_signal,
            'qualified': len(qualified),
            'wins': len(wins),
            'win_rate': win_rate,
            'total_roi': total_roi,
            'avg_roi': avg_roi_per_trade
        })

    # Sort by win rate
    results.sort(key=lambda x: x['win_rate'], reverse=True)

    print("📈 WIN RATE RANKINGS:\n")
    print(f"{'Setting':<20} {'Edge%':<8} {'Prob':<7} {'Signal':<8} {'Trades':<8} {'Wins':<6} {'Win%':<8} {'Avg ROI':<10}")
    print("-" * 90)

    for r in results:
        print(f"{r['name']:<20} {r['min_edge']:<8} {r['min_prob']:<7.0%} {r['min_signal']:<8} "
              f"{r['qualified']:<8} {r['wins']:<6} {r['win_rate']:<7.1f}% {r['avg_roi']:<9.1f}%")

    # Sort by total ROI
    results.sort(key=lambda x: x['total_roi'], reverse=True)

    print(f"\n\n💰 TOTAL ROI RANKINGS:\n")
    print(f"{'Setting':<20} {'Edge%':<8} {'Prob':<7} {'Signal':<8} {'Trades':<8} {'Total ROI':<12} {'Avg ROI':<10}")
    print("-" * 95)

    for r in results:
        print(f"{r['name']:<20} {r['min_edge']:<8} {r['min_prob']:<7.0%} {r['min_signal']:<8} "
              f"{r['qualified']:<8} {r['total_roi']:<11.1f}% {r['avg_roi']:<9.1f}%")

    # Recommendations
    print(f"\n\n{'='*80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'='*80}\n")

    best_wr = results[0] if results else None
    if best_wr:
        print(f"✅ Best Win Rate: {best_wr['name']}")
        print(f"   Settings: Edge≥{best_wr['min_edge']}%, Prob≥{best_wr['min_prob']:.0%}, Signal≥{best_wr['min_signal']}")
        print(f"   Results: {best_wr['win_rate']:.1f}% win rate over {best_wr['qualified']} trades")
        print(f"   ROI: {best_wr['avg_roi']:.1f}% per trade\n")

    results.sort(key=lambda x: x['total_roi'], reverse=True)
    best_roi = results[0] if results else None

    if best_roi and best_roi != best_wr:
        print(f"💰 Best Total ROI: {best_roi['name']}")
        print(f"   Settings: Edge≥{best_roi['min_edge']}%, Prob≥{best_roi['min_prob']:.0%}, Signal≥{best_roi['min_signal']}")
        print(f"   Results: {best_roi['win_rate']:.1f}% win rate over {best_roi['qualified']} trades")
        print(f"   ROI: {best_roi['avg_roi']:.1f}% per trade\n")

    print("\n💭 Interpretation:")
    print("   - Higher edge/prob thresholds = fewer trades but higher win rate")
    print("   - Lower thresholds = more trades but higher risk")
    print("   - Optimal balance depends on your risk tolerance\n")

if __name__ == "__main__":
    import pytz
    from datetime import timedelta

    # Default to 5:30 PM ET today
    if len(sys.argv) > 1:
        since_time = sys.argv[1]
    else:
        since_time = "17:30"  # 5:30 PM

    analyze_edges(since_time)
