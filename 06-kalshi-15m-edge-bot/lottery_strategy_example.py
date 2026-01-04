#!/usr/bin/env python3
"""
Example walkthrough of how the Lottery Ticket strategy works.
This is a simulation showing the logic, not the actual implementation.
"""

# === STEP 1: SCAN FOR CHEAP CONTRACTS ===

def scan_for_lottery_tickets():
    """
    Every 10 seconds, scan all open 15m markets looking for cheap contracts.
    """

    # Example market found at 2026-02-16 10:05:23
    market = {
        'ticker': 'KXBTC15M-26FEB161015-B75K',
        'symbol': 'BTC',
        'title': 'BTC Up or Down - 15 minutes',
        'close_time': '2026-02-16T10:15:00Z',
        'minutes_to_close': 9.6,

        # Current market prices
        'yes_bid': 0.05,  # Best price someone will pay you
        'yes_ask': 0.08,  # Best price you can buy at
        'no_bid': 0.89,   # Best price for NO side
        'no_ask': 0.92,   # Best price to buy NO

        # Order book depth
        'yes_ask_size': 150,  # 150 contracts available at $0.08
        'no_ask_size': 200,   # 200 contracts available at $0.92

        # Market info
        'threshold': 74529.84,  # "Price to beat" for YES to win
        'current_spot_price': 74325.12,  # BTC is currently $204 BELOW threshold
        'volume': 1250  # Total volume traded so far
    }

    # === FILTER 1: PRICE RANGE ===
    if not (0.05 <= market['yes_ask'] <= 0.15):
        return None  # Skip: Outside lottery ticket range

    print("✅ PASS: YES price = $0.08 (in $0.05-$0.15 range)")

    # === FILTER 2: TIME WINDOW ===
    if not (8.0 <= market['minutes_to_close'] <= 12.0):
        return None  # Skip: Too early or too late

    print("✅ PASS: 9.6 minutes to close (in 8-12 minute window)")

    # === FILTER 3: LIQUIDITY ===
    if market['yes_ask_size'] < 100:
        return None  # Skip: Not enough liquidity

    print("✅ PASS: 150 contracts available (>100 minimum)")

    return market


# === STEP 2: CALCULATE MOMENTUM & EDGE ===

def analyze_momentum(market):
    """
    Use your existing momentum analyzer to calculate probability.
    This is the SAME code you already have!
    """

    # Get price history for last 15 minutes
    price_history = [
        (0, 74125.00),   # 15 min ago
        (5, 74180.50),   # 10 min ago
        (10, 74280.30),  # 5 min ago
        (14, 74325.12),  # Now
    ]

    # Calculate momentum (your existing code)
    momentum_pct = ((74325.12 - 74125.00) / 74125.00) * 100
    # = +0.27% upward momentum

    # Calculate distance to threshold
    distance_pct = ((74529.84 - 74325.12) / 74325.12) * 100
    # = +0.275% away from threshold (BTC needs to go UP)

    # Calculate trend quality (R²)
    r_squared = 0.68  # Clean uptrend

    # Your momentum analyzer calculates probability
    # Using existing v2_calibrated model:
    probability_yes_wins = calculate_probability(
        momentum_pct=0.27,
        distance_to_threshold_pct=0.275,
        r_squared=0.68,
        minutes_to_close=9.6,
        volatility_regime='normal'
    )
    # Returns: 0.28 (28% chance YES wins)

    print(f"\n📊 MOMENTUM ANALYSIS:")
    print(f"   Momentum: +0.27% (upward)")
    print(f"   Distance to threshold: +0.275%")
    print(f"   Trend quality (R²): 0.68")
    print(f"   Model probability: 28%")

    return {
        'momentum_pct': 0.27,
        'distance_pct': 0.275,
        'r_squared': 0.68,
        'probability': 0.28
    }


# === STEP 3: CALCULATE EXPECTED VALUE ===

def calculate_expected_value(market, analysis):
    """
    Determine if this lottery ticket has positive expected value.
    """

    entry_price = market['yes_ask']  # $0.08
    payout = 1.00  # $1.00 if YES wins
    probability = analysis['probability']  # 28%

    # Expected value calculation
    expected_payout = probability * payout  # 0.28 × $1.00 = $0.28
    expected_cost = entry_price  # $0.08
    gross_ev = expected_payout - expected_cost  # $0.28 - $0.08 = $0.20

    # After 7% Kalshi fees on profit
    if gross_ev > 0:
        net_ev = gross_ev * 0.93  # $0.20 × 0.93 = $0.186
    else:
        net_ev = gross_ev

    ev_percentage = (net_ev / entry_price) * 100  # 232.5% expected return!

    print(f"\n💰 EXPECTED VALUE:")
    print(f"   Entry price: ${entry_price:.2f}")
    print(f"   Win probability: {probability*100:.1f}%")
    print(f"   Expected payout: ${expected_payout:.2f}")
    print(f"   Expected profit: ${net_ev:.2f} ({ev_percentage:+.1f}%)")

    return net_ev


