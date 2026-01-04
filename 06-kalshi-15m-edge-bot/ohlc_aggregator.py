#!/usr/bin/env python3
"""
OHLC Aggregator - Convert 1-second price ticks to 1-minute candles
Reduces noise in R² calculation while maintaining execution speed
"""

from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class OHLCAggregator:
    """Aggregate high-frequency price data into 1-minute OHLC candles"""

    @staticmethod
    def aggregate_to_candles(price_history: List[Tuple[datetime, float]],
                            interval_seconds: int = 60) -> List[Dict]:
        """
        Aggregate price history into OHLC candles.

        Args:
            price_history: List of (timestamp, price) tuples
            interval_seconds: Candle interval (default: 60 = 1 minute)

        Returns:
            List of candle dicts with: {timestamp, open, high, low, close}
        """
        if not price_history or len(price_history) < 2:
            return []

        candles = []

        # Sort by timestamp (should already be sorted, but ensure)
        sorted_prices = sorted(price_history, key=lambda x: x[0])

        # Get first candle start time (floor to interval)
        first_ts = sorted_prices[0][0]
        candle_start = first_ts.replace(second=0, microsecond=0)

        # Iterate through prices and build candles
        current_candle = None

        for ts, price in sorted_prices:
            # Determine which candle this price belongs to
            candle_ts = ts.replace(second=0, microsecond=0)
            candle_ts = candle_ts.replace(second=(candle_ts.second // interval_seconds) * interval_seconds)

            # Start new candle if needed
            if current_candle is None or current_candle['timestamp'] != candle_ts:
                # Save previous candle if exists
                if current_candle is not None:
                    candles.append(current_candle)

                # Start new candle
                current_candle = {
                    'timestamp': candle_ts,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'count': 1
                }
            else:
                # Update existing candle
                current_candle['high'] = max(current_candle['high'], price)
                current_candle['low'] = min(current_candle['low'], price)
                current_candle['close'] = price  # Last price in interval
                current_candle['count'] += 1

        # Add last candle
        if current_candle is not None:
            candles.append(current_candle)

        logger.debug(f"Aggregated {len(sorted_prices)} ticks into {len(candles)} candles")

        return candles

    @staticmethod
    def get_close_prices(candles: List[Dict]) -> List[float]:
        """Extract close prices from candles for R² calculation"""
        return [candle['close'] for candle in candles]

    @staticmethod
    def filter_complete_candles(candles: List[Dict], current_time: datetime,
                               interval_seconds: int = 60) -> List[Dict]:
        """
        Filter out incomplete (current) candle.

        For R² calculation, we only want COMPLETE candles.
        The current candle is still forming and may be incomplete.
        """
        if not candles:
            return []

        # Current candle timestamp
        current_candle_ts = current_time.replace(second=0, microsecond=0)
        current_candle_ts = current_candle_ts.replace(
            second=(current_candle_ts.second // interval_seconds) * interval_seconds
        )

        # Return all candles except the current one
        complete = [c for c in candles if c['timestamp'] < current_candle_ts]

        logger.debug(f"Filtered {len(candles)} candles → {len(complete)} complete candles")

        return complete
