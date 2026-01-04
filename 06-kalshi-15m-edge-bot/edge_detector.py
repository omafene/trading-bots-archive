import logging
import time
from typing import List, Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)

class EdgeDetector:
    def __init__(self, spot_feed, momentum_analyzer, config: Dict, order_book_feed=None):
        self.spot_feed = spot_feed
        self.momentum = momentum_analyzer
        self.order_book_feed = order_book_feed
        self.config = config
        self.strat = config['strategy']
        self.traded_tickers = set()

        # Time-based lock protection (prevents API lag race conditions)
        self.api_lag_protection_enabled = config['strategy'].get('api_lag_protection_enabled', True)
        self.ticker_trade_timestamps = {}  # ticker: timestamp
        self.min_lock_duration = config['strategy'].get('min_ticker_lock_seconds', 30)

        # --- NEW: RTI History for 60-second Smoothing ---
        self.rti_history = {}
        self.samples_needed = 12 

    def reset_locks(self):
        self.traded_tickers.clear()
        logger.info("♻️ Ticker locks reset")

    def _get_smoothed_rti(self, symbol, current_rti):
        """Implements the 60-second averaging rule."""
        if symbol not in self.rti_history:
            self.rti_history[symbol] = deque(maxlen=self.samples_needed)
        self.rti_history[symbol].append(current_rti)
        return sum(self.rti_history[symbol]) / len(self.rti_history[symbol])

    def analyze_market(self, market: Dict) -> Optional[Dict]:
        symbol, ticker = market['symbol'], market['ticker']
        
        if self.strat.get('ticker_lock_enabled', True) and ticker in self.traded_tickers:
            logger.debug(f"⏭️ {ticker} skip: Ticker Locked")
            return None

        # --- FIX: Match your specific spot_feed method names ---
        raw_rti = self.spot_feed._get_price(symbol)
        if not raw_rti:
            logger.info(f"⏭️ {ticker} skip: No Spot Price for {symbol}")
            return None

        # --- FIX 2: Apply 60-second Smoothing ---
        smoothed_price = self._get_smoothed_rti(symbol, raw_rti)
        
        self.momentum.update_price_history(symbol, price=smoothed_price)
        momentum = self.momentum.calculate_momentum(symbol, minutes=15)
        if not momentum:
            logger.info(f"⏭️ {ticker} skip: Building History for {symbol}")
            return None

        # Trend filter
        if self.strat.get('trend_filter_enabled', False):
            allowed_trends = self.strat.get('allowed_trends', ['up', 'down', 'flat'])
            current_trend = momentum['direction']
            if current_trend not in allowed_trends:
                logger.debug(f"⏭️ {ticker} skip: Trend '{current_trend}' not in allowed {allowed_trends}")
                return None

        # NEW: R² Confidence Filter (skip noisy/choppy markets)
        if self.strat.get('r_squared_filter_enabled', False):
            min_r_squared = self.strat.get('min_r_squared', 0.3)
            current_r_squared = momentum.get('r_squared', 0)
            if current_r_squared < min_r_squared:
                logger.info(f"⏭️ {ticker} skip: Low R² ({current_r_squared:.2f} < {min_r_squared:.2f}) - noisy trend")
                return None

        # --- NEW: Order Book Imbalance Veto ---
        if self.order_book_feed and self.strat.get('order_book_filter_enabled', False):
            if not self.order_book_feed.is_data_fresh(symbol):
                logger.debug(f"⏭️ {ticker} skip: Stale Order Book Data")
                return None

            imbalance = self.order_book_feed.get_imbalance(symbol)
            if imbalance is None:
                logger.debug(f"⏭️ {ticker} skip: No Order Book Data")
                return None

            # Veto neutral imbalance (no clear directional pressure)
            min_imbalance = self.strat.get('order_book_min_imbalance', 0.40)
            max_imbalance = self.strat.get('order_book_max_imbalance', 0.60)

            if min_imbalance < imbalance < max_imbalance:
                logger.info(f"⏭️ {ticker} skip: Weak Order Book Imbalance ({imbalance:.2%} - neutral)")
                return None

            # Store imbalance for later logging
            order_book_imbalance = imbalance
        else:
            order_book_imbalance = None

        # --- FIX 3: Explicit Fee Subtraction ---
        # Treat slippage_buffer as dollars (aligned with position_manager)
        exchange_fee = 0.015 * 100
        slippage_dollars = self.strat.get('slippage_buffer', 0.02)  # e.g., 0.10 = $0.10

        expected_prob = self._get_expected_prob(market, momentum, smoothed_price)
        if not expected_prob:
            logger.info(f"⏭️ {ticker} skip: Prob Model Failed")
            return None

        # Subtract slippage from entry point, then convert to percentage and subtract fee
        edge_yes = ((expected_prob - market['yes_ask'] - slippage_dollars) * 100) - exchange_fee
        edge_no = (((1 - expected_prob) - market['no_ask'] - slippage_dollars) * 100) - exchange_fee

        if edge_yes > edge_no and edge_yes >= self.strat.get('min_edge_percent', 15.0):
            side, edge, entry, depth = 'yes', edge_yes, market['yes_ask'], market['yes_ask_size']
        elif edge_no >= self.strat.get('min_edge_percent', 15.0):
            side, edge, entry, depth = 'no', edge_no, market['no_ask'], market['no_ask_size']
        else: 
            logger.info(f"⏭️ {ticker} skip: Low Edge (Yes: {edge_yes:.1f}%, No: {edge_no:.1f}%)")
            return None

        # --- NEW: Spread Filter ---
        if self.strat.get('max_spread_filter_enabled', False):
            max_spread = self.strat.get('max_bid_ask_spread', 0.10)
            # Calculate spread for the specific side we are trading
            current_spread = (market['yes_ask'] - market['yes_bid']) if side == 'yes' else (market['no_ask'] - market['no_bid'])
            
            if current_spread > max_spread:
                logger.info(f"⏭️ {ticker} skip: High Spread (${current_spread:.2f} > ${max_spread:.2f})")
                return None

        # --- NEW: Trend Protection Veto ---
        if self.strat.get('trend_protection_enabled', False):
            trend_val = momentum.get('trend_strength', 0)
            trend_dir = momentum.get('direction', 'flat')
            
            # Veto NO trades if the trend is strongly against us
            if side == 'no':
                max_trend = self.strat.get('max_trend_for_no', 0.70)
                # If we bet NO on an 'Above' market, a strong 'UP' trend is dangerous
                if market['market_type'] == 'above' and trend_dir == 'up' and trend_val > max_trend:
                    logger.info(f"⏭️ {ticker} skip: Trend Veto (Strong UP trend vs NO bet)")
                    return None
                # If we bet NO on a 'Below' market, a strong 'DOWN' trend is dangerous
                if market['market_type'] == 'below' and trend_dir == 'down' and trend_val > max_trend:
                    logger.info(f"⏭️ {ticker} skip: Trend Veto (Strong DOWN trend vs NO bet)")
                    return None


        # Safety Gates
        min_entry = self.strat.get('min_entry_price', 0.10)
        if self.strat.get('price_floor_enabled', True) and entry < min_entry:
            logger.info(f"⏭️ {ticker} skip: Price Floor (${entry:.2f} < ${min_entry:.2f})")
            return None

        expected_win_prob = expected_prob if side == 'yes' else (1 - expected_prob)
        if expected_win_prob < self.strat.get('min_expected_probability', 0.60): 
            logger.info(f"⏭️ {ticker} skip: Low Win Prob ({expected_win_prob:.1%})")
            return None
        
        signal_strength = self._calculate_signal_strength(edge, momentum, expected_win_prob)
        if signal_strength < self.strat.get('min_signal_strength', 0):
            logger.info(f"⏭️ {ticker} skip: Low Signal ({signal_strength:.1f})")
            return None

        # --- FIX: ROI Calculation ---
        expected_roi = ((expected_win_prob - entry) / entry) * 100 if entry > 0 else 0

        # --- NEW: Liquidity Gate ---
        if self.strat.get('liquidity_gate_enabled', False):
            min_depth = self.strat.get('min_order_book_depth', 5)
            if depth < min_depth:
                logger.info(f"⏭️ {ticker} skip: Insufficient Depth ({depth} < {min_depth})")
                return None

        return {
            **market,
            'minutes_to_close': market.get('minutes_to_close', 0),
            'expected_probability': expected_prob,
            'edge_percent': edge,
            'recommended_side': side,
            'entry_price': entry,
            'expected_win_prob': expected_win_prob,
            'expected_roi': expected_roi,
            'depth': depth,
            'signal_strength': signal_strength,
            'momentum': momentum,
            'market_probability': entry,
            'order_book_imbalance': order_book_imbalance  # NEW: Track imbalance for analysis
        }

    def _get_expected_prob(self, market, momentum, smoothed_price):
        """Passes the smoothed price into the probability model."""
        return self.momentum.calculate_expected_probability(
            market['symbol'], market['market_type'], market.get('threshold'), 15, current_price=smoothed_price
        )

    def _calculate_signal_strength(self, edge, momentum, expected_prob):
        """
        Calculate signal strength with R² confidence weighting.
        High R² = clean trend = bonus points
        Low R² = noisy/choppy = penalty points
        """
        # Base scores
        edge_score = (min(edge, 20) / 20) * 50
        prob_score = max(0, (expected_prob - 0.5) * 2) * 25
        mom_score = 10 if 0.5 <= abs(momentum.get('percent_change', 0)) <= 2.0 else 0

        # Trend penalty (extreme trends risky)
        trend_val = abs(momentum.get('trend_strength', 0))
        trend_penalty = ((max(0, trend_val - 0.65)) / 0.35)**2 * 25 if trend_val > 0.65 else 0

        # NEW: R² Confidence Bonus/Penalty
        r_squared = momentum.get('r_squared', 0.5)  # Default to medium if missing

        if r_squared >= 0.7:
            # High confidence = strong, clean trend
            confidence_adjust = 15
        elif r_squared >= 0.4:
            # Medium confidence = acceptable
            confidence_adjust = 0
        else:
            # Low confidence = noisy, choppy = penalize
            confidence_adjust = -10

        total = edge_score + prob_score + mom_score + confidence_adjust - trend_penalty
        return max(0, min(100, round(total, 1)))

    def scan_for_edges(self, markets: List[Dict]) -> List[Dict]:
        opportunities = []
        for market in markets:
            opp = self.analyze_market(market)
            if opp: opportunities.append(opp)
        return sorted(opportunities, key=lambda x: x['edge_percent'], reverse=True)
