"""
Advanced Multi-Factor Edge Detector
Integrates momentum, volatility, microstructure, and statistical arbitrage signals
"""

import logging
from typing import List, Dict, Optional
from collections import deque
from negative_edge_tracker import NegativeEdgeTracker

logger = logging.getLogger(__name__)


class AdvancedEdgeDetector:
    """Multi-factor edge detection with true information advantages"""

    def __init__(self, spot_feed, momentum_analyzer, volatility_analyzer,
                 orderbook_analyzer, basis_monitor, config: Dict):
        self.spot_feed = spot_feed
        self.momentum = momentum_analyzer
        self.volatility = volatility_analyzer
        self.orderbook = orderbook_analyzer
        self.basis = basis_monitor
        self.config = config
        self.strat = config['strategy']
        self.traded_tickers = set()

        # RTI smoothing
        self.rti_history = {}
        self.samples_needed = 12

        # Negative edge tracking (calibration)
        calibration_enabled = config.get('calibration', {}).get('enabled', True)
        if calibration_enabled:
            self.neg_edge_tracker = NegativeEdgeTracker()
            logger.info("✅ Negative edge tracking enabled for calibration")
        else:
            self.neg_edge_tracker = None

        logger.info("✅ Advanced multi-factor edge detector initialized")

    def reset_locks(self):
        self.traded_tickers.clear()
        logger.info("♻️ Ticker locks reset")

    def _get_smoothed_rti(self, symbol, current_rti):
        """60-second smoothing"""
        if symbol not in self.rti_history:
            self.rti_history[symbol] = deque(maxlen=self.samples_needed)
        self.rti_history[symbol].append(current_rti)
        return sum(self.rti_history[symbol]) / len(self.rti_history[symbol])

    def analyze_market(self, market: Dict) -> Optional[Dict]:
        """
        Multi-factor edge analysis with true information advantages

        Signal Stack (in order of application):
        1. Base momentum signal (legacy)
        2. Volatility regime adjustment (±20%)
        3. Microstructure signal (orderbook analysis) (±20%)
        4. Statistical arbitrage (basis/lag detection) (±25%)
        5. Time value decay (±10%)

        Total possible adjustment: ±75% on top of base probability
        """
        symbol, ticker = market['symbol'], market['ticker']

        # Ticker lock
        if self.strat.get('ticker_lock_enabled', True) and ticker in self.traded_tickers:
            logger.debug(f"⏭️ {ticker} skip: Ticker Locked")
            return None

        # Get spot price (smoothed)
        raw_rti = self.spot_feed._get_price(symbol)
        if not raw_rti:
            logger.info(f"⏭️ {ticker} skip: No Spot Price for {symbol}")
            return None

        smoothed_price = self._get_smoothed_rti(symbol, raw_rti)

        # Update analyzers
        self.momentum.update_price_history(symbol, price=smoothed_price)
        self.volatility.update_price(symbol, smoothed_price)

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

        # === PHASE 1: Base Expected Probability (Momentum-Based) ===
        base_prob = self._get_expected_prob(market, momentum, smoothed_price)
        if not base_prob:
            logger.info(f"⏭️ {ticker} skip: Prob Model Failed")
            return None

        logger.debug(f"📊 {ticker} | Base Prob: {base_prob:.2%}")

        # === PHASE 2: Volatility Regime Adjustment ===
        vol_signal = self.volatility.get_volatility_signal(
            symbol, base_prob, market.get('threshold') or smoothed_price,
            smoothed_price, market.get('minutes_to_close') or 5
        )

        vol_adjustment = 0.0
        if vol_signal:
            # Volatility signal adjusts probability
            if vol_signal['signal'] == 'fade':
                # Market underpricing vol → reduce directional probability
                vol_adjustment = -vol_signal['strength']
            elif vol_signal['signal'] == 'ride':
                # Market overpricing vol → increase directional probability
                vol_adjustment = vol_signal['strength']

            logger.debug(f"💨 {ticker} | Vol Signal: {vol_signal['signal']} "
                        f"({vol_signal['vol_ratio']:.2f}x) → {vol_adjustment:+.1%}")

        # === PHASE 3: Microstructure / Order Flow ===
        orderbook_data = {
            'yes_bid': market.get('yes_bid', 0),
            'yes_ask': market.get('yes_ask', 0.50),
            'no_bid': market.get('no_bid', 0),
            'no_ask': market.get('no_ask', 0.50),
            'yes_bid_size': market.get('yes_bid_size', 0),
            'yes_ask_size': market.get('yes_ask_size', 0),
            'no_bid_size': market.get('no_bid_size', 0),
            'no_ask_size': market.get('no_ask_size', 0)
        }

        # Try yes side first
        micro_yes = self.orderbook.get_microstructure_signal(ticker, orderbook_data, side='yes')
        micro_no = self.orderbook.get_microstructure_signal(ticker, orderbook_data, side='no')

        logger.debug(f"📈 {ticker} | Microstructure → YES: {micro_yes['adjustment']:+.1%}, "
                    f"NO: {micro_no['adjustment']:+.1%}")

        # === PHASE 4: Statistical Arbitrage (Basis/Lag) ===
        stat_arb = self.basis.get_stat_arb_signal(
            ticker, symbol, market, orderbook_data, smoothed_price
        )

        logger.debug(f"⚡ {ticker} | Stat Arb → {stat_arb['adjustment']:+.1%}")

        # === PHASE 5: Time Value Decay ===
        time_adjustment = self._calculate_time_value_adjustment(
            market.get('minutes_to_close') or 5, market.get('market_type', '')
        )

        logger.debug(f"⏱️ {ticker} | Time Value → {time_adjustment:+.1%}")

        # === COMBINE ALL FACTORS ===
        # Apply adjustments to base probability

        # YES side calculation
        adjusted_prob_yes = base_prob + vol_adjustment + micro_yes['adjustment'] + \
                           stat_arb['adjustment'] + time_adjustment
        adjusted_prob_yes = max(0.05, min(0.95, adjusted_prob_yes))  # Cap 5-95%

        # NO side calculation
        adjusted_prob_no = (1 - base_prob) + vol_adjustment + micro_no['adjustment'] + \
                          stat_arb['adjustment'] + time_adjustment
        adjusted_prob_no = max(0.05, min(0.95, adjusted_prob_no))

        # Calculate edges (after fees)
        exchange_fee = 0.015 * 100  # 1.5%
        buffer = (self.strat.get('slippage_buffer', 0.02) * 100) + exchange_fee

        edge_yes = ((adjusted_prob_yes - market['yes_ask']) * 100) - buffer
        edge_no = ((adjusted_prob_no - market['no_ask']) * 100) - buffer

        logger.debug(f"🎯 {ticker} | Edge → YES: {edge_yes:.1f}%, NO: {edge_no:.1f}%")

        # Select best side
        min_edge = self.strat.get('min_edge_percent', 10.0)
        if edge_yes > edge_no and edge_yes >= min_edge:
            side, edge, entry = 'yes', edge_yes, market['yes_ask']
            depth = market.get('yes_ask_size', 0)
            final_prob = adjusted_prob_yes
        elif edge_no >= min_edge:
            side, edge, entry = 'no', edge_no, market['no_ask']
            depth = market.get('no_ask_size', 0)
            final_prob = adjusted_prob_no
        else:
            logger.info(f"⏭️ {ticker} skip: Low Edge (YES: {edge_yes:.1f}%, NO: {edge_no:.1f}%)")
            return None

        # === FILTERS ===
        # Spread filter
        if self.strat.get('max_spread_filter_enabled', False):
            max_spread = self.strat.get('max_bid_ask_spread', 0.10)
            current_spread = (market['yes_ask'] - market['yes_bid']) if side == 'yes' else \
                           (market['no_ask'] - market['no_bid'])
            if current_spread > max_spread:
                logger.info(f"⏭️ {ticker} skip: High Spread (${current_spread:.2f})")
                return None

        # Trend protection
        if self.strat.get('trend_protection_enabled', False):
            trend_val = momentum.get('trend_strength', 0)
            trend_dir = momentum.get('direction', 'flat')
            if side == 'no':
                max_trend = self.strat.get('max_trend_for_no', 0.70)
                if market['market_type'] == 'above' and trend_dir == 'up' and trend_val > max_trend:
                    logger.info(f"⏭️ {ticker} skip: Trend Veto")
                    return None
                if market['market_type'] == 'below' and trend_dir == 'down' and trend_val > max_trend:
                    logger.info(f"⏭️ {ticker} skip: Trend Veto")
                    return None

        # Price floor
        if self.strat.get('price_floor_enabled', True) and \
           entry < self.strat.get('min_entry_price', 0.10):
            logger.info(f"⏭️ {ticker} skip: Price Floor")
            return None

        # Win probability threshold
        if final_prob < self.strat.get('min_expected_probability', 0.60):
            logger.info(f"⏭️ {ticker} skip: Low Win Prob ({final_prob:.1%})")
            return None

        # Signal strength
        signal_strength = self._calculate_signal_strength(
            edge, momentum, final_prob, vol_signal, stat_arb
        )
        if signal_strength < self.strat.get('min_signal_strength', 0):
            logger.info(f"⏭️ {ticker} skip: Low Signal ({signal_strength:.1f})")
            return None

        # Liquidity gate
        if self.strat.get('liquidity_gate_enabled', False):
            min_depth = self.strat.get('min_order_book_depth', 5)
            if depth < min_depth:
                logger.info(f"⏭️ {ticker} skip: Insufficient Depth")
                return None

        # Expected ROI
        expected_roi = ((final_prob - entry) / entry) * 100 if entry > 0 else 0

        return {
            **market,
            'minutes_to_close': market.get('minutes_to_close', 0),
            'base_probability': base_prob,
            'expected_probability': final_prob,
            'edge_percent': edge,
            'recommended_side': side,
            'entry_price': entry,
            'expected_win_prob': final_prob,
            'expected_roi': expected_roi,
            'depth': depth,
            'signal_strength': signal_strength,
            'momentum': momentum,
            'market_probability': entry,
            # Enhanced signal breakdown
            'signal_breakdown': {
                'vol_adjustment': vol_adjustment,
                'micro_adjustment': micro_yes['adjustment'] if side == 'yes' else micro_no['adjustment'],
                'stat_arb_adjustment': stat_arb['adjustment'],
                'time_adjustment': time_adjustment,
                'vol_signal': vol_signal,
                'micro_signal': micro_yes if side == 'yes' else micro_no,
                'stat_arb_signal': stat_arb
            }
        }

    def _get_expected_prob(self, market, momentum, smoothed_price):
        """Base probability from momentum model"""
        return self.momentum.calculate_expected_probability(
            market['symbol'], market['market_type'],
            market.get('threshold'), 15, current_price=smoothed_price
        )

    def _calculate_time_value_adjustment(self, minutes_to_close: float,
                                        market_type: str) -> float:
        """
        Time value decay adjustment

        For very short-dated options, time decay accelerates
        Markets with <2 minutes have minimal time for price discovery
        """
        # Handle None case
        if minutes_to_close is None:
            minutes_to_close = 5  # Default to 5 minutes

        if minutes_to_close < 2:
            # Very little time left → reduce directional probability
            return -0.10
        elif minutes_to_close > 10:
            # Too far out for 15-minute market
            return -0.05
        else:
            # Sweet spot: 2-10 minutes
            return 0.0

    def _calculate_signal_strength(self, edge: float, momentum: Dict,
                                   expected_prob: float, vol_signal: Optional[Dict],
                                   stat_arb: Dict) -> float:
        """
        Enhanced signal strength calculation

        Components (0-100 scale):
        - Edge score: 0-30 points (30% weight)
        - Probability score: 0-20 points (20% weight)
        - Momentum alignment: 0-15 points (15% weight)
        - Volatility confidence: 0-15 points (15% weight)
        - Stat arb strength: 0-20 points (20% weight)
        - Trend penalty: -25 points max
        """
        # Edge component (0-30)
        edge_score = (min(edge, 20) / 20) * 30

        # Probability confidence (0-20)
        prob_score = max(0, (expected_prob - 0.5) * 2) * 20

        # Momentum alignment (0-15)
        mom_pct = abs(momentum.get('percent_change', 0))
        if 0.5 <= mom_pct <= 2.0:
            mom_score = 15  # Sweet spot
        elif mom_pct > 2.0:
            mom_score = 10  # Too much momentum
        else:
            mom_score = 5  # Weak momentum

        # Volatility confidence (0-15)
        vol_score = 0
        if vol_signal:
            if vol_signal['signal'] != 'neutral':
                # Strong vol signal adds confidence
                vol_score = min(abs(vol_signal['strength']) * 100, 15)

        # Stat arb strength (0-20)
        stat_arb_score = min(abs(stat_arb['adjustment']) * 80, 20)

        # Trend penalty (max -25)
        trend_val = abs(momentum.get('trend_strength', 0))
        if trend_val > 0.65:
            trend_penalty = ((trend_val - 0.65) / 0.35) ** 2 * 25
        else:
            trend_penalty = 0

        total = edge_score + prob_score + mom_score + vol_score + \
                stat_arb_score - trend_penalty

        return max(0, min(100, round(total, 1)))

    def scan_for_edges(self, markets: List[Dict]) -> List[Dict]:
        """Scan all markets for edges using multi-factor analysis"""
        opportunities = []
        skipped_count = 0

        for market in markets:
            opp = self.analyze_market(market)
            if opp:
                opportunities.append(opp)
            else:
                # Track skipped market for calibration (if enabled)
                skipped_count += 1
                # Note: Detailed skip tracking happens in analyze_market's log statements
                # We could enhance this later to capture full edge data for skipped trades

        if skipped_count > 0:
            logger.debug(f"Skipped {skipped_count} markets below threshold (tracking for calibration)")

        # Sort by edge strength
        return sorted(opportunities, key=lambda x: x['edge_percent'], reverse=True)
