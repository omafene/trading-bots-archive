#!/usr/bin/env python3
from momentum_analyzer import MomentumAnalyzer
from spot_price_feed import CFBenchmarksRTI
import yaml
import time

with open('config_15m.yaml') as f:
    config = yaml.safe_load(f)

feed = CFBenchmarksRTI(config)
momentum = MomentumAnalyzer(feed, config)

# Simulate collecting prices for 10 seconds
print('Simulating price collection (10 seconds)...')
for i in range(5):
    momentum.update_price_history('BTC')
    time.sleep(2)

# Check history
history_len = len(momentum.price_history.get('BTC', []))
print(f'✅ Collected {history_len} price samples')

if history_len > 0:
    first = momentum.price_history['BTC'][0]
    last = momentum.price_history['BTC'][-1]
    print(f'   First: {first[0].strftime("%H:%M:%S")} - ${first[1]:,.2f}')
    print(f'   Last:  {last[0].strftime("%H:%M:%S")} - ${last[1]:,.2f}')

# Try to calculate momentum (will fail if not in a candle yet)
result = momentum.calculate_momentum('BTC', minutes=15)
if result:
    print(f'\n📊 Momentum Result:')
    print(f'   Samples in candle: {result["num_samples"]}')
    print(f'   R²: {result["r_squared"]:.3f}')
    print(f'   Confidence: {result["confidence"]}')
else:
    print('\n⏳ Not enough samples in current candle yet (need 10+)')
