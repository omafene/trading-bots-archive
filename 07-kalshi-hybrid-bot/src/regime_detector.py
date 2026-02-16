"""
Regime Detector
Implements Gemini's regime detection filter (trending vs mean-reverting vs choppy).
"""

import logging
import numpy as np
from typing import Dict, List, Tuple
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects market regime and filters trades accordingly."""

    def __init__(self, config: Dict):
        self.config = config['strategy']['regime']
        self.trend_config = self.config['trend']
        self.vol_config = self.config['volatility']

        # Price history cache
        self.price_history = {}  # symbol -> deque of (timestamp, price)

        logger.info("✅ Regime Detector initialized")

    def check_regime(self, symbol: str, momentum_direction: str) -> Dict:
        """
        Layer 4: Regime Detection Filter

        Args:
            symbol: Asset symbol (BTC, ETH, etc.)
            momentum_direction: 'up' or 'down'

        Returns:
            {
                'passes': bool,
                'reason': str,
                'regime': str,  # 'trending', 'mean_reverting', 'choppy'
                'r_squared': float,
                'slope': float,
                'volatility': float
            }
        """

        if not self.config['enabled']:
            return {
                'passes': True,
                'reason': 'Regime filter disabled',
                'regime': 'unknown'
            }

        # Get price history
        prices = self._get_price_history(symbol)

        if len(prices) < 10:
            return {
                'passes': False,
                'reason': 'Insufficient price history',
                'regime': 'unknown'
            }

        # Calculate trend metrics
        r_squared, slope = self._calculate_trend_strength(prices)

        # Classify regime
        regime = self._classify_regime(r_squared)

        # Check if regime is allowed
        allowed_regimes = self.config['allowed_regimes']

        if regime not in allowed_regimes:
            return {
                'passes': False,
                'reason': f'Regime "{regime}" not in allowed list: {allowed_regimes}',
                'regime': regime,
                'r_squared': r_squared,
                'slope': slope
            }

        # Check momentum aligns with trend (anti-reversal protection)
        if regime == 'trending':
            min_slope = self.trend_config['min_slope_pct']

            if slope > min_slope and momentum_direction == 'down':
                return {
                    'passes': False,
                    'reason': f'Betting DOWN against strong uptrend (slope: {slope:.2%})',
                    'regime': regime,
                    'r_squared': r_squared,
                    'slope': slope
                }

            if slope < -min_slope and momentum_direction == 'up':
                return {
                    'passes': False,
                    'reason': f'Betting UP against strong downtrend (slope: {slope:.2%})',
                    'regime': regime,
                    'r_squared': r_squared,
                    'slope': slope
                }

        # Check volatility
        volatility = self._calculate_volatility(prices)
        max_vol = self.vol_config['max_atr_pct']

        if volatility > max_vol:
            return {
                'passes': False,
                'reason': f'Volatility {volatility:.2%} exceeds max {max_vol:.0%}',
                'regime': regime,
                'r_squared': r_squared,
                'slope': slope,
                'volatility': volatility
            }

        return {
            'passes': True,
            'reason': f'Regime OK: {regime}, R²={r_squared:.2f}, slope={slope:.2%}',
            'regime': regime,
            'r_squared': r_squared,
            'slope': slope,
            'volatility': volatility
        }

    def update_price_history(self, symbol: str, price: float, timestamp: datetime = None):
        """Add price observation to history."""

        if timestamp is None:
            timestamp = datetime.utcnow()

        if symbol not in self.price_history:
            # Keep enough history for 1-hour lookback
            self.price_history[symbol] = deque(maxlen=120)  # 2 observations per minute

        self.price_history[symbol].append((timestamp, price))

    def _get_price_history(self, symbol: str) -> List[float]:
        """Get prices for lookback period."""

        if symbol not in self.price_history:
            return []

        lookback_minutes = self.trend_config['lookback_minutes']
        cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)

        recent_prices = [
            price for ts, price in self.price_history[symbol]
            if ts >= cutoff_time
        ]

        return recent_prices

    def _calculate_trend_strength(self, prices: List[float]) -> Tuple[float, float]:
        """
        Calculate trend strength using linear regression.

        Returns:
            (r_squared, slope_pct)
        """

        if len(prices) < 2:
            return 0.0, 0.0

        try:
            # Linear regression
            x = np.arange(len(prices))
            y = np.array(prices)

            # Calculate slope and intercept
            n = len(x)
            x_mean = np.mean(x)
            y_mean = np.mean(y)

            numerator = np.sum((x - x_mean) * (y - y_mean))
            denominator = np.sum((x - x_mean) ** 2)

            if denominator == 0:
                return 0.0, 0.0

            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

            # Calculate R²
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y_mean) ** 2)

            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            # Convert slope to percentage
            slope_pct = (slope / y_mean) * 100 if y_mean != 0 else 0

            return max(0, r_squared), slope_pct

        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0, 0.0

    def _classify_regime(self, r_squared: float) -> str:
        """Classify market regime based on R²."""

        min_r2 = self.trend_config['min_r2']

        if r_squared >= min_r2:
            return "trending"
        elif r_squared < 0.40:
            return "mean_reverting"
        else:
            return "choppy"

    def _calculate_volatility(self, prices: List[float]) -> float:
        """
        Calculate ATR (Average True Range) as percentage of price.
        """

        if len(prices) < self.vol_config['lookback_periods']:
            return 0.0

        try:
            prices_array = np.array(prices)

            # Calculate true range (simplified: just high-low of each period)
            # In practice, would use OHLC data
            high_low = np.abs(np.diff(prices_array))

            # Average true range
            atr = np.mean(high_low[-self.vol_config['lookback_periods']:])

            # As percentage of current price
            current_price = prices[-1]
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

            return atr_pct

        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.0

    def get_stats(self, symbol: str) -> Dict:
        """Get regime statistics for a symbol."""

        prices = self._get_price_history(symbol)

        if not prices:
            return {
                'regime': 'unknown',
                'r_squared': 0,
                'slope': 0,
                'volatility': 0,
                'observations': 0
            }

        r_squared, slope = self._calculate_trend_strength(prices)
        volatility = self._calculate_volatility(prices)
        regime = self._classify_regime(r_squared)

        return {
            'regime': regime,
            'r_squared': r_squared,
            'slope': slope,
            'volatility': volatility,
            'observations': len(prices),
            'lookback_minutes': self.trend_config['lookback_minutes']
        }
