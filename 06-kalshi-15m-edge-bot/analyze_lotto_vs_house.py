#!/usr/bin/env python3
"""
Analyze Lotto Mode vs House Mode profitability using historical data.

Lotto Mode: Buy YES contracts priced $0.05-$0.15
House Mode: Buy NO contracts priced $0.85-$0.95 (equivalent to "selling" YES)
"""

import pandas as pd
import sys

def analyze_strategies(csv_path):
    """Compare Lotto vs House mode performance."""

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Error reading {csv_path}: {e}")
        return

    # Filter to only rows with actual outcomes
    df = df[df['outcome_checked'] == True].copy()

    print(f"📊 Total observations: {len(df)}")

    # DEDUPLICATE: Take only one entry per unique market (ticker)
    # Use the last observation (closest to close time) as it has most accurate pricing
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').groupby('ticker').last().reset_index()

    print(f"📊 Unique markets after deduplication: {len(df)}")
    print(f"   (Multiple scans of same market removed)\n")
    print("=" * 70)

    # === LOTTO MODE: Buying cheap YES contracts ===
    print("\n🎲 LOTTO MODE: Buy YES at $0.05-$0.15")
    print("-" * 70)

    lotto_yes = df[(df['yes_market_price'] >= 0.05) & (df['yes_market_price'] <= 0.15)].copy()

    if len(lotto_yes) > 0:
        lotto_yes['would_win_yes'] = lotto_yes['actual_outcome'] == 'yes'

        win_rate_yes = lotto_yes['would_win_yes'].mean() * 100
        total_trades_yes = len(lotto_yes)
        wins_yes = lotto_yes['would_win_yes'].sum()
        losses_yes = total_trades_yes - wins_yes

        # Calculate P&L (assuming $100 per contract)
        avg_entry = lotto_yes['yes_market_price'].mean()
        total_cost = total_trades_yes * avg_entry * 100
        total_payout = wins_yes * 100  # Each win pays $100 (contract = $1.00)
        gross_profit = total_payout - total_cost
        net_profit = gross_profit * 0.93  # After 7% fees

        roi = (net_profit / total_cost) * 100 if total_cost > 0 else 0

        print(f"Total opportunities: {total_trades_yes}")
        print(f"Avg entry price: ${avg_entry:.3f}")
        print(f"Win rate: {win_rate_yes:.1f}% ({wins_yes} wins, {losses_yes} losses)")
        print(f"\nP&L (if trading 100 contracts each):")
        print(f"  Total invested: ${total_cost:,.0f}")
        print(f"  Total payout: ${total_payout:,.0f}")
        print(f"  Gross profit: ${gross_profit:,.0f}")
        print(f"  Net profit (after fees): ${net_profit:,.0f}")
        print(f"  ROI: {roi:+.1f}%")

        # Breakeven analysis
        breakeven = avg_entry / (1.0 - avg_entry) * 1.075  # Include fees
        print(f"\nBreakeven win rate needed: {avg_entry * 107.5:.1f}%")
        print(f"Actual win rate: {win_rate_yes:.1f}%")
        if win_rate_yes > (avg_entry * 107.5):
            print("✅ PROFITABLE STRATEGY")
        else:
            print("❌ LOSING STRATEGY")
    else:
        print("No opportunities found in this price range")

    # === HOUSE MODE: Buying expensive NO contracts (selling YES) ===
    print("\n\n🏦 HOUSE MODE: Buy NO at $0.85-$0.95 (selling YES)")
    print("-" * 70)

    house_no = df[(df['no_market_price'] >= 0.85) & (df['no_market_price'] <= 0.95)].copy()

    if len(house_no) > 0:
        house_no['would_win_no'] = house_no['actual_outcome'] == 'no'

        win_rate_no = house_no['would_win_no'].mean() * 100
        total_trades_no = len(house_no)
        wins_no = house_no['would_win_no'].sum()
        losses_no = total_trades_no - wins_no

        # Calculate P&L
        avg_entry_no = house_no['no_market_price'].mean()
        total_cost_no = total_trades_no * avg_entry_no * 100
        total_payout_no = wins_no * 100
        gross_profit_no = total_payout_no - total_cost_no
        net_profit_no = gross_profit_no * 0.93  # After 7% fees

        roi_no = (net_profit_no / total_cost_no) * 100 if total_cost_no > 0 else 0

        print(f"Total opportunities: {total_trades_no}")
        print(f"Avg entry price: ${avg_entry_no:.3f}")
        print(f"Win rate: {win_rate_no:.1f}% ({wins_no} wins, {losses_no} losses)")
        print(f"\nP&L (if trading 100 contracts each):")
        print(f"  Total invested: ${total_cost_no:,.0f}")
        print(f"  Total payout: ${total_payout_no:,.0f}")
        print(f"  Gross profit: ${gross_profit_no:,.0f}")
        print(f"  Net profit (after fees): ${net_profit_no:,.0f}")
        print(f"  ROI: {roi_no:+.1f}%")

        # Breakeven analysis
        breakeven_no = avg_entry_no / (1.0 - avg_entry_no) * 1.075
        required_wr = (avg_entry_no / (1.0 - avg_entry_no + avg_entry_no)) * 107.5
        print(f"\nBreakeven win rate needed: {avg_entry_no * 107.5:.1f}%")
        print(f"Actual win rate: {win_rate_no:.1f}%")
        if win_rate_no > (avg_entry_no * 107.5):
            print("✅ PROFITABLE STRATEGY")
        else:
            print("❌ LOSING STRATEGY")
    else:
        print("No opportunities found in this price range")

    # === COMPARISON ===
    print("\n\n🏆 HEAD-TO-HEAD COMPARISON")
    print("=" * 70)

    if len(lotto_yes) > 0 and len(house_no) > 0:
        print(f"\n{'Metric':<30} {'Lotto Mode':<20} {'House Mode':<20}")
        print("-" * 70)
        print(f"{'Total Opportunities':<30} {len(lotto_yes):<20} {len(house_no):<20}")
        print(f"{'Win Rate':<30} {win_rate_yes:.1f}%{'':<16} {win_rate_no:.1f}%")
        print(f"{'Net Profit':<30} ${net_profit:,.0f}{'':<14} ${net_profit_no:,.0f}")
        print(f"{'ROI':<30} {roi:+.1f}%{'':<15} {roi_no:+.1f}%")
        print(f"{'Max Loss Per Trade':<30} $10-15{'':<14} $85-95")
        print(f"{'Max Win Per Trade':<30} $85-95{'':<14} $10-15")
        print(f"{'Risk Profile':<30} {'Low (capped)':<20} {'High (steamroller)':<20}")

        print("\n🎯 WINNER: ", end="")
        if net_profit > net_profit_no:
            diff = net_profit - net_profit_no
            print(f"🎲 LOTTO MODE by ${diff:,.0f} ({(diff/total_cost)*100:.1f}% better ROI)")
        else:
            diff = net_profit_no - net_profit
            print(f"🏦 HOUSE MODE by ${diff:,.0f} ({(diff/total_cost_no)*100:.1f}% better ROI)")

    print("\n" + "=" * 70)

    # === ADDITIONAL ANALYSIS: Win Rate by Price Bucket ===
    print("\n\n📈 WIN RATE BY PRICE BUCKET (YES contracts)")
    print("-" * 70)

    price_buckets = [
        (0.01, 0.05, "$0.01-$0.05"),
        (0.05, 0.10, "$0.05-$0.10"),
        (0.10, 0.15, "$0.10-$0.15"),
        (0.15, 0.25, "$0.15-$0.25"),
        (0.25, 0.50, "$0.25-$0.50"),
    ]

    print(f"\n{'Price Range':<15} {'Count':<10} {'Win Rate':<12} {'Expected Value':<15} {'Verdict'}")
    print("-" * 70)

    for low, high, label in price_buckets:
        bucket = df[(df['yes_market_price'] >= low) & (df['yes_market_price'] < high)].copy()
        if len(bucket) > 0:
            bucket['would_win'] = bucket['actual_outcome'] == 'yes'
            wr = bucket['would_win'].mean()
            avg_price = bucket['yes_market_price'].mean()

            # Expected value per $1 invested
            ev = (wr * (1.00 - avg_price) - (1 - wr) * avg_price) * 0.93  # After fees

            verdict = "✅ +EV" if ev > 0 else "❌ -EV"

            print(f"{label:<15} {len(bucket):<10} {wr*100:>5.1f}%{'':<6} {ev:>+6.1f}%{'':<9} {verdict}")

    # === RECOMMENDED PRICE RANGE ===
    print("\n\n💡 RECOMMENDATION")
    print("=" * 70)

    # Find most profitable bucket
    best_ev = -999
    best_bucket = None

    for low, high, label in price_buckets:
        bucket = df[(df['yes_market_price'] >= low) & (df['yes_market_price'] < high)].copy()
        if len(bucket) > 10:  # Require at least 10 samples
            bucket['would_win'] = bucket['actual_outcome'] == 'yes'
            wr = bucket['would_win'].mean()
            avg_price = bucket['yes_market_price'].mean()
            ev = (wr * (1.00 - avg_price) - (1 - wr) * avg_price) * 0.93

            if ev > best_ev:
                best_ev = ev
                best_bucket = (label, len(bucket), wr * 100)

    if best_bucket:
        print(f"\n🎯 Best Price Range: {best_bucket[0]}")
        print(f"   Opportunities: {best_bucket[1]}")
        print(f"   Win Rate: {best_bucket[2]:.1f}%")
        print(f"   Expected Value: {best_ev:+.1f}% per trade")

        if best_ev > 0:
            print(f"\n✅ Strategy is PROFITABLE at this price range!")
            print(f"   Expected weekly profit (50 trades): ${50 * 10 * best_ev / 100:.0f}")
        else:
            print(f"\n❌ Even best price range is -EV. Strategy not viable.")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    csv_path = "/root/kalshi_15m_bot/data/negative_edges/skipped_trades.csv"
    analyze_strategies(csv_path)
