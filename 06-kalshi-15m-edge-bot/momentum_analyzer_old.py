"""
Analyze BTC/ETH momentum to calculate expected probability.
Updated: Supports Smoothed RTI injection and Explicit Current Price.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple
import statistics
import time

logger = logging.getLogger(__name__)

class MomentumAnalyzer:
    """Calculate expected probability based on spot price momentum"""
    
    def __init__(self, spot_feed):
        self.spot_feed = spot_feed
        # CHANGED: Initialize as empty for SOL support
        self.price_history = {}
        self.max_history_length = 200  # Keep last 200 samples
        logger.info("✅ Momentum analyzer initialized")
    
    def update_price_history(self, symbol: str, price: Optional[float] = None):
        """Add price to history. Supports Smoothed RTI."""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            
        if price is None:
            price = self.spot_feed._get_price(symbol)
            
        if price:
            now = datetime.now(timezone.utc)
            self.price_history[symbol].append((now, price))
            if len(self.price_history[symbol]) > self.max_history_length:
                self.price_history[symbol] = self.price_history[symbol][-self.max_history_length:]
            logger.debug(f"{symbol} history updated: {len(self.price_history[symbol])} samples")

    def calculate_momentum(self, symbol: str, minutes: int = 15) -> Optional[Dict]:
        """Calculate price momentum over last N minutes."""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            logger.debug(f"{symbol}: Insufficient history")
            return None

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=minutes)
        recent_prices = [(ts, price) for ts, price in self.price_history[symbol] if ts >= cutoff]
        
        if len(recent_prices) < 2:
            logger.debug(f"{symbol}: Only {len(recent_prices)} samples in last {minutes}min")
            return None
        
        start_price, end_price = recent_prices[0][1], recent_prices[-1][1]
        percent_change = ((end_price - start_price) / start_price) * 100
        
        returns = []
        for i in range(1, len(recent_prices)):
            ret = (recent_prices[i][1] - recent_prices[i-1][1]) / recent_prices[i-1][1]
            returns.append(ret)
        
        volatility = statistics.stdev(returns) * 100 if len(returns) > 1 else 0
        
        # Direction
        if abs(percent_change) < 0.05: direction = 'flat'
        elif percent_change > 0: direction = 'up'
        else: direction = 'down'
        
        if returns:
            max_directional = max(sum(1 for r in returns if r > 0), sum(1 for r in returns if r < 0))
            trend_strength = (max_directional / len(returns) - 0.5) * 2
            trend_strength = max(0, min(1, trend_strength))
        else:
            trend_strength = 0
        
        return {
            'percent_change': percent_change, 'direction': direction,
            'volatility': volatility, 'trend_strength': trend_strength,
            'start_price': start_price, 'end_price': end_price, 'num_samples': len(recent_prices)
        }
    
    def calculate_expected_probability(self, symbol: str, market_type: str, 
                                      threshold: Optional[float] = None, 
                                      minutes: int = 15,
                                      current_price: Optional[float] = None) -> Optional[float]:
        """Calculate expected probability for market outcome."""
        momentum = self.calculate_momentum(symbol, minutes)
        if not momentum: return None
        
        active_price = current_price if current_price is not None else momentum['end_price']
        
        # 1. UP/DOWN Markets
        if market_type in ['up', 'down']:
            percent_change = abs(momentum['percent_change'])
            trend_strength = momentum['trend_strength']
            if momentum['direction'] == 'up' and market_type == 'up':
                expected_prob = 0.50 + min(percent_change * 5, 0.25) + (trend_strength * 0.15)
            elif momentum['direction'] == 'down' and market_type == 'down':
                expected_prob = 0.50 + min(percent_change * 5, 0.25) + (trend_strength * 0.15)
            elif (momentum['direction'] != market_type): expected_prob = 0.30 
            else: expected_prob = 0.50
        
        # 2. ABOVE/BELOW Threshold Markets
        elif market_type in ['above', 'below'] and threshold:
            distance_pct = ((threshold - active_price) / active_price) * 100
            if market_type == 'above':
                if active_price >= threshold: expected_prob = 0.80 
                else:
                    expected_prob = 0.50 - (distance_pct * 0.05)
                    if momentum['direction'] == 'up': expected_prob += 0.15
            else:  # 'below'
                if active_price <= threshold: expected_prob = 0.80
                else:
                    expected_prob = 0.50 + (distance_pct * 0.05)
                    if momentum['direction'] == 'down': expected_prob += 0.15
        else: return None
        
        return max(0.05, min(0.95, expected_prob))
