"""
Advanced Volatility Analysis for Edge Detection
Implements realized vs implied volatility comparison and regime detection
"""

import logging
import statistics
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class VolatilityAnalyzer:
    """Analyze volatility regimes to detect mispriced options"""

    def __init__(self, window_minutes: int = 15):
        self.window_minutes = window_minutes
        self.price_history = {}  # symbol -> deque of (timestamp, price)
        self.max_samples = 500
        logger.info(f"✅ Volatility analyzer initialized (window={window_minutes}m)")

    def update_price(self, symbol: str, price: float, timestamp: Optional[datetime] = None):
        """Update price history for volatility calculation"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.max_samples)

        self.price_history[symbol].append((timestamp, price))

    def calculate_realized_volatility(self, symbol: str, minutes: int = 15) -> Optional[float]:
        """
        Calculate realized volatility (annualized) from price history

        Returns:
            Annualized volatility as decimal (e.g., 0.50 = 50% annual vol)
        """
        if symbol not in self.price_history:
            return None

        history = self.price_history[symbol]
        if len(history) < 2:
            return None

        # Filter to time window
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=minutes)
        recent = [(ts, p) for ts, p in history if ts >= cutoff]

        if len(recent) < 2:
            return None

        # Calculate log returns
        returns = []
        for i in range(1, len(recent)):
            ret = (recent[i][1] - recent[i-1][1]) / recent[i-1][1]
            returns.append(ret)

        if not returns:
            return None

        # Calculate standard deviation of returns
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0

        # Annualize: assume 2-second sampling, scale to annual
        # 252 trading days * 24 hours * 30 samples/hour (2-second intervals)
        samples_per_year = 252 * 24 * 30 * 60
        annualized_vol = std_dev * (samples_per_year ** 0.5)

        return annualized_vol

    def estimate_implied_volatility(self, market_prob: float, strike: float,
                                   spot: float, minutes_to_expiry: float) -> Optional[float]:
        """
        Estimate implied volatility from market probability

        For binary options, we can back out implied vol from market price
        Using simplified model: prob ≈ N(d1) where d1 = (log(S/K) + 0.5*σ²*T) / (σ*√T)

        Returns:
            Implied volatility (annualized)
        """
        if minutes_to_expiry <= 0 or market_prob <= 0 or market_prob >= 1:
            return None

        # Convert minutes to years
        time_to_expiry = minutes_to_expiry / (252 * 24 * 60)

        # For binary options, we use a simplified approximation
        # The steeper the odds, the lower the implied vol
        # Market prob close to 50% = high uncertainty = high vol
        # Market prob near 0% or 100% = low uncertainty = low vol

        # Distance from 50% (maximum uncertainty)
        distance_from_50 = abs(market_prob - 0.50)

        # Base implied vol: inversely related to confidence
        # More confident market (away from 50%) = lower vol
        implied_vol = 0.30 * (1 - distance_from_50 * 2)  # Scale 0-30% base vol

        # Adjust for moneyness
        if spot > 0 and strike > 0:
            moneyness = abs(spot - strike) / strike
            # Higher moneyness = higher implied vol (more risky)
            implied_vol += moneyness * 0.50

        # Time decay adjustment: shorter time = higher relative vol
        if time_to_expiry < (5 / (252 * 24 * 60)):  # Less than 5 minutes
            implied_vol *= 1.5

        return max(0.01, min(implied_vol, 2.0))  # Cap between 1% and 200%

    def get_volatility_signal(self, symbol: str, market_prob: float,
                             strike: float, spot: float,
                             minutes_to_expiry: float) -> Optional[Dict]:
        """
        Generate volatility-based trading signal

        Returns:
            Dictionary with signal strength and direction
        """
        realized_vol = self.calculate_realized_volatility(symbol, minutes=self.window_minutes)
        implied_vol = self.estimate_implied_volatility(market_prob, strike, spot, minutes_to_expiry)

        if realized_vol is None or implied_vol is None:
            return None

        # Calculate vol ratio
        vol_ratio = realized_vol / implied_vol if implied_vol > 0 else 1.0

        # Generate signal
        # vol_ratio > 1.2: Realized > Implied → Market underpricing volatility → Fade momentum
        # vol_ratio < 0.8: Realized < Implied → Market overpricing volatility → Ride momentum

        if vol_ratio > 1.3:
            signal = 'fade'  # Market too confident, reality is more volatile
            strength = min((vol_ratio - 1.0) * 0.30, 0.20)  # Up to 20% adjustment
        elif vol_ratio < 0.7:
            signal = 'ride'  # Market too fearful, reality is calmer
            strength = min((1.0 - vol_ratio) * 0.30, 0.20)
        else:
            signal = 'neutral'
            strength = 0.0

        return {
            'signal': signal,
            'strength': strength,
            'realized_vol': realized_vol,
            'implied_vol': implied_vol,
            'vol_ratio': vol_ratio
        }

    def detect_volatility_regime(self, symbol: str) -> Optional[Dict]:
        """
        Detect current volatility regime (quiet/normal/volatile)

        Returns:
            Regime classification and characteristics
        """
        vol_5m = self.calculate_realized_volatility(symbol, minutes=5)
        vol_15m = self.calculate_realized_volatility(symbol, minutes=15)
        vol_60m = self.calculate_realized_volatility(symbol, minutes=60)

        if vol_5m is None or vol_15m is None:
            return None

        # Classify regime
        if vol_5m < 0.20:
            regime = 'quiet'
            risk_adjustment = -0.05  # Lower probability for directional moves
        elif vol_5m > 0.60:
            regime = 'explosive'
            risk_adjustment = 0.10  # Higher probability for continued momentum
        else:
            regime = 'normal'
            risk_adjustment = 0.0

        # Detect regime change (5m vs 15m comparison)
        if vol_60m and vol_5m > vol_60m * 1.5:
            regime_change = 'accelerating'
            risk_adjustment += 0.05
        elif vol_60m and vol_5m < vol_60m * 0.7:
            regime_change = 'decelerating'
            risk_adjustment -= 0.05
        else:
            regime_change = 'stable'

        return {
            'regime': regime,
            'regime_change': regime_change,
            'risk_adjustment': risk_adjustment,
            'vol_5m': vol_5m,
            'vol_15m': vol_15m,
            'vol_60m': vol_60m
        }
