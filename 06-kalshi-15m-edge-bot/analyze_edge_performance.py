#!/usr/bin/env python3
"""
Edge Performance Analyzer
Analyzes skipped trades, win rates, and configuration effectiveness
"""

import pandas as pd
from datetime import datetime, timedelta
import sys

def analyze_skipped_trades(hours=24):
    """Analyze skipped trades over the last N hours"""

    # Read data
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filter by time
    cutoff = datetime.now(df['timestamp'].iloc[0].tzinfo) - timedelta(hours=hours)
    recent = df[df['timestamp'] > cutoff]

    print(f"\n{'='*80}")
    print(f"EDGE PERFORMANCE ANALYSIS - Last {hours} Hours")
    print(f"{'='*80}\n")

    # Overall stats
    print(f"📊 OVERALL STATISTICS")
    print(f"   Total skipped trades: {len(recent)}")

    if len(recent) == 0:
        print("\n   ⚠️  NO TRADES SKIPPED - Check if bot is running or filters are too loose\n")
        return

    # Skip reasons
    print(f"\n   Skip Reasons:")
    for reason, count in recent['skip_reason'].value_counts().items():
        pct = count / len(recent) * 100
        print(f"      {reason}: {count} ({pct:.1f}%)")

    # Outcome analysis
    checked = recent[recent['outcome_checked'] == True]
    if len(checked) > 0:
        wins = len(checked[checked['would_have_won'] == True])
        losses = len(checked) - wins
        win_rate = wins / len(checked) * 100
        total_pnl = checked['theoretical_pnl'].sum()
        avg_pnl = total_pnl / len(checked)

        print(f"\n💰 OUTCOME ANALYSIS (Checked outcomes only)")
        print(f"   Checked: {len(checked)} trades")
        print(f"   Would have won: {wins} ({win_rate:.1f}%)")
        print(f"   Would have lost: {losses} ({(100-win_rate):.1f}%)")
        print(f"   Theoretical PnL: ${total_pnl:.2f}")
        print(f"   Avg PnL per trade: ${avg_pnl:.2f}")

        # Win rate by skip reason
        print(f"\n📈 WIN RATE BY SKIP REASON")
        for reason in recent['skip_reason'].unique():
            subset = checked[checked['skip_reason'] == reason]
            if len(subset) > 0:
                reason_wins = len(subset[subset['would_have_won'] == True])
                reason_wr = reason_wins / len(subset) * 100
                reason_pnl = subset['theoretical_pnl'].sum()
                avg_edge = recent[recent['skip_reason'] == reason]['best_edge_pct'].mean()

                status = "✅" if reason_wr < 45 else "⚠️" if reason_wr < 55 else "❌"
                print(f"   {status} {reason}:")
                print(f"      Win rate: {reason_wr:.1f}% | PnL: ${reason_pnl:.2f} | Avg edge: {avg_edge:.2f}%")

        # Edge size analysis
        print(f"\n🎯 WIN RATE BY EDGE SIZE")
        checked_copy = checked.copy()
        checked_copy['edge_bucket'] = pd.cut(
            checked_copy['best_edge_pct'],
            bins=[-1000, -5, 0, 5, 10, 15, 20, 1000],
            labels=['< -5%', '-5 to 0%', '0-5%', '5-10%', '10-15%', '15-20%', '> 20%']
        )

        for bucket in checked_copy['edge_bucket'].cat.categories:
            subset = checked_copy[checked_copy['edge_bucket'] == bucket]
            if len(subset) > 0:
                bucket_wins = len(subset[subset['would_have_won'] == True])
                bucket_wr = bucket_wins / len(subset) * 100
                bucket_pnl = subset['theoretical_pnl'].sum()
                print(f"   {bucket}: {bucket_wins}/{len(subset)} ({bucket_wr:.1f}%) | PnL: ${bucket_pnl:.2f}")

        # Probability analysis
        print(f"\n🎲 PROBABILITY DISTRIBUTION")
        print(f"   Best edge side probability:")
        best_probs = recent[['yes_expected_prob', 'no_expected_prob']].max(axis=1)
        print(f"      Mean: {best_probs.mean():.2%}")
        print(f"      Median: {best_probs.median():.2%}")
        print(f"      Min: {best_probs.min():.2%}")
        print(f"      Max: {best_probs.max():.2%}")

    print(f"\n{'='*80}\n")

