"""
Unified Edge Detector
Combines all filters into one adaptive system that works for both lottery and balanced modes.
"""

import logging
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UnifiedEdgeDetector:
    """
    Single edge detector that adapts strategy based on entry price range.

    Implements 8-layer validation:
    1. Universal filters (price, time, liquidity)
    2. Momentum analysis
    3. Volume confirmation (Gemini)
    4. Regime detection (Gemini)
    5. Probability calculation
    6. Expected value
    7. Position sizing
    8. Execution protection (Gemini)
    """

    def __init__(self, config: Dict, spot_feed, volume_analyzer, regime_detector):
        self.config = config['strategy']
        self.spot_feed = spot_feed
        self.volume_analyzer = volume_analyzer
        self.regime_detector = regime_detector

        # Price range configuration
        self.min_price = self.config['entry_price_range']['min']
        self.max_price = self.config['entry_price_range']['max']

        # Detect operating mode
        self.mode = self._detect_mode()

        logger.info(f"✅ Unified Edge Detector initialized in {self.mode.upper()} mode")
        logger.info(f"   Price range: ${self.min_price:.2f} - ${self.max_price:.2f}")

    def _detect_mode(self) -> str:
        """Auto-detect operating mode based on price range."""

        if self.max_price <= 0.20:
            return "lottery"
        elif self.min_price >= 0.35:
            return "balanced"
        else:
            return "hybrid"

    def evaluate_opportunity(self, market_data: Dict) -> Optional[Dict]:
        """
        Evaluate a market opportunity through all 8 layers.

        Args:
            market_data: {
                'ticker': str,
                'symbol': str,
                'title': str,
                'close_time': datetime,
                'minutes_to_close': float,
                'yes_ask': float,
                'no_ask': float,
                'yes_bid': float,
                'no_bid': float,
                'yes_ask_size': int,
                'no_ask_size': int,
                'threshold': float,
                'volume': int,
                'orderbook': dict
            }

        Returns:
            Opportunity dict if passes all filters, None otherwise
        """

        ticker = market_data.get('ticker', 'unknown')

        try:
            # ===== LAYER 1: UNIVERSAL FILTERS =====

            layer1 = self._check_universal_filters(market_data)
            if not layer1['passes']:
                logger.debug(f"❌ {ticker}: {layer1['reason']}")
                return None

            # ===== LAYER 2: MOMENTUM ANALYSIS =====

            layer2 = self._analyze_momentum(market_data)
            if not layer2['passes']:
                logger.debug(f"❌ {ticker}: {layer2['reason']}")
                return None

            # ===== LAYER 3: VOLUME CONFIRMATION =====

            layer3 = self.volume_analyzer.check_volume_confirmation(
                symbol=market_data['symbol'],
                current_volume=market_data.get('volume', 0)
            )

            if not layer3['passes']:
                logger.debug(f"❌ {ticker}: {layer3['reason']}")
                return None

            # Check order book imbalance
            layer3_orderbook = self.volume_analyzer.check_orderbook_imbalance(
                orderbook=market_data.get('orderbook', {}),
                momentum_direction=layer2['direction']
            )

            if not layer3_orderbook['passes']:
                logger.debug(f"❌ {ticker}: {layer3_orderbook['reason']}")
                return None

            # ===== LAYER 4: REGIME DETECTION =====

            layer4 = self.regime_detector.check_regime(
                symbol=market_data['symbol'],
                momentum_direction=layer2['direction']
            )

            if not layer4['passes']:
                logger.debug(f"❌ {ticker}: {layer4['reason']}")
                return None

            # ===== LAYER 5: PROBABILITY CALCULATION =====

            layer5 = self._calculate_probability(market_data, layer2)

            if not layer5['passes']:
                logger.debug(f"❌ {ticker}: {layer5['reason']}")
                return None

            # ===== LAYER 6: EXPECTED VALUE =====

            layer6 = self._calculate_expected_value(
                entry_price=market_data['yes_ask'],
                probability=layer5['probability']
            )

            if not layer6['passes']:
                logger.debug(f"❌ {ticker}: {layer6['reason']}")
                return None

            # ===== LAYER 7: POSITION SIZING =====

            layer7 = self._calculate_position_size(
                entry_price=market_data['yes_ask'],
                probability=layer5['probability'],
                expected_value=layer6['expected_value']
            )

            # ===== LAYER 8: EXECUTION PROTECTION =====

            layer8 = self._check_execution_protection(market_data)

            if not layer8['passes']:
                logger.debug(f"❌ {ticker}: {layer8['reason']}")
                return None

            # ===== ALL LAYERS PASSED! =====

            opportunity = {
                'ticker': ticker,
                'symbol': market_data['symbol'],
                'title': market_data['title'],
                'close_time': market_data['close_time'],
                'minutes_to_close': market_data['minutes_to_close'],

                # Entry details
                'side': 'yes',
                'entry_price': market_data['yes_ask'],
                'position_size': layer7['num_contracts'],
                'total_cost': layer7['total_cost'],

                # Strategy mode
                'mode': 'lottery' if market_data['yes_ask'] <= 0.20 else 'balanced',

                # Analytics
                'probability': layer5['probability'],
                'expected_value': layer6['expected_value'],
                'momentum_pct': layer2['momentum_pct'],
                'trend_quality_r2': layer2['r_squared'],

                # Filter results
                'filters': {
                    'universal': layer1,
                    'momentum': layer2,
                    'volume': {**layer3, **layer3_orderbook},
                    'regime': layer4,
                    'probability': layer5,
                    'expected_value': layer6,
                    'position_size': layer7,
                    'execution': layer8
                },

                # Timestamp
                'analyzed_at': datetime.utcnow()
            }

            logger.info(f"✅ {ticker}: OPPORTUNITY FOUND!")
            logger.info(f"   Mode: {opportunity['mode'].upper()}")
            logger.info(f"   Entry: ${opportunity['entry_price']:.2f}")
            logger.info(f"   Size: {opportunity['position_size']} contracts (${opportunity['total_cost']:.2f})")
            logger.info(f"   Probability: {opportunity['probability']:.1%}")
            logger.info(f"   Expected Value: {opportunity['expected_value']:.1%}")

            return opportunity

        except Exception as e:
            logger.error(f"Error evaluating {ticker}: {e}", exc_info=True)
            return None

    def _check_universal_filters(self, market_data: Dict) -> Dict:
        """Layer 1: Check price range, time window, and liquidity."""

        entry_price = market_data['yes_ask']

        # Price range filter
        if not (self.min_price <= entry_price <= self.max_price):
            return {
                'passes': False,
                'reason': f'Price ${entry_price:.2f} outside range ${self.min_price:.2f}-${self.max_price:.2f}'
            }

        # Time window filter
        minutes_to_close = market_data['minutes_to_close']
        min_time = self.config['time_window']['min_minutes_to_close']
        max_time = self.config['time_window']['max_minutes_to_close']

        if not (min_time <= minutes_to_close <= max_time):
            return {
                'passes': False,
                'reason': f'Time {minutes_to_close:.1f}m outside window {min_time}-{max_time}m'
            }

        # Liquidity filter
        min_contracts = self.config['liquidity']['min_contracts_available']
        available = market_data.get('yes_ask_size', 0)

        if available < min_contracts:
            return {
                'passes': False,
                'reason': f'Liquidity {available} < {min_contracts} contracts'
            }

        return {
            'passes': True,
            'entry_price': entry_price,
            'minutes_to_close': minutes_to_close,
            'available_contracts': available
        }

    def _analyze_momentum(self, market_data: Dict) -> Dict:
        """Layer 2: Analyze momentum and trend quality."""

        symbol = market_data['symbol']
        threshold = market_data.get('threshold')
        current_price = self.spot_feed._get_price(symbol)

        if not current_price or not threshold:
            return {
                'passes': False,
                'reason': 'Missing price or threshold data'
            }

        # Get price history
        price_history = self._get_price_history(symbol)

        if len(price_history) < 5:
            return {
                'passes': False,
                'reason': 'Insufficient price history'
            }

        # Calculate momentum
        momentum_pct = ((current_price - price_history[0]) / price_history[0]) * 100

        # Calculate distance to threshold
        distance_pct = ((threshold - current_price) / current_price) * 100

        # Determine direction
        if distance_pct > 0:
            direction = 'up'  # Price needs to go UP to reach threshold
        else:
            direction = 'down'  # Price needs to go DOWN

        # Check momentum alignment
        min_momentum = self.config['momentum']['min_alignment_pct']

        if direction == 'up' and momentum_pct < min_momentum:
            return {
                'passes': False,
                'reason': f'Momentum {momentum_pct:.2%} < {min_momentum:.0%} for UP bet'
            }

        if direction == 'down' and momentum_pct > -min_momentum:
            return {
                'passes': False,
                'reason': f'Momentum {momentum_pct:.2%} > -{min_momentum:.0%} for DOWN bet'
            }

        # Calculate trend quality (R²)
        r_squared = self._calculate_r_squared(price_history)
        min_r2 = self.config['momentum']['min_trend_quality_r2']

        if r_squared < min_r2:
            return {
                'passes': False,
                'reason': f'Trend quality R²={r_squared:.2f} < {min_r2}'
            }

        return {
            'passes': True,
            'direction': direction,
            'momentum_pct': momentum_pct,
            'distance_to_threshold_pct': abs(distance_pct),
            'r_squared': r_squared,
            'current_price': current_price,
            'threshold': threshold
        }

    def _calculate_probability(self, market_data: Dict, momentum: Dict) -> Dict:
        """Layer 5: Calculate win probability with adaptive thresholds."""

        # Simplified v2_calibrated model
        # In production, would use more sophisticated model

        momentum_pct = momentum['momentum_pct']
        distance_pct = momentum['distance_to_threshold_pct']
        r_squared = momentum['r_squared']

        # Base probability
        base_prob = 0.50

        # Momentum factor (stronger momentum = higher probability)
        momentum_factor = abs(momentum_pct) * 0.05

        # Distance factor (further from threshold = lower probability)
        distance_factor = -distance_pct * 0.02

        # Trend quality factor (cleaner trend = higher confidence)
        trend_factor = (r_squared - 0.5) * 0.10

        # Combined probability
        probability = base_prob + momentum_factor + distance_factor + trend_factor

        # Clamp to 5-95%
        probability = max(0.05, min(0.95, probability))

        # Check adaptive thresholds based on entry price
        entry_price = market_data['yes_ask']

        if entry_price <= 0.20:
            # Lottery mode thresholds
            min_prob = self.config['probability']['lottery_mode']['min_probability']
            max_prob = self.config['probability']['lottery_mode']['max_probability']
        else:
            # Balanced mode thresholds
            min_prob = self.config['probability']['balanced_mode']['min_probability']
            max_prob = self.config['probability']['balanced_mode']['max_probability']

        if not (min_prob <= probability <= max_prob):
            return {
                'passes': False,
                'reason': f'Probability {probability:.1%} outside range {min_prob:.0%}-{max_prob:.0%}',
                'probability': probability
            }

        return {
            'passes': True,
            'probability': probability,
            'components': {
                'base': base_prob,
                'momentum': momentum_factor,
                'distance': distance_factor,
                'trend': trend_factor
            }
        }

    def _calculate_expected_value(self, entry_price: float, probability: float) -> Dict:
        """Layer 6: Calculate expected value."""

        payout = 1.00
        cost = entry_price

        expected_payout = probability * payout
        expected_cost = cost

        gross_ev = expected_payout - expected_cost

        # After 7% Kalshi fees on profit
        if gross_ev > 0:
            net_ev = gross_ev * 0.93
        else:
            net_ev = gross_ev

        ev_percentage = (net_ev / cost) * 100 if cost > 0 else 0

        if net_ev <= 0:
            return {
                'passes': False,
                'reason': f'Negative EV: {ev_percentage:.1%}',
                'expected_value': ev_percentage / 100
            }

        return {
            'passes': True,
            'expected_value': ev_percentage / 100,
            'ev_percentage': ev_percentage,
            'expected_profit': net_ev
        }

    def _calculate_position_size(self, entry_price: float, probability: float, expected_value: float) -> Dict:
        """Layer 7: Calculate optimal position size using Kelly criterion."""

        # Determine mode-specific parameters
        if entry_price <= 0.20:
            # Lottery mode
            base_size = self.config['position_sizing']['lottery_mode']['base_position']
            max_size = self.config['position_sizing']['lottery_mode']['max_position']
        else:
            # Balanced mode
            base_size = self.config['position_sizing']['balanced_mode']['base_position']
            max_size = self.config['position_sizing']['balanced_mode']['max_position']

        # Kelly criterion
        payout_ratio = (1.0 - entry_price) / entry_price
        kelly_fraction = (probability * payout_ratio - (1 - probability)) / payout_ratio

        # Use fractional Kelly (25% for safety)
        kelly_pct = max(0, kelly_fraction) * self.config['position_sizing']['kelly_fraction']

        # Calculate position size (assuming $1000 capital for now)
        capital = 1000  # TODO: Get from account balance
        kelly_size = kelly_pct * capital

        # Cap at configured limits
        position_size = min(max(base_size, kelly_size), max_size)

        # Convert to number of contracts
        num_contracts = int(position_size / entry_price) if entry_price > 0 else 0

        total_cost = num_contracts * entry_price

        return {
            'num_contracts': num_contracts,
            'total_cost': total_cost,
            'kelly_fraction': kelly_pct,
            'base_size': base_size,
            'max_size': max_size
        }

    def _check_execution_protection(self, market_data: Dict) -> Dict:
        """Layer 8: Check spread and execution conditions."""

        yes_bid = market_data.get('yes_bid', 0)
        yes_ask = market_data.get('yes_ask', 1)

        spread = yes_ask - yes_bid
        max_spread = self.config['execution']['max_spread_cents']

        if spread > max_spread:
            return {
                'passes': False,
                'reason': f'Spread {spread:.2f} > {max_spread} cents',
                'spread': spread
            }

        return {
            'passes': True,
            'spread': spread
        }

    def _get_price_history(self, symbol: str, lookback_minutes: int = None) -> List[float]:
        """Get recent price history from spot feed."""

        if lookback_minutes is None:
            lookback_minutes = self.config['momentum']['lookback_minutes']

        # TODO: Implement actual price history retrieval
        # For now, return empty list (will be populated by spot feed)
        return []

    def _calculate_r_squared(self, prices: List[float]) -> float:
        """Calculate R² for trend quality."""

        if len(prices) < 2:
            return 0.0

        try:
            x = np.arange(len(prices))
            y = np.array(prices)

            x_mean = np.mean(x)
            y_mean = np.mean(y)

            numerator = np.sum((x - x_mean) * (y - y_mean))
            denominator = np.sum((x - x_mean) ** 2)

            if denominator == 0:
                return 0.0

            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y_mean) ** 2)

            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

            return max(0, r_squared)

        except Exception as e:
            logger.error(f"Error calculating R²: {e}")
            return 0.0
