#!/usr/bin/env python3
"""Check outcomes for all contrarian bet markets that haven't been verified yet"""

import csv
from collections import defaultdict
from kalshi_client import KalshiClient
from config_loader import load_config_with_env
import time

def main():
    # Load contrarian bet data
    contrarian_markets = defaultdict(lambda: {
        'scans': 0,
        'outcome_checked': False,
        'won': None,
        'side': None,
        'momentum_direction': None,
        'sample_data': None
    })

    with open('/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['skip_reason'] == 'Contrarian Bet':
                ticker = row['ticker']
                contrarian_markets[ticker]['scans'] += 1

                # Store sample data from first scan
                if contrarian_markets[ticker]['sample_data'] is None:
                    contrarian_markets[ticker]['sample_data'] = row
                    contrarian_markets[ticker]['side'] = row.get('best_edge_side', '')
                    contrarian_markets[ticker]['momentum_direction'] = row.get('momentum_direction', '')

                if row['outcome_checked'] == 'True':
                    contrarian_markets[ticker]['outcome_checked'] = True
                    contrarian_markets[ticker]['won'] = (row['would_have_won'] == 'True')

    # Filter to unchecked markets
    unchecked = [(ticker, data) for ticker, data in contrarian_markets.items()
                 if not data['outcome_checked']]

    print(f"📊 CHECKING {len(unchecked)} UNCHECKED CONTRARIAN BET MARKETS")
    print(f"=" * 70)

    # Initialize Kalshi client
    config = load_config_with_env()
    client = KalshiClient(config)

    results = {
        'total_checked': 0,
        'wins': 0,
        'losses': 0,
        'errors': 0,
        'not_settled': 0
    }

    for i, (ticker, data) in enumerate(unchecked, 1):
        try:
            # Rate limit
            if i > 1:
                time.sleep(0.5)

            market = client.get_market(ticker)
            status = market.get('status', 'unknown')
            result = market.get('result', 'unknown')

            if status != 'finalized' or result == 'unknown':
                results['not_settled'] += 1
                continue

            # Determine if contrarian bet would have won
            side = data['side']
            momentum = data['momentum_direction']

            # Contrarian bet: betting against momentum
            # If momentum was DOWN and side was YES (betting UP), check if market went UP (yes won)
            # If momentum was UP and side was NO (betting DOWN), check if market went DOWN (no won)

            would_have_won = (result == side)

            results['total_checked'] += 1
            if would_have_won:
                results['wins'] += 1
                outcome_str = "✅ WON"
            else:
                results['losses'] += 1
                outcome_str = "❌ LOST"

            print(f"{i:3d}. {ticker}")
            print(f"     Momentum: {momentum.upper()}, Bet: {side.upper()}, "
                  f"Result: {result.upper()} → {outcome_str}")

        except Exception as e:
            results['errors'] += 1
            if 'not found' not in str(e).lower():
                print(f"{i:3d}. {ticker} - Error: {e}")

    # Print summary
    print(f"\n" + "=" * 70)
    print(f"📈 RESULTS SUMMARY")
    print(f"=" * 70)
    print(f"Markets Checked: {results['total_checked']}")
    print(f"✅ Would Have Won: {results['wins']}")
    print(f"❌ Would Have Lost: {results['losses']}")
    print(f"⏳ Not Yet Settled: {results['not_settled']}")
    print(f"⚠️  Errors/Not Found: {results['errors']}")

    if results['total_checked'] > 0:
        win_rate = (results['wins'] / results['total_checked']) * 100
        print(f"\n🎯 Win Rate: {win_rate:.1f}% ({results['wins']}/{results['total_checked']})")

        # Combined with previous data
        prev_checked = 18
        prev_wins = 0
        total_unique = prev_checked + results['total_checked']
        total_wins = prev_wins + results['wins']

        print(f"\n" + "=" * 70)
        print(f"🔍 COMBINED EVIDENCE (ALL UNIQUE MARKETS)")
        print(f"=" * 70)
        print(f"Previously Checked: {prev_wins}/{prev_checked} wins")
        print(f"Newly Checked: {results['wins']}/{results['total_checked']} wins")
        print(f"TOTAL: {total_wins}/{total_unique} = {(total_wins/total_unique)*100:.1f}% win rate")

if __name__ == "__main__":
    main()
