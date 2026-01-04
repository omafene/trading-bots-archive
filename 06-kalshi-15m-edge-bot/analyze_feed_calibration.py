#!/usr/bin/env python3
"""
Analyze Spot Feed Calibration Data

Reviews the tracked comparison of Kalshi's floor_strike vs our spot price feed
to identify systematic bias and guide potential calibration adjustments.
"""

import csv
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_calibration():
    csv_path = Path("data/feed_calibration/floor_strike_vs_spot.csv")

    if not csv_path.exists():
        print("❌ No calibration data found yet.")
        print(f"   Expected file: {csv_path}")
        print("\n💡 Run the bot for a few hours to collect data from market opens.")
        return

    # Read data
    data = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    if not data:
        print("❌ Calibration file exists but has no data yet.")
        print("   Wait for markets to open and bot will track the data.")
        return

    print(f"\n📊 Spot Feed Calibration Analysis")
    print(f"=" * 60)
    print(f"Sample size: {len(data)} market opens\n")

    # Analyze by symbol
    by_symbol = defaultdict(list)
    for row in data:
        symbol = row['symbol']
        delta_dollars = float(row['delta_dollars'])
        delta_pct = float(row['delta_pct'])
        by_symbol[symbol].append({
            'delta_dollars': delta_dollars,
            'delta_pct': delta_pct,
            'ticker': row['ticker'],
            'kalshi_floor': float(row['kalshi_floor_strike']),
            'our_spot': float(row['our_spot_price']),
        })

    # Summary by symbol
    for symbol in sorted(by_symbol.keys()):
        samples = by_symbol[symbol]
        deltas_dollars = [s['delta_dollars'] for s in samples]
        deltas_pct = [s['delta_pct'] for s in samples]

        avg_delta = statistics.mean(deltas_dollars)
        avg_pct = statistics.mean(deltas_pct)
        std_delta = statistics.stdev(deltas_dollars) if len(deltas_dollars) > 1 else 0

        print(f"\n{symbol}:")
        print(f"  Samples: {len(samples)}")
        print(f"  Average delta: ${avg_delta:+.2f} ({avg_pct:+.3f}%)")
        print(f"  Std deviation: ${std_delta:.2f}")

        # Bias detection
        if abs(avg_delta) > 2.0:
            direction = "HIGH" if avg_delta > 0 else "LOW"
            print(f"  ⚠️  BIAS DETECTED: Your feed is consistently {direction} by ${abs(avg_delta):.2f}")

        # Show recent examples
        print(f"\n  Recent samples:")
        for sample in samples[-3:]:
            print(f"    {sample['ticker']}: Kalshi=${sample['kalshi_floor']:.2f} vs Ours=${sample['our_spot']:.2f} (delta: ${sample['delta_dollars']:+.2f})")

    # Overall summary
    print(f"\n{'=' * 60}")
    print(f"\n📋 Summary:")

    all_deltas = [float(row['delta_dollars']) for row in data]
    overall_avg = statistics.mean(all_deltas)
    overall_std = statistics.stdev(all_deltas) if len(all_deltas) > 1 else 0

    print(f"Overall average delta: ${overall_avg:+.2f}")
    print(f"Overall std deviation: ${overall_std:.2f}")

    # Recommendations
    print(f"\n💡 Recommendations:")

    if abs(overall_avg) < 1.0:
        print("✅ Your spot feed is well-calibrated with Kalshi's reference.")
        print("   No adjustments needed.")
    elif abs(overall_avg) < 3.0:
        print(f"⚠️  Minor bias detected (${overall_avg:+.2f}).")
        print("   Consider monitoring for a few more hours to confirm pattern.")
    else:
        print(f"🔴 Significant bias detected (${overall_avg:+.2f})!")
        print("   Recommendations:")
        print(f"   1. Apply calibration offset: adjusted_price = raw_price - {overall_avg:.2f}")
        print(f"   2. Or investigate which exchange is closest to Kalshi (check CSV)")
        print(f"   3. Consider switching from median to weighted average")

    print(f"\n📁 Full data: {csv_path}")

if __name__ == "__main__":
    analyze_calibration()
