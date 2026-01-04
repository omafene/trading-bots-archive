"""
Order Book Microstructure Analysis
Detects institutional flow, liquidity imbalances, and hidden information in orderbook
"""

import logging
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OrderbookAnalyzer:
    """Analyze orderbook microstructure for edge detection"""

    def __init__(self):
        self.orderbook_history = {}  # ticker -> deque of (timestamp, orderbook_snapshot)
        self.max_history = 50
        logger.info("✅ Orderbook analyzer initialized")

    def update_orderbook(self, ticker: str, orderbook: Dict):
        """Store orderbook snapshot for analysis"""
        if ticker not in self.orderbook_history:
            self.orderbook_history[ticker] = deque(maxlen=self.max_history)

        timestamp = datetime.now(timezone.utc)
        self.orderbook_history[ticker].append((timestamp, orderbook))

    def calculate_order_flow_imbalance(self, orderbook: Dict, side: str = 'yes') -> float:
        """
        Calculate order flow imbalance (OFI)

        OFI = (Bid Size - Ask Size) / (Bid Size + Ask Size)

        Positive OFI = More buying pressure
        Negative OFI = More selling pressure

        Returns:
            OFI score between -1.0 and 1.0
        """
        if side == 'yes':
            bid_size = orderbook.get('yes_bid_size', 0)
            ask_size = orderbook.get('yes_ask_size', 0)
        else:
            bid_size = orderbook.get('no_bid_size', 0)
            ask_size = orderbook.get('no_ask_size', 0)

        total = bid_size + ask_size
        if total == 0:
            return 0.0

        ofi = (bid_size - ask_size) / total
        return ofi

    def calculate_depth_imbalance(self, orderbook: Dict) -> Dict:
        """
        Calculate depth imbalance between yes/no sides

        Returns:
            Dictionary with imbalance metrics
        """
        yes_bid = orderbook.get('yes_bid_size', 0)
        yes_ask = orderbook.get('yes_ask_size', 0)
        no_bid = orderbook.get('no_bid_size', 0)
        no_ask = orderbook.get('no_ask_size', 0)

        total_yes = yes_bid + yes_ask
        total_no = no_bid + no_ask
        total = total_yes + total_no

        if total == 0:
            return {'imbalance': 0.0, 'signal': 'neutral', 'strength': 0.0}

        # Imbalance: positive = yes side has more liquidity
        imbalance = (total_yes - total_no) / total

        # Generate signal
        if imbalance > 0.30:  # 30%+ more liquidity on yes side
            signal = 'yes'
            strength = min(abs(imbalance) * 0.15, 0.15)  # Up to 15% boost
        elif imbalance < -0.30:  # 30%+ more liquidity on no side
            signal = 'no'
            strength = min(abs(imbalance) * 0.15, 0.15)
        else:
            signal = 'neutral'
            strength = 0.0

        return {
            'imbalance': imbalance,
            'signal': signal,
            'strength': strength,
            'yes_depth': total_yes,
            'no_depth': total_no
        }

    def calculate_bid_ask_pressure(self, orderbook: Dict, side: str = 'yes') -> Dict:
        """
        Measure bid/ask size pressure to detect imminent moves

        Large bid + small ask = Buying pressure (bullish)
        Small bid + large ask = Selling pressure (bearish)

        Returns:
            Pressure metrics and signal
        """
        if side == 'yes':
            bid_size = orderbook.get('yes_bid_size', 0)
            ask_size = orderbook.get('yes_ask_size', 0)
            bid_price = orderbook.get('yes_bid', 0)
            ask_price = orderbook.get('yes_ask', 1)
        else:
            bid_size = orderbook.get('no_bid_size', 0)
            ask_size = orderbook.get('no_ask_size', 0)
            bid_price = orderbook.get('no_bid', 0)
            ask_price = orderbook.get('no_ask', 1)

        if ask_size == 0:
            pressure_ratio = 999  # Infinite buying pressure
        else:
            pressure_ratio = bid_size / ask_size

        # Also consider spread tightness
        spread = ask_price - bid_price
        is_tight_spread = spread < 0.03  # Spread < 3 cents

        # Generate signal
        if pressure_ratio > 2.5 and is_tight_spread:
            # Strong buying pressure + tight spread = likely upward move
            signal = 'bullish'
            strength = min((pressure_ratio - 1.0) * 0.08, 0.12)  # Up to 12% boost
        elif pressure_ratio < 0.4 and is_tight_spread:
            # Strong selling pressure + tight spread = likely downward move
            signal = 'bearish'
            strength = min((1.0 - pressure_ratio) * 0.08, 0.12)
        else:
            signal = 'neutral'
            strength = 0.0

        return {
            'pressure_ratio': pressure_ratio,
            'spread': spread,
            'signal': signal,
            'strength': strength
        }

    def detect_liquidity_event(self, ticker: str, orderbook: Dict) -> Optional[Dict]:
        """
        Detect sudden liquidity changes (whales entering/exiting)

        Returns:
            Event description if significant change detected
        """
        if ticker not in self.orderbook_history or len(self.orderbook_history[ticker]) < 3:
            return None

        history = self.orderbook_history[ticker]
        prev_ob = history[-2][1]  # Previous orderbook

        # Calculate total liquidity change
        prev_yes_depth = prev_ob.get('yes_bid_size', 0) + prev_ob.get('yes_ask_size', 0)
        curr_yes_depth = orderbook.get('yes_bid_size', 0) + orderbook.get('yes_ask_size', 0)

        prev_no_depth = prev_ob.get('no_bid_size', 0) + prev_ob.get('no_ask_size', 0)
        curr_no_depth = orderbook.get('no_bid_size', 0) + orderbook.get('no_ask_size', 0)

        # Detect significant changes (>50% increase or decrease)
        if prev_yes_depth > 0:
            yes_change_pct = (curr_yes_depth - prev_yes_depth) / prev_yes_depth
        else:
            yes_change_pct = 0

        if prev_no_depth > 0:
            no_change_pct = (curr_no_depth - prev_no_depth) / prev_no_depth
        else:
            no_change_pct = 0

        # Flag significant events
        if abs(yes_change_pct) > 0.50 or abs(no_change_pct) > 0.50:
            event_type = 'liquidity_surge' if (yes_change_pct > 0 or no_change_pct > 0) else 'liquidity_drain'

            return {
                'event': event_type,
                'yes_change': yes_change_pct,
                'no_change': no_change_pct,
                'timestamp': datetime.now(timezone.utc)
            }

        return None

    def get_microstructure_signal(self, ticker: str, orderbook: Dict, side: str = 'yes') -> Dict:
        """
        Aggregate all microstructure signals into unified score

        Returns:
            Combined signal with strength and components
        """
        # Update history
        self.update_orderbook(ticker, orderbook)

        # Calculate individual signals
        ofi = self.calculate_order_flow_imbalance(orderbook, side)
        depth_imb = self.calculate_depth_imbalance(orderbook)
        pressure = self.calculate_bid_ask_pressure(orderbook, side)
        liquidity_event = self.detect_liquidity_event(ticker, orderbook)

        # Weight the signals
        # OFI: 40% weight
        # Depth imbalance: 30% weight
        # Bid/ask pressure: 30% weight

        ofi_contribution = ofi * 0.10  # ±10% max

        if side == depth_imb['signal']:
            depth_contribution = depth_imb['strength']
        elif depth_imb['signal'] == 'neutral':
            depth_contribution = 0.0
        else:
            depth_contribution = -depth_imb['strength']  # Against our side

        # Pressure signal alignment
        if (side == 'yes' and pressure['signal'] == 'bullish') or \
           (side == 'no' and pressure['signal'] == 'bearish'):
            pressure_contribution = pressure['strength']
        else:
            pressure_contribution = 0.0

        # Total microstructure adjustment
        total_adjustment = ofi_contribution + depth_contribution + pressure_contribution

        # Cap at ±20%
        total_adjustment = max(-0.20, min(0.20, total_adjustment))

        return {
            'adjustment': total_adjustment,
            'ofi': ofi,
            'depth_imbalance': depth_imb,
            'pressure': pressure,
            'liquidity_event': liquidity_event,
            'components': {
                'ofi_contribution': ofi_contribution,
                'depth_contribution': depth_contribution,
                'pressure_contribution': pressure_contribution
            }
        }
