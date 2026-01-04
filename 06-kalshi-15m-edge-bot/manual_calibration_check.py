#!/usr/bin/env python3
"""
Manual calibration check and outcome verification
1. Check outcomes via Kalshi API for recently closed markets
2. Force drift calibration check
"""

import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from outcome_checker import OutcomeChecker
from negative_edge_tracker import NegativeEdgeTracker
from momentum_analyzer import MomentumAnalyzer
from spot_price_feed import CFBenchmarksRTI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_recent_outcomes():
    """Check outcomes for recently closed markets"""
    print("\n" + "="*70)
    print("📊 CHECKING RECENT MARKET OUTCOMES VIA KALSHI API")
    print("="*70 + "\n")

    # Load config
    config = load_config_with_env("config_15m.yaml")
    client = KalshiClient(config)

    # Initialize tracker
    tracker = NegativeEdgeTracker(data_dir="data/negative_edges")

    # Initialize outcome checker
    outcome_checker = OutcomeChecker(client, tracker)

    # Check pending outcomes
    checked_count = outcome_checker.check_pending_outcomes(max_checks=100)

    print(f"\n✅ Checked {checked_count} market outcomes\n")

    # Load updated data and show results
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filter to past 6 hours with known outcomes
    import pytz
    utc = pytz.UTC
    six_hours_ago = datetime.now(utc) - timedelta(hours=6)
    recent = df[df['timestamp'] >= six_hours_ago].copy()

    checked = recent[recent['outcome_checked'] == True]

    if len(checked) > 0:
        print(f"📈 OUTCOMES FOR PAST 6 HOURS:")
        print(f"-" * 70)

        winners = checked[checked['would_have_won'] == True]
        losers = checked[checked['would_have_won'] == False]
        win_rate = (len(winners) / len(checked)) * 100

        print(f"Total checked:    {len(checked):4d}")
        print(f"Would have WON:   {len(winners):4d} ({win_rate:5.1f}%)")
        print(f"Would have LOST:  {len(losers):4d} ({100-win_rate:5.1f}%)")

        total_pnl = checked['theoretical_pnl'].sum()
        avg_pnl = checked['theoretical_pnl'].mean()

        print(f"\nTheoretical P&L:  ${total_pnl:+.2f}")
        print(f"Average per trade: ${avg_pnl:+.2f}")

        # Break down by skip reason
        print(f"\n\n🎯 WINNERS BY SKIP REASON:")
        print(f"-" * 70)

        skip_reasons = checked['skip_reason'].value_counts()
        for reason in skip_reasons.index[:5]:
            reason_checked = checked[checked['skip_reason'] == reason]
            reason_winners = reason_checked[reason_checked['would_have_won'] == True]
            reason_win_rate = (len(reason_winners) / len(reason_checked)) * 100
            reason_pnl = reason_checked['theoretical_pnl'].sum()

            print(f"\n{reason}:")
            print(f"  Checked: {len(reason_checked):3d} | Won: {len(reason_winners):3d} ({reason_win_rate:5.1f}%) | P&L: ${reason_pnl:+.2f}")

            if len(reason_winners) > 0:
                # Show top 3 examples
                top_examples = reason_winners.nlargest(3, 'theoretical_pnl')[
                    ['ticker', 'symbol', 'best_edge_side', 'best_edge_pct', 'theoretical_pnl']
                ]
                for _, row in top_examples.iterrows():
                    print(f"    ✓ {row['ticker']:30s} {row['symbol']:3s} {row['best_edge_side']:3s} edge={row['best_edge_pct']:+6.1f}% pnl=${row['theoretical_pnl']:+6.1f}")
    else:
        print("⚠️ No outcomes available yet for recent trades")

    print("\n" + "="*70 + "\n")
    return checked_count

def check_drift_calibration():
    """Force drift calibration check"""
    print("\n" + "="*70)
    print("⚙️  DRIFT CALIBRATION CHECK")
    print("="*70 + "\n")

    # Load config
    config = load_config_with_env("config_15m.yaml")
    spot_feed = CFBenchmarksRTI(config)
    momentum = MomentumAnalyzer(spot_feed, config)

    print(f"Calibration Mode: {momentum.recalibration_mode}")
    print(f"Drift Threshold: {momentum.drift_threshold_percent * 100:.1f}%")
    print(f"Min Samples: {momentum.min_samples_for_recalibration}")
    print(f"Lookback Days: {momentum.recalibration_lookback_days}")

    # Get last recalibration time
    hours_since_last = (datetime.now() - momentum.last_recalibration).total_seconds() / 3600
    print(f"\n⏰ Last Recalibration: {momentum.last_recalibration.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ({hours_since_last:.1f} hours ago)")

    # Check cooldown
    min_hours = momentum.min_recalibration_interval_hours
    if hours_since_last < min_hours:
        print(f"\n⏸️  IN COOLDOWN PERIOD")
        print(f"   Minimum interval: {min_hours} hours")
        print(f"   Time remaining: {min_hours - hours_since_last:.1f} hours")
        print("\n" + "="*70 + "\n")
        return

    # Calculate drift
    print(f"\n📊 Calculating drift from performance data...")
    drift_data = momentum._calculate_calibration_drift()

    if not drift_data:
        print(f"⚠️ Insufficient data for drift calculation")
        print(f"   Need at least {momentum.min_drift_samples} samples")
        print("\n" + "="*70 + "\n")
        return

    print(f"\n📈 DRIFT ANALYSIS:")
    print(f"-" * 70)

    for direction, drift_pct in drift_data.items():
        status = "🔴 NEEDS RECAL" if abs(drift_pct) >= momentum.drift_threshold_percent * 100 else "✅ OK"
        print(f"{direction.upper():5s}: {drift_pct:+6.1f}% drift  {status}")

    # Check if recalibration should trigger
    should_recal = any(
        abs(drift) >= momentum.drift_threshold_percent * 100
        for drift in drift_data.values()
    )

    if should_recal:
        print(f"\n🔄 TRIGGERING RECALIBRATION...")
        momentum._recalibrate_from_data()
        print(f"✅ Recalibration completed!")
        print(f"   New calibration curves loaded from recent performance data")
    else:
        print(f"\n✅ NO RECALIBRATION NEEDED")
        print(f"   Drift is within acceptable threshold ({momentum.drift_threshold_percent * 100:.1f}%)")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    try:
        # Task 1: Check outcomes via API
        checked_count = check_recent_outcomes()

        # Task 2: Drift calibration check
        check_drift_calibration()

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)
