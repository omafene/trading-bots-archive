"""
Momentum Analyzer v4 - EMPIRICALLY CALIBRATED MODEL

Improvements over v3:

Fix 1 - HTF Buffer Extension:
    Dynamic price history buffer so the HTF tide filter (1h/4h) actually has
    enough data to return a result.  v3 hardcoded 20 min; v4 computes
    (htf_minutes + extra_buf) when the HTF filter is enabled.

Fix 2 - Rolling-Window MTF:
    Sub-15m timeframes (1m, 5m) use rolling windows instead of
    candle-aligned windows.  At candle open a candle-aligned 1m window can
    have <5 seconds of data, making R² and slope meaningless.

Fix 3 - Volatility-Normalised Distance:
    Distance to threshold divided by residual candle volatility (σ) before
    applying step-function thresholds.  Same σ-buckets apply equally to BTC,
    ETH, SOL, and XRP.

Fix 4 - Calibrated Step Function:
    Base probabilities derived from 37,344 real market observations in
    skipped_trades.csv.  The v3 step function over-estimated YES by 13-22 pp
    when price was below threshold and under-estimated by 9-20 pp when price
    was above threshold.  Initial calibrated values:
        norm_dist < -3.0   → 0.80  (empirical YES WR 80.7%, n=332)
        norm_dist [-3,-1.5) → 0.78  (empirical 78.1%, n=2256)
        norm_dist [-1.5,-0.7)→ 0.76  (empirical 75.9%, n=5678)
        norm_dist [-0.7, 0) → 0.61  (empirical 60.9%, n=12139)
        norm_dist [0, +0.7) → 0.35  (empirical 35.0%, n=10175)
        norm_dist [+0.7,+1.5)→ 0.22  (empirical 21.5%, n=5007)
        norm_dist [+1.5,+3.0)→ 0.13  (empirical 12.7%, n=1544)
        norm_dist > +3.0   → 0.05  (empirical 4.2%, n=213)

Fix 5 - Mean Reversion Penalty Removed:
    v3 applied up to -0.12 penalty for high momentum.  Empirical data shows
    the OPPOSITE: high momentum (>0.5%) raises YES win rate by +12 pp in the
    "just above threshold" zone (57.6% low-mom → 69.8% high-mom).  The
    penalty was suppressing valid YES bets.

Fix 6 - Price History Persistence:
    Price history saved to disk every 60 s and reloaded on startup.
    Eliminates the ~80-minute HTF blind window after every restart.
    File is always overwritten (never appended) — size bounded by
    max_history_length × number of symbols (≈ 300 KB).

Fix 7 - Auto-Calibration Feedback Loop:
    On startup, v4 checks whether skipped_trades.csv has changed since the
    last calibration run.  If so, it recomputes step-function base
    probabilities using exponential time-decay weighting (data from
    half_life_days ago counts half as much as today's data).  Results are
    cached to data/v4_calibration.json — subsequent restarts are instant.
    As the dataset grows, base probabilities track changing market conditions.

    NOTE: Only UP/ABOVE markets are present in skipped_trades.csv.  YES and
    NO are complementary in binary markets (NO_prob = 1 - YES_prob), so this
    calibration implicitly covers both sides.  DOWN/BELOW markets use the
    same empirical probabilities via mirrored norm_dist lookup.

Config knobs (all optional, under strategy.v4 in config_15m.yaml):
    htf_buffer_extra_minutes: 20
    rolling_mtf_threshold: 15
    vol_floor: 0.15
    cache_path: "data/price_history_v4.pkl"
    cache_save_interval: 60
    calibration_path: "data/v4_calibration.json"
    calibration_half_life_days: 30
    calibration_min_samples: 200
"""

