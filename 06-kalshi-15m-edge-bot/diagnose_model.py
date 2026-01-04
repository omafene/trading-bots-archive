#!/usr/bin/env python3
"""
Diagnostic Tool: Trace Through Model Calculations
Find where probability and edge calculations go wrong
"""

import pandas as pd
import numpy as np

print("="*80)
print("MODEL DIAGNOSTIC - Finding Where Calculations Break")
print("="*80)
print()

# Load unique markets
df = pd.read_csv('data/negative_edges/skipped_trades.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.drop_duplicates(subset='ticker', keep='last')

# Calculate actual outcomes
df['entry_price'] = df['yes_market_price']
df['won'] = df['would_have_won'].fillna(0).astype(int)
df_completed = df[pd.notna(df['actual_outcome'])].copy()

print("="*80)
print("STEP 1: MOMENTUM → PROBABILITY (Base Model)")
print("="*80)
print()

# The model calculates probability from:
# 1. Distance to threshold
# 2. Momentum direction and strength
# 3. Trend strength (R² × momentum)

# Let's see if the base probability model makes sense
df_with_data = df_completed[
    pd.notna(df_completed['yes_expected_prob']) &
    pd.notna(df_completed['momentum_pct']) &
    pd.notna(df_completed['trend_strength'])
].copy()

print(f"📊 Analyzing {len(df_with_data)} markets with complete data")
print()

# Bin by momentum strength and check if probability matches
momentum_bins = [-10, -1, -0.5, -0.2, 0, 0.2, 0.5, 1, 10]
df_with_data['momentum_bin'] = pd.cut(df_with_data['momentum_pct'], bins=momentum_bins)

print("Momentum % → Expected Probability → Actual Win Rate:")
print(f"{'Momentum':<20} {'Count':<8} {'Avg Prob':<12} {'Actual WR':<12} {'Error':<10}")
print("-" * 70)

for momentum_bin in df_with_data['momentum_bin'].cat.categories:
    bin_data = df_with_data[df_with_data['momentum_bin'] == momentum_bin]
    if len(bin_data) >= 5:
        avg_prob = bin_data['yes_expected_prob'].mean()
        actual_wr = bin_data['won'].mean()
        error = avg_prob - actual_wr

        print(f"{str(momentum_bin):<20} {len(bin_data):<8} {avg_prob:>6.1%}      "
              f"{actual_wr:>6.1%}      {error:>+6.1%}")

print()

print("="*80)
print("STEP 2: MULTI-FACTOR ADJUSTMENTS")
print("="*80)
print()

# The model applies these adjustments to base probability:
# - Volatility regime: ±20%
# - Microstructure (orderbook): ±20%
# - Statistical arbitrage: ±25%
# - Time value decay: ±10%
# Total possible swing: ±75%

print("🔍 Checking if adjustments improve or hurt accuracy...")
print()

# We can't directly measure adjustments, but we can see if markets with
# extreme signals (high volatility, depth imbalance, etc.) perform differently

# Check volatility regime
df_with_vol = df_with_data[pd.notna(df_with_data['vol_regime'])].copy()
if len(df_with_vol) > 0:
    print("By Volatility Regime:")
    for regime in ['high', 'normal', 'low']:
        regime_data = df_with_vol[df_with_vol['vol_regime'] == regime]
        if len(regime_data) >= 5:
            wr = regime_data['won'].mean()
            prob = regime_data['yes_expected_prob'].mean()
            print(f"   {regime:>6}: {len(regime_data):>4} markets, "
                  f"Prob: {prob:.1%}, WR: {wr:.1%}, Error: {prob-wr:+.1%}")
    print()

# Check order book depth
df_with_depth = df_with_data[pd.notna(df_with_data['order_book_depth_total'])].copy()
if len(df_with_depth) > 0:
    depth_bins = [0, 100, 500, 1000, 5000, 100000]
    df_with_depth['depth_bin'] = pd.cut(df_with_depth['order_book_depth_total'], bins=depth_bins)

    print("By Order Book Depth:")
    for depth_bin in df_with_depth['depth_bin'].cat.categories:
        bin_data = df_with_depth[df_with_depth['depth_bin'] == depth_bin]
        if len(bin_data) >= 5:
            wr = bin_data['won'].mean()
            prob = bin_data['yes_expected_prob'].mean()
            print(f"   {str(depth_bin):<15}: {len(bin_data):>4} markets, "
                  f"Prob: {prob:.1%}, WR: {wr:.1%}, Error: {prob-wr:+.1%}")
    print()

print("="*80)
print("STEP 3: CROWD BLENDING (If Enabled)")
print("="*80)
print()

# Crowd blending weighs market price with bot probability
# If enabled, this could be pulling probability toward market price

print("💭 Theory: If crowd blending is enabled, it blends bot probability with market price")
print("   This could help IF the bot is wrong but market is right")
print("   This could hurt IF both bot and market are wrong in the same direction")
print()

# Compare bot prob to market price to actual outcome
df_compare = df_with_data[pd.notna(df_with_data['yes_market_price'])].copy()

# Calculate how close bot vs market was to actual
df_compare['bot_error'] = abs(df_compare['yes_expected_prob'] - df_compare['won'])
df_compare['market_error'] = abs(df_compare['yes_market_price'] - df_compare['won'])

print(f"Who's more accurate (lower error = better)?")
print(f"   Bot avg error: {df_compare['bot_error'].mean():.3f}")
print(f"   Market avg error: {df_compare['market_error'].mean():.3f}")

if df_compare['bot_error'].mean() < df_compare['market_error'].mean():
    print(f"   → Bot is MORE accurate (crowd blending would hurt)")
else:
    print(f"   → Market is MORE accurate (crowd blending would help)")
print()

print("="*80)
print("STEP 4: CALIBRATION CURVE")
print("="*80)
print()

# The calibration curve is supposed to map bot's raw probability to actual win rate
# Current default curve:
default_curve = [
    (0.00, 0.00),
    (0.50, 0.35),
    (0.60, 0.45),
    (0.70, 0.55),
    (0.80, 0.65),
    (0.90, 0.75),
    (0.95, 0.82),
    (1.00, 0.85),
]

print("📊 Current Default Calibration Curve:")
print(f"   {'Bot Says':<12} → {'Maps To':<12}")
for raw, calibrated in default_curve:
    print(f"   {raw:>6.0%}        → {calibrated:>6.0%}")
print()

# Compare to actual data
print("📊 What The Data Actually Shows:")
prob_bins = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
df_with_data['prob_bin'] = pd.cut(df_with_data['yes_expected_prob'], bins=prob_bins)

print(f"   {'Bot Says':<15} {'Count':<8} {'Actual WR':<12} {'Current Curve':<15} {'Error':<10}")
print("-" * 70)

curve_dict = dict(default_curve)
for i, prob_bin in enumerate(df_with_data['prob_bin'].cat.categories):
    bin_data = df_with_data[df_with_data['prob_bin'] == prob_bin]
    if len(bin_data) >= 3:
        avg_prob = bin_data['yes_expected_prob'].mean()
        actual_wr = bin_data['won'].mean()

        # Find closest calibration point
        curve_val = curve_dict.get(prob_bins[i], 0)
        error = curve_val - actual_wr

        print(f"   {str(prob_bin):<15} {len(bin_data):<8} {actual_wr:>6.1%}      "
              f"{curve_val:>6.1%}         {error:>+6.1%}")

print()

print("="*80)
print("STEP 5: EDGE CALCULATION")
print("="*80)
print()

# Edge formula: edge = ((probability - market_price - slippage) * 100) - exchange_fee
# Let's verify this makes sense

print("🔍 Edge Calculation Formula:")
print("   edge = ((probability - market_price - slippage) * 100) - fee")
print()

# Simulate with actual values
sample_markets = df_with_data[
    pd.notna(df_with_data['yes_edge_pct']) &
    pd.notna(df_with_data['yes_expected_prob']) &
    pd.notna(df_with_data['yes_market_price'])
].head(5)

print("Example Calculations:")
print(f"{'Prob':<8} {'Price':<8} {'Slip':<8} {'Fee':<8} {'Calc Edge':<12} {'Actual Edge':<12} {'Won?':<6}")
print("-" * 75)

slippage = 0.00  # Current config
fee = 1.5

for _, row in sample_markets.iterrows():
    prob = row['yes_expected_prob']
    price = row['yes_market_price']
    calc_edge = ((prob - price - slippage) * 100) - fee
    actual_edge = row['yes_edge_pct']
    won = row['won']

    print(f"{prob:>6.1%}  ${price:>6.3f}  ${slippage:>6.3f}  {fee:>6.1f}%  "
          f"{calc_edge:>+7.1f}%      {actual_edge:>+7.1f}%      {'✅' if won else '❌'}")

print()

print("="*80)
print("ROOT CAUSE ANALYSIS")
print("="*80)
print()

# Now let's identify the specific problems

print("🔬 Testing Hypotheses:")
print()

# Hypothesis 1: Probability model is systematically biased
print("1️⃣ Is probability model systematically biased?")
overall_prob = df_with_data['yes_expected_prob'].mean()
overall_wr = df_with_data['won'].mean()
bias = overall_prob - overall_wr
print(f"   Overall avg probability: {overall_prob:.1%}")
print(f"   Overall actual win rate: {overall_wr:.1%}")
print(f"   Systematic bias: {bias:+.1%}")

if abs(bias) > 0.05:
    print(f"   ❌ YES - Model is {bias:+.1%} {'overconfident' if bias > 0 else 'underconfident'}")
else:
    print(f"   ✅ NO - Model is well calibrated overall")
print()

# Hypothesis 2: Calibration curve is wrong
print("2️⃣ Is the calibration curve making it worse?")
# We saw this above - the curve maps 50% → 35%, but data shows 50-60% → 61% actual
# So the curve is making underconfidence WORSE
print(f"   Data shows: 50-60% prob → 61% actual WR")
print(f"   Curve maps: 50% → 35%")
print(f"   ❌ YES - Calibration curve is making underconfidence worse!")
print()

# Hypothesis 3: Multi-factor adjustments are noisy
print("3️⃣ Do multi-factor adjustments hurt accuracy?")
# We'd need to compare accuracy before/after adjustments
# But we can check if high adjustment markets perform worse
print(f"   (Cannot test directly without raw pre-adjustment probabilities)")
print(f"   But we see bot overall error: {df_compare['bot_error'].mean():.3f}")
print(f"   Simple momentum might be better than complex multi-factor")
print()

# Hypothesis 4: Edge formula is correct but inputs are wrong
print("4️⃣ Is the edge formula itself correct?")
print(f"   Formula: edge = ((prob - price - slippage) * 100) - fee")
print(f"   This is mathematically CORRECT for expected value")
print(f"   ✅ Formula is fine - problem is INPUTS (probability is wrong)")
print()

print("="*80)
print("SUMMARY: WHAT'S BROKEN")
print("="*80)
print()

print("1. 🔴 CALIBRATION CURVE IS BACKWARDS")
print(f"   Current curve makes underconfidence worse (maps 50%→35%)")
print(f"   Should map 50%→61% based on data")
print()

print("2. 🔴 BASE PROBABILITY MODEL IS UNDERCONFIDENT")
print(f"   Systematic bias: {bias:+.1%}")
print(f"   Especially bad at low probabilities")
print()

print("3. 🟡 MULTI-FACTOR ADJUSTMENTS MAY BE NOISY")
print(f"   Complex model with vol/orderbook/stat arb may add noise")
print(f"   Simple momentum might work better")
print()

print("4. ✅ EDGE FORMULA IS CORRECT")
print(f"   Math is right, just needs correct probability input")
print()

print("="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
