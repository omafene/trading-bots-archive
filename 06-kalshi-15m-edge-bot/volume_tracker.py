"""
Volume Divergence Tracker
Detects when price makes new highs/lows but volume is declining (fake breakouts)
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VolumeTracker:
    """Track price/volume history and detect divergences"""

    def __init__(self, config: Dict):
        self.config = config
        self.strat = config.get('strategy', {})

        # Configuration
        self.lookback_samples = self.strat.get('volume_lookback_samples', 10)
        self.divergence_threshold = self.strat.get('volume_divergence_threshold', 0.20)
        self.min_price_move = self.strat.get('min_price_move_for_divergence', 0.005)
        self.sample_interval = self.strat.get('volume_sample_interval', 30)

        # Storage: symbol -> deque of (timestamp, price, activity)
        self.price_volume_history = {}
        self.last_sample_time = {}

        logger.info(f"✅ Volume Tracker initialized "
                   f"(lookback: {self.lookback_samples} samples, "
                   f"threshold: {self.divergence_threshold:.0%}, "
                   f"interval: {self.sample_interval}s)")

    def should_sample(self, symbol: str) -> bool:
        """Check if enough time has passed to sample again"""
        if symbol not in self.last_sample_time:
            return True

        elapsed = time.time() - self.last_sample_time[symbol]
        return elapsed >= self.sample_interval

    def add_sample(self, symbol: str, price: float, volume: Optional[float] = None):
        """
        Add a price/volume sample.
        Always uses price-change magnitude as the activity proxy — exchange volume
        data is 24h rolling (Kraken v[1]) which changes by <0.1% between 30s samples,
        making the divergence threshold unreachable with real volume figures.
        """
        if not self.should_sample(symbol):
            return

        if symbol not in self.price_volume_history:
            self.price_volume_history[symbol] = deque(maxlen=self.lookback_samples)

        # Always use price-change magnitude as activity proxy
        # (exchange volume = 24h rolling, too slow-changing for 30s samples)
        if len(self.price_volume_history[symbol]) > 0:
            last_price = self.price_volume_history[symbol][-1][1]
            activity = abs(price - last_price)
        else:
            activity = 0.0

        timestamp = time.time()
        self.price_volume_history[symbol].append((timestamp, price, activity))
        self.last_sample_time[symbol] = timestamp

        logger.debug(f"📊 {symbol}: Sampled price=${price:.2f}, activity={activity:.4f} "
                    f"(history: {len(self.price_volume_history[symbol])}/{self.lookback_samples})")

    def detect_divergence(self, symbol: str, current_price: float, current_volume: float) -> Optional[str]:
        """
        Detect price/activity divergence.

        Returns:
            'bearish' - Price making new high but momentum declining (veto YES trades)
            'bullish' - Price making new low but momentum declining (veto NO trades)
            None - No divergence detected
        """
        if symbol not in self.price_volume_history:
            return None

        history = list(self.price_volume_history[symbol])
        if len(history) < 3:
            # Need at least 3 samples to detect peaks/troughs
            return None

        # Extract price and activity arrays
        prices = [p for _, p, _ in history]
        activities = [a for _, _, a in history]

        # Current activity = price change since the last stored sample (same unit as history)
        current_activity = abs(current_price - history[-1][1])

        # Find recent price peak (highest price in history)
        max_price_idx = prices.index(max(prices))
        max_price = prices[max_price_idx]
        activity_at_max = activities[max_price_idx]

        # Find recent price trough (lowest price in history)
        min_price_idx = prices.index(min(prices))
        min_price = prices[min_price_idx]
        activity_at_min = activities[min_price_idx]

        # === BEARISH DIVERGENCE ===
        # Current price is making new high, but activity (momentum) is declining
        if current_price > max_price:
            price_increase = (current_price - max_price) / max_price

            # Only check if price moved significantly
            if price_increase >= self.min_price_move:
                if activity_at_max > 0:
                    activity_drop = (activity_at_max - current_activity) / activity_at_max
                    if activity_drop >= self.divergence_threshold:
                        logger.info(f"🔴 {symbol}: BEARISH DIVERGENCE detected!")
                        logger.info(f"   Price: ${max_price:.2f} → ${current_price:.2f} (+{price_increase:.2%})")
                        logger.info(f"   Activity: {activity_at_max:.4f} → {current_activity:.4f} (-{activity_drop:.2%})")
                        return 'bearish'

        # === BULLISH DIVERGENCE ===
        # Current price is making new low, but activity (momentum) is declining
        if current_price < min_price:
            price_decrease = (min_price - current_price) / min_price

            # Only check if price moved significantly
            if price_decrease >= self.min_price_move:
                if activity_at_min > 0:
                    activity_drop = (activity_at_min - current_activity) / activity_at_min
                    if activity_drop >= self.divergence_threshold:
                        logger.info(f"🟢 {symbol}: BULLISH DIVERGENCE detected!")
                        logger.info(f"   Price: ${min_price:.2f} → ${current_price:.2f} (-{price_decrease:.2%})")
                        logger.info(f"   Activity: {activity_at_min:.4f} → {current_activity:.4f} (-{activity_drop:.2%})")
                        return 'bullish'

        return None

    def get_status(self) -> Dict:
        """Get tracker status"""
        return {
            symbol: {
                'samples': len(history),
                'max_samples': self.lookback_samples
            }
            for symbol, history in self.price_volume_history.items()
        }