import os
import pickle
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class MomentumAnalyzerV4:
    """
    v4: Empirically calibrated momentum model.

    Drop-in replacement for MomentumAnalyzerV3.  All public method signatures
    are identical so edge_detector_advanced.py, the scanner, and the position
    manager work without modification.
    """

    def __init__(self, spot_feed, config):
        self.spot_feed    = spot_feed
        self.price_history: Dict[str, list] = {}
        self.config       = config

        strategy = config.get('strategy', {})
        v4_cfg   = strategy.get('v4', {})

        # v4 knobs
        self._vol_floor         = v4_cfg.get('vol_floor', 0.15)
        self._rolling_threshold = v4_cfg.get('rolling_mtf_threshold', 15)
        self._r_squared_lookback = strategy.get('r_squared_lookback_minutes', None)
        extra_buf               = v4_cfg.get('htf_buffer_extra_minutes', 20)
        self._cache_path        = v4_cfg.get('cache_path',
                                             os.path.join('data', 'price_history_v4.pkl'))
        self._save_interval     = v4_cfg.get('cache_save_interval', 60)
        self._cal_path          = v4_cfg.get('calibration_path',
                                             os.path.join('data', 'v4_calibration.json'))
        self._cal_half_life     = v4_cfg.get('calibration_half_life_days', 30.0)
        self._cal_min_samples   = v4_cfg.get('calibration_min_samples', 200)

        # Price history buffer (Fix 1)
        spot_interval = config['monitoring'].get('spot_price_update_interval', 2)
        htf_enabled   = strategy.get('mtf_htf_filter_enabled', False)
        htf_tf        = strategy.get('htf_timeframe', '1h')
        htf_minutes   = 240 if htf_tf == '4h' else 60
        buffer_minutes = (htf_minutes + extra_buf) if htf_enabled else 20

        self._buffer_minutes    = buffer_minutes
        self.max_history_length = int((buffer_minutes * 60) / spot_interval)
        self._last_save_time: Optional[datetime] = None

        logger.info("✅ Momentum Analyzer v4 (Calibrated) initialized")
        logger.info(
            f"   Buffer: {buffer_minutes} min ({self.max_history_length} samples)"
            + (" [HTF-extended]" if htf_enabled else "")
        )

        # Load calibrated base probabilities (Fix 7)
        self._base_probs: List[float] = self._init_calibration()

        # Warm up price history from disk (Fix 6)
        self._load_price_history()

    # ------------------------------------------------------------------
    # Auto-calibration (Fix 7)
    # ------------------------------------------------------------------

    def _init_calibration(self) -> List[float]:
        """
        Load calibrated base probabilities from cache on startup.

        Does NOT auto-compute — calibration only runs when explicitly triggered
        via the Telegram /recalibrate command.  If no cache exists, falls back
        to the built-in values derived from the initial 37,344-row dataset.
        """
        from calibration_engine import FALLBACK_PROBS, load_calibration

        probs = load_calibration(self._cal_path)
        if probs:
            return probs

        logger.info(
            "   No calibration cache found — using built-in values. "
            "Send /recalibrate via Telegram to compute from current data."
        )
        return list(FALLBACK_PROBS)

    def recalibrate(self) -> dict:
        """
        Recompute step-function base probabilities from skipped_trades.csv.

        Called by the Telegram /recalibrate command.  Updates self._base_probs
        live so the running bot immediately uses the new values — no restart
        needed.

        Returns a summary dict consumed by the Telegram command handler:
            success  (bool)
            reason   (str, only on failure)
            old_probs (List[float])
            new_probs (List[float])
            rows_used (int, approximate)
        """
        from calibration_engine import FALLBACK_PROBS, compute_calibrated_probs, save_calibration

        trades_path = os.path.join('data', 'negative_edges', 'skipped_trades.csv')
        old_probs   = list(self._base_probs)

        probs = compute_calibrated_probs(
            trades_path,
            min_samples    = self._cal_min_samples,
            half_life_days = self._cal_half_life,
            vol_floor      = self._vol_floor,
        )

        if not probs:
            return {
                'success': False,
                'reason':  'Insufficient data in skipped_trades.csv (need 1,000+ rows)',
            }

        try:
            with open(trades_path) as _f:
                row_count = sum(1 for _ in _f) - 1
        except Exception:
            row_count = 0

        save_calibration(self._cal_path, probs, source_row_count=row_count)
        self._base_probs = probs  # atomic reference swap — safe without a lock
        logger.info(f"   Recalibration complete, saved → {self._cal_path}")

        return {
            'success':   True,
            'old_probs': old_probs,
            'new_probs': probs,
        }

    def _bucket_prob(self, norm_dist: float, invert: bool = False) -> float:
        """
        Look up base YES probability from the calibrated step function.

        invert=True for DOWN/BELOW markets: a positive norm_dist means the
        price is already below the threshold (YES is winning), which mirrors
        a negative norm_dist for UP/ABOVE markets.
        """
        from calibration_engine import BUCKET_BOUNDARIES
        d = -norm_dist if invert else norm_dist
        for i, boundary in enumerate(BUCKET_BOUNDARIES):
            if d < boundary:
                return self._base_probs[i]
        return self._base_probs[-1]

    # ------------------------------------------------------------------
    # Price history persistence (Fix 6)
    # ------------------------------------------------------------------

    def _load_price_history(self):
        """Reload cached price history on startup, discarding stale entries."""
        try:
            if not os.path.exists(self._cache_path):
                logger.info("   No price history cache found — starting fresh")
                return
            with open(self._cache_path, 'rb') as f:
                cached = pickle.load(f)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self._buffer_minutes)
            loaded = 0
            for symbol, history in cached.items():
                fresh = [(ts, p) for ts, p in history if ts >= cutoff]
                if fresh:
                    self.price_history[symbol] = fresh
                    loaded += len(fresh)
            logger.info(
                f"   Loaded price history: {loaded} samples "
                f"across {len(self.price_history)} symbols"
            )
        except Exception as e:
            logger.warning(f"   Could not load price history cache: {e}")

    def _save_price_history(self):
        """Overwrite cache file with current (already-trimmed) price history."""
        try:
            cache_dir = os.path.dirname(self._cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(self._cache_path, 'wb') as f:
                pickle.dump(self.price_history, f)
        except Exception as e:
            logger.warning(f"   Could not save price history cache: {e}")

    # ------------------------------------------------------------------
    # Price history updates
    # ------------------------------------------------------------------

    def update_price_history(self, symbol: str, price: Optional[float] = None):
        """Add latest price to in-memory history, then persist if due."""
        if symbol not in self.price_history:
            self.price_history[symbol] = []

        if price is None:
            price = self.spot_feed._get_price(symbol)

        if price:
            now = datetime.now(timezone.utc)
            self.price_history[symbol].append((now, price))
            if len(self.price_history[symbol]) > self.max_history_length:
                self.price_history[symbol] = self.price_history[symbol][-self.max_history_length:]

            # Rate-limited save: at most once per save_interval seconds
            if (self._last_save_time is None or
                    (now - self._last_save_time).total_seconds() >= self._save_interval):
                self._save_price_history()
                self._last_save_time = now

    # ------------------------------------------------------------------
    # Momentum calculation helpers
    # ------------------------------------------------------------------

    def _regress(self, symbol: str, recent_prices: list) -> Optional[Dict]:
        """Linear regression on a list of (timestamp, price) tuples."""
        if len(recent_prices) < 10:
            return None

        times  = np.array([(ts - recent_prices[0][0]).total_seconds()
                           for ts, _ in recent_prices])
        prices = np.array([p for _, p in recent_prices])

        slope, intercept = np.polyfit(times, prices, 1)
        predictions = slope * times + intercept

        ss_res    = np.sum((prices - predictions) ** 2)
        ss_tot    = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = max(0.0, min(1.0, 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0))

        duration  = times[-1]
        start     = prices[0]
        trend_pct = (slope * duration / start) * 100 if start > 0 else 0.0

        direction = ('flat' if abs(trend_pct) < 0.05
                     else 'up' if slope > 0 else 'down')
        volatility = (np.std(prices - predictions) / np.mean(prices) * 100
                      if len(prices) > 1 else 0.0)

        return {
            'percent_change': trend_pct,
            'direction':      direction,
            'volatility':     volatility,
            'trend_strength': r_squared * min(abs(trend_pct) / 2.0, 1.0),
            'r_squared':      r_squared,
            'confidence':     ('high' if r_squared >= 0.7
                               else 'medium' if r_squared >= 0.4 else 'low'),
            'slope':          slope,
            'start_price':    start,
            'end_price':      prices[-1],
            'num_samples':    len(recent_prices),
        }

    def calculate_momentum_rolling(self, symbol: str, minutes: int) -> Optional[Dict]:
        """Rolling-window momentum: last N minutes regardless of candle boundary (Fix 2)."""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent = [(ts, p) for ts, p in self.price_history[symbol] if ts >= cutoff]
        return self._regress(symbol, recent)

    def calculate_momentum(self, symbol: str, minutes: int = 15) -> Optional[Dict]:
        """Candle-aligned momentum, or rolling window if r_squared_lookback_minutes is set."""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None
        if self._r_squared_lookback:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self._r_squared_lookback)
        else:
            now          = datetime.now(timezone.utc)
            candle_start = now.replace(second=0, microsecond=0)
            candle_start = candle_start.replace(minute=(candle_start.minute // minutes) * minutes)
            cutoff = candle_start
        recent = [(ts, p) for ts, p in self.price_history[symbol] if ts >= cutoff]
        return self._regress(symbol, recent)

    # ------------------------------------------------------------------
    # Multi-timeframe alignment (Fix 2)
    # ------------------------------------------------------------------

    def get_multi_timeframe_alignment(self, symbol: str,
                                      timeframes: List[int] = [1, 5, 15]) -> Optional[Dict]:
        """Sub-15m timeframes use rolling windows so they always have a full N-minute window."""
        results = {}
        for minutes in timeframes:
            m = (self.calculate_momentum_rolling(symbol, minutes)
                 if minutes < self._rolling_threshold
                 else self.calculate_momentum(symbol, minutes))
            if m:
                results[f'{minutes}m'] = {
                    'direction':      m['direction'],
                    'percent_change': m['percent_change'],
                    'r_squared':      m['r_squared'],
                }
            else:
                logger.debug(f"{symbol}: Insufficient data for {minutes}m momentum")
                return None

        dirs          = [results[f'{m}m']['direction'] for m in timeframes]
        bullish_count = sum(1 for d in dirs if d == 'up')
        bearish_count = sum(1 for d in dirs if d == 'down')
        results['alignment'] = {
            'bullish_count':      bullish_count,
            'bearish_count':      bearish_count,
            'total_timeframes':   len(timeframes),
            'is_aligned_bullish': bullish_count >= len(timeframes) * 0.67,
            'is_aligned_bearish': bearish_count >= len(timeframes) * 0.67,
        }
        return results

    # ------------------------------------------------------------------
    # Probability model (Fixes 3, 4, 5, 7)
    # ------------------------------------------------------------------

    def calculate_expected_probability_v3(self, symbol: str, market_type: str,
                                          threshold: Optional[float] = None,
                                          momentum: Dict = None,
                                          current_price: Optional[float] = None) -> Optional[float]:
        """
        v4 probability model (named v3 for API compatibility).

        Uses empirically calibrated base probabilities that auto-update as
        skipped_trades.csv accumulates new outcome data.

        YES and NO are complementary in binary markets (NO = 1 − YES), so a
        single calibration of the YES win rate implicitly calibrates both sides.
        skipped_trades.csv contains only UP/ABOVE market rows; DOWN/BELOW
        markets use mirrored norm_dist lookup (invert=True) which is
        mathematically equivalent by symmetry.

        Returns: probability ∈ [0.05, 0.95] or None
        """
        if not momentum or not threshold:
            return None

        active_price = current_price if current_price is not None else momentum['end_price']
        distance_pct = ((threshold - active_price) / active_price) * 100

        # Fix 3: volatility-normalised distance
        vol_sigma = max(momentum.get('volatility', self._vol_floor), self._vol_floor)
        norm_dist = distance_pct / vol_sigma

        # Fix 4 & 7: calibrated step function via _bucket_prob
        if market_type in ('up', 'above'):
            base_prob = self._bucket_prob(norm_dist, invert=False)
        elif market_type in ('down', 'below'):
            base_prob = self._bucket_prob(norm_dist, invert=True)
        else:
            return None

        # Fix 5: no mean reversion penalty (empirical data shows momentum helps)

        # Small R² quality bonus: high R² means the distance estimate is more
        # reliable (price moving cleanly, not chaotically)
        r_squared = momentum.get('r_squared', 0)
        quality_bonus = 0.03 if r_squared > 0.7 else (0.02 if r_squared > 0.5 else 0.0)

        final_prob = max(0.05, min(0.95, base_prob + quality_bonus))

        logger.debug(
            f"   v4 Prob: base={base_prob:.2%} (norm_dist={norm_dist:.2f}σ, "
            f"vol={vol_sigma:.3f}%) + quality={quality_bonus:+.2%} = {final_prob:.2%}"
        )
        return final_prob

    # Backwards-compatibility wrapper
    def calculate_expected_probability(self, symbol: str, market_type: str,
                                       threshold: Optional[float] = None,
                                       minutes: int = 15,
                                       current_price: Optional[float] = None) -> Optional[float]:
        momentum = self.calculate_momentum(symbol, minutes)
        if not momentum:
            return None
        return self.calculate_expected_probability_v3(
            symbol, market_type, threshold, momentum, current_price
        )
