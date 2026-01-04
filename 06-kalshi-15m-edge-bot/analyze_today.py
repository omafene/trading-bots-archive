#!/usr/bin/env python3
"""
Today's Trading Analysis
Detailed breakdown of Feb 2, 2026 trading activity
"""

import re
from datetime import datetime
from collections import defaultdict


def parse_todays_data(log_file: str = "logs/edge_bot.log"):
    """Parse all Feb 2 trading data"""
    signals = []
    executions = []
    balance_updates = []

    with open(log_file, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Only process Feb 2 lines
        if not line.startswith('2026-02-02'):
            i += 1
            continue

        timestamp = line[:19]  # 2026-02-02 HH:MM:SS

        # Parse signals
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

            # Extract symbol
            if 'BTC' in ticker:
                symbol = 'BTC'
            elif 'ETH' in ticker:
                symbol = 'ETH'
            elif 'SOL' in ticker:
                symbol = 'SOL'
            else:
                symbol = 'UNKNOWN'

            # Get signal strength from next lines
            signal_strength = None
            for j in range(i+1, min(i+5, len(lines))):
                strength_match = re.search(r'Signal Strength: ([\d.]+)/100', lines[j])
                if strength_match:
                    signal_strength = float(strength_match.group(1))
                    break

            signals.append({
                'timestamp': timestamp,
                'ticker': ticker,
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'edge_percent': edge,
                'expected_roi': expected_roi,
                'signal_strength': signal_strength
            })

        # Parse executions
        exec_match = re.search(
            r'🚀 Executing (MARKET|LIMIT) (?:order )?for (\S+) \((\w+)\)',
            line
        )
        if exec_match:
            order_type = exec_match.group(1)
            ticker = exec_match.group(2)
            side = exec_match.group(3).upper()

            executions.append({
                'timestamp': timestamp,
                'ticker': ticker,
                'side': side,
                'order_type': order_type
            })

        # Parse balance updates
        balance_match = re.search(r'Cash: \$([\d.]+)', line)
        if balance_match:
            balance = float(balance_match.group(1))
            balance_updates.append({
                'timestamp': timestamp,
                'balance': balance
            })

        # Parse failures
        if '❌ Execution failed' in line:
            fail_match = re.search(r'❌ Execution failed for (\S+)', line)
            if fail_match:
                ticker = fail_match.group(1)
                # Mark the execution as failed
                if executions and executions[-1]['ticker'] == ticker:
                    executions[-1]['failed'] = True

        i += 1

    return signals, executions, balance_updates


def analyze_today():
    """Main analysis"""
    print("="*80)
    print("📅 FEBRUARY 2, 2026 - TRADING DAY ANALYSIS")
    print("="*80)

    signals, executions, balance_updates = parse_todays_data()

    # Overall stats
    print(f"\n📊 Overview:")
    print(f"   Signals Detected: {len(signals)}")
    print(f"   Trade Attempts: {len(executions)}")

    failed_execs = sum(1 for e in executions if e.get('failed', False))
    successful_execs = len(executions) - failed_execs
    print(f"   Successful Executions: {successful_execs}")
    print(f"   Failed Executions: {failed_execs}")

    if balance_updates:
        start_balance = balance_updates[0]['balance']
        end_balance = balance_updates[-1]['balance']
        pnl = end_balance - start_balance
        pnl_pct = (pnl / start_balance) * 100 if start_balance > 0 else 0

        print(f"\n💰 Balance Tracking:")
        print(f"   Start: ${start_balance:.2f}")
        print(f"   End: ${end_balance:.2f}")
        print(f"   Change: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

    # Hourly breakdown
    print(f"\n⏰ Activity Timeline:")
    hourly = defaultdict(lambda: {'signals': 0, 'executions': 0})

    for s in signals:
        hour = s['timestamp'][11:13]
        hourly[hour]['signals'] += 1

    for e in executions:
        hour = e['timestamp'][11:13]
        hourly[hour]['executions'] += 1

    print(f"\n{'Hour':<8} {'Signals':<12} {'Executions'}")
    print("-" * 40)
    for hour in sorted(hourly.keys()):
        print(f"{hour}:00{'':<4} {hourly[hour]['signals']:<12} {hourly[hour]['executions']}")

    # Signal details
    print(f"\n📈 Signal Characteristics:")

    if signals:
        avg_edge = sum(s['edge_percent'] for s in signals) / len(signals)
        avg_strength = sum(s['signal_strength'] for s in signals if s['signal_strength']) / \
                      sum(1 for s in signals if s['signal_strength'])
        avg_entry = sum(s['entry_price'] for s in signals) / len(signals)

        print(f"   Average Edge: {avg_edge:.1f}%")
        print(f"   Average Strength: {avg_strength:.1f}")
        print(f"   Average Entry Price: ${avg_entry:.2f}")

        # By symbol
        by_symbol = defaultdict(int)
        for s in signals:
            by_symbol[s['symbol']] += 1

        print(f"\n   By Symbol:")
        for symbol, count in sorted(by_symbol.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(signals) * 100
            print(f"      {symbol}: {count} ({pct:.0f}%)")

        # By side
        yes_count = sum(1 for s in signals if s['side'] == 'YES')
        no_count = sum(1 for s in signals if s['side'] == 'NO')
        print(f"\n   By Side:")
        print(f"      YES: {yes_count} ({yes_count/len(signals)*100:.0f}%)")
        print(f"      NO: {no_count} ({no_count/len(signals)*100:.0f}%)")

    # Detailed signal list
    print(f"\n📋 All Signals Today:")
    print(f"\n{'Time':<10} {'Symbol':<6} {'Side':<4} {'Entry':<8} {'Edge':<8} {'Strength':<10} {'Ticker'}")
    print("-" * 80)

    for s in signals:
        time_str = s['timestamp'][11:19]
        entry_str = f"{s['entry_price']:.0%}"
        edge_str = f"{s['edge_percent']:.1f}%"
        strength_str = f"{s['signal_strength']:.0f}" if s['signal_strength'] else 'N/A'
        ticker_short = s['ticker'][:25]

        print(f"{time_str:<10} {s['symbol']:<6} {s['side']:<4} {entry_str:<8} "
              f"{edge_str:<8} {strength_str:<10} {ticker_short}")

    # Execution details
    if executions:
        print(f"\n🚀 Execution Details:")
        print(f"\n{'Time':<10} {'Type':<8} {'Ticker':<30} {'Side':<4} {'Status'}")
        print("-" * 80)

        for e in executions:
            time_str = e['timestamp'][11:19]
            ticker_short = e['ticker'][:30]
            status = '❌ FAILED' if e.get('failed', False) else '✅ OK'

            print(f"{time_str:<10} {e['order_type']:<8} {ticker_short:<30} "
                  f"{e['side']:<4} {status}")

    # Best signals of the day
    if signals:
        print(f"\n🏆 Top 5 Signals (by Edge):")
        top_signals = sorted(signals, key=lambda x: x['edge_percent'], reverse=True)[:5]

        for i, s in enumerate(top_signals, 1):
            executed = any(e['ticker'] == s['ticker'] and e['side'] == s['side']
                          for e in executions)
            exec_mark = '✅' if executed else '❌'

            print(f"\n{i}. {exec_mark} {s['ticker']}")
            print(f"   {s['symbol']} {s['side']} @ {s['entry_price']:.0%} | "
                  f"Edge: {s['edge_percent']:.1f}% | Strength: {s['signal_strength']:.0f} | "
                  f"ROI: {s['expected_roi']:.0f}%")
            print(f"   Time: {s['timestamp'][11:19]}")


if __name__ == '__main__':
    analyze_today()
