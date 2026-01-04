#!/usr/bin/env python3
"""
Trade Analysis Tool
Analyzes trading performance from edge_bot logs
"""

import re
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict
import statistics


class TradeAnalyzer:
    """Analyze trade signals and performance from logs"""

    def __init__(self, log_file: str = "logs/edge_bot.log"):
        self.log_file = log_file
        self.signals = []
        self.executions = []

    def parse_logs(self):
        """Parse log file for trade signals and executions"""
        print(f"📖 Parsing {self.log_file}...")

        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for signal detection pattern
            # 🎯 KXBTC15M-26FEB021815-15 | NO @ 53% | Edge: 32.5% | ROI: 79.2%
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

                # Get timestamp
                timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                timestamp = timestamp_match.group(1) if timestamp_match else None

                # Look for signal strength in next few lines
                signal_strength = None
                for j in range(i+1, min(i+5, len(lines))):
                    strength_match = re.search(r'Signal Strength: ([\d.]+)/100', lines[j])
                    if strength_match:
                        signal_strength = float(strength_match.group(1))
                        break

                # Extract market info from ticker
                symbol = self._extract_symbol(ticker)
                market_time = self._extract_market_time(ticker)

                signal = {
                    'timestamp': timestamp,
                    'ticker': ticker,
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'edge_percent': edge,
                    'expected_roi': expected_roi,
                    'signal_strength': signal_strength,
                    'market_time': market_time
                }

                self.signals.append(signal)

            # Look for execution pattern
            # 🚀 Executing MARKET/LIMIT for KXBTC15M-26FEB021815-15 (YES/NO)
            exec_match = re.search(
                r'🚀 Executing (MARKET|LIMIT) (?:order )?for (\S+) \((\w+)\)',
                line
            )

            if exec_match:
                order_type = exec_match.group(1)
                ticker = exec_match.group(2)
                side = exec_match.group(3).upper()

                timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                timestamp = timestamp_match.group(1) if timestamp_match else None

                execution = {
                    'timestamp': timestamp,
                    'ticker': ticker,
                    'side': side,
                    'order_type': order_type
                }

                self.executions.append(execution)

            i += 1

        print(f"✅ Found {len(self.signals)} signals, {len(self.executions)} executions")

    def _extract_symbol(self, ticker: str) -> str:
        """Extract symbol from ticker (e.g., KXBTC15M-... -> BTC)"""
        if 'BTC' in ticker:
            return 'BTC'
        elif 'ETH' in ticker:
            return 'ETH'
        elif 'SOL' in ticker:
            return 'SOL'
        return 'UNKNOWN'

    def _extract_market_time(self, ticker: str) -> str:
        """Extract market time from ticker"""
        # KXBTC15M-26FEB021815-15 -> 18:15
        match = re.search(r'-\d{2}[A-Z]{3}\d{2}(\d{2})(\d{2})-', ticker)
        if match:
            hour = match.group(1)
            minute = match.group(2)
            return f"{hour}:{minute}"
        return None

    def analyze_signals(self):
        """Analyze signal characteristics"""
        if not self.signals:
            print("❌ No signals to analyze")
            return

        print("\n" + "="*60)
        print("📊 SIGNAL ANALYSIS")
        print("="*60)

        # Overall stats
        print(f"\n📈 Total Signals: {len(self.signals)}")
        print(f"🎯 Total Executions: {len(self.executions)}")
        print(f"📉 Execution Rate: {len(self.executions)/len(self.signals)*100:.1f}%")

        # Edge distribution
        edges = [s['edge_percent'] for s in self.signals]
        print(f"\n💰 Edge Statistics:")
        print(f"   Mean: {statistics.mean(edges):.1f}%")
        print(f"   Median: {statistics.median(edges):.1f}%")
        print(f"   Min: {min(edges):.1f}%")
        print(f"   Max: {max(edges):.1f}%")
        print(f"   StdDev: {statistics.stdev(edges):.1f}%")

        # Signal strength distribution
        strengths = [s['signal_strength'] for s in self.signals if s['signal_strength']]
        if strengths:
            print(f"\n🎯 Signal Strength Statistics:")
            print(f"   Mean: {statistics.mean(strengths):.1f}/100")
            print(f"   Median: {statistics.median(strengths):.1f}/100")
            print(f"   Min: {min(strengths):.1f}/100")
            print(f"   Max: {max(strengths):.1f}/100")

        # By symbol
        print(f"\n📊 Signals by Symbol:")
        by_symbol = defaultdict(int)
        for s in self.signals:
            by_symbol[s['symbol']] += 1
        for symbol, count in sorted(by_symbol.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.signals) * 100
            print(f"   {symbol}: {count} ({pct:.1f}%)")

        # By side
        print(f"\n📊 Signals by Side:")
        by_side = defaultdict(int)
        for s in self.signals:
            by_side[s['side']] += 1
        for side, count in sorted(by_side.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.signals) * 100
            print(f"   {side}: {count} ({pct:.1f}%)")

        # Entry price distribution
        print(f"\n💵 Entry Price Distribution:")
        entry_ranges = {
            '0-10¢': 0,
            '10-25¢': 0,
            '25-50¢': 0,
            '50-75¢': 0,
            '75-90¢': 0,
            '90-100¢': 0
        }
        for s in self.signals:
            price_cents = s['entry_price'] * 100
            if price_cents < 10:
                entry_ranges['0-10¢'] += 1
            elif price_cents < 25:
                entry_ranges['10-25¢'] += 1
            elif price_cents < 50:
                entry_ranges['25-50¢'] += 1
            elif price_cents < 75:
                entry_ranges['50-75¢'] += 1
            elif price_cents < 90:
                entry_ranges['75-90¢'] += 1
            else:
                entry_ranges['90-100¢'] += 1

        for range_name, count in entry_ranges.items():
            if count > 0:
                pct = count / len(self.signals) * 100
                print(f"   {range_name}: {count} ({pct:.1f}%)")

    def analyze_by_strength_buckets(self):
        """Analyze signals by strength buckets"""
        print("\n" + "="*60)
        print("🎯 ANALYSIS BY SIGNAL STRENGTH")
        print("="*60)

        buckets = {
            '0-30': [],
            '30-40': [],
            '40-50': [],
            '50-60': [],
            '60-70': [],
            '70-80': [],
            '80-100': []
        }

        for s in self.signals:
            strength = s.get('signal_strength')
            if strength is None:
                continue

            if strength < 30:
                bucket = '0-30'
            elif strength < 40:
                bucket = '30-40'
            elif strength < 50:
                bucket = '40-50'
            elif strength < 60:
                bucket = '50-60'
            elif strength < 70:
                bucket = '60-70'
            elif strength < 80:
                bucket = '70-80'
            else:
                bucket = '80-100'

            buckets[bucket].append(s)

        print(f"\n{'Strength':<12} {'Count':<8} {'Avg Edge':<12} {'Avg ROI':<12} {'Execution %'}")
        print("-" * 60)

        for bucket_name, signals in buckets.items():
            if not signals:
                continue

            count = len(signals)
            avg_edge = statistics.mean([s['edge_percent'] for s in signals])
            avg_roi = statistics.mean([s['expected_roi'] for s in signals])

            # Count executions for this bucket
            executed = sum(1 for s in signals
                          if any(e['ticker'] == s['ticker'] and e['side'] == s['side']
                                for e in self.executions))
            exec_rate = executed / count * 100 if count > 0 else 0

            print(f"{bucket_name:<12} {count:<8} {avg_edge:<12.1f} {avg_roi:<12.1f} {exec_rate:.1f}%")

    def analyze_by_edge_buckets(self):
        """Analyze signals by edge buckets"""
        print("\n" + "="*60)
        print("💰 ANALYSIS BY EDGE SIZE")
        print("="*60)

        buckets = {
            '0-10%': [],
            '10-20%': [],
            '20-30%': [],
            '30-40%': [],
            '40-50%': [],
            '50%+': []
        }

        for s in self.signals:
            edge = s['edge_percent']

            if edge < 10:
                bucket = '0-10%'
            elif edge < 20:
                bucket = '10-20%'
            elif edge < 30:
                bucket = '20-30%'
            elif edge < 40:
                bucket = '30-40%'
            elif edge < 50:
                bucket = '40-50%'
            else:
                bucket = '50%+'

            buckets[bucket].append(s)

        print(f"\n{'Edge Range':<12} {'Count':<8} {'Avg Strength':<15} {'Avg Entry $'}")
        print("-" * 60)

        for bucket_name, signals in buckets.items():
            if not signals:
                continue

            count = len(signals)
            avg_strength = statistics.mean([s['signal_strength'] for s in signals
                                           if s['signal_strength']])
            avg_entry = statistics.mean([s['entry_price'] for s in signals])

            print(f"{bucket_name:<12} {count:<8} {avg_strength:<15.1f} ${avg_entry:.2f}")

    def recent_activity(self, days: int = 7):
        """Show recent trading activity"""
        print("\n" + "="*60)
        print(f"📅 RECENT ACTIVITY (Last {days} days)")
        print("="*60)

        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)

        recent_signals = [s for s in self.signals
                         if s['timestamp'] and
                         datetime.strptime(s['timestamp'], '%Y-%m-%d %H:%M:%S') >= cutoff]

        if not recent_signals:
            print(f"❌ No signals in last {days} days")
            return

        print(f"\n📊 {len(recent_signals)} signals detected")

        # Group by day
        by_day = defaultdict(list)
        for s in recent_signals:
            day = s['timestamp'][:10]
            by_day[day].append(s)

        for day in sorted(by_day.keys(), reverse=True):
            signals = by_day[day]
            avg_edge = statistics.mean([s['edge_percent'] for s in signals])
            avg_strength = statistics.mean([s['signal_strength'] for s in signals
                                           if s['signal_strength']])

            print(f"\n{day}: {len(signals)} signals (Avg Edge: {avg_edge:.1f}%, "
                  f"Avg Strength: {avg_strength:.1f})")

            # Show top 3 signals
            top_signals = sorted(signals, key=lambda x: x['edge_percent'], reverse=True)[:3]
            for s in top_signals:
                print(f"  • {s['ticker'][:20]:20} | {s['side']:3} @ {s['entry_price']:.0%} | "
                      f"Edge: {s['edge_percent']:5.1f}% | Strength: {s['signal_strength']:.0f}")

    def export_to_csv(self, output_file: str = "data/signal_analysis.csv"):
        """Export signals to CSV for further analysis"""
        import csv
        from pathlib import Path

        Path(output_file).parent.mkdir(exist_ok=True, parents=True)

        with open(output_file, 'w', newline='') as f:
            fieldnames = ['timestamp', 'ticker', 'symbol', 'side', 'entry_price',
                         'edge_percent', 'expected_roi', 'signal_strength', 'market_time']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for signal in self.signals:
                writer.writerow(signal)

        print(f"\n💾 Exported {len(self.signals)} signals to {output_file}")


def main():
    analyzer = TradeAnalyzer()

    # Parse logs
    analyzer.parse_logs()

    # Run analyses
    analyzer.analyze_signals()
    analyzer.analyze_by_strength_buckets()
    analyzer.analyze_by_edge_buckets()
    analyzer.recent_activity(days=7)

    # Export data
    analyzer.export_to_csv()

    print("\n" + "="*60)
    print("✅ Analysis Complete!")
    print("="*60)


if __name__ == '__main__':
    main()
