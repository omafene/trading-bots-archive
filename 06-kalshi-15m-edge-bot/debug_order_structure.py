#!/usr/bin/env python3
"""Debug order structure"""

from kalshi_client import KalshiClient
from config_loader import load_config_with_env
import json


config = load_config_with_env()
client = KalshiClient(config)

orders = client.get_orders()

# Find today's executed orders
today_executed = [o for o in orders
                  if '2026-02-02' in o.get('created_time', '')
                  and o.get('status') == 'executed']

if today_executed:
    print("Sample executed order structure:")
    print(json.dumps(today_executed[0], indent=2))
else:
    print("No executed orders found for today")
