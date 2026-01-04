"""
Statistical Arbitrage Monitor
Detects when Kalshi markets lag spot price movements (basis trading opportunities)
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class BasisMonitor:
    """Monitor basis between Kalshi implied prices and spot prices"""

    def __init__(self):
        self.spot_history = {}  # symbol -> deque of (timestamp, price)
        self.kalshi_implied_history = {}  # ticker -> deque of (timestamp, implied_price)
        self.basis_history = {}  # ticker -> deque of (timestamp, basis)
        self.max_samples = 100
        logger.info("✅ Basis monitor initialized")

    def update_spot_price(self, symbol: str, price: float):
        """Update spot price history"""
        if symbol not in self.spot_history:
            self.spot_history[symbol] = deque(maxlen=self.max_samples)

        timestamp = datetime.now(timezone.utc)
        self.spot_history[symbol].append((timestamp, price))

    def calculate_implied_spot_from_market(self, market: Dict, orderbook: Dict) -> Optional[float]:
        """
        Back out implied spot price from Kalshi market prices

        For threshold markets (ABOVE/BELOW):
            If market says "ABOVE 95K" trades at 80 cents, implied spot ≈ 95K+
        For directional markets (UP/DOWN):
            If "UP" trades at 60 cents, implied spot is trending up

        Returns:
            Implied spot price
        """
        market_type = market.get('market_type', '').lower()
        threshold = market.get('threshold', 0)
        yes_ask = orderbook.get('yes_ask', 0.50)
        no_ask = orderbook.get('no_ask', 0.50)

        # For ABOVE/BELOW markets, we can estimate implied price
        if market_type == 'above' and threshold > 0:
            # If yes_ask = 0.80, market thinks 80% chance price > threshold
            # Estimate implied spot using simple linear approximation
            # Higher yes_ask = higher implied spot
            distance_pct = (yes_ask - 0.50) * 0.02  # ±2% per 10% probability
            implied_spot = threshold * (1 + distance_pct)
            return implied_spot

        elif market_type == 'below' and threshold > 0:
            # If yes_ask = 0.80, market thinks 80% chance price < threshold
            distance_pct = (yes_ask - 0.50) * 0.02
            implied_spot = threshold * (1 - distance_pct)
            return implied_spot

        # For UP/DOWN markets, no clear implied price
        return None

    def calculate_basis(self, ticker: str, symbol: str, market: Dict,
                       orderbook: Dict, current_spot: float) -> Optional[Dict]:
        """
        Calculate basis between Kalshi implied price and actual spot

        Basis = Implied Spot - Actual Spot

        Positive basis = Kalshi overpricing (spot catching up)
        Negative basis = Kalshi underpricing (spot lagging)

        Returns:
            Basis metrics and trading signal
        """
        implied_spot = self.calculate_implied_spot_from_market(market, orderbook)

        if implied_spot is None or current_spot <= 0:
            return None

        # Calculate basis
        basis = implied_spot - current_spot
        basis_pct = (basis / current_spot) * 100

        # Store history
        timestamp = datetime.now(timezone.utc)
        if ticker not in self.basis_history:
            self.basis_history[ticker] = deque(maxlen=self.max_samples)
        self.basis_history[ticker].append((timestamp, basis_pct))

        # Generate signal
        # If basis > 0.5%: Kalshi overpricing, expect reversion → Fade the move
        # If basis < -0.5%: Kalshi underpricing, expect catch-up → Ride the move

        if basis_pct > 0.50:
            signal = 'fade'
            strength = min(abs(basis_pct) * 0.03, 0.15)  # 3% strength per 1% basis, cap 15%
        elif basis_pct < -0.50:
            signal = 'ride'
            strength = min(abs(basis_pct) * 0.03, 0.15)
        else:
            signal = 'neutral'
            strength = 0.0

        return {
            'basis': basis,
            'basis_pct': basis_pct,
            'signal': signal,
            'strength': strength,
            'implied_spot': implied_spot,
            'actual_spot': current_spot
        }

    def detect_lag_opportunity(self, symbol: str, current_spot: float,
                               window_seconds: int = 60) -> Optional[Dict]:
        """
        Detect if spot has moved significantly but Kalshi hasn't caught up yet

        This is the core stat arb edge: spot moves, Kalshi lags, we trade the gap

        Returns:
            Lag detection signal
        """
        if symbol not in self.spot_history or len(self.spot_history[symbol]) < 5:
            return None

        # Get price from window_seconds ago
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        history = self.spot_history[symbol]
        past_prices = [p for ts, p in history if ts <= cutoff]
        recent_prices = [p for ts, p in history if ts > cutoff]

        if not past_prices or not recent_prices:
            return None

        # Calculate spot price change
        old_price = past_prices[-1]  # Last price before window
        price_change_pct = ((current_spot - old_price) / old_price) * 100

        # Significant move = opportunity for lag trade
        # If spot moved >1% in last 60 seconds, Kalshi may not have updated yet
        if abs(price_change_pct) > 1.0:
            direction = 'up' if price_change_pct > 0 else 'down'

            # Strength scales with magnitude of move
            strength = min(abs(price_change_pct) * 0.05, 0.25)  # Up to 25% boost

            return {
                'lag_detected': True,
                'direction': direction,
                'spot_change_pct': price_change_pct,
                'strength': strength,
                'window_seconds': window_seconds
            }

        return None

    def get_stat_arb_signal(self, ticker: str, symbol: str, market: Dict,
                           orderbook: Dict, current_spot: float) -> Dict:
        """
        Aggregate statistical arbitrage signals

        Returns:
            Combined stat arb signal
        """
        self.update_spot_price(symbol, current_spot)

        basis_signal = self.calculate_basis(ticker, symbol, market, orderbook, current_spot)
        lag_signal = self.detect_lag_opportunity(symbol, current_spot, window_seconds=60)

        # Combine signals
        total_adjustment = 0.0

        if basis_signal:
            if basis_signal['signal'] == 'ride':
                total_adjustment += basis_signal['strength']
            elif basis_signal['signal'] == 'fade':
                total_adjustment -= basis_signal['strength']

        if lag_signal and lag_signal['lag_detected']:
            # Lag opportunity adds to the signal
            total_adjustment += lag_signal['strength']

        # Cap adjustment
        total_adjustment = max(-0.25, min(0.25, total_adjustment))

        return {
            'adjustment': total_adjustment,
            'basis': basis_signal,
            'lag': lag_signal
        }