# === STEP 4: EDGE FILTERS ===

def check_edge_filters(market, analysis):
    """
    Additional filters to ensure quality.
    """

    filters = {
        'momentum_alignment': False,
        'trend_quality': False,
        'probability_range': False,
        'signal_strength': False
    }

    # FILTER 4: Momentum must align with bet
    # We're betting YES (price will go UP)
    # Momentum is +0.27% (upward) ✓
    if analysis['momentum_pct'] > 0:  # Positive momentum
        filters['momentum_alignment'] = True
        print("✅ Momentum aligned: +0.27% (betting on continuation)")

    # FILTER 5: Trend quality
    # R² > 0.60 means clean trend (not random noise)
    if analysis['r_squared'] > 0.60:
        filters['trend_quality'] = True
        print("✅ Clean trend: R² = 0.68")

    # FILTER 6: Probability sweet spot
    # Want 20-40% probability for lottery tickets
    # Too low (<15%) = pure gambling
    # Too high (>40%) = not a lottery ticket anymore
    if 0.20 <= analysis['probability'] <= 0.40:
        filters['probability_range'] = True
        print("✅ Probability in range: 28% (sweet spot)")

    # FILTER 7: Signal strength
    # Your existing signal_strength metric (0-100 scale)
    # Require minimum 40 for quality
    signal_strength = 52  # From your momentum analyzer
    if signal_strength >= 40:
        filters['signal_strength'] = True
        print("✅ Signal strength: 52/100")

    # All filters must pass
    return all(filters.values())


# === STEP 5: POSITION SIZING ===

def calculate_position_size(market, analysis, account_balance=1000):
    """
    Kelly Criterion for lottery tickets.
    """

    entry_price = market['yes_ask']  # $0.08
    probability = analysis['probability']  # 0.28
    payout_multiplier = (1.00 / entry_price) - 1  # 11.5x

    # Modified Kelly for lottery tickets
    # Kelly = (p × multiplier - q) / multiplier
    # Where p = win prob, q = loss prob

    p = probability
    q = 1 - probability
    multiplier = payout_multiplier

    kelly_fraction = (p * multiplier - q) / multiplier
    # = (0.28 × 11.5 - 0.72) / 11.5
    # = (3.22 - 0.72) / 11.5
    # = 0.217 (21.7% of bankroll!)

    # Use fractional Kelly (25% of Kelly) for safety
    position_fraction = kelly_fraction * 0.25
    position_size_dollars = account_balance * position_fraction

    # Cap at $20 per ticket for risk management
    position_size_dollars = min(position_size_dollars, 20)

    # Convert to number of contracts
    num_contracts = int(position_size_dollars / entry_price)

    print(f"\n📐 POSITION SIZING:")
    print(f"   Account balance: ${account_balance}")
    print(f"   Kelly fraction: {kelly_fraction*100:.1f}%")
    print(f"   Using 25% Kelly: {position_fraction*100:.1f}%")
    print(f"   Position size: ${position_size_dollars:.0f}")
    print(f"   Contracts: {num_contracts} @ ${entry_price:.2f} = ${num_contracts * entry_price:.2f}")

    return num_contracts


# === STEP 6: EXECUTE TRADE ===

def execute_lottery_ticket(market, num_contracts):
    """
    Place the order on Kalshi.
    """

    ticker = market['ticker']
    entry_price = market['yes_ask']
    total_cost = num_contracts * entry_price * 100  # Kalshi uses cents

    print(f"\n🎫 EXECUTING LOTTERY TICKET:")
    print(f"   Market: {ticker}")
    print(f"   Side: YES")
    print(f"   Price: ${entry_price:.2f}")
    print(f"   Quantity: {num_contracts} contracts")
    print(f"   Total cost: ${total_cost/100:.2f}")
    print(f"   Max loss: ${total_cost/100:.2f} (100%)")
    print(f"   Max gain: ${num_contracts:.2f} (${num_contracts - total_cost/100:.2f} profit)")

    # Send order to Kalshi
    order = {
        'ticker': ticker,
        'side': 'yes',
        'type': 'limit',
        'price': int(entry_price * 100),  # Convert to cents
        'quantity': num_contracts,
        'expiration': 60  # Cancel if not filled in 60 seconds
    }

    print(f"\n✅ ORDER PLACED")
    print(f"   Status: Pending fill...")

    return order


