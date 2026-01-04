#!/usr/bin/env python3
"""
Calibration Analysis CLI Tool

Usage:
    python3 analyze_calibration.py --report        # Full report
    python3 analyze_calibration.py --by-symbol     # Symbol analysis only
    python3 analyze_calibration.py --by-crowd      # Crowd wisdom analysis
    python3 analyze_calibration.py --recommend     # Top recommendations
    python3 analyze_calibration.py --check-outcomes # Check pending outcomes
"""

import argparse
import sys
from negative_edge_tracker import NegativeEdgeTracker
from calibration_analyzer import CalibrationAnalyzer
from outcome_checker import OutcomeChecker
from config_loader import load_config_with_env
from kalshi_client import KalshiClient

def main():
    parser = argparse.ArgumentParser(description='Analyze calibration data and generate recommendations')
    parser.add_argument('--report', action='store_true', help='Generate full calibration report')
    parser.add_argument('--by-symbol', action='store_true', help='Analyze by symbol only')
    parser.add_argument('--by-crowd', action='store_true', help='Analyze crowd wisdom only')
    parser.add_argument('--recommend', action='store_true', help='Show top recommendations')
    parser.add_argument('--check-outcomes', action='store_true', help='Check pending outcomes')
    parser.add_argument('--stats', action='store_true', help='Show summary stats')

    args = parser.parse_args()

    # Initialize
    tracker = NegativeEdgeTracker()
    analyzer = CalibrationAnalyzer(tracker)

    # If no args, show full report
    if not any(vars(args).values()):
        args.report = True

    # Check outcomes first if requested
    if args.check_outcomes:
        print("Checking pending outcomes...")
        config = load_config_with_env()
        client = KalshiClient(config)
        outcome_checker = OutcomeChecker(client, tracker)
        checked = outcome_checker.check_pending_outcomes(max_checks=50)
        print(f"✅ Checked {checked} outcomes")
        print()

        # Reload data after checking outcomes
        analyzer = CalibrationAnalyzer(tracker)

    # Summary stats
    if args.stats:
        stats = analyzer.get_summary_stats()
        print("=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total tracked: {stats['total_tracked']}")
        print(f"Outcomes checked: {stats['outcomes_checked']}")
        print(f"Would have won: {stats['would_have_won']} ({stats['win_rate']:.1f}%)")
        print(f"Theoretical missed profit: ${stats['theoretical_missed_profit']:.2f}")
        print(f"Avg per trade: ${stats['avg_missed_per_trade']:.2f}")
        print()

    # Symbol analysis
    if args.by_symbol:
        print("=" * 80)
        print("ANALYSIS BY SYMBOL")
        print("=" * 80)
        symbol_analysis = analyzer.analyze_by_symbol()
        for symbol, data in symbol_analysis.items():
            print(f"\n{symbol}:")
            print(f"  Checked: {data['total_checked']}")
            print(f"  Win rate: {data['win_rate']:.1f}%")
            print(f"  Avg edge: {data['avg_edge']:.1f}%")
            print(f"  Missed profit: ${data['total_pnl']:.2f}")
            print(f"  → {data['recommendation']}")
            print(f"  → Suggested threshold: {data['suggested_threshold']}%")
        print()

    # Crowd wisdom
    if args.by_crowd:
        print("=" * 80)
        print("CROWD WISDOM ANALYSIS")
        print("=" * 80)
        crowd_analysis = analyzer.analyze_by_crowd_wisdom()
        for bucket, data in crowd_analysis.items():
            print(f"\n{bucket.replace('_', ' ').title()}:")
            print(f"  Total: {data['total']}")
            print(f"  Market win rate: {data['market_win_rate']:.1f}%")
            print(f"  Bot win rate: {data['bot_win_rate']:.1f}%")
            print(f"  Recommended market weight: {data['recommended_market_weight']:.1f}")
            print(f"  → {data['recommendation']}")
        print()

    # Recommendations
    if args.recommend:
        print("=" * 80)
        print("TOP RECOMMENDATIONS")
        print("=" * 80)
        recommendations = analyzer.get_comprehensive_recommendations()
        for i, rec in enumerate(recommendations[:10], 1):
            print(f"\n{i}. [{rec['priority']}] {rec['category']}: {rec['action']}")
            print(f"   Reason: {rec['reason']}")
            print(f"   Expected impact: {rec['expected_impact']}")
            if rec['config_change']:
                change = rec['config_change']
                print(f"   Config: {change['file']} → {change['section']}.{change['key']} = {change['value']}")
        print()

    # Full report
    if args.report:
        report = analyzer.generate_report()
        print(report)

if __name__ == '__main__':
    main()
