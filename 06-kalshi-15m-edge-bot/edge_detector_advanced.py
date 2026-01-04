"""
Advanced Multi-Factor Edge Detector
Integrates momentum, volatility, microstructure, and statistical arbitrage signals
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from collections import deque
from negative_edge_tracker import NegativeEdgeTracker

logger = logging.getLogger(__name__)


class AdvancedEdgeDetector:
    """Multi-factor edge detection with true information advantages"""

    def __init__(self, spot_feed, momentum_analyzer, volatility_analyzer,
                 orderbook_analyzer, basis_monitor, config: Dict, order_book_feed=None,
                 volume_tracker=None):
        self.spot_feed = spot_feed
        self.momentum = momentum_analyzer
        self.volatility = volatility_analyzer
        self.orderbook = orderbook_analyzer
        self.basis = basis_monitor
        self.order_book_feed = order_book_feed  # CEX order book feed for imbalance filtering
        self.volume_tracker = volume_tracker  # V3 Elite: Volume divergence tracker
        self.config = config
        self.strat = config['strategy']
        self.traded_tickers = set()

        # Time-based lock protection (prevents API lag race conditions)
        self.api_lag_protection_enabled = config['strategy'].get('api_lag_protection_enabled', True)
        self.ticker_trade_timestamps = {}  # ticker: timestamp
        self.min_lock_duration = config['strategy'].get('min_ticker_lock_seconds', 30)

        # CONSERVATIVE FIX: Lock ALL trade attempts (prevent duplicates from API lag)
        # Locks expire after min_ticker_lock_seconds (user-configurable)
        self.preventive_lock_timestamps = {}  # ticker: timestamp (when preventively locked)

        # RTI smoothing
        self.rti_history = {}
        self.samples_needed = 12

        # Momentum persistence tracking (consecutive scans above threshold per symbol)
        self._momentum_streak: Dict[str, int] = {}    # symbol → consecutive scans above threshold
        self._momentum_streak_ts: Dict[str, float] = {}  # symbol → last update timestamp

        # Momentum acceleration tracking (slope over last 3 readings, sampled every 30s)
        # Detects fading moves: momentum above threshold but declining over last ~90s
        self._momentum_history: Dict[str, deque] = {}  # symbol → deque of (timestamp, momentum_pct)

        # Kalshi internal price direction tracking (YES ask per ticker, sampled every 10s)
        self._kalshi_price_history: Dict[str, deque] = {}  # ticker → deque of (timestamp, yes_ask)

        # Spike cluster tracking: recent spike events per symbol for cluster confirmation
        self._spike_history: Dict[str, list] = {}  # symbol → [(timestamp, direction), ...]

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
        self.preventive_lock_timestamps.clear()
        self.ticker_trade_timestamps.clear()
        logger.info("♻️ Ticker locks reset (including preventive locks)")

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

        # Ticker lock - Check preventive locks first (highest priority)
        if self.strat.get('ticker_lock_enabled', True):
            if ticker in self.preventive_lock_timestamps:
                logger.debug(f"⏭️ {ticker} skip: Preventively Locked (Trade Attempted)")
                return None
            if ticker in self.traded_tickers:
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

        # === EARLY ENTRY SPIKE FILTER ===
        # Runs before the trend filter so it can set the trade direction from the spike.
        # Two modes (spike_determines_direction):
        #   true  — any spike ≥ threshold passes; spike direction overrides momentum direction
        #           and bypasses the trend filter (allows both UP and DOWN entries)
        #   false — spike must match the existing momentum direction (original gating behaviour)
        # Disabled entirely when early_entry_spike_filter_enabled: false.
        _spike_overrides_direction = False
        if self.strat.get('early_entry_spike_filter_enabled', False):
            _early_max_mtc = self.strat.get('early_entry_max_minutes_to_close', 10)
            _early_min_mtc = self.strat.get('early_entry_min_minutes_to_close', None)
            _minutes_to_close = market.get('minutes_to_close', 0)
            _in_early_window = (
                _minutes_to_close > _early_max_mtc
                and (_early_min_mtc is None or _minutes_to_close <= _early_min_mtc)
            )
            if _in_early_window:
                _spike_pct   = self.strat.get('early_entry_min_spike_pct', 0.25)
                _window_secs = self.strat.get('early_entry_window_seconds', 30)
                _spike_dir_mode = self.strat.get('spike_determines_direction', False)
                _trade_dir   = momentum.get('direction', 'flat')
                _spike_seen  = False
                _move_pct    = None

                history = self.momentum.price_history.get(symbol, [])
                if len(history) >= 2:
                    from datetime import datetime, timezone
                    _now    = datetime.now(timezone.utc)
                    _cutoff = _now.timestamp() - _window_secs
                    _window = [(ts, p) for ts, p in history if ts.timestamp() >= _cutoff]
                    if len(_window) >= 2:
                        _oldest_p = _window[0][1]
                        _newest_p = _window[-1][1]
                        _move_pct = (_newest_p - _oldest_p) / _oldest_p * 100
                        if _spike_dir_mode:
                            # Any direction — spike magnitude alone determines pass/fail
                            if abs(_move_pct) >= _spike_pct:
                                _spike_dir = 'down' if _move_pct < 0 else 'up'
                                momentum = {**momentum, 'direction': _spike_dir}
                                _spike_overrides_direction = True
                                _spike_seen = True
                        else:
                            # Must match existing momentum direction
                            if _trade_dir == 'down' and _move_pct <= -_spike_pct:
                                _spike_seen = True
                            elif _trade_dir == 'up' and _move_pct >= _spike_pct:
                                _spike_seen = True
                            elif _trade_dir not in ('up', 'down'):
                                # Flat/unknown momentum — let spike set direction
                                if abs(_move_pct) >= _spike_pct:
                                    _spike_dir = 'down' if _move_pct < 0 else 'up'
                                    momentum = {**momentum, 'direction': _spike_dir}
                                    _spike_overrides_direction = True
                                    _spike_seen = True

                # === SPIKE CLUSTER CHECK ===
                # Require at least spike_min_cluster_count spike events in the same direction
                # within spike_cluster_window_secs before trading. Filters isolated noise spikes
                # vs sustained directional moves (which re-trigger repeatedly).
                # spike_min_cluster_count: 1 = disabled (any single spike passes)
                _min_cluster = self.strat.get('spike_min_cluster_count', 1)
                _cluster_win = self.strat.get('spike_cluster_window_secs', 15)
                _spike_dir_str = 'down' if (_move_pct is not None and _move_pct < 0) else 'up'

                # Record this spike in history (before cluster check)
                if _spike_seen:
                    _hist = self._spike_history.setdefault(symbol, [])
                    _hist.append((_now.timestamp(), _spike_dir_str))
                    # Trim to cluster window + buffer
                    _trim_cutoff = _now.timestamp() - _cluster_win - 5
                    self._spike_history[symbol] = [
                        (t, d) for t, d in _hist if t >= _trim_cutoff
                    ]

                if _spike_seen and _min_cluster > 1:
                    _cluster_cutoff = _now.timestamp() - _cluster_win
                    _recent = [
                        (t, d) for t, d in self._spike_history.get(symbol, [])
                        if t >= _cluster_cutoff and d == _spike_dir_str
                    ]
                    _cluster_count = len(_recent)
                    if _cluster_count < _min_cluster:
                        _spike_seen = False
                        logger.info(
                            f"⏭️ {ticker} skip: Spike cluster too weak "
                            f"({_cluster_count}/{_min_cluster} {_spike_dir_str} spikes "
                            f"in {_cluster_win}s)"
                        )
                    else:
                        logger.debug(
                            f"✅ {ticker} spike cluster confirmed: {_cluster_count} "
                            f"{_spike_dir_str} spikes in {_cluster_win}s"
                        )

                if not _spike_seen:
                    _actual = f"{_move_pct:+.3f}" if _move_pct is not None else "n/a"
                    if _spike_dir_mode:
                        _needed = f"±{_spike_pct:.3f}"
                    else:
                        _needed = f"-{_spike_pct:.3f}" if _trade_dir == 'down' else f"+{_spike_pct:.3f}"
                    logger.info(f"⏭️ {ticker} skip: No early-candle spike ({_actual}% vs {_needed}% needed in {_window_secs}s)")
                    return None
                else:
                    _actual = f"{_move_pct:+.3f}" if _move_pct is not None else "n/a"
                    _spike_trade_side = 'NO (DOWN)' if momentum.get('direction') == 'down' else 'YES (UP)'
                    logger.info(f"⚡ {ticker} spike PASSED: {_actual}% in {_window_secs}s (threshold ±{_spike_pct:.3f}%) → {_spike_trade_side}")

        # Trend filter (with per-symbol override support)
        # Bypassed when spike_determines_direction is active — spike already set the side.
        if self.strat.get('trend_filter_enabled', False) and not _spike_overrides_direction:
            # Check for symbol-specific allowed_trends, otherwise use global
            symbol_configs = self.strat.get('symbol_configs', {})
            symbol_config = symbol_configs.get(symbol, {})
            allowed_trends = symbol_config.get('allowed_trends',
                                               self.strat.get('allowed_trends', ['up', 'down', 'flat']))
            current_trend = momentum['direction']
            if current_trend not in allowed_trends:
                logger.info(f"⏭️ {ticker} skip: {symbol} trend '{current_trend}' not in allowed {allowed_trends}")
                return None

        # R² Confidence Filter — moved to after HTF block (regime-adaptive).
        # See "=== R² CONFIDENCE FILTER (HTF-aware) ===" section below.

        # Momentum Strength Filter (skip weak momentum markets)
        # Early-candle bypass: spike filter already confirmed a sharp directional move;
        # the regression-based momentum + streak check lags the spike and would block it.
        _momentum_early_bypass = (
            self.strat.get('early_entry_spike_filter_enabled', False)
            and _in_early_window
        )
        min_momentum = self.strat.get('min_momentum_pct')
        max_momentum = self.strat.get('max_momentum_pct', None)
        if (min_momentum or max_momentum) and not _momentum_early_bypass:
            current_momentum = abs(momentum.get('percent_change', 0))

            # Momentum persistence: update streak counter once per scan cycle per symbol.
            # Deduplicates across multiple markets for the same symbol in one cycle (e.g. BTC 1600, BTC 1615).
            min_consecutive = self.strat.get('min_momentum_consecutive', 1)
            if min_consecutive > 1:
                now_ts = time.time()
                last_ts = self._momentum_streak_ts.get(symbol, 0)
                if now_ts - last_ts > 0.5:  # New scan cycle
                    if current_momentum >= min_momentum:
                        self._momentum_streak[symbol] = self._momentum_streak.get(symbol, 0) + 1
                    else:
                        self._momentum_streak[symbol] = 0
                    self._momentum_streak_ts[symbol] = now_ts

            if min_momentum and current_momentum < min_momentum:
                _mom_dir = momentum.get('direction', '?')
                _r2 = momentum.get('r_squared', 0)
                _trend_pct = momentum.get('percent_change', 0)
                logger.info(f"⏭️ {ticker} skip: Low Momentum ({current_momentum:.3f} < {min_momentum:.3f}) dir={_mom_dir} R²={_r2:.2f} trend={_trend_pct:.2f}% - weak trend")
                return None

            if max_momentum and current_momentum > max_momentum:
                logger.info(f"⏭️ {ticker} skip: High Momentum ({current_momentum:.3f} > {max_momentum:.3f}) - already priced in")
                return None

            # === MOMENTUM ACCELERATION GATE ===
            # Samples momentum every 30s, keeps last 3 readings (~90s of history).
            # Computes slope (last - first). If slope < min_momentum_slope, the move is
            # fading and we skip — even though current value still passes the threshold.
            min_slope = self.strat.get('min_momentum_slope')
            if min_slope is not None and not _momentum_early_bypass:
                now_ts = time.time()
                hist = self._momentum_history.setdefault(symbol, deque(maxlen=3))
                if not hist or now_ts - hist[-1][0] >= 30.0:
                    hist.append((now_ts, current_momentum))
                if len(hist) >= 3:
                    slope = hist[-1][1] - hist[0][1]  # last - first over ~60-90s
                    if slope < min_slope:
                        logger.info(
                            f"⏭️ {ticker} skip: Momentum decelerating "
                            f"(slope={slope:+.4f} < {min_slope:+.4f} over {len(hist)} readings)"
                        )
                        if self.neg_edge_tracker:
                            self.neg_edge_tracker.log_skipped_trade(market, "Momentum Decelerating", {
                                'yes_edge_pct': 0, 'no_edge_pct': 0,
                                'yes_expected_prob': 0, 'no_expected_prob': 0,
                                'yes_price': market.get('yes_ask', 0),
                                'no_price': market.get('no_ask', 0),
                                'spot_price': 0, 'signal_strength': 0,
                                'momentum_direction': momentum.get('direction', 'unknown'),
                                'momentum_pct': momentum.get('percent_change', 0),
                                'trend_strength': momentum.get('trend_strength', 0),
                                'r_squared': 0,
                                'orderbook': {},
                            })
                        return None

            # Persistence gate: require momentum above threshold for N consecutive scans
            if min_consecutive > 1:
                streak = self._momentum_streak.get(symbol, 0)
                if streak < min_consecutive:
                    logger.info(f"⏭️ {ticker} skip: Momentum not sustained "
                                f"({streak}/{min_consecutive} consecutive scans)")
                    if self.neg_edge_tracker:
                        self.neg_edge_tracker.log_skipped_trade(market, "Momentum Not Sustained", {
                            'yes_edge_pct': 0, 'no_edge_pct': 0,
                            'yes_expected_prob': 0, 'no_expected_prob': 0,
                            'yes_price': market.get('yes_ask', 0),
                            'no_price': market.get('no_ask', 0),
                            'spot_price': 0, 'signal_strength': 0,
                            'momentum_direction': momentum.get('direction', 'unknown'),
                            'momentum_pct': momentum.get('percent_change', 0),
                            'trend_strength': momentum.get('trend_strength', 0),
                            'r_squared': 0,
                            'orderbook': {},
                        })
                    return None

        # Trend Strength Filter (combines R² quality + momentum direction)
        # Calibration-proven: >0.3 trend_strength = 43% win rate vs <0.3 = 36% win rate
        min_trend_strength = self.strat.get('min_trend_strength')
        if min_trend_strength:
            current_trend_strength = momentum.get('trend_strength', 0)
            if current_trend_strength < min_trend_strength:
                logger.info(f"⏭️ {ticker} skip: Low Trend Strength ({current_trend_strength:.2f} < {min_trend_strength:.2f}) - weak signal")
                return None

        # === KALSHI INTERNAL PRICE DIRECTION FILTER ===
        # Tracks YES ask price per ticker over time (sampled every ~10s).
        # If Kalshi market participants are pricing against your trade direction,
        # it's a red flag even when CEX momentum is strong.
        # YES rising = market expects YES → block NO trades
        # YES falling = market expects NO → block YES trades
        # Always build price history for data collection (even when filter is disabled/observe mode)
        _kpd_mode = self.strat.get('kalshi_price_direction_filter_enabled', False)  # False=off, 'observe'=log only, True=enforce
        _lookback = self.strat.get('kalshi_price_lookback_seconds', 30)
        _min_move = self.strat.get('kalshi_price_min_change', 0.005)
        yes_ask_now = market.get('yes_ask', 0)
        if _kpd_mode and yes_ask_now:
            now_ts = time.time()
            _phist = self._kalshi_price_history.setdefault(ticker, deque(maxlen=20))
            # Sample every ~10s to avoid noise from rapid micro-fluctuations
            if not _phist or now_ts - _phist[-1][0] >= 10.0:
                _phist.append((now_ts, yes_ask_now))
            # Find oldest reading within lookback window
            _cutoff = now_ts - _lookback
            _window = [(t, p) for t, p in _phist if t >= _cutoff]
            if len(_window) >= 2:
                _yes_change = _window[-1][1] - _window[0][1]  # positive = YES rising
                _trade_dir = momentum.get('direction', 'flat')
                _opposes = False
                if _trade_dir == 'down' and _yes_change > _min_move:
                    _opposes = True
                    logger.info(f"⏭️ {ticker} {'skip' if _kpd_mode is True else 'observe'}: Kalshi price opposes direction "
                                f"(YES +{_yes_change:.4f} over {_lookback}s, betting NO)")
                elif _trade_dir == 'up' and _yes_change < -_min_move:
                    _opposes = True
                    logger.info(f"⏭️ {ticker} {'skip' if _kpd_mode is True else 'observe'}: Kalshi price opposes direction "
                                f"(YES {_yes_change:.4f} over {_lookback}s, betting YES)")
                if _opposes:
                    if self.neg_edge_tracker:
                        self.neg_edge_tracker.log_skipped_trade(market, "Kalshi Price Opposes Direction", {
                            'yes_edge_pct': 0, 'no_edge_pct': 0,
                            'yes_expected_prob': 0, 'no_expected_prob': 0,
                            'yes_price': yes_ask_now, 'no_price': market.get('no_ask', 0),
                            'spot_price': smoothed_price, 'signal_strength': 0,
                            'momentum_direction': _trade_dir,
                            'momentum_pct': momentum.get('percent_change', 0),
                            'trend_strength': momentum.get('trend_strength', 0),
                            'r_squared': 0, 'orderbook': {},
                        })
                    if _kpd_mode is True:  # Only block in enforce mode
                        return None

        # === MINIMUM DISTANCE TO THRESHOLD FILTER ===
        # Applies to all probability models. If price is already very close to threshold
        # the outcome is too uncertain regardless of what the model computes.
        _min_dist = self.strat.get('min_distance_pct')
        _threshold = market.get('threshold')
        if _min_dist and _threshold and smoothed_price:
            _distance_pct = ((_threshold - smoothed_price) / smoothed_price) * 100
            if abs(_distance_pct) < _min_dist:
                logger.info(f"⏭️ {ticker} skip: Too Close to Threshold "
                            f"({_distance_pct:+.3f}% — min ±{_min_dist:.2f}%)")
                return None

        # === ORDER BOOK IMBALANCE FILTER ===
        # Veto trades when CEX order books show weak/neutral directional pressure
        imbalance = None  # Will be captured below if order book feed is active
        if self.order_book_feed and self.strat.get('order_book_filter_enabled', False):
            # Check if order book data is fresh
            if not self.order_book_feed.is_data_fresh(symbol):
                logger.debug(f"⏭️ {ticker} skip: Stale Order Book Data")
                return None

            # Get current imbalance (with volume-weighted averaging)
            imbalance = self.order_book_feed.get_imbalance(symbol)
            if imbalance is None:
                logger.debug(f"⏭️ {ticker} skip: No Order Book Data")
                return None

            # Veto neutral imbalance (no clear directional pressure)
            # Use config values, not hardcoded 0.4-0.6
            min_imbalance = self.strat.get('order_book_min_imbalance', 0.40)
            max_imbalance = self.strat.get('order_book_max_imbalance', 0.60)

            if min_imbalance < imbalance < max_imbalance:
                logger.info(f"⏭️ {ticker} skip: Weak Order Book Imbalance ({imbalance:.2%} - neutral zone {min_imbalance:.0%}-{max_imbalance:.0%})")
                return None

            logger.debug(f"📊 {ticker} | OBI: {imbalance:.2%} ({'BULLISH' if imbalance > max_imbalance else 'BEARISH' if imbalance < min_imbalance else 'NEUTRAL'})")

            # === OBI TREND CHECK ===
            # off:       no trend check (snapshot only)
            # defensive: block if trend actively opposes trade direction, neutral passes
            # strict:    require trend to confirm trade direction, neutral blocked
            _trend_mode = self.strat.get('order_book_trend_mode', 'off')
            if _trend_mode in ('defensive', 'strict'):
                _trend_window    = self.strat.get('order_book_trend_window', 45)
                _trend_threshold = self.strat.get('order_book_trend_threshold', 0.03)
                _obi_trend = self.order_book_feed.get_imbalance_trend(
                    symbol, window_seconds=_trend_window, threshold=_trend_threshold
                )
                _trade_dir = momentum.get('direction', 'flat')  # up / down / flat

                if _obi_trend is None:
                    # Insufficient history — skip trend check, don't block
                    logger.debug(f"📊 {ticker} | OBI trend: insufficient history (window={_trend_window}s)")
                elif _trend_mode == 'defensive':
                    # Block only if trend actively opposes the trade direction
                    if _trade_dir == 'up' and _obi_trend == 'falling':
                        logger.info(f"⏭️ {ticker} skip: OBI trend opposes trade — UP bet but OBI falling (window={_trend_window}s)")
                        return None
                    elif _trade_dir == 'down' and _obi_trend == 'rising':
                        logger.info(f"⏭️ {ticker} skip: OBI trend opposes trade — DOWN bet but OBI rising (window={_trend_window}s)")
                        return None
                    else:
                        logger.debug(f"📊 {ticker} | OBI trend: {_obi_trend} (defensive OK for {_trade_dir})")
                elif _trend_mode == 'strict':
                    # Require trend to confirm trade direction
                    if _trade_dir == 'up' and _obi_trend != 'rising':
                        logger.info(f"⏭️ {ticker} skip: OBI trend not rising for UP bet ({_obi_trend}, window={_trend_window}s)")
                        return None
                    elif _trade_dir == 'down' and _obi_trend != 'falling':
                        logger.info(f"⏭️ {ticker} skip: OBI trend not falling for DOWN bet ({_obi_trend}, window={_trend_window}s)")
                        return None
                    else:
                        logger.debug(f"📊 {ticker} | OBI trend: {_obi_trend} (strict OK for {_trade_dir})")

        # === V3 ELITE FILTER 1: MULTI-TIMEFRAME ALIGNMENT (SHORT-TERM) ===
        # Early-candle bypass: when the spike filter is enabled and we are in the early
        # window (minutes_to_close > early_entry_max_minutes_to_close), the 5m timeframe
        # hasn't had time to reflect the spike yet — skip MTF to avoid false blocks.
        _mtf_early_bypass = (
            self.strat.get('mtf_early_entry_bypass', False)
            and self.strat.get('early_entry_spike_filter_enabled', False)
            and _in_early_window
        )
        if self.strat.get('mtf_short_term_filter_enabled', False) and not _mtf_early_bypass:
            short_term_timeframes_raw = self.strat.get('short_term_timeframes', [1, 5, 15])
            min_aligned = self.strat.get('min_aligned_timeframes', 2)

            # Parse timeframe strings (e.g., "1m", "5m") to integers
            short_term_timeframes = []
            for tf in short_term_timeframes_raw:
                if isinstance(tf, str):
                    # Extract number from "1m", "5m", "15m", etc.
                    short_term_timeframes.append(int(tf.rstrip('mMhH')))
                else:
                    short_term_timeframes.append(int(tf))

            mtf_data = self.momentum.get_multi_timeframe_alignment(symbol, short_term_timeframes)
            if not mtf_data:
                logger.debug(f"⏭️ {ticker} skip: MTF data unavailable")
                return None

            alignment = mtf_data['alignment']
            direction = momentum['direction']

            # Check if enough timeframes align with trade direction
            if direction == 'up':
                apply_mtf_up = self.strat.get('mtf_short_term_filter_enabled_up', True)
                if apply_mtf_up and alignment['bullish_count'] < min_aligned:
                    logger.info(f"⏭️ {ticker} skip: MTF Short-Term Misalignment "
                               f"(only {alignment['bullish_count']}/{alignment['total_timeframes']} bullish, need {min_aligned})")
                    return None
            elif direction == 'down':
                apply_mtf_down = self.strat.get('mtf_short_term_filter_enabled_down', True)
                if apply_mtf_down and alignment['bearish_count'] < min_aligned:
                    logger.info(f"⏭️ {ticker} skip: MTF Short-Term Misalignment "
                               f"(only {alignment['bearish_count']}/{alignment['total_timeframes']} bearish, need {min_aligned})")
                    return None

            logger.debug(f"✅ {ticker} | MTF Short-Term: {alignment['bullish_count']} bull, {alignment['bearish_count']} bear")

        # HTF state — populated inside the HTF block below, used by R² filter + scoring
        htf_direction = None
        htf_percent = 0.0
        htf_aligned = False

        # === V3 ELITE FILTER 2: MULTI-TIMEFRAME ALIGNMENT (HTF TIDE) ===
        # Early-candle bypass: when the spike filter is enabled and we are in the early
        # window (minutes_to_close > early_entry_max_minutes_to_close), the 1h HTF hasn't
        # had time to confirm the spike direction — skip HTF veto to avoid false blocks.
        _htf_early_bypass = (
            self.strat.get('htf_early_entry_bypass', False)
            and self.strat.get('early_entry_spike_filter_enabled', False)
            and _in_early_window
        )
        if self.strat.get('mtf_htf_filter_enabled', False) and not _htf_early_bypass:
            htf_timeframe_str = self.strat.get('htf_timeframe', '1h')
            htf_minutes = 60 if htf_timeframe_str == '1h' else 240  # 1h or 4h
            htf_threshold = self.strat.get('htf_min_trend_threshold', 0.01)  # 1%

            htf_momentum = self.momentum.calculate_momentum(symbol, htf_minutes)
            if not htf_momentum:
                logger.debug(f"⏭️ {ticker} skip: HTF momentum unavailable ({htf_timeframe_str})")
                # Don't block trade if HTF data unavailable (graceful degradation)
            else:
                htf_direction = htf_momentum['direction']
                htf_percent = abs(htf_momentum['percent_change'])

                # Only enforce alignment if HTF shows strong trend
                if htf_percent >= htf_threshold:
                    direction = momentum['direction']

                    # Veto trades against the HTF tide
                    if htf_direction == 'up' and direction == 'down':
                        logger.info(f"⏭️ {ticker} skip: Against HTF Tide "
                                   f"({htf_timeframe_str} +{htf_percent:.2%} bullish, trade is bearish)")
                        return None
                    elif htf_direction == 'down' and direction == 'up':
                        logger.info(f"⏭️ {ticker} skip: Against HTF Tide "
                                   f"({htf_timeframe_str} {htf_percent:.2%} bearish, trade is bullish)")
                        return None

                    logger.debug(f"✅ {ticker} | HTF Tide: {htf_timeframe_str} {htf_direction} {htf_percent:.2%}")
                    htf_aligned = True  # Trade is aligned with a strong HTF trend

        # === R² CONFIDENCE FILTER (HTF-aware — regime adaptive) ===
        # When r_squared_htf_aware=True: relax R² for HTF-aligned trades.
        # (Sharp trending moves in the HTF direction are non-linear → low R² but win.)
        # When False: falls back to legacy per-direction config flags.
        if self.strat.get('r_squared_filter_enabled', False):
            direction = momentum.get('direction', 'unknown')
            min_r_squared = self.strat.get('min_r_squared', 0.3)
            current_r_squared = momentum.get('r_squared', 0)
            if self.strat.get('r_squared_htf_aware', False):
                # HTF-aware: if aligned with a confirmed HTF trend, skip the gate
                apply_r2 = not htf_aligned
            else:
                # Legacy: per-direction override flags
                dir_key = f'r_squared_filter_enabled_{direction}'
                dir_override = self.strat.get(dir_key)  # None if not set
                apply_r2 = dir_override if dir_override is not None else True
            if apply_r2 and current_r_squared < min_r_squared:
                logger.info(f"⏭️ {ticker} skip: Low R² ({current_r_squared:.2f} < {min_r_squared:.2f}) - noisy trend")
                if self.neg_edge_tracker:
                    edge_data = {
                        'yes_edge_pct': 0,
                        'no_edge_pct': 0,
                        'yes_expected_prob': 0,
                        'no_expected_prob': 0,
                        'yes_price': market.get('yes_ask', 0),
                        'no_price': market.get('no_ask', 0),
                        'spot_price': smoothed_price,
                        'signal_strength': 0,
                        'momentum_direction': momentum.get('direction', 'unknown'),
                        'momentum_pct': momentum.get('percent_change', 0),
                        'trend_strength': momentum.get('trend_strength', 0),
                        'r_squared': current_r_squared,
                        'orderbook': {
                            'yes_depth': market.get('yes_ask_size', 0),
                            'no_depth': market.get('no_ask_size', 0),
                            'bid_ask_spread': market.get('yes_ask', 0) - market.get('yes_bid', 0)
                        },
                        'volatility': {}
                    }
                    self.neg_edge_tracker.log_skipped_trade(market, "Low R²", edge_data)
                return None

        # === V3 ELITE FILTER 3: VOLUME DIVERGENCE ===
        if self.volume_tracker and self.strat.get('volume_divergence_filter_enabled', False):
            # Sample current price/volume
            current_price = smoothed_price
            current_volume = self.spot_feed.get_volume(symbol)

            # Add sample to tracker (uses volatility if no volume)
            self.volume_tracker.add_sample(symbol, current_price, current_volume)

            # Detect divergence
            divergence = self.volume_tracker.detect_divergence(symbol, current_price, current_volume or 0)

            if divergence:
                direction = momentum['direction']

                # Bearish divergence = price up, volume down → veto YES trades
                if divergence == 'bearish' and direction == 'up':
                    logger.info(f"⏭️ {ticker} skip: Bearish Volume Divergence detected (price up, volume down - fake breakout)")
                    return None

                # Bullish divergence = price down, volume down → veto NO trades
                elif divergence == 'bullish' and direction == 'down':
                    logger.info(f"⏭️ {ticker} skip: Bullish Volume Divergence detected (price down, volume down - selling exhaustion)")
                    return None

                logger.debug(f"✅ {ticker} | Volume Divergence: {divergence} (but doesn't conflict with trade direction)")

        # === PHASE 1: Base Expected Probability (Momentum-Based) ===
        base_prob = self._get_expected_prob(market, momentum, smoothed_price)
        if not base_prob:
            logger.info(f"⏭️ {ticker} skip: Prob Model Failed")
            return None

        logger.debug(f"📊 {ticker} | Base Prob (bot model): {base_prob:.2%}")

        # === PHASE 1.5: Crowd Confidence Blending (NEW!) ===
        # Calibration showed: Market prices 68-84% accurate vs Bot 35-39%
        # Strategy: Blend market price with bot model based on liquidity
        crowd_config = self.config.get('calibration', {}).get('crowd_confidence', {})

        # Check if crowd blending should be disabled for this momentum direction
        momentum_direction = momentum.get('direction', 'unknown')
        disabled_directions = crowd_config.get('disabled_for_directions', [])
        crowd_blending_active = crowd_config.get('enabled', False) and momentum_direction not in disabled_directions

        if crowd_blending_active:
            # Extract orderbook data for crowd blending
            orderbook_data_temp = {
                'yes_bid': market.get('yes_bid', 0),
                'yes_ask': market.get('yes_ask', 0.50),
                'no_bid': market.get('no_bid', 0),
                'no_ask': market.get('no_ask', 0.50),
                'yes_bid_size': market.get('yes_bid_size', 0),
                'yes_ask_size': market.get('yes_ask_size', 0),
                'no_bid_size': market.get('no_bid_size', 0),
                'no_ask_size': market.get('no_ask_size', 0)
            }
            blended_prob = self._apply_crowd_confidence_blending(
                base_prob, market, orderbook_data_temp, crowd_config
            )
            if blended_prob != base_prob:
                logger.debug(f"👥 {ticker} | Crowd Blending: {base_prob:.2%} → {blended_prob:.2%} "
                           f"(market weight based on depth)")
            base_prob = blended_prob
        elif crowd_config.get('enabled', False) and momentum_direction in disabled_directions:
            logger.debug(f"🚫 {ticker} | Crowd Blending DISABLED for {momentum_direction.upper()} trends (using bot's raw probability: {base_prob:.2%})")

        logger.debug(f"📊 {ticker} | Final Base Prob: {base_prob:.2%}")

        # === MULTI-FACTOR ADJUSTMENTS STRIPPED (2026-04-10) ===
        # Data from 5m bot (584 trades) showed higher "edge" from adjustments = LOWER WR.
        # Phases 2-5 (vol, microstructure, stat arb, time decay) zeroed out.
        # Backup: edge_detector_advanced.py.bak_multifactor

        vol_signal = {}
        vol_adjustment = 0.0

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
        stat_arb = {'adjustment': 0.0}

        # === PROBABILITY: Base v4 model only, no adjustments ===
        adjusted_prob_yes = max(0.05, min(0.95, base_prob))
        adjusted_prob_no = 1.0 - adjusted_prob_yes

        # Calculate edges (after fees and slippage)
        exchange_fee = 0.015 * 100  # 1.5%
        slippage_dollars = self.strat.get('slippage_buffer', 0.02)

        edge_yes = ((adjusted_prob_yes - market['yes_ask'] - slippage_dollars) * 100) - exchange_fee
        edge_no = ((adjusted_prob_no - market['no_ask'] - slippage_dollars) * 100) - exchange_fee

        logger.debug(f"🎯 {ticker} | Edge → YES: {edge_yes:.1f}%, NO: {edge_no:.1f}%")

        # Select best side
        # Depth = counterparty liquidity: buying YES matches against NO bids; buying NO matches against YES bids.
        min_edge = self.strat.get('min_edge_percent', 10.0)
        max_edge = self.strat.get('max_edge_percent', None)  # null in config disables the cap
        if edge_yes > edge_no and edge_yes >= min_edge:
            side, edge, entry = 'yes', edge_yes, market['yes_ask']
            depth = market.get('yes_ask_size', 0)  # counterparties for YES buyers (= NO bid depth)
            final_prob = adjusted_prob_yes
        elif edge_no >= min_edge:
            side, edge, entry = 'no', edge_no, market['no_ask']
            depth = market.get('no_ask_size', 0)   # counterparties for NO buyers (= YES bid depth)
            final_prob = adjusted_prob_no
        else:
            logger.info(f"⏭️ {ticker} skip: Low Edge (YES: {edge_yes:.1f}%, NO: {edge_no:.1f}%)")

            # Log skipped trade for calibration
            if self.neg_edge_tracker:
                edge_data = {
                    'yes_edge_pct': edge_yes,
                    'no_edge_pct': edge_no,
                    'yes_expected_prob': adjusted_prob_yes,
                    'no_expected_prob': adjusted_prob_no,
                    'yes_price': market['yes_ask'],
                    'no_price': market['no_ask'],
                    'spot_price': smoothed_price,
                    'signal_strength': self._calculate_signal_strength(
                        max(edge_yes, edge_no), momentum,
                        adjusted_prob_yes if edge_yes > edge_no else adjusted_prob_no,
                        vol_signal, stat_arb, htf_aligned
                    ),
                    'momentum_direction': momentum.get('direction', 'unknown'),
                    'momentum_pct': momentum.get('percent_change', 0),
                    'trend_strength': momentum.get('trend_strength', 0),
                    'orderbook': {
                        'yes_depth': market.get('yes_ask_size', 0),
                        'no_depth': market.get('no_ask_size', 0),
                        'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                    },
                    'volatility': vol_signal if vol_signal else {},
                    'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                    'stat_arb_adjustment': stat_arb['adjustment'],
                }
                self.neg_edge_tracker.log_skipped_trade(market, "Low Edge", edge_data)

            return None

        # === MAX EDGE FILTER ===
        if max_edge is not None and edge > max_edge:
            logger.info(f"⏭️ {ticker} skip: High Edge {edge:.1f}% > cap {max_edge}% (high edge bucket had poor WR)")
            if self.neg_edge_tracker:
                edge_data = {
                    'yes_edge_pct': edge_yes,
                    'no_edge_pct': edge_no,
                    'yes_expected_prob': adjusted_prob_yes,
                    'no_expected_prob': adjusted_prob_no,
                    'yes_price': market['yes_ask'],
                    'no_price': market['no_ask'],
                    'spot_price': smoothed_price,
                    'signal_strength': self._calculate_signal_strength(
                        edge, momentum, final_prob, vol_signal, stat_arb, htf_aligned
                    ),
                    'momentum_direction': momentum.get('direction', 'unknown'),
                    'momentum_pct': momentum.get('percent_change', 0),
                    'trend_strength': momentum.get('trend_strength', 0),
                    'orderbook': {
                        'yes_depth': market.get('yes_ask_size', 0),
                        'no_depth': market.get('no_ask_size', 0),
                        'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                    },
                    'volatility': vol_signal if vol_signal else {},
                    'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                    'stat_arb_adjustment': stat_arb['adjustment'],
                }
                self.neg_edge_tracker.log_skipped_trade(market, "High Edge", edge_data)
            return None

        # === OBI DIRECTION ALIGNMENT (evaluated after bet side is known) ===
        # YES bets need bullish OBI, NO bets need bearish OBI.
        if imbalance is not None and self.strat.get('order_book_filter_enabled', False):
            if self.strat.get('order_book_direction_alignment', True):
                _obi_min = self.strat.get('order_book_min_imbalance', 0.40)
                _obi_max = self.strat.get('order_book_max_imbalance', 0.60)
                if side == 'yes' and imbalance < _obi_min:
                    logger.info(f"⏭️ {ticker} skip: OBI Direction Conflict — YES bet but OBI bearish ({imbalance:.2%} < {_obi_min:.0%})")
                    return None
                elif side == 'no' and imbalance > _obi_max:
                    logger.info(f"⏭️ {ticker} skip: OBI Direction Conflict — NO bet but OBI bullish ({imbalance:.2%} > {_obi_max:.0%})")
                    return None

        # === CONTRARIAN BETTING FILTER ===
        faded_original_edge = None  # Set if a contrarian bet is flipped (faded)
        # Check if bet goes against momentum direction (contrarian bet)
        if self.strat.get('disable_contrarian_bets', False):
            market_type = market.get('market_type', '')
            momentum_direction = momentum.get('direction', 'unknown')

            # For 'up' markets: YES=UP, NO=DOWN
            # For 'down' markets: YES=DOWN, NO=UP
            # For 'above' markets: YES=ABOVE, NO=BELOW
            # For 'below' markets: YES=BELOW, NO=ABOVE

            is_contrarian = False

            if market_type == 'up':
                # Betting YES when momentum is DOWN = contrarian
                # Betting NO when momentum is UP = contrarian
                if (side == 'yes' and momentum_direction == 'down') or \
                   (side == 'no' and momentum_direction == 'up'):
                    is_contrarian = True

            elif market_type == 'down':
                # Betting YES when momentum is UP = contrarian
                # Betting NO when momentum is DOWN = contrarian
                if (side == 'yes' and momentum_direction == 'up') or \
                   (side == 'no' and momentum_direction == 'down'):
                    is_contrarian = True

            elif market_type == 'above':
                # Betting YES when momentum is DOWN = contrarian
                # Betting NO when momentum is UP = contrarian
                if (side == 'yes' and momentum_direction == 'down') or \
                   (side == 'no' and momentum_direction == 'up'):
                    is_contrarian = True

            elif market_type == 'below':
                # Betting YES when momentum is UP = contrarian
                # Betting NO when momentum is DOWN = contrarian
                if (side == 'yes' and momentum_direction == 'up') or \
                   (side == 'no' and momentum_direction == 'down'):
                    is_contrarian = True

            if is_contrarian:
                # Check if we should FADE the contrarian bet (take opposite side)
                fade_contrarian = self.strat.get('fade_contrarian_bets', False)

                if fade_contrarian:
                    # FADE: Take the OPPOSITE side of the contrarian bet
                    original_side = side
                    original_edge = edge
                    original_prob = final_prob

                    # Flip to opposite side
                    if side == 'yes':
                        side = 'no'
                        edge = edge_no
                        entry = market['no_ask']
                        depth = market.get('no_ask_size', 0)   # counterparties for NO buyers (= YES bid depth)
                        final_prob = adjusted_prob_no
                    else:  # side == 'no'
                        side = 'yes'
                        edge = edge_yes
                        entry = market['yes_ask']
                        depth = market.get('yes_ask_size', 0)  # counterparties for YES buyers (= NO bid depth)
                        final_prob = adjusted_prob_yes

                    # Store original edge for use in downstream gates (e.g. use_original_edge_for_signal)
                    faded_original_edge = original_edge

                    # Optionally use original (contrarian) probability for the prob gate instead of flipped side's prob
                    # use_original_prob_for_fade: false = flipped side prob (better quality filter, ~81% WR at 0.60)
                    # use_original_prob_for_fade: true  = original side prob (bypasses filter, ~68% WR at 0.60)
                    if self.strat.get('use_original_prob_for_fade', False):
                        final_prob = original_prob

                    # Faded edge gate: uses min_fade_edge if set, otherwise falls back to min_edge_percent.
                    # This allows fades to have negative edge (momentum wins regardless of model edge)
                    # while keeping normal trades protected at min_edge_percent.
                    min_edge_for_fade = self.strat.get('min_fade_edge', self.strat.get('min_edge_percent', 10.0))

                    if edge < min_edge_for_fade:
                        logger.info(f"⏭️ {ticker} skip: Faded edge insufficient ({edge:.1f}% < {min_edge_for_fade:.1f}%) "
                                  f"[Original: {original_side.upper()} @ {original_edge:.1f}%]")
                        return None

                    logger.info(f"🔄 {ticker} FADING Contrarian Bet: "
                              f"Momentum {momentum_direction.upper()}, original bet {original_side.upper()} "
                              f"(edge: {original_edge:.1f}%) → FLIPPED to {side.upper()} (edge: {edge:.1f}%)")

                    # Continue with the FADED trade (don't return, let it proceed)
                    # Note: Faded trades can have negative edge but empirically show 84% win rate

                else:
                    # SKIP: Don't take contrarian bets (current behavior)
                    logger.info(f"⏭️ {ticker} skip: Contrarian Bet (momentum {momentum_direction.upper()}, "
                              f"betting {side.upper()} on {market_type.upper()} market)")

                    # Log skipped trade for calibration
                    if self.neg_edge_tracker:
                        edge_data = {
                            'yes_edge_pct': edge_yes,
                            'no_edge_pct': edge_no,
                            'yes_expected_prob': adjusted_prob_yes,
                            'no_expected_prob': adjusted_prob_no,
                            'yes_price': market['yes_ask'],
                            'no_price': market['no_ask'],
                            'spot_price': smoothed_price,
                            'signal_strength': self._calculate_signal_strength(
                                edge, momentum, final_prob, vol_signal, stat_arb, htf_aligned
                            ),
                            'momentum_direction': momentum_direction,
                            'momentum_pct': momentum.get('percent_change', 0),
                            'trend_strength': momentum.get('trend_strength', 0),
                            'orderbook': {
                                'yes_depth': market.get('yes_ask_size', 0),
                                'no_depth': market.get('no_ask_size', 0),
                                'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                            },
                            'volatility': vol_signal if vol_signal else {},
                            'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                            'stat_arb_adjustment': stat_arb['adjustment'],
                        }
                        self.neg_edge_tracker.log_skipped_trade(market, "Contrarian Bet", edge_data)

                    return None

        # === CONTRARIAN ONLY MODE ===
        # If enabled, ONLY take faded contrarian bets (skip all non-contrarian)
        contrarian_only_mode = self.strat.get('contrarian_only_mode', False)
        if contrarian_only_mode and not is_contrarian:
            logger.info(f"⏭️ {ticker} skip: Contrarian-Only Mode (non-contrarian trade)")
            return None

        # === FILTERS ===
        # Spread filter
        if self.strat.get('max_spread_filter_enabled', False):
            max_spread = self.strat.get('max_bid_ask_spread', 0.10)
            current_spread = (market['yes_ask'] - market['yes_bid']) if side == 'yes' else \
                           (market['no_ask'] - market['no_bid'])
            if current_spread > max_spread:
                logger.info(f"⏭️ {ticker} skip: High Spread (${current_spread:.2f})")

                # Log skipped trade for calibration
                if self.neg_edge_tracker:
                    edge_data = {
                        'yes_edge_pct': edge_yes,
                        'no_edge_pct': edge_no,
                        'yes_expected_prob': adjusted_prob_yes,
                        'no_expected_prob': adjusted_prob_no,
                        'yes_price': market['yes_ask'],
                        'no_price': market['no_ask'],
                        'spot_price': smoothed_price,
                        'signal_strength': 0,  # Not calculated yet at this point
                        'momentum_direction': momentum.get('direction', 'unknown'),
                        'momentum_pct': momentum.get('percent_change', 0),
                        'trend_strength': momentum.get('trend_strength', 0),
                        'orderbook': {
                            'yes_depth': market.get('yes_ask_size', 0),
                            'no_depth': market.get('no_ask_size', 0),
                            'bid_ask_spread': current_spread
                        },
                        'volatility': vol_signal if vol_signal else {},
                        'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                        'stat_arb_adjustment': stat_arb['adjustment'],
                    }
                    self.neg_edge_tracker.log_skipped_trade(market, "High Spread", edge_data)

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
        min_entry = self.strat.get('min_entry_price', 0.10)
        if self.strat.get('price_floor_enabled', True) and entry < min_entry:
            logger.info(f"⏭️ {ticker} skip: Price Floor (${entry:.2f} < ${min_entry:.2f})")
            return None

        # Price ceiling (max entry price for high leverage)
        max_entry = self.strat.get('max_entry_price')
        if max_entry and entry > max_entry:
            logger.info(f"⏭️ {ticker} skip: Price Ceiling (${entry:.2f} > ${max_entry:.2f})")
            return None

        # Win probability threshold (min and max)
        # Faded trades use min_fade_expected_probability if set, else fall back to main gate
        if faded_original_edge is not None:
            min_prob = self.strat.get('min_fade_expected_probability',
                                      self.strat.get('min_expected_probability', 0.60))
        else:
            min_prob = self.strat.get('min_expected_probability', 0.60)
        max_prob = self.strat.get('max_expected_probability', 1.0)

        if final_prob < min_prob:
            logger.info(f"⏭️ {ticker} skip: Low Win Prob ({final_prob:.1%} < {min_prob:.1%})")

            # Log skipped trade for calibration
            if self.neg_edge_tracker:
                edge_data = {
                    'yes_edge_pct': edge_yes,
                    'no_edge_pct': edge_no,
                    'yes_expected_prob': adjusted_prob_yes,
                    'no_expected_prob': adjusted_prob_no,
                    'yes_price': market['yes_ask'],
                    'no_price': market['no_ask'],
                    'spot_price': smoothed_price,
                    'signal_strength': 0,  # Not calculated yet at this point
                    'momentum_direction': momentum.get('direction', 'unknown'),
                    'momentum_pct': momentum.get('percent_change', 0),
                    'trend_strength': momentum.get('trend_strength', 0),
                    'orderbook': {
                        'yes_depth': market.get('yes_ask_size', 0),
                        'no_depth': market.get('no_ask_size', 0),
                        'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                    },
                    'volatility': vol_signal if vol_signal else {},
                    'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                    'stat_arb_adjustment': stat_arb['adjustment'],
                }
                self.neg_edge_tracker.log_skipped_trade(market, "Low Win Prob", edge_data)

            return None

        if final_prob > max_prob:
            logger.info(f"⏭️ {ticker} skip: Overconfident Prob ({final_prob:.1%} > {max_prob:.1%}) - model overconfidence")

            # Log skipped trade for calibration
            if self.neg_edge_tracker:
                edge_data = {
                    'yes_edge_pct': edge_yes,
                    'no_edge_pct': edge_no,
                    'yes_expected_prob': adjusted_prob_yes,
                    'no_expected_prob': adjusted_prob_no,
                    'yes_price': market['yes_ask'],
                    'no_price': market['no_ask'],
                    'spot_price': smoothed_price,
                    'signal_strength': 0,
                    'momentum_direction': momentum.get('direction', 'unknown'),
                    'momentum_pct': momentum.get('percent_change', 0),
                    'trend_strength': momentum.get('trend_strength', 0),
                    'orderbook': {
                        'yes_depth': market.get('yes_ask_size', 0),
                        'no_depth': market.get('no_ask_size', 0),
                        'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                    },
                    'volatility': vol_signal if vol_signal else {},
                    'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                    'stat_arb_adjustment': stat_arb['adjustment'],
                }
                self.neg_edge_tracker.log_skipped_trade(market, "Overconfident Prob", edge_data)

            return None

        # Signal strength
        signal_strength = self._calculate_signal_strength(
            edge, momentum, final_prob, vol_signal, stat_arb, htf_aligned
        )
        if signal_strength < self.strat.get('min_signal_strength', 0):
            logger.info(f"⏭️ {ticker} skip: Low Signal ({signal_strength:.1f})")

            # Log skipped trade for calibration
            if self.neg_edge_tracker:
                edge_data = {
                    'yes_edge_pct': edge_yes,
                    'no_edge_pct': edge_no,
                    'yes_expected_prob': adjusted_prob_yes,
                    'no_expected_prob': adjusted_prob_no,
                    'yes_price': market['yes_ask'],
                    'no_price': market['no_ask'],
                    'spot_price': smoothed_price,
                    'signal_strength': signal_strength,
                    'momentum_direction': momentum.get('direction', 'unknown'),
                    'momentum_pct': momentum.get('percent_change', 0),
                    'trend_strength': momentum.get('trend_strength', 0),
                    'orderbook': {
                        'yes_depth': market.get('yes_ask_size', 0),
                        'no_depth': market.get('no_ask_size', 0),
                        'bid_ask_spread': market['yes_ask'] - market['yes_bid']
                    },
                    'volatility': vol_signal if vol_signal else {},
                    'cex_obi_imbalance': imbalance if imbalance is not None else 0.0,
                    'stat_arb_adjustment': stat_arb['adjustment'],
                }
                self.neg_edge_tracker.log_skipped_trade(market, "Low Signal", edge_data)

            return None

        # Liquidity gate
        if self.strat.get('liquidity_gate_enabled', False):
            min_depth = self.strat.get('min_order_book_depth', 5)
            if depth < min_depth:
                logger.info(f"⏭️ {ticker} skip: Insufficient Depth ({depth} < {min_depth} required)")
                return None

        # Inverted mode: flip yes↔no before returning
        if self.strat.get('inverted_mode', False):
            if side == 'yes':
                side = 'no'
                entry = market.get('no_ask', 1.0 - entry)
            else:
                side = 'yes'
                entry = market.get('yes_ask', 1.0 - entry)
            logger.info(f"🔁 {ticker} | Inverted mode: flipped to {side.upper()} @ ${entry:.2f}")

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
            'ob_imbalance': imbalance,  # CEX order book imbalance (0.0-1.0), None if unavailable
            # Signal breakdown (multi-factor adjustments stripped — all zeroed)
            'signal_breakdown': {
                'vol_adjustment': 0.0,
                'micro_adjustment': 0.0,
                'stat_arb_adjustment': 0.0,
                'time_adjustment': 0.0,
                'vol_signal': vol_signal,
                'micro_signal': {'adjustment': 0.0},
                'stat_arb_signal': stat_arb
            }
        }

    def _get_expected_prob(self, market, momentum, smoothed_price):
        """
        Base probability from momentum model.

        Supports three models:
        - 'v1' (legacy): Original model with momentum bonus
        - 'v2' or 'v2_calibrated': Calibrated model
        - 'v3': Mean reversion model (RECOMMENDED - fixes bugs)
        """
        # Check which probability model to use
        prob_model = self.config.get('strategy', {}).get('probability_model', 'v1')

        # v3/v4: Mean reversion model (v4 uses calibrated step function)
        if prob_model in ('v3', 'v4'):
            return self.momentum.calculate_expected_probability_v3(
                market['symbol'],
                market['market_type'],
                market.get('threshold'),
                momentum=momentum,
                current_price=smoothed_price
            )

        # v2: Calibrated model
        elif prob_model in ['v2', 'v2_calibrated']:
            return self.momentum.calculate_expected_probability_calibrated(
                market['symbol'],
                market['market_type'],
                market.get('threshold'),
                momentum=momentum,
                current_price=smoothed_price
            )

        # v1: Legacy model
        else:
            return self.momentum.calculate_expected_probability(
                market['symbol'],
                market['market_type'],
                market.get('threshold'),
                15,
                current_price=smoothed_price
            )

    def _calculate_time_value_adjustment(self, minutes_to_close: float,
                                        market_type: str,
                                        current_price: float,
                                        threshold: float,
                                        base_prob: float,
                                        momentum: Dict = None,
                                        htf_aligned: bool = False) -> tuple:
        """
        Time value decay adjustment - CORRECTED VERSION

        As expiry approaches:
        - ABOVE/BELOW markets: If price is clearly above/below threshold → increase confidence
        - UP/DOWN markets: If momentum is strong and persistent → increase confidence

        Returns: (yes_adjustment, no_adjustment)
        """
        # Handle None/missing data for time
        if minutes_to_close is None:
            return (0.0, 0.0)

        # === HANDLE UP/DOWN MARKETS (no threshold) ===
        if market_type in ['up', 'down'] and (threshold is None or threshold == 0):
            if momentum is None:
                return (0.0, 0.0)

            # Extract momentum data
            momentum_pct = momentum.get('percent_change', 0)  # Can be positive or negative
            momentum_direction = momentum.get('direction', 'flat')
            r_squared = momentum.get('r_squared', 0.5)
            trend_strength = momentum.get('trend_strength', 0)

            # Calculate time pressure (same as threshold markets)
            if minutes_to_close < 1:
                time_pressure = 1.0  # Maximum pressure
            elif minutes_to_close < 2:
                time_pressure = 0.8
            elif minutes_to_close < 5:
                time_pressure = 0.4
            else:
                time_pressure = 0.0  # No adjustment for >5 min

            # No adjustment if no time pressure
            if time_pressure == 0:
                return (0.0, 0.0)

            # Calculate confidence boost based on momentum strength and trend quality
            momentum_strength = abs(momentum_pct)

            # HTF-aligned trades bypass R² requirements: sharp trending moves in
            # the HTF direction are non-linear (low R²) but empirically win 63%+.
            r2_ok = htf_aligned  # if aligned, treat R² as sufficient regardless
            if momentum_strength > 0.5 and (r_squared > 0.4 or r2_ok):
                # Strong momentum (>0.5%), good trend quality (or HTF-aligned)
                confidence_boost = 0.25
            elif momentum_strength > 0.3 and (r_squared > 0.3 or r2_ok):
                # Medium momentum (0.3-0.5%), decent trend (or HTF-aligned)
                confidence_boost = 0.15
            elif momentum_strength > 0.1 and (r_squared > 0.2 or r2_ok):
                # Weak but positive momentum (or HTF-aligned)
                confidence_boost = 0.08
            elif momentum_strength < 0.05:
                # Very weak momentum - high reversal risk
                confidence_boost = -0.05  # Reduce confidence
            else:
                # Minimal momentum
                confidence_boost = 0.03

            # Apply time pressure
            adjustment_magnitude = confidence_boost * time_pressure

            # Apply to correct side based on momentum direction and market type
            if (momentum_direction == 'up' and market_type == 'up') or \
               (momentum_direction == 'down' and market_type == 'down'):
                # Momentum aligns with market type → boost YES (the direction)
                yes_adjustment = adjustment_magnitude
                no_adjustment = -adjustment_magnitude
            else:
                # Momentum against market type → boost NO
                yes_adjustment = -adjustment_magnitude
                no_adjustment = adjustment_magnitude

            return (yes_adjustment, no_adjustment)

        # === HANDLE ABOVE/BELOW THRESHOLD MARKETS ===
        if threshold is None or threshold == 0:
            return (0.0, 0.0)

        # Calculate how far price is from threshold (as percentage)
        distance_pct = abs((current_price - threshold) / threshold)

        # Determine which side should win based on market type
        if market_type in ['above', 'up']:
            price_favors_yes = current_price > threshold
        elif market_type in ['below', 'down']:
            price_favors_yes = current_price < threshold
        else:
            # Can't determine, no adjustment
            return (0.0, 0.0)

        # Calculate time pressure factor (0 to 1)
        # More time pressure = more certainty needed
        if minutes_to_close < 1:
            time_pressure = 1.0  # Maximum pressure
        elif minutes_to_close < 2:
            time_pressure = 0.8
        elif minutes_to_close < 5:
            time_pressure = 0.4
        else:
            time_pressure = 0.0  # No adjustment for >5 min

        # Calculate base adjustment strength based on distance
        # Stronger if price is far from threshold
        if distance_pct > 0.05:  # >5% away from threshold
            confidence_boost = 0.30  # Strong confidence
        elif distance_pct > 0.02:  # 2-5% away
            confidence_boost = 0.20  # Medium confidence
        elif distance_pct > 0.005:  # 0.5-2% away
            confidence_boost = 0.10  # Low confidence
        else:  # <0.5% away - too close to call!
            confidence_boost = -0.10  # Actually REDUCE confidence (uncertain)

        # Apply time pressure
        adjustment_magnitude = confidence_boost * time_pressure

        # Apply to correct side
        if price_favors_yes:
            # Price favors YES → boost YES, reduce NO
            yes_adjustment = adjustment_magnitude
            no_adjustment = -adjustment_magnitude
        else:
            # Price favors NO → boost NO, reduce YES
            yes_adjustment = -adjustment_magnitude
            no_adjustment = adjustment_magnitude

        return (yes_adjustment, no_adjustment)

    def _calculate_signal_strength(self, edge: float, momentum: Dict,
                                   expected_prob: float, vol_signal: Optional[Dict],
                                   stat_arb: Dict,
                                   htf_aligned: bool = False) -> float:
        """
        Simplified signal strength — multi-factor adjustments stripped.

        Only uses the signals the data proved work:
        - Edge from base v4 model (0-30 points)
        - Probability confidence (0-25 points)
        - Momentum sweet spot (0-20 points)
        - R² trend quality (0-25 points)

        Total: 0-100 scale
        """
        # Edge component (0-30) — now purely from v4 base model
        edge_score = (min(max(edge, 0), 20) / 20) * 30

        # Probability confidence (0-25)
        prob_score = max(0, (expected_prob - 0.5) * 2) * 25

        # Momentum alignment (0-20)
        mom_pct = abs(momentum.get('percent_change', 0))
        if 0.3 <= mom_pct <= 1.5:
            mom_score = 20  # Sweet spot — clean move, not exhausted
        elif mom_pct > 1.5:
            mom_score = 10  # May be priced in already
        elif mom_pct >= 0.12:
            mom_score = 12  # Weak but directional
        else:
            mom_score = 0   # Flat — no conviction

        # R² trend quality (0-25) — the strongest predictor in the data
        r_squared = momentum.get('r_squared', 0.5)
        if r_squared >= 0.75:
            r2_score = 25   # Very clean trend
        elif r_squared >= 0.65:
            r2_score = 20   # Good trend (our minimum threshold)
        elif r_squared >= 0.50:
            r2_score = 10   # Marginal
        else:
            r2_score = 0    # Noisy — shouldn't reach here with filter

        total = edge_score + prob_score + mom_score + r2_score

        return max(0, min(100, round(total, 1)))

    def _apply_crowd_confidence_blending(self, bot_prob: float, market: Dict,
                                         orderbook: Dict, crowd_config: Dict) -> float:
        """
        Blend bot probability with market-implied probability based on liquidity.

        Calibration Results:
        - High depth markets: Market 83.8% accurate vs Bot 39.1%
        - Med depth markets: Market 70.9% accurate vs Bot 34.9%
        - Low depth markets: Market 68.7% accurate vs Bot 39.2%

        Strategy: Trust market more in high-liquidity scenarios.

        Args:
            bot_prob: Bot's calculated probability
            market: Market dict
            orderbook: Order book data
            crowd_config: Crowd confidence config

        Returns:
            Blended probability
        """
        try:
            # Get market-implied probability from YES bid price
            # The YES bid is the highest price buyers are willing to pay → market's probability estimate
            market_prob = orderbook.get('yes_bid', 0.50)

            # Calculate total liquidity (depth)
            total_depth = (orderbook.get('yes_ask_size', 0) +
                          orderbook.get('yes_bid_size', 0) +
                          orderbook.get('no_ask_size', 0) +
                          orderbook.get('no_bid_size', 0))

            # Determine market weight based on liquidity
            high_threshold = crowd_config.get('high_depth_threshold', 500)
            low_threshold = crowd_config.get('low_depth_threshold', 100)
            max_weight = crowd_config.get('max_market_weight', 0.7)
            min_weight = crowd_config.get('min_market_weight', 0.3)

            if total_depth >= high_threshold:
                # High liquidity → trust market more (70%)
                market_weight = max_weight
            elif total_depth <= low_threshold:
                # Low liquidity → trust bot more (30% market, 70% bot)
                market_weight = min_weight
            else:
                # Medium liquidity → linear interpolation
                ratio = (total_depth - low_threshold) / (high_threshold - low_threshold)
                market_weight = min_weight + (max_weight - min_weight) * ratio

            # Blend probabilities
            blended = (market_weight * market_prob) + ((1 - market_weight) * bot_prob)

            # Clamp to reasonable bounds
            blended = max(0.05, min(0.95, blended))

            logger.debug(f"👥 Crowd Blend: depth={total_depth}, market_prob={market_prob:.2%}, "
                        f"bot_prob={bot_prob:.2%}, weight={market_weight:.1%}, "
                        f"result={blended:.2%}")

            return blended

        except Exception as e:
            logger.warning(f"Error in crowd confidence blending: {e}")
            return bot_prob  # Fallback to bot probability

    def scan_for_edges(self, markets: List[Dict]) -> List[Dict]:
        """Scan all markets for edges using multi-factor analysis.
        Markets are evaluated in parallel — each analyze_market() call is independent
        (pure calculation + GIL-safe deque appends), so threading is safe here.
        """
        if not markets:
            return []

        opportunities = []
        skipped_count = 0
        workers = min(len(markets), 8)  # cap threads; 4-8 markets typical

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.analyze_market, m): m for m in markets}
            for future in as_completed(futures):
                try:
                    opp = future.result()
                    if opp:
                        opportunities.append(opp)
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.error(f"analyze_market error: {e}")
                    skipped_count += 1

        if skipped_count > 0:
            logger.debug(f"Skipped {skipped_count} markets below threshold (tracking for calibration)")

        # Sort by edge strength
        return sorted(opportunities, key=lambda x: x['edge_percent'], reverse=True)
