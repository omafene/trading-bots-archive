#!/usr/bin/env python3
"""
Spot Feed Calibration Tracker

Compares Kalshi's floor_strike (price to beat) vs our spot price feed
at market open to detect systematic bias in our aggregation method.

Purpose:
- Validate our Coinbase/Binance/Kraken median calculation
- Identify if we're consistently high/low vs Kalshi's reference
- Determine which exchange is closest to Kalshi's methodology
- Guide potential feed calibration adjustments
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class SpotFeedCalibrationTracker:
    """Track spot price feed accuracy vs Kalshi's floor_strike reference"""

    def __init__(self, data_dir="data/feed_calibration"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.csv_path = self.data_dir / "floor_strike_vs_spot.csv"
        self._ensure_csv_exists()

        # Track which markets we've already logged (avoid duplicates)
        self.logged_markets = set()

        logger.info(f"✅ Spot feed calibration tracker initialized: {self.csv_path}")

    def _ensure_csv_exists(self):
        """Create CSV with headers if doesn't exist"""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'ticker',
                    'symbol',
                    'market_open_time',
                    'minutes_until_close',

                    # Kalshi's reference
                    'kalshi_floor_strike',

                    # Our spot feed
                    'our_spot_price',

                    # Delta analysis
                    'delta_dollars',
                    'delta_pct',
                    'delta_basis_points',

                    # Individual exchanges (for analysis)
                    'coinbase_price',
                    'binance_price',
                    'kraken_price',
                    'our_aggregation_method',

                    # Which exchange was closest to Kalshi?
                    'closest_exchange',
                    'closest_delta_dollars',
                ])

    def track_market_open(self, ticker: str, symbol: str, floor_strike: float,
                          our_spot_price: float, market_open_time: str,
                          minutes_until_close: float,
                          exchange_prices: dict = None):
        """
        Track comparison at market open

        Args:
            ticker: Market ticker
            symbol: Asset symbol (BTC/ETH/SOL)
            floor_strike: Kalshi's price to beat
            our_spot_price: Our aggregated spot price at this moment
            market_open_time: When market opened (ISO format)
            minutes_until_close: Minutes until market closes
            exchange_prices: Dict with 'coinbase', 'binance', 'kraken' prices
        """
        # Skip if already logged this market
        if ticker in self.logged_markets:
            return

        self.logged_markets.add(ticker)

        # Calculate delta
        delta_dollars = our_spot_price - floor_strike
        delta_pct = (delta_dollars / floor_strike) * 100
        delta_bps = delta_pct * 100  # Basis points

        # Find closest exchange
        closest_exchange = None
        closest_delta = None
        if exchange_prices:
            for exchange, price in exchange_prices.items():
                if price is not None:
                    ex_delta = abs(price - floor_strike)
                    if closest_delta is None or ex_delta < closest_delta:
                        closest_exchange = exchange
                        closest_delta = ex_delta

        # Log to CSV
        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    ticker,
                    symbol,
                    market_open_time,
                    f"{minutes_until_close:.2f}",

                    f"{floor_strike:.4f}",
                    f"{our_spot_price:.4f}",

                    f"{delta_dollars:.4f}",
                    f"{delta_pct:.4f}",
                    f"{delta_bps:.2f}",

                    f"{exchange_prices.get('Coinbase', ''):.4f}" if exchange_prices and exchange_prices.get('Coinbase') else '',
                    f"{exchange_prices.get('Binance', ''):.4f}" if exchange_prices and exchange_prices.get('Binance') else '',
                    f"{exchange_prices.get('Kraken', ''):.4f}" if exchange_prices and exchange_prices.get('Kraken') else '',
                    'median',

                    closest_exchange or '',
                    f"{closest_delta:.4f}" if closest_delta else '',
                ])

            logger.info(f"📊 Feed calibration: {symbol} floor_strike=${floor_strike:.2f} vs our_spot=${our_spot_price:.2f} (delta: ${delta_dollars:+.2f} / {delta_pct:+.3f}%)")

        except Exception as e:
            logger.error(f"Error tracking feed calibration: {e}")

    def get_summary_stats(self) -> dict:
        """
        Calculate summary statistics from tracked data

        Returns dict with average deltas by symbol
        """
        stats = {}

        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)

                symbol_deltas = {}
                for row in reader:
                    symbol = row['symbol']
                    delta = float(row['delta_dollars'])

                    if symbol not in symbol_deltas:
                        symbol_deltas[symbol] = []
                    symbol_deltas[symbol].append(delta)

                # Calculate averages
                for symbol, deltas in symbol_deltas.items():
                    avg_delta = sum(deltas) / len(deltas)
                    stats[symbol] = {
                        'avg_delta_dollars': avg_delta,
                        'sample_count': len(deltas),
                        'consistently_high': all(d > 0 for d in deltas),
                        'consistently_low': all(d < 0 for d in deltas),
                    }
        except Exception as e:
            logger.error(f"Error calculating summary stats: {e}")

        return stats
