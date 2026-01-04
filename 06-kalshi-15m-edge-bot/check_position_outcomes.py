"""
Check outcomes of expired positions to calculate actual P&L
"""

import pandas as pd
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
import time

def check_market_outcome(client, ticker):
    """Get final settlement price for a market"""
    try:
        market = client.get_market(ticker)
        if market and 'result' in market:
            return market['result']  # 'yes' or 'no'
        return None
    except:
        return None


def main():
    print("=" * 80)
    print("CHECKING POSITION OUTCOMES")
    print("=" * 80)
    print()

    # Load positions
    trades = pd.read_csv('data/trade_history.csv')
    open_positions = trades[trades['status'] == 'open']

    print(f"Checking {len(open_positions)} positions...")
    print()

    # Load config and client
    config = load_config_with_env('config_15m.yaml')
    client = KalshiClient(config)

    if not client.authenticate():
        print("❌ Authentication failed!")
        return

    # Check outcomes
    results = []
    wins = 0
    losses = 0
    pending = 0
    total_invested = 0
    total_payout = 0

    for idx, pos in open_positions.iterrows():
        ticker = pos['ticker']
        side = pos['side']
        contracts = pos['contracts']
        cost_per_contract = pos['avg_buy']
        total_cost = contracts * cost_per_contract

        total_invested += total_cost

        # Check outcome
        outcome = check_market_outcome(client, ticker)

        if outcome:
            won = (outcome == side)

            if won:
                wins += 1
                payout = contracts * 1.0  # Each contract pays $1
                pnl = payout - total_cost
                total_payout += payout
            else:
                losses += 1
                payout = 0
                pnl = -total_cost

            results.append({
                'ticker': ticker,
                'side': side,
                'contracts': contracts,
                'cost': total_cost,
                'outcome': outcome,
                'won': won,
                'payout': payout,
                'pnl': pnl
            })
        else:
            pending += 1

        # Rate limit
        if idx % 10 == 0:
            print(f"   Checked {idx}/{len(open_positions)} positions...")
            time.sleep(0.1)

    print()
    print("=" * 80)
    print("ACTUAL P&L")
    print("=" * 80)
    print()

    if results:
        results_df = pd.DataFrame(results)

        actual_pnl = results_df['pnl'].sum()
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

        print(f"📊 Results:")
        print(f"   Wins: {wins}")
        print(f"   Losses: {losses}")
        print(f"   Pending: {pending}")
        print(f"   Win Rate: {win_rate:.1%}")
        print()
        print(f"💰 Financial:")
        print(f"   Total Invested: ${total_invested:.2f}")
        print(f"   Total Payout: ${total_payout:.2f}")
        print(f"   Net P&L: ${actual_pnl:.2f}")
        print()

        if actual_pnl > 0:
            print(f"✅ YOU'RE UP ${actual_pnl:.2f}!")
        else:
            print(f"❌ YOU'RE DOWN ${abs(actual_pnl):.2f}")

        print()

        # Show best/worst trades
        print("🏆 Top 10 Winners:")
        winners = results_df[results_df['won'] == True].sort_values('pnl', ascending=False)
        for idx, trade in winners.head(10).iterrows():
            print(f"   ✅ {trade['ticker'][:40]:40s} +${trade['pnl']:.2f} ({int(trade['contracts'])} @ ${trade['cost']/trade['contracts']:.3f})")

        print()
        print("💀 Top 10 Losers:")
        losers = results_df[results_df['won'] == False].sort_values('pnl')
        for idx, trade in losers.head(10).iterrows():
            print(f"   ❌ {trade['ticker'][:40]:40s} -${abs(trade['pnl']):.2f}")

        # Save results
        results_df.to_csv('data/position_outcomes.csv', index=False)
        print()
        print("💾 Saved outcomes to data/position_outcomes.csv")

    else:
        print("❌ Could not retrieve any outcomes")
        print("   Markets may still be pending settlement")


if __name__ == '__main__':
    main()
