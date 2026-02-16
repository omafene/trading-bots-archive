"""
Volume & Order Book Analyzer
Implements Gemini's volume confirmation and order book pressure filters.
"""

import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class VolumeAnalyzer:
    """Analyzes volume expansion and order book imbalance."""

    def __init__(self, config: Dict):
        self.config = config['strategy']['volume']
        self.orderbook_config = config['strategy']['orderbook']

        # Volume history cache
        self.volume_history = {}  # symbol -> deque of (timestamp, volume)

        logger.info("✅ Volume Analyzer initialized")

    def check_volume_confirmation(self, symbol: str, current_volume: float) -> Dict:
        """
        Layer 3: Volume Confirmation Filter

        Returns:
            {
                'passes': bool,
                'reason': str,
                'volume_ratio': float,
                'current_volume': float,
                'avg_volume': float
            }
        """

        if not self.config['enabled']:
            return {
                'passes': True,
                'reason': 'Volume filter disabled',
                'volume_ratio': 1.0
            }

        # Get average volume
        avg_volume = self._get_average_volume(symbol)

        if avg_volume == 0:
            return {
                'passes': False,
                'reason': 'No historical volume data',
                'volume_ratio': 0
            }

        # Calculate volume ratio
        volume_ratio = current_volume / avg_volume
        min_ratio = self.config['min_volume_ratio']

        if volume_ratio < min_ratio:
            return {
                'passes': False,
                'reason': f'Volume ratio {volume_ratio:.2f} < {min_ratio}',
                'volume_ratio': volume_ratio,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }

        return {
            'passes': True,
            'reason': f'Volume confirmed: {volume_ratio:.2f}x average',
            'volume_ratio': volume_ratio,
            'current_volume': current_volume,
            'avg_volume': avg_volume
        }

    def check_orderbook_imbalance(
        self,
        orderbook: Dict,
        momentum_direction: str
    ) -> Dict:
        """
        Check order book pressure supports the trade direction.

        Args:
            orderbook: {'yes': [[price, size], ...], 'no': [[price, size], ...]}
            momentum_direction: 'up' or 'down'

        Returns:
            {
                'passes': bool,
                'reason': str,
                'imbalance': float,  # Positive = more bids, Negative = more asks
                'bid_depth': int,
                'ask_depth': int
            }
        """

        if not self.orderbook_config['enabled']:
            return {
                'passes': True,
                'reason': 'Orderbook filter disabled',
                'imbalance': 0
            }

        try:
            # Get order book depth
            yes_orders = orderbook.get('yes', [])
            no_orders = orderbook.get('no', [])

            if not yes_orders or not no_orders:
                return {
                    'passes': False,
                    'reason': 'Empty order book',
                    'imbalance': 0
                }

            # Calculate depth (top N levels)
            depth_levels = self.orderbook_config['depth_levels']

            # For YES side: bids = willing to buy YES, asks = willing to sell YES
            yes_bid_depth = sum(order[1] for order in yes_orders[-depth_levels:])  # Bids
            yes_ask_depth = sum(order[1] for order in yes_orders[:depth_levels])   # Asks

            # For NO side: bids = willing to buy NO, asks = willing to sell NO
            no_bid_depth = sum(order[1] for order in no_orders[-depth_levels:])
            no_ask_depth = sum(order[1] for order in no_orders[:depth_levels])

            # Calculate imbalance
            # Positive imbalance = more buying pressure (bullish)
            # Negative imbalance = more selling pressure (bearish)

            total_depth = yes_bid_depth + yes_ask_depth + no_bid_depth + no_ask_depth

            if total_depth == 0:
                return {
                    'passes': False,
                    'reason': 'No order book depth',
                    'imbalance': 0
                }

            # Buying pressure = YES bids + NO asks (people betting price goes UP)
            # Selling pressure = YES asks + NO bids (people betting price goes DOWN)
            buying_pressure = yes_bid_depth + no_ask_depth
            selling_pressure = yes_ask_depth + no_bid_depth

            imbalance = (buying_pressure - selling_pressure) / total_depth

            min_imbalance = self.orderbook_config['min_imbalance']

            # Check if imbalance supports our direction
            if momentum_direction == 'up':
                if imbalance < min_imbalance:
                    return {
                        'passes': False,
                        'reason': f'Imbalance {imbalance:.2%} < {min_imbalance:.0%} for UP bet',
                        'imbalance': imbalance,
                        'bid_depth': yes_bid_depth + no_ask_depth,
                        'ask_depth': yes_ask_depth + no_bid_depth
                    }
            else:  # down
                if imbalance > -min_imbalance:
                    return {
                        'passes': False,
                        'reason': f'Imbalance {imbalance:.2%} > -{min_imbalance:.0%} for DOWN bet',
                        'imbalance': imbalance,
                        'bid_depth': yes_bid_depth + no_ask_depth,
                        'ask_depth': yes_ask_depth + no_bid_depth
                    }

            return {
                'passes': True,
                'reason': f'Orderbook supports {momentum_direction.upper()}: imbalance {imbalance:.2%}',
                'imbalance': imbalance,
                'bid_depth': buying_pressure,
                'ask_depth': selling_pressure
            }

        except Exception as e:
            logger.error(f"Error analyzing order book: {e}")
            return {
                'passes': False,
                'reason': f'Orderbook analysis error: {e}',
                'imbalance': 0
            }

    def update_volume_history(self, symbol: str, volume: float, timestamp: datetime = None):
        """Track volume history for average calculation."""

        if timestamp is None:
            timestamp = datetime.utcnow()

        if symbol not in self.volume_history:
            self.volume_history[symbol] = deque(maxlen=100)  # Keep last 100 observations

        self.volume_history[symbol].append((timestamp, volume))

    def _get_average_volume(self, symbol: str) -> float:
        """Calculate average volume over lookback period."""

        if symbol not in self.volume_history:
            return 0

        lookback_minutes = self.config['lookback_minutes']
        cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)

        recent_volumes = [
            vol for ts, vol in self.volume_history[symbol]
            if ts >= cutoff_time
        ]

        if not recent_volumes:
            return 0

        return sum(recent_volumes) / len(recent_volumes)

    def get_stats(self, symbol: str) -> Dict:
        """Get volume statistics for a symbol."""

        if symbol not in self.volume_history:
            return {
                'observations': 0,
                'avg_volume': 0,
                'latest_volume': 0
            }

        history = list(self.volume_history[symbol])

        if not history:
            return {
                'observations': 0,
                'avg_volume': 0,
                'latest_volume': 0
            }

        volumes = [vol for _, vol in history]

        return {
            'observations': len(volumes),
            'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
            'latest_volume': volumes[-1] if volumes else 0,
            'min_volume': min(volumes) if volumes else 0,
            'max_volume': max(volumes) if volumes else 0
        }
