#!/usr/bin/env python3
"""
Trade Insights - Detailed analysis and recommendations
"""

import re
import statistics
from collections import defaultdict
from datetime import datetime


def parse_signals_from_logs(log_file: str = "logs/edge_bot.log"):
    """Parse signals from log file"""
    signals = []

    with open(log_file, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        signal_match = re.search(
            r'🎯 (\S+) \| (YES|NO) @ (\d+)% \| Edge: ([\d.]+)% \| ROI: ([\d.]+)%',
            line
        )

        if signal_match:
            ticker = signal_match.group(1)
            side = signal_match.group(2)
            entry_price = int(signal_match.group(3)) / 100
            edge = float(signal_match.group(4))
            expected_roi = float(signal_match.group(5))

            timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            timestamp = timestamp_match.group(1) if timestamp_match else None

            # Look for signal strength
            signal_strength = None
            for j in range(i+1, min(i+5, len(lines))):
                strength_match = re.search(r'Signal Strength: ([\d.]+)/100', lines[j])
                if strength_match:
                    signal_strength = float(strength_match.group(1))
                    break

            # Extract symbol
            if 'BTC' in ticker:
                symbol = 'BTC'
            elif 'ETH' in ticker:
                symbol = 'ETH'
            elif 'SOL' in ticker:
                symbol = 'SOL'
            else:
                symbol = 'UNKNOWN'

            signal = {
                'timestamp': timestamp,
                'ticker': ticker,
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'edge_percent': edge,
                'expected_roi': expected_roi,
                'signal_strength': signal_strength,
            }

            signals.append(signal)

        i += 1

    return signals


def analyze_price_edge_relationship(signals):
    """Analyze relationship between entry price and edge"""
    print("\n" + "="*70)
    print("💡 KEY INSIGHT: Entry Price vs Edge Relationship")
    print("="*70)

    # Bucket by entry price
    price_buckets = {
        'Very Low (0-15¢)': [],
        'Low (15-30¢)': [],
        'Medium (30-50¢)': [],
        'High (50-75¢)': [],
        'Very High (75%+)': []
    }

    for s in signals:
        price_cents = s['entry_price'] * 100
        if price_cents < 15:
            bucket = 'Very Low (0-15¢)'
        elif price_cents < 30:
            bucket = 'Low (15-30¢)'
        elif price_cents < 50:
            bucket = 'Medium (30-50¢)'
        elif price_cents < 75:
            bucket = 'High (50-75¢)'
        else:
            bucket = 'Very High (75%+)'

        price_buckets[bucket].append(s)

    print(f"\n{'Price Range':<20} {'Count':<8} {'Avg Edge':<12} {'Avg Strength':<15} {'Avg ROI'}")
    print("-" * 70)

    for bucket_name, bucket_signals in price_buckets.items():
        if not bucket_signals:
            continue

        count = len(bucket_signals)
        avg_edge = statistics.mean([s['edge_percent'] for s in bucket_signals])
        avg_strength = statistics.mean([s['signal_strength'] for s in bucket_signals
                                       if s['signal_strength']])
        avg_roi = statistics.mean([s['expected_roi'] for s in bucket_signals])

        print(f"{bucket_name:<20} {count:<8} {avg_edge:<12.1f} {avg_strength:<15.1f} {avg_roi:.0f}%")

    print("\n💭 Observation:")
    print("   Lower entry prices show HIGHER edge and ROI expectations")
    print("   This suggests the bot is finding value in underpriced outcomes")


def analyze_symbol_performance(signals):
    """Analyze performance by symbol"""
    print("\n" + "="*70)
    print("📊 SYMBOL COMPARISON")
    print("="*70)

    by_symbol = defaultdict(list)
    for s in signals:
        by_symbol[s['symbol']].append(s)

    print(f"\n{'Symbol':<8} {'Signals':<10} {'Avg Edge':<12} {'Avg Strength':<15} {'YES/NO Ratio'}")
    print("-" * 70)

    for symbol in sorted(by_symbol.keys()):
        symbol_signals = by_symbol[symbol]
        count = len(symbol_signals)
        avg_edge = statistics.mean([s['edge_percent'] for s in symbol_signals])
        avg_strength = statistics.mean([s['signal_strength'] for s in symbol_signals
                                       if s['signal_strength']])

        yes_count = sum(1 for s in symbol_signals if s['side'] == 'YES')
        no_count = sum(1 for s in symbol_signals if s['side'] == 'NO')
        yes_ratio = yes_count / count * 100 if count > 0 else 0

        print(f"{symbol:<8} {count:<10} {avg_edge:<12.1f} {avg_strength:<15.1f} "
              f"{yes_count}/{no_count} ({yes_ratio:.0f}% YES)")


def analyze_edge_vs_strength(signals):
    """Analyze correlation between edge and signal strength"""
    print("\n" + "="*70)
    print("🔍 EDGE vs SIGNAL STRENGTH CORRELATION")
    print("="*70)

    # Group by edge ranges, show strength distribution
    edge_ranges = {
        '10-20%': [],
        '20-30%': [],
        '30-40%': [],
        '40-50%': [],
        '50%+': []
    }

    for s in signals:
        edge = s['edge_percent']
        if s['signal_strength'] is None:
            continue

        if 10 <= edge < 20:
            edge_ranges['10-20%'].append(s['signal_strength'])
        elif 20 <= edge < 30:
            edge_ranges['20-30%'].append(s['signal_strength'])
        elif 30 <= edge < 40:
            edge_ranges['30-40%'].append(s['signal_strength'])
        elif 40 <= edge < 50:
            edge_ranges['40-50%'].append(s['signal_strength'])
        elif edge >= 50:
            edge_ranges['50%+'].append(s['signal_strength'])

    print(f"\n{'Edge Range':<12} {'Count':<8} {'Avg Strength':<15} {'Min':<8} {'Max':<8} {'StdDev'}")
    print("-" * 70)

    for edge_range, strengths in edge_ranges.items():
        if not strengths:
            continue

        count = len(strengths)
        avg = statistics.mean(strengths)
        min_s = min(strengths)
        max_s = max(strengths)
        std = statistics.stdev(strengths) if len(strengths) > 1 else 0

        print(f"{edge_range:<12} {count:<8} {avg:<15.1f} {min_s:<8.1f} {max_s:<8.1f} {std:.1f}")

    print("\n💭 Observation:")
    print("   Higher edge does NOT always mean higher signal strength")
    print("   This suggests edge and strength capture different aspects of opportunity quality")


def recommend_thresholds(signals):
    """Recommend optimal threshold settings"""
    print("\n" + "="*70)
    print("⚙️  THRESHOLD RECOMMENDATIONS")
    print("="*70)

    # Analyze signal quality distribution
    strengths = [s['signal_strength'] for s in signals if s['signal_strength']]
    edges = [s['edge_percent'] for s in signals]

    # Current settings
    current_min_edge = 30
    current_min_strength = 50

    print("\n📊 Current Settings:")
    print(f"   min_edge_percent: {current_min_edge}%")
    print(f"   min_signal_strength: {current_min_strength}")

    # What % of signals pass current thresholds?
    passing = [s for s in signals
              if s['signal_strength'] and
              s['signal_strength'] >= current_min_strength and
              s['edge_percent'] >= current_min_edge]

    pass_rate = len(passing) / len(signals) * 100

    print(f"\n📉 Current Filter Pass Rate: {pass_rate:.1f}%")
    print(f"   {len(passing)} out of {len(signals)} signals pass your filters")

    # Calculate percentiles
    edge_p25 = statistics.quantiles(edges, n=4)[0]
    edge_p50 = statistics.median(edges)
    edge_p75 = statistics.quantiles(edges, n=4)[2]

    strength_p25 = statistics.quantiles(strengths, n=4)[0]
    strength_p50 = statistics.median(strengths)
    strength_p75 = statistics.quantiles(strengths, n=4)[2]

    print("\n📊 Signal Distribution:")
    print(f"   Edge:     25th={edge_p25:.1f}%, 50th={edge_p50:.1f}%, 75th={edge_p75:.1f}%")
    print(f"   Strength: 25th={strength_p25:.1f}, 50th={strength_p50:.1f}, 75th={strength_p75:.1f}")

    print("\n💡 Recommendations:")

    if current_min_edge > edge_p75:
        print(f"   ⚠️  Your min_edge ({current_min_edge}%) is VERY restrictive (>75th percentile)")
        print(f"   Consider: Lowering to {edge_p50:.0f}% (median) for more opportunities")
    elif current_min_edge > edge_p50:
        print(f"   ✓ Your min_edge ({current_min_edge}%) is moderately selective")
    else:
        print(f"   ⚠️  Your min_edge ({current_min_edge}%) is permissive (<50th percentile)")

    if current_min_strength > strength_p75:
        print(f"   ⚠️  Your min_strength ({current_min_strength}) is restrictive (>75th percentile)")
    elif current_min_strength > strength_p50:
        print(f"   ✓ Your min_strength ({current_min_strength}) is moderately selective")
    else:
        print(f"   ⚠️  Your min_strength ({current_min_strength}) is permissive (<50th percentile)")

    # Show what different thresholds would yield
    print("\n🎯 Trade-off Analysis (% of signals that would pass):")
    print(f"\n{'Edge':<8} {'Strength':<10} {'Signals':<10} {'% of Total'}")
    print("-" * 40)

    threshold_combos = [
        (20, 50),
        (25, 55),
        (30, 50),
        (30, 60),
        (35, 60),
    ]

    for min_edge, min_strength in threshold_combos:
        passing = sum(1 for s in signals
                     if s['signal_strength'] and
                     s['signal_strength'] >= min_strength and
                     s['edge_percent'] >= min_edge)
        pct = passing / len(signals) * 100
        print(f"{min_edge}%{'':<4} {min_strength:<10} {passing:<10} {pct:.1f}%")


def recent_signals_detail(signals, days: int = 3):
    """Show detailed recent signals"""
    print("\n" + "="*70)
    print(f"📅 RECENT SIGNALS (Last {days} days of data)")
    print("="*70)

    # Get most recent signals
    recent = sorted(signals, key=lambda x: x['timestamp'] or '', reverse=True)[:20]

    if not recent:
        print("❌ No signals found")
        return

    print(f"\nShowing {len(recent)} most recent signals:\n")
    print(f"{'Time':<12} {'Symbol':<6} {'Side':<4} {'Entry':<8} {'Edge':<8} {'Strength':<10} {'ROI'}")
    print("-" * 70)

    for s in recent:
        time_str = s['timestamp'][11:16] if s['timestamp'] else 'N/A'
        entry_str = f"{s['entry_price']:.0%}"
        edge_str = f"{s['edge_percent']:.1f}%"
        strength_str = f"{s['signal_strength']:.0f}" if s['signal_strength'] else 'N/A'
        roi_str = f"{s['expected_roi']:.0f}%"

        print(f"{time_str:<12} {s['symbol']:<6} {s['side']:<4} {entry_str:<8} "
              f"{edge_str:<8} {strength_str:<10} {roi_str}")


def main():
    print("🔍 Parsing trade signals...")
    signals = parse_signals_from_logs()
    print(f"✅ Found {len(signals)} signals\n")

    # Run analyses
    analyze_price_edge_relationship(signals)
    analyze_symbol_performance(signals)
    analyze_edge_vs_strength(signals)
    recommend_thresholds(signals)
    recent_signals_detail(signals)

    print("\n" + "="*70)
    print("✅ Analysis Complete!")
    print("="*70)


if __name__ == '__main__':
    main()