def analyze_all_time():
    """Analyze all-time performance"""
    df = pd.read_csv('data/negative_edges/skipped_trades.csv')

    print(f"\n{'='*80}")
    print(f"ALL-TIME PERFORMANCE ANALYSIS")
    print(f"{'='*80}\n")

    print(f"📊 Total skipped trades: {len(df)}")
    print(f"\n   Skip Reasons:")
    for reason, count in df['skip_reason'].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {reason}: {count} ({pct:.1f}%)")

    # Analyze each skip reason
    print(f"\n🔍 FILTER EFFECTIVENESS ANALYSIS\n")
    for reason in df['skip_reason'].unique():
        subset = df[df['skip_reason'] == reason]
        checked = subset[subset['outcome_checked'] == True]

        if len(checked) > 0:
            wins = len(checked[checked['would_have_won'] == True])
            win_rate = wins / len(checked) * 100
            total_pnl = checked['theoretical_pnl'].sum()
            avg_edge = subset['best_edge_pct'].mean()

            # Determine if filter is working well
            if win_rate < 45:
                status = "✅ PROTECTING"
                color = ""
            elif win_rate < 55:
                status = "⚠️  NEUTRAL"
                color = ""
            else:
                status = "❌ MISSING EDGES"
                color = ""

            print(f"{status} | {reason}")
            print(f"   Total: {len(subset)} | Checked: {len(checked)}")
            print(f"   Win rate: {win_rate:.1f}%")
            print(f"   Total PnL: ${total_pnl:.2f}")
            print(f"   Avg edge: {avg_edge:.2f}%")
            print()

    print(f"{'='*80}\n")

def check_recent_logs():
    """Check recent log entries for current filter activity"""
    import subprocess

    print(f"\n{'='*80}")
    print(f"RECENT BOT ACTIVITY (Last 50 log entries)")
    print(f"{'='*80}\n")

    try:
        result = subprocess.run(
            ["tail", "-50", "logs/edge_bot.log"],
            capture_output=True,
            text=True
        )

        # Extract skip reasons
        skip_lines = [line for line in result.stdout.split('\n') if 'skip:' in line.lower()]

        if skip_lines:
            print("Recent skip reasons:")
            # Count skip types
            skip_counts = {}
            for line in skip_lines[-20:]:  # Last 20 skips
                if 'Low Momentum' in line:
                    skip_counts['Low Momentum'] = skip_counts.get('Low Momentum', 0) + 1
                elif 'Low Edge' in line:
                    skip_counts['Low Edge'] = skip_counts.get('Low Edge', 0) + 1
                elif 'Low Win Prob' in line or 'Low Prob' in line:
                    skip_counts['Low Win Prob'] = skip_counts.get('Low Win Prob', 0) + 1
                elif 'Low Signal' in line:
                    skip_counts['Low Signal'] = skip_counts.get('Low Signal', 0) + 1
                elif 'Low Trend Strength' in line:
                    skip_counts['Low Trend Strength'] = skip_counts.get('Low Trend Strength', 0) + 1

            for reason, count in sorted(skip_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   {reason}: {count} times")

            print(f"\n   Most recent skips:")
            for line in skip_lines[-5:]:
                # Extract just the skip reason part
                if 'skip:' in line:
                    parts = line.split('skip:')
                    if len(parts) > 1:
                        print(f"      {parts[1].strip()[:80]}")
        else:
            print("   No recent skip messages found")

        # Check for edge found
        edge_lines = [line for line in result.stdout.split('\n') if 'EDGE FOUND' in line]
        if edge_lines:
            print(f"\n   ✅ Recent edges found: {len(edge_lines)}")
        else:
            print(f"\n   ⚠️  No edges found in recent activity")

    except Exception as e:
        print(f"   Error reading logs: {e}")

    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    hours = 24
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except:
            print(f"Usage: {sys.argv[0]} [hours]")
            sys.exit(1)

    check_recent_logs()
    analyze_skipped_trades(hours=hours)
    analyze_all_time()

    print("\n💡 RECOMMENDATIONS:")
    print("   1. Check config_15m.yaml settings (especially min_momentum_pct)")
    print("   2. If no edges found, filters may be too strict")
    print("   3. If too many edges, filters may be too loose")
    print("   4. Target: 2-5 edge detections per hour with >50% win rate")
    print()
