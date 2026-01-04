"""
Momentum Analyzer v3 - MEAN REVERSION MODEL

Key Changes from v1/v2:
- Removed momentum bonus (was making model overconfident)
- Simplified distance-based probability calculation
- Added mean reversion penalty for strong momentum
- No broken calibration curve
- Clean, interpretable logic

Based on data analysis showing:
- Kalshi thresholds are optimistically set (hard to reach)
- Strong momentum often leads to reversals
- Simple models outperform complex multi-factor adjustments
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class MomentumAnalyzerV3:
    """
    v3: Mean reversion model with distance-based probabilities

    Philosophy:
    - Kalshi sets thresholds optimistically (markets designed to be 50/50)
    - Strong momentum often exhausts (mean reversion)
    - Simple distance-based model works better than complex adjustments
    """

    def __init__(self, spot_feed, config):
        self.spot_feed = spot_feed
        self.price_history = {}
        self.config = config

        spot_interval = config['monitoring'].get('spot_price_update_interval', 2)
        buffer_minutes = 20
        self.max_history_length = int((buffer_minutes * 60) / spot_interval)

        logger.info(f"✅ Momentum Analyzer v3 (Mean Reversion) initialized")
        logger.info(f"   Data: {buffer_minutes} min buffer, {self.max_history_length} samples")

    def update_price_history(self, symbol: str, price: Optional[float] = None):
        """Add price to history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []

        if price is None:
            price = self.spot_feed._get_price(symbol)

        if price:
            now = datetime.now(timezone.utc)
            self.price_history[symbol].append((now, price))
            if len(self.price_history[symbol]) > self.max_history_length:
                self.price_history[symbol] = self.price_history[symbol][-self.max_history_length:]

    def calculate_momentum(self, symbol: str, minutes: int = 15) -> Optional[Dict]:
        """
        Calculate momentum using linear regression

        Returns:
        - percent_change: Trend % from regression
        - direction: 'up', 'down', 'flat'
        - volatility: Price variance around trend
        - r_squared: Trend quality (0-1)
        - trend_strength: R² × momentum magnitude
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None

        now = datetime.now(timezone.utc)

        # Use full candle (not rolling window)
        candle_start = now.replace(second=0, microsecond=0)
        minutes_into_hour = candle_start.minute
        candle_minute = (minutes_into_hour // minutes) * minutes
        candle_start = candle_start.replace(minute=candle_minute)
        cutoff = candle_start

        recent_prices = [(ts, price) for ts, price in self.price_history[symbol] if ts >= cutoff]

        if len(recent_prices) < 10:
            return None

        # Linear regression
        times = np.array([(ts - recent_prices[0][0]).total_seconds() for ts, _ in recent_prices])
        prices = np.array([price for _, price in recent_prices])

        slope, intercept = np.polyfit(times, prices, 1)
        predictions = slope * times + intercept

        # R² (goodness of fit)
        ss_res = np.sum((prices - predictions) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        r_squared = max(0, min(1, r_squared))

        # Trend percent from regression
        duration_seconds = times[-1]
        start_price = prices[0]
        trend_percent = (slope * duration_seconds / start_price) * 100 if start_price > 0 else 0

        # Direction
        if abs(trend_percent) < 0.05:
            direction = 'flat'
        elif slope > 0:
            direction = 'up'
        else:
            direction = 'down'

        # Trend strength
        trend_strength = r_squared * min(abs(trend_percent) / 2.0, 1.0)

        # Volatility
        volatility = np.std(prices - predictions) / np.mean(prices) * 100 if len(prices) > 1 else 0

        # Confidence label based on R²
        if r_squared >= 0.7:
            confidence = 'high'
        elif r_squared >= 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'percent_change': trend_percent,
            'direction': direction,
            'volatility': volatility,
            'trend_strength': trend_strength,
            'r_squared': r_squared,
            'confidence': confidence,
            'slope': slope,
            'start_price': start_price,
            'end_price': prices[-1],
            'num_samples': len(recent_prices)
        }

    def get_multi_timeframe_alignment(self, symbol: str, timeframes: List[int] = [1, 5, 15]) -> Optional[Dict]:
        """
        Calculate momentum across multiple timeframes for alignment checking.

        Args:
            symbol: Asset symbol (BTC, ETH, SOL, XRP)
            timeframes: List of minute intervals to check (e.g., [1, 5, 15])

        Returns:
            Dict with momentum direction for each timeframe, or None if insufficient data
        """
        results = {}

        for minutes in timeframes:
            momentum = self.calculate_momentum(symbol, minutes)

            if momentum:
                results[f'{minutes}m'] = {
                    'direction': momentum['direction'],
                    'percent_change': momentum['percent_change'],
                    'r_squared': momentum['r_squared']
                }
            else:
                # If we can't calculate momentum for any timeframe, return None
                logger.debug(f"{symbol}: Insufficient data for {minutes}m momentum")
                return None

        # Calculate alignment score
        directions = [results[f'{m}m']['direction'] for m in timeframes]
        bullish_count = sum(1 for d in directions if d == 'up')
        bearish_count = sum(1 for d in directions if d == 'down')

        results['alignment'] = {
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'total_timeframes': len(timeframes),
            'is_aligned_bullish': bullish_count >= len(timeframes) * 0.67,  # 2/3 majority
            'is_aligned_bearish': bearish_count >= len(timeframes) * 0.67
        }

        return results

    def calculate_expected_probability_v3(self, symbol: str, market_type: str,
                                          threshold: Optional[float] = None,
                                          momentum: Dict = None,
                                          current_price: Optional[float] = None) -> Optional[float]:
        """
        v3 Probability Model: Distance-based with mean reversion

        Core Insights from Data:
        1. Kalshi thresholds are set optimistically (~0.2% above current price)
        2. Strong momentum (>0.5%) often reverses (mean reversion)
        3. Distance to threshold is best predictor
        4. Simple model beats complex multi-factor

        Returns: Probability (0.05-0.95) or None
        """
        if not momentum or not threshold:
            return None

        active_price = current_price if current_price is not None else momentum['end_price']

        # Distance to threshold as raw %
        distance_pct = ((threshold - active_price) / active_price) * 100

        # --- BASE PROBABILITY (Raw Distance) ---
        if market_type in ['up', 'above']:
            # YES wins if price >= threshold at close
            if   distance_pct < -2.0:  base_prob = 0.70  # >2% above — very safe
            elif distance_pct < -1.0:  base_prob = 0.62  # 1–2% above
            elif distance_pct < -0.5:  base_prob = 0.56  # 0.5–1% above
            elif distance_pct <  0.0:  base_prob = 0.52  # just above
            elif distance_pct <  0.5:  base_prob = 0.48  # just below
            elif distance_pct <  1.0:  base_prob = 0.42  # 0.5–1% below
            elif distance_pct <  2.0:  base_prob = 0.35  # 1–2% below
            else:                      base_prob = 0.25  # >2% below — unlikely

        elif market_type in ['down', 'below']:
            # YES wins if price < threshold (inverted)
            if   distance_pct >  2.0:  base_prob = 0.70
            elif distance_pct >  1.0:  base_prob = 0.62
            elif distance_pct >  0.5:  base_prob = 0.56
            elif distance_pct >  0.0:  base_prob = 0.52
            elif distance_pct > -0.5:  base_prob = 0.48
            elif distance_pct > -1.0:  base_prob = 0.42
            elif distance_pct > -2.0:  base_prob = 0.35
            else:                      base_prob = 0.25
        else:
            return None

        # --- MEAN REVERSION PENALTY (flat, applied uniformly) ---
        momentum_pct = abs(momentum.get('percent_change', 0))
        if   momentum_pct > 0.8:  mean_reversion_penalty = -0.12
        elif momentum_pct > 0.5:  mean_reversion_penalty = -0.08
        elif momentum_pct > 0.3:  mean_reversion_penalty = -0.04
        else:                     mean_reversion_penalty =  0.00

        # --- QUALITY ADJUSTMENT (R²) ---
        r_squared = momentum.get('r_squared', 0)
        if   r_squared > 0.7:  quality_bonus = 0.03
        elif r_squared > 0.5:  quality_bonus = 0.02
        else:                  quality_bonus = 0.00

        # --- FINAL PROBABILITY ---
        final_prob = base_prob + mean_reversion_penalty + quality_bonus
        final_prob = max(0.05, min(0.95, final_prob))

        logger.debug(f"   v3 Prob: base={base_prob:.2%} (dist={distance_pct:+.3f}%) "
                     f"+ reversion={mean_reversion_penalty:+.3f} "
                     f"+ quality={quality_bonus:+.2%} = {final_prob:.2%}")

        return final_prob

    # Wrapper for backwards compatibility
    def calculate_expected_probability(self, symbol: str, market_type: str,
                                      threshold: Optional[float] = None,
                                      minutes: int = 15,
                                      current_price: Optional[float] = None) -> Optional[float]:
        """Wrapper that calculates momentum then probability"""
        momentum = self.calculate_momentum(symbol, minutes)
        if not momentum:
            return None

        return self.calculate_expected_probability_v3(
            symbol, market_type, threshold, momentum, current_price
        )
