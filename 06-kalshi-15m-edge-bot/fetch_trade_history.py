"""
Fetch complete trade history from Kalshi and analyze performance
"""

import sys
from datetime import datetime, timezone, timedelta
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
import pandas as pd
import json

def fetch_all_fills(client, days_back=30):
    """Fetch all fills from the last N days"""
    print(f"📥 Fetching trade history from last {days_back} days...")

    # Calculate timestamp range
    now = datetime.now(timezone.utc)
    min_time = now - timedelta(days=days_back)
    min_ts = int(min_time.timestamp() * 1000)  # Convert to milliseconds

    all_fills = []
    limit = 1000  # Max per request
    cursor = None

    # Fetch in batches
    while True:
        try:
            fills = client.get_fills(min_ts=min_ts, limit=limit)

            if not fills:
                break

            all_fills.extend(fills)
            print(f"   Fetched {len(fills)} fills (total: {len(all_fills)})...")

            # Check if there are more
            if len(fills) < limit:
                break

            # If we got fewer than requested, we're done
            # (The API doesn't support cursor pagination for fills)
            break

        except Exception as e:
            print(f"   Error fetching fills: {e}")
            break

    return all_fills


def analyze_fills(fills):
    """Analyze fill history and calculate P&L"""
    if not fills:
        print("❌ No fills found!")
        return

    print(f"\n📊 Analyzing {len(fills)} fills...")

    # Convert to DataFrame
    df = pd.DataFrame(fills)

    # Parse timestamps (handle both ISO string and milliseconds)
    if df['created_time'].dtype == 'object':
        df['timestamp'] = pd.to_datetime(df['created_time'])
    else:
        df['timestamp'] = pd.to_datetime(df['created_time'], unit='ms')
    df['price_dollars'] = df['price'] / 100  # Convert cents to dollars

    # Separate buys and sells
    buys = df[df['action'] == 'buy'].copy()
    sells = df[df['action'] == 'sell'].copy()

    print(f"\n📈 Trade Summary:")
    print(f"   Total fills: {len(df)}")
    print(f"   Buys: {len(buys)} ({buys['count'].sum()} contracts)")
    print(f"   Sells: {len(sells)} ({sells['count'].sum()} contracts)")
    print()

    # Calculate P&L by matching buys and sells per ticker
    tickers = df['ticker'].unique()

    total_pnl = 0
    wins = 0
    losses = 0

    trades_detail = []

    for ticker in tickers:
        ticker_buys = buys[buys['ticker'] == ticker]
        ticker_sells = sells[sells['ticker'] == ticker]

        if len(ticker_buys) == 0:
            continue

        # Aggregate by side
        for side in ticker_buys['side'].unique():
            side_buys = ticker_buys[ticker_buys['side'] == side]
            side_sells = ticker_sells[ticker_sells['side'] == side]

            # Calculate costs and revenues
            buy_cost = (side_buys['count'] * side_buys['price_dollars']).sum()
            buy_contracts = side_buys['count'].sum()

            sell_revenue = (side_sells['count'] * side_sells['price_dollars']).sum()
            sell_contracts = side_sells['count'].sum()

            # Open positions (not yet sold)
            open_contracts = buy_contracts - sell_contracts

            if sell_contracts > 0:
                # Closed positions - calculate realized P&L
                avg_buy = buy_cost / buy_contracts
                avg_sell = sell_revenue / sell_contracts

                pnl = sell_revenue - (sell_contracts * avg_buy)
                total_pnl += pnl

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                trades_detail.append({
                    'ticker': ticker,
                    'side': side,
                    'contracts': sell_contracts,
                    'avg_buy': avg_buy,
                    'avg_sell': avg_sell,
                    'pnl': pnl,
                    'status': 'closed'
                })

            if open_contracts > 0:
                trades_detail.append({
                    'ticker': ticker,
                    'side': side,
                    'contracts': open_contracts,
                    'avg_buy': buy_cost / buy_contracts,
                    'avg_sell': None,
                    'pnl': 0,
                    'status': 'open'
                })

    # Print closed trades
    closed_trades = [t for t in trades_detail if t['status'] == 'closed']
    open_trades = [t for t in trades_detail if t['status'] == 'open']

    print(f"💰 Closed Trades: {len(closed_trades)}")
    print(f"   Wins: {wins}")
    print(f"   Losses: {losses}")
    print(f"   Win Rate: {wins/(wins+losses)*100:.1f}%" if (wins+losses) > 0 else "   Win Rate: N/A")
    print(f"   Total P&L: ${total_pnl:.2f}")
    print()

    if closed_trades:
        print("📋 Top 10 Closed Trades:")
        closed_df = pd.DataFrame(closed_trades)
        closed_sorted = closed_df.sort_values('pnl', ascending=False)

        for idx, trade in closed_sorted.head(10).iterrows():
            emoji = "✅" if trade['pnl'] > 0 else "❌"
            print(f"   {emoji} {trade['ticker'][:35]:35s} {trade['side']:3s} "
                  f"${trade['avg_buy']:.2f}→${trade['avg_sell']:.2f} "
                  f"P&L: ${trade['pnl']:6.2f}")
        print()

    if open_trades:
        print(f"🔓 Open Positions: {len(open_trades)}")
        for trade in open_trades[:10]:
            print(f"   {trade['ticker'][:35]:35s} {trade['side']:3s} "
                  f"${trade['avg_buy']:.2f} ({int(trade['contracts'])} contracts)")
        print()

    # Save to CSV for analysis
    if trades_detail:
        trades_df = pd.DataFrame(trades_detail)
        trades_df.to_csv('data/trade_history.csv', index=False)
        print(f"💾 Saved trade history to data/trade_history.csv")

    # Save raw fills
    df.to_csv('data/raw_fills.csv', index=False)
    print(f"💾 Saved raw fills to data/raw_fills.csv")

    return {
        'total_fills': len(df),
        'closed_trades': len(closed_trades),
        'open_trades': len(open_trades),
        'wins': wins,
        'losses': losses,
        'win_rate': wins/(wins+losses) if (wins+losses) > 0 else 0,
        'total_pnl': total_pnl,
        'trades_detail': trades_detail
    }


def main():
    print("=" * 80)
    print("FETCHING KALSHI TRADE HISTORY")
    print("=" * 80)
    print()

    # Load config
    config = load_config_with_env('config_15m.yaml')

    # Initialize client
    client = KalshiClient(config)

    # Authenticate
    if not client.authenticate():
        print("❌ Authentication failed!")
        return

    print("✅ Authenticated successfully")
    print()

    # Fetch fills
    fills = fetch_all_fills(client, days_back=60)  # Last 60 days

    if not fills:
        print("❌ No trade history found!")
        print()
        print("This could mean:")
        print("  1. You haven't placed any trades in the last 60 days")
        print("  2. The bot has been in demo mode")
        print("  3. API authentication issue")
        return

    # Analyze
    results = analyze_fills(fills)

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Fills: {results['total_fills']}")
    print(f"Closed Trades: {results['closed_trades']}")
    print(f"Open Positions: {results['open_trades']}")
    print(f"Win Rate: {results['win_rate']:.1%}")
    print(f"Total P&L: ${results['total_pnl']:.2f}")
    print()


if __name__ == '__main__':
    main()