# === STEP 7: TRACK OUTCOMES ===

def track_outcome(market, num_contracts, entry_price):
    """
    Wait for market to close and check if we won.
    """

    # Market closes at 10:15:00
    # ... time passes ...

    # Kalshi settles the market
    final_spot_price = 74615.23  # BTC at close
    threshold = market['threshold']  # 74529.84

    if final_spot_price > threshold:
        outcome = 'YES'
        won = True
    else:
        outcome = 'NO'
        won = False

    print(f"\n⏰ MARKET CLOSED:")
    print(f"   Final BTC price: ${final_spot_price:.2f}")
    print(f"   Threshold: ${threshold:.2f}")
    print(f"   Outcome: {outcome}")

    if won:
        payout = num_contracts * 1.00
        profit = payout - (num_contracts * entry_price)
        profit_after_fees = profit * 0.93

        print(f"\n🎉 WINNER!")
        print(f"   Invested: ${num_contracts * entry_price:.2f}")
        print(f"   Payout: ${payout:.2f}")
        print(f"   Gross profit: ${profit:.2f}")
        print(f"   Net profit (after fees): ${profit_after_fees:.2f}")
        print(f"   ROI: {(profit_after_fees / (num_contracts * entry_price)) * 100:.1f}%")

        return profit_after_fees
    else:
        loss = num_contracts * entry_price

        print(f"\n❌ LOSER")
        print(f"   Invested: ${loss:.2f}")
        print(f"   Payout: $0.00")
        print(f"   Loss: -${loss:.2f}")

        return -loss


# === FULL EXAMPLE ===

def main():
    """
    Complete example of one lottery ticket trade.
    """

    print("=" * 70)
    print("🎲 LOTTERY TICKET STRATEGY - EXAMPLE TRADE")
    print("=" * 70)

    # Step 1: Find opportunity
    print("\n1️⃣ SCANNING FOR OPPORTUNITIES...")
    market = scan_for_lottery_tickets()
    if not market:
        print("❌ No opportunities found")
        return

    # Step 2: Analyze momentum
    print("\n2️⃣ ANALYZING MOMENTUM...")
    analysis = analyze_momentum(market)

    # Step 3: Calculate EV
    print("\n3️⃣ CALCULATING EXPECTED VALUE...")
    ev = calculate_expected_value(market, analysis)

    if ev <= 0:
        print(f"❌ SKIP: Negative EV ({ev:.2f})")
        return

    # Step 4: Check filters
    print("\n4️⃣ CHECKING EDGE FILTERS...")
    passed = check_edge_filters(market, analysis)

    if not passed:
        print("❌ SKIP: Failed edge filters")
        return

    # Step 5: Position sizing
    print("\n5️⃣ CALCULATING POSITION SIZE...")
    num_contracts = calculate_position_size(market, analysis, account_balance=1000)

    # Step 6: Execute
    print("\n6️⃣ EXECUTING TRADE...")
    order = execute_lottery_ticket(market, num_contracts)

    # Step 7: Track outcome
    print("\n7️⃣ WAITING FOR MARKET CLOSE...")
    print("   (9.6 minutes remaining...)")
    result = track_outcome(market, num_contracts, market['yes_ask'])

    print("\n" + "=" * 70)
    print(f"FINAL RESULT: ${result:+.2f}")
    print("=" * 70)


def calculate_probability(momentum_pct, distance_to_threshold_pct, r_squared,
                         minutes_to_close, volatility_regime):
    """
    Placeholder for your actual momentum analyzer.
    This would use your existing v2_calibrated model.
    """
    # Simplified version - your actual code is more sophisticated
    base_prob = 0.50
    momentum_factor = momentum_pct * 0.05
    distance_factor = -abs(distance_to_threshold_pct) * 0.02
    trend_factor = (r_squared - 0.5) * 0.10

    prob = base_prob + momentum_factor + distance_factor + trend_factor
    prob = max(0.05, min(0.95, prob))  # Clamp to 5-95%

    return prob


if __name__ == "__main__":
    main()
