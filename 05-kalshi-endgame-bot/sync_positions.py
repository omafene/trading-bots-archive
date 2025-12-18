import json
import yaml
from kalshi_client import KalshiClient
from pathlib import Path

# Load config and client
config = yaml.safe_load(open("config.yaml"))
client = KalshiClient(config)

# Fetch live positions from Kalshi
live_positions = client.get_positions()
formatted_positions = []

for p in live_positions:
    formatted_positions.append({
        "ticker": p['ticker'],
        "side": p['side'],
        "quantity": p['position'],
        "cost": (p['position'] * p['market_price_cents']) / 100, # Estimated
        "entry_price": p['market_price_cents'] / 100,
        "status": "open",
        "entry_time": "2025-12-20T16:00:00", # Estimated
        "title": "Synced Position",
        "category": "General",
        "probability": 0.5,
        "expected_return": 0.0,
        "days_to_close": 0,
        "close_time": "2025-12-31T23:59:59",
        "pnl": 0,
        "pnl_pct": 0
    })

# Save to the bot's database
Path("data").mkdir(exist_ok=True)
with open("data/positions.json", "w") as f:
    json.dump(formatted_positions, f, indent=2)

print(f"Successfully synced {len(formatted_positions)} positions to local database.")
