#!/usr/bin/env python3
"""
Advanced Calibration Analyzer - Multi-dimensional edge analysis

Analyzes tracked data across multiple dimensions to identify patterns and
generate actionable recommendations for model improvement.

Enhancement Dimensions:
1. Symbol-specific patterns
2. Crowd wisdom (order book depth)
3. Temporal patterns (time of day, day of week)
4. Volatility regimes
5. Price level effects
6. Edge magnitude calibration
7. Momentum strength correlation
8. Liquidity vs edge relationships
9. Market efficiency scoring
10. Win rate prediction
"""

import csv
import logging
from pathlib import Path
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class CalibrationAnalyzer:
    """
    Advanced multi-dimensional calibration analysis

    Identifies where bot is systematically wrong and provides
    data-driven recommendations for improvement.
    """

    def __init__(self, tracker):
        """
        Args:
            tracker: NegativeEdgeTracker instance
        """
        self.tracker = tracker
        self.data = None
        self._load_data()

    def _load_data(self):
        """Load all tracked data into memory for analysis"""
        self.data = []

        try:
            if not self.tracker.csv_path.exists():
                logger.warning("No tracking data found")
                return

            with open(self.tracker.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                self.data = list(reader)

            logger.info(f"Loaded {len(self.data)} tracked trades for analysis")

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.data = []

    def get_summary_stats(self):
        """Get overall summary statistics"""
        total = len(self.data)
        checked = sum(1 for row in self.data if row['outcome_checked'] == 'True')
        won = sum(1 for row in self.data if row['would_have_won'] == 'True')

        negative_edges = [row for row in self.data if float(row['best_edge_pct']) < 0]
        small_positive = [row for row in self.data if 0 <= float(row['best_edge_pct']) < 10]

        total_pnl = sum(float(row.get('theoretical_pnl', 0)) for row in self.data if row['outcome_checked'] == 'True')

        return {
            'total_tracked': total,
            'outcomes_checked': checked,
            'would_have_won': won,
            'win_rate': (won / checked * 100) if checked > 0 else 0,
            'negative_edges_count': len(negative_edges),
            'small_positive_edges_count': len(small_positive),
            'theoretical_missed_profit': total_pnl,
            'avg_missed_per_trade': (total_pnl / checked) if checked > 0 else 0
        }

    def analyze_by_symbol(self):
        """
        Analyze performance by symbol (BTC/ETH/SOL)

        Returns dict with recommendations per symbol
        """
        by_symbol = defaultdict(lambda: {'total': 0, 'checked': 0, 'won': 0, 'edges': [], 'pnl': 0})

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            symbol = row['symbol']
            by_symbol[symbol]['total'] += 1
            by_symbol[symbol]['checked'] += 1
            by_symbol[symbol]['edges'].append(float(row['best_edge_pct']))

            if row['would_have_won'] == 'True':
                by_symbol[symbol]['won'] += 1

            by_symbol[symbol]['pnl'] += float(row.get('theoretical_pnl', 0))

        results = {}
        for symbol, stats in by_symbol.items():
            win_rate = (stats['won'] / stats['checked'] * 100) if stats['checked'] > 0 else 0
            avg_edge = sum(stats['edges']) / len(stats['edges']) if stats['edges'] else 0

            # Recommendation logic
            if win_rate > 55 and avg_edge < 0:
                recommendation = f"Lower {symbol} threshold to capture negative edges (currently winning {win_rate:.1f}%)"
                suggested_threshold = 7 if win_rate > 60 else 8
            elif win_rate > 50 and 0 <= avg_edge < 10:
                recommendation = f"Lower {symbol} threshold slightly (small edges winning {win_rate:.1f}%)"
                suggested_threshold = 8
            else:
                recommendation = f"Keep current threshold (win rate {win_rate:.1f}% on skipped trades)"
                suggested_threshold = 10

            results[symbol] = {
                'total_checked': stats['checked'],
                'won': stats['won'],
                'win_rate': win_rate,
                'avg_edge': avg_edge,
                'total_pnl': stats['pnl'],
                'recommendation': recommendation,
                'suggested_threshold': suggested_threshold
            }

        return results

    def analyze_by_crowd_wisdom(self):
        """
        Analyze by order book depth (crowd wisdom)

        Determines when to trust market pricing vs bot model
        """
        depth_buckets = {
            'high_depth': {'threshold': 500, 'total': 0, 'market_right': 0, 'bot_right': 0},
            'med_depth': {'threshold': 100, 'total': 0, 'market_right': 0, 'bot_right': 0},
            'low_depth': {'threshold': 0, 'total': 0, 'market_right': 0, 'bot_right': 0}
        }

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            depth = float(row.get('order_book_depth_total', 0))
            actual_outcome = row['actual_outcome']
            best_side = row['best_edge_side']

            # Which bucket?
            if depth >= 500:
                bucket = 'high_depth'
            elif depth >= 100:
                bucket = 'med_depth'
            else:
                bucket = 'low_depth'

            depth_buckets[bucket]['total'] += 1

            # Did market price suggest correct side?
            # Market is "right" if the MORE expensive side won
            yes_price = float(row['yes_market_price'])
            no_price = float(row['no_market_price'])
            market_predicted = 'yes' if yes_price > no_price else 'no'

            if market_predicted == actual_outcome:
                depth_buckets[bucket]['market_right'] += 1

            # Did bot's best edge predict correct side?
            if best_side == actual_outcome:
                depth_buckets[bucket]['bot_right'] += 1

        # Calculate confidence weights
        recommendations = {}
        for bucket, stats in depth_buckets.items():
            if stats['total'] == 0:
                continue

            market_rate = (stats['market_right'] / stats['total'] * 100)
            bot_rate = (stats['bot_right'] / stats['total'] * 100)

            # Recommendation
            if market_rate > bot_rate + 10:
                weight = 0.7  # Trust market 70%
                rec = f"Trust market MORE in {bucket} scenarios (market: {market_rate:.1f}%, bot: {bot_rate:.1f}%)"
            elif bot_rate > market_rate + 10:
                weight = 0.3  # Trust market 30%
                rec = f"Trust model MORE in {bucket} scenarios (bot: {bot_rate:.1f}%, market: {market_rate:.1f}%)"
            else:
                weight = 0.5  # Equal weight
                rec = f"Equal weighting appropriate (market: {market_rate:.1f}%, bot: {bot_rate:.1f}%)"

            recommendations[bucket] = {
                'total': stats['total'],
                'market_win_rate': market_rate,
                'bot_win_rate': bot_rate,
                'recommended_market_weight': weight,
                'recommendation': rec
            }

        return recommendations

    def analyze_temporal_patterns(self):
        """
        Analyze by time of day and day of week

        Identifies if bot performs better/worse at certain times
        """
        by_time = defaultdict(lambda: {'total': 0, 'won': 0})
        by_day = defaultdict(lambda: {'total': 0, 'won': 0})

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            time_bucket = row.get('time_bucket', 'unknown')
            day_of_week = row.get('day_of_week', 'unknown')

            by_time[time_bucket]['total'] += 1
            by_day[day_of_week]['total'] += 1

            if row['would_have_won'] == 'True':
                by_time[time_bucket]['won'] += 1
                by_day[day_of_week]['won'] += 1

        # Calculate win rates
        time_results = {}
        for bucket, stats in by_time.items():
            if stats['total'] > 0:
                win_rate = (stats['won'] / stats['total'] * 100)
                time_results[bucket] = {
                    'total': stats['total'],
                    'win_rate': win_rate,
                    'recommendation': 'More aggressive' if win_rate > 55 else 'Keep conservative'
                }

        day_results = {}
        for day, stats in by_day.items():
            if stats['total'] > 0:
                win_rate = (stats['won'] / stats['total'] * 100)
                day_results[day] = {
                    'total': stats['total'],
                    'win_rate': win_rate,
                    'recommendation': 'More aggressive' if win_rate > 55 else 'Keep conservative'
                }

        return {'by_time_of_day': time_results, 'by_day_of_week': day_results}

    def analyze_by_volatility_regime(self):
        """
        Analyze by volatility regime (quiet/normal/explosive)

        Determines if bot is too conservative/aggressive in different vol environments
        """
        by_regime = defaultdict(lambda: {'total': 0, 'won': 0, 'edges': []})

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            regime = row.get('vol_regime', 'normal')
            by_regime[regime]['total'] += 1
            by_regime[regime]['edges'].append(float(row['best_edge_pct']))

            if row['would_have_won'] == 'True':
                by_regime[regime]['won'] += 1

        results = {}
        for regime, stats in by_regime.items():
            if stats['total'] == 0:
                continue

            win_rate = (stats['won'] / stats['total'] * 100)
            avg_edge = sum(stats['edges']) / len(stats['edges'])

            if win_rate > 55:
                rec = f"Bot too conservative in {regime} vol (winning {win_rate:.1f}% of skipped trades)"
            else:
                rec = f"Bot appropriately selective in {regime} vol (win rate {win_rate:.1f}%)"

            results[regime] = {
                'total': stats['total'],
                'win_rate': win_rate,
                'avg_edge': avg_edge,
                'recommendation': rec
            }

        return results

    def analyze_by_price_level(self):
        """
        Analyze by contract price level (cheap/mid/expensive)

        Determines if bot performs differently on cheap vs expensive contracts
        """
        by_price = defaultdict(lambda: {'total': 0, 'won': 0})

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            price_bucket = row.get('price_level_bucket', 'mid')
            by_price[price_bucket]['total'] += 1

            if row['would_have_won'] == 'True':
                by_price[price_bucket]['won'] += 1

        results = {}
        for bucket, stats in by_price.items():
            if stats['total'] > 0:
                win_rate = (stats['won'] / stats['total'] * 100)
                results[bucket] = {
                    'total': stats['total'],
                    'win_rate': win_rate,
                    'recommendation': 'More aggressive' if win_rate > 55 else 'Appropriately selective'
                }

        return results

    def analyze_edge_calibration(self):
        """
        Analyze actual win rate by edge magnitude

        Tests if reported edges are accurate (e.g., 15% edge should win 65% of time)
        """
        edge_buckets = {
            'very_negative': {'range': (-100, -20), 'total': 0, 'won': 0},
            'negative': {'range': (-20, -5), 'total': 0, 'won': 0},
            'near_zero': {'range': (-5, 5), 'total': 0, 'won': 0},
            'small_positive': {'range': (5, 10), 'total': 0, 'won': 0},
            'medium_positive': {'range': (10, 15), 'total': 0, 'won': 0},
            'large_positive': {'range': (15, 100), 'total': 0, 'won': 0}
        }

        for row in self.data:
            if row['outcome_checked'] != 'True':
                continue

            edge = float(row['best_edge_pct'])

            # Find bucket
            for bucket_name, bucket_data in edge_buckets.items():
                low, high = bucket_data['range']
                if low <= edge < high:
                    bucket_data['total'] += 1
                    if row['would_have_won'] == 'True':
                        bucket_data['won'] += 1
                    break

        results = {}
        for bucket, stats in edge_buckets.items():
            if stats['total'] > 0:
                win_rate = (stats['won'] / stats['total'] * 100)
                results[bucket] = {
                    'range': stats['range'],
                    'total': stats['total'],
                    'win_rate': win_rate,
                    'calibrated': 45 <= win_rate <= 65 if 'negative' in bucket else True
                }

        return results

    def get_comprehensive_recommendations(self):
        """
        Generate comprehensive, prioritized recommendations based on all analyses

        Returns ranked list of actionable changes
        """
        recommendations = []

        # 1. Symbol-specific thresholds
        symbol_analysis = self.analyze_by_symbol()
        for symbol, data in symbol_analysis.items():
            if data['suggested_threshold'] < 10:
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'Symbol Threshold',
                    'action': f"Lower {symbol} min_edge_percent to {data['suggested_threshold']}%",
                    'reason': data['recommendation'],
                    'expected_impact': f"+${data['total_pnl']:.0f} captured, {data['total_checked']} more trades",
                    'config_change': {
                        'file': 'config_15m.yaml',
                        'section': 'strategy.symbol_overrides',
                        'key': symbol,
                        'value': data['suggested_threshold']
                    }
                })

        # 2. Crowd wisdom weighting
        crowd_analysis = self.analyze_by_crowd_wisdom()
        for bucket, data in crowd_analysis.items():
            if data['recommended_market_weight'] != 0.5:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'Crowd Wisdom',
                    'action': f"Adjust market confidence weight for {bucket}",
                    'reason': data['recommendation'],
                    'expected_impact': f"Better probability estimates in {data['total']} cases",
                    'config_change': {
                        'file': 'config_15m.yaml',
                        'section': 'calibration.crowd_confidence',
                        'key': f'{bucket}_market_weight',
                        'value': data['recommended_market_weight']
                    }
                })

        # 3. Temporal adjustments
        temporal_analysis = self.analyze_temporal_patterns()
        for time_bucket, data in temporal_analysis['by_time_of_day'].items():
            if data['win_rate'] > 60 and data['total'] > 10:
                recommendations.append({
                    'priority': 'LOW',
                    'category': 'Temporal Pattern',
                    'action': f"Be more aggressive during {time_bucket}",
                    'reason': f"Win rate {data['win_rate']:.1f}% on skipped trades",
                    'expected_impact': f"{data['total']} opportunities",
                    'config_change': None  # Would need time-based threshold logic
                })

        # 4. Volatility regime adjustments
        vol_analysis = self.analyze_by_volatility_regime()
        for regime, data in vol_analysis.items():
            if data['win_rate'] > 55 and data['total'] > 10:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'Volatility Regime',
                    'action': f"Lower threshold in {regime} volatility",
                    'reason': data['recommendation'],
                    'expected_impact': f"{data['total']} opportunities, {data['win_rate']:.1f}% win rate",
                    'config_change': None  # Would need regime-based logic
                })

        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        recommendations.sort(key=lambda x: priority_order[x['priority']])

        return recommendations

    def generate_report(self):
        """Generate comprehensive text report"""
        summary = self.get_summary_stats()
        symbol_analysis = self.analyze_by_symbol()
        crowd_analysis = self.analyze_by_crowd_wisdom()
        temporal = self.analyze_temporal_patterns()
        vol_analysis = self.analyze_by_volatility_regime()
        price_analysis = self.analyze_by_price_level()
        edge_calib = self.analyze_edge_calibration()
        recommendations = self.get_comprehensive_recommendations()

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COMPREHENSIVE CALIBRATION ANALYSIS REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Total tracked: {summary['total_tracked']}")
        report_lines.append(f"Outcomes checked: {summary['outcomes_checked']}")
        report_lines.append(f"Would have won: {summary['would_have_won']} ({summary['win_rate']:.1f}%)")
        report_lines.append(f"Theoretical missed profit: ${summary['theoretical_missed_profit']:.2f}")
        report_lines.append("")

        # Symbol analysis
        report_lines.append("-" * 80)
        report_lines.append("ANALYSIS BY SYMBOL")
        report_lines.append("-" * 80)
        for symbol, data in symbol_analysis.items():
            report_lines.append(f"\n{symbol}:")
            report_lines.append(f"  Win rate on skipped: {data['win_rate']:.1f}%")
            report_lines.append(f"  Avg edge: {data['avg_edge']:.1f}%")
            report_lines.append(f"  Missed profit: ${data['total_pnl']:.2f}")
            report_lines.append(f"  → {data['recommendation']}")

        # Crowd wisdom
        report_lines.append("\n" + "-" * 80)
        report_lines.append("CROWD WISDOM ANALYSIS")
        report_lines.append("-" * 80)
        for bucket, data in crowd_analysis.items():
            report_lines.append(f"\n{bucket}:")
            report_lines.append(f"  Market win rate: {data['market_win_rate']:.1f}%")
            report_lines.append(f"  Bot win rate: {data['bot_win_rate']:.1f}%")
            report_lines.append(f"  → {data['recommendation']}")

        # Recommendations
        report_lines.append("\n" + "=" * 80)
        report_lines.append("TOP RECOMMENDATIONS")
        report_lines.append("=" * 80)
        for i, rec in enumerate(recommendations[:5], 1):
            report_lines.append(f"\n{i}. [{rec['priority']}] {rec['action']}")
            report_lines.append(f"   Reason: {rec['reason']}")
            report_lines.append(f"   Impact: {rec['expected_impact']}")

        report_lines.append("\n" + "=" * 80)

        return "\n".join(report_lines)
