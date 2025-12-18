#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime

# Load trades
with open('data/positions.json', 'r') as f:
    positions = json.load(f)

# Analyze by category
by_category = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
by_probability = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})
by_days = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0})

for pos in positions:
    if pos.get('status') == 'closed':
        # By category
        cat = pos.get('category', 'Unknown')
        by_category[cat]['trades'] += 1
        if pos.get('profit', 0) > 0:
            by_category[cat]['wins'] += 1
        by_category[cat]['pnl'] += pos.get('profit', 0)
        
        # By probability range
        prob = pos.get('entry_probability', 0)
        prob_bucket = f"{int(prob*100)//5*5}-{int(prob*100)//5*5+5}%"
        by_probability[prob_bucket]['trades'] += 1
        if pos.get('profit', 0) > 0:
            by_probability[prob_bucket]['wins'] += 1
        by_probability[prob_bucket]['pnl'] += pos.get('profit', 0)
        
        # By days to expiration
        days = pos.get('days_to_expiration', 0)
        day_bucket = f"{int(days)//3*3}-{int(days)//3*3+3} days"
        by_days[day_bucket]['trades'] += 1
        if pos.get('profit', 0) > 0:
            by_days[day_bucket]['wins'] += 1
        by_days[day_bucket]['pnl'] += pos.get('profit', 0)

# Print results
print("=" * 60)
print("PERFORMANCE BY CATEGORY")
print("=" * 60)
for cat, stats in sorted(by_category.items(), key=lambda x: x[1]['pnl'], reverse=True):
    win_rate = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
    avg_pnl = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
    print(f"{cat:20s} | Trades: {stats['trades']:3d} | Win Rate: {win_rate:5.1f}% | P&L: ${stats['pnl']:+7.2f} | Avg: ${avg_pnl:+6.2f}")

print("\n" + "=" * 60)
print("PERFORMANCE BY PROBABILITY RANGE")
print("=" * 60)
for prob, stats in sorted(by_probability.items()):
    win_rate = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
    avg_pnl = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
    print(f"{prob:15s} | Trades: {stats['trades']:3d} | Win Rate: {win_rate:5.1f}% | P&L: ${stats['pnl']:+7.2f} | Avg: ${avg_pnl:+6.2f}")

print("\n" + "=" * 60)
print("PERFORMANCE BY DAYS TO EXPIRATION")
print("=" * 60)
for days, stats in sorted(by_days.items()):
    win_rate = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
    avg_pnl = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
    print(f"{days:15s} | Trades: {stats['trades']:3d} | Win Rate: {win_rate:5.1f}% | P&L: ${stats['pnl']:+7.2f} | Avg: ${avg_pnl:+6.2f}")
