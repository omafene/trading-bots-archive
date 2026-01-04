"""
Analyze BTC/ETH momentum to calculate expected probability.
Updated: Linear Regression with R² confidence for high-quality signals.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple
import statistics
import time
import numpy as np
import pandas as pd
import os
from ohlc_aggregator import OHLCAggregator

logger = logging.getLogger(__name__)

class MomentumAnalyzer:
    """Calculate expected probability based on spot price momentum"""

    def __init__(self, spot_feed, config):
        self.spot_feed = spot_feed
        self.price_history = {}
        self.config = config

        # Calculate buffer size using the effective write interval.
        # The WS price feed (binance_price_feed) may write faster than the REST poll
        # interval, so size the buffer against whichever source writes more frequently.
        spot_interval = config['monitoring'].get('spot_price_update_interval', 2)
        ws_interval = config.get('binance_price_feed', {}).get('min_write_interval', spot_interval)
        effective_interval = min(spot_interval, ws_interval)
        buffer_minutes = 20  # Always keep 20 minutes of data
        self.max_history_length = int((buffer_minutes * 60) / effective_interval)

        # Rolling window for R² calculation (for late-window trading)
        self.r_squared_lookback_minutes = config['strategy'].get('r_squared_lookback_minutes', None)

        # OHLC aggregation for R² calculation (reduces 1-second noise)
        self.use_ohlc_for_r_squared = config['strategy'].get('use_ohlc_for_r_squared', False)
        self.ohlc_interval_seconds = config['strategy'].get('ohlc_interval_seconds', 60)

        lookback_info = f"{self.r_squared_lookback_minutes}min rolling" if self.r_squared_lookback_minutes else "full candle"
        data_source = "1-min OHLC candles" if self.use_ohlc_for_r_squared else "smoothed ticks"
        logger.info(f"✅ Momentum analyzer initialized "
                    f"(effective interval: {effective_interval}s, buffer: {self.max_history_length} samples = {buffer_minutes} min, "
                    f"R² window: {lookback_info}, data: {data_source})")

        # === DYNAMIC CALIBRATION (v2 model only) ===
        self.calibration_config = config.get('calibration', {})
        self.dynamic_recalibration_enabled = self.calibration_config.get('dynamic_recalibration_enabled', True)

        # Recalibration mode and settings
        self.recalibration_mode = self.calibration_config.get('recalibration_mode', 'hybrid')
        self.recalibration_interval_days = self.calibration_config.get('recalibration_interval_days', 7)
        self.recalibration_lookback_days = self.calibration_config.get('recalibration_lookback_days', 30)
        self.min_samples_for_recalibration = self.calibration_config.get('min_samples_for_recalibration', 100)
        self.separate_curves_by_direction = self.calibration_config.get('separate_curves_by_direction', True)

        # Drift-based recalibration settings
        self.drift_threshold_percent = self.calibration_config.get('drift_threshold_percent', 10.0) / 100.0  # Convert to decimal
        self.drift_check_interval_trades = self.calibration_config.get('drift_check_interval_trades', 50)
        self.min_drift_samples = self.calibration_config.get('min_drift_samples', 50)
        self.drift_lookback_trades = self.calibration_config.get('drift_lookback_trades', 100)

        # Hybrid mode limits
        self.max_recalibration_interval_days = self.calibration_config.get('max_recalibration_interval_days', 7)
        self.min_recalibration_interval_hours = self.calibration_config.get('min_recalibration_interval_hours', 12)

        # Initialize calibration curves with static defaults
        self.calibration_curve_up = self._default_calibration_curve()
        self.calibration_curve_down = self._default_calibration_curve()
        self.last_recalibration = datetime.now()

        # Drift tracking state
        self.trades_since_last_drift_check = 0
        self.last_drift_check_time = datetime.now()

        # Try to load dynamic calibration from recent data on startup
        if self.dynamic_recalibration_enabled:
            self._maybe_recalibrate()
            mode_str = f"{self.recalibration_mode} mode"
            if self.recalibration_mode == 'drift':
                logger.info(f"📊 Dynamic calibration ENABLED ({mode_str}, drift threshold {self.drift_threshold_percent*100:.1f}%)")
            elif self.recalibration_mode == 'hybrid':
                logger.info(f"📊 Dynamic calibration ENABLED ({mode_str}, drift {self.drift_threshold_percent*100:.1f}% OR {self.recalibration_interval_days}d)")
            else:
                logger.info(f"📊 Dynamic calibration ENABLED ({mode_str}, every {self.recalibration_interval_days}d)")
    
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
        """
        Calculate price momentum using Linear Regression with R² confidence.

        Two modes:
        1. Rolling Window (if r_squared_lookback_minutes is set): Uses last N minutes of data
           - Better for late-window trading (last 5-6 mins of candle)
           - R² measures recent trend quality
        2. Full Candle (default): Uses all data from candle start to now
           - Traditional approach
           - R² measures overall candle trend quality
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            logger.debug(f"{symbol}: Insufficient history (need 10+ samples)")
            return None

        now = datetime.now(timezone.utc)

        # Determine cutoff time based on mode
        if self.r_squared_lookback_minutes:
            # ROLLING WINDOW MODE: Use last N minutes
            cutoff = now - timedelta(minutes=self.r_squared_lookback_minutes)
        else:
            # FULL CANDLE MODE: Find start of current candle interval (floor to :00, :15, :30, :45)
            candle_start = now.replace(second=0, microsecond=0)
            minutes_into_hour = candle_start.minute
            candle_minute = (minutes_into_hour // minutes) * minutes
            candle_start = candle_start.replace(minute=candle_minute)
            cutoff = candle_start

        # Get all prices from cutoff to now
        recent_prices = [(ts, price) for ts, price in self.price_history[symbol] if ts >= cutoff]

        if len(recent_prices) < 10:
            logger.debug(f"{symbol}: Only {len(recent_prices)} samples in current candle (need 10+)")
            return None

        # Choose data source for R² calculation
        if self.use_ohlc_for_r_squared:
            # Aggregate to OHLC candles (reduces noise)
            candles = OHLCAggregator.aggregate_to_candles(
                recent_prices,
                interval_seconds=self.ohlc_interval_seconds
            )
            # Filter out incomplete current candle
            complete_candles = OHLCAggregator.filter_complete_candles(
                candles, now, self.ohlc_interval_seconds
            )

            if len(complete_candles) < 3:
                logger.debug(f"{symbol}: Only {len(complete_candles)} complete candles (need 3+)")
                return None

            # Use close prices for R² calculation
            prices_for_r2 = np.array(OHLCAggregator.get_close_prices(complete_candles))
            times_for_r2 = np.array([
                (candle['timestamp'] - complete_candles[0]['timestamp']).total_seconds()
                for candle in complete_candles
            ])

            logger.debug(f"{symbol}: Using {len(complete_candles)} OHLC candles for R² (from {len(recent_prices)} ticks)")
        else:
            # Use raw smoothed prices (existing behavior)
            prices_for_r2 = np.array([price for _, price in recent_prices])
            times_for_r2 = np.array([(ts - recent_prices[0][0]).total_seconds() for ts, _ in recent_prices])

        # Extract timestamps and prices for percentage calculation (always use raw data)
        times = np.array([(ts - recent_prices[0][0]).total_seconds() for ts, _ in recent_prices])
        prices = np.array([price for _, price in recent_prices])

        # Linear Regression: price = slope * time + intercept
        # Use OHLC data for R² if enabled, raw data for slope/percentage
        slope_r2, intercept_r2 = np.polyfit(times_for_r2, prices_for_r2, 1)

        # Calculate R² (goodness of fit - how well prices follow the trend)
        # Use the same data we fitted (OHLC or raw)
        predictions_r2 = slope_r2 * times_for_r2 + intercept_r2
        ss_res = np.sum((prices_for_r2 - predictions_r2) ** 2)  # Residual sum of squares
        ss_tot = np.sum((prices_for_r2 - np.mean(prices_for_r2)) ** 2)  # Total sum of squares
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        r_squared = max(0, min(1, r_squared))  # Clamp to [0, 1]

        # Use raw data for actual slope calculation (for responsiveness)
        slope, intercept = np.polyfit(times, prices, 1)

        # Calculate predictions for volatility calculation (using raw data slope)
        predictions = slope * times + intercept

        # Calculate percent change based on regression line (not just endpoints)
        duration_seconds = times[-1]
        start_price = prices[0]
        end_price = prices[-1]

        # Trend percent from regression slope
        trend_percent = (slope * duration_seconds / start_price) * 100 if start_price > 0 else 0

        # Simple percent change (for comparison/fallback)
        simple_percent_change = ((end_price - start_price) / start_price) * 100

        # Calculate volatility (price variance around trend line)
        volatility = np.std(prices - predictions) / np.mean(prices) * 100 if len(prices) > 1 else 0

        # Direction based on regression slope
        if abs(trend_percent) < 0.05:
            direction = 'flat'
        elif slope > 0:
            direction = 'up'
        else:
            direction = 'down'

        # Trend strength: combination of R² and slope magnitude
        # High R² + significant slope = strong trend
        trend_strength = r_squared * min(abs(trend_percent) / 2.0, 1.0)  # 0-1 scale

        # Confidence level based on R²
        if r_squared >= 0.7:
            confidence = 'high'
        elif r_squared >= 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'percent_change': trend_percent,  # Based on regression (better)
            'simple_percent_change': simple_percent_change,  # Old method (for comparison)
            'direction': direction,
            'volatility': volatility,
            'trend_strength': trend_strength,
            'r_squared': r_squared,  # NEW: Trend confidence (0-1)
            'confidence': confidence,  # NEW: high/medium/low
            'slope': slope,  # $/second
            'start_price': start_price,
            'end_price': end_price,
            'num_samples': len(recent_prices)
        }

    def get_multi_timeframe_alignment(self, symbol: str, timeframes: List[int] = [1, 5, 15]) -> Optional[Dict]:
        """
        Calculate momentum across multiple timeframes for alignment checking.

        Args:
            symbol: Asset symbol (BTC, ETH, SOL, XRP)
            timeframes: List of minute intervals to check (e.g., [1, 5, 15])

        Returns:
            Dict with momentum direction for each timeframe, or None if insufficient data
        """
        results = {}

        for minutes in timeframes:
            momentum = self.calculate_momentum(symbol, minutes)
            if momentum:
                results[f'{minutes}m'] = {
                    'direction': momentum['direction'],
                    'percent_change': momentum['percent_change'],
                    'r_squared': momentum['r_squared']
                }
            else:
                # If we can't calculate momentum for any timeframe, return None
                logger.debug(f"{symbol}: Insufficient data for {minutes}m momentum")
                return None

        # Calculate alignment score
        directions = [results[f'{m}m']['direction'] for m in timeframes]
        bullish_count = sum(1 for d in directions if d == 'up')
        bearish_count = sum(1 for d in directions if d == 'down')

        results['alignment'] = {
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'total_timeframes': len(timeframes),
            'is_aligned_bullish': bullish_count >= len(timeframes) * 0.67,  # 2/3 majority
            'is_aligned_bearish': bearish_count >= len(timeframes) * 0.67
        }

        return results

    def calculate_expected_probability(self, symbol: str, market_type: str, 
                                      threshold: Optional[float] = None, 
                                      minutes: int = 15,
                                      current_price: Optional[float] = None) -> Optional[float]:
        """Calculate expected probability for market outcome."""
        momentum = self.calculate_momentum(symbol, minutes)
        if not momentum: return None
        
        active_price = current_price if current_price is not None else momentum['end_price']

        # 1. UP/DOWN Markets (with threshold - treat like ABOVE/BELOW)
        if market_type in ['up', 'down'] and threshold:
            # UP markets: need price to be >= threshold at close (YES wins)
            # DOWN markets: need price to be < threshold at close (YES wins)
            distance_pct = ((threshold - active_price) / active_price) * 100

            if market_type == 'up':
                # If already above threshold, YES is likely
                if active_price >= threshold:
                    expected_prob = 0.80
                else:
                    # Below threshold - how far away are we?
                    expected_prob = 0.50 - (distance_pct * 0.05)
                    if momentum['direction'] == 'up': expected_prob += 0.15
            else:  # 'down'
                # If already below threshold, YES is likely
                if active_price < threshold:
                    expected_prob = 0.80
                else:
                    # Above threshold - how far away are we?
                    expected_prob = 0.50 + (distance_pct * 0.05)
                    if momentum['direction'] == 'down': expected_prob += 0.15

        # 2. UP/DOWN Markets (fallback without threshold - momentum only)
        elif market_type in ['up', 'down']:
            percent_change = abs(momentum['percent_change'])
            trend_strength = momentum['trend_strength']
            if momentum['direction'] == 'up' and market_type == 'up':
                expected_prob = 0.50 + min(percent_change * 5, 0.25) + (trend_strength * 0.15)
            elif momentum['direction'] == 'down' and market_type == 'down':
                expected_prob = 0.50 + min(percent_change * 5, 0.25) + (trend_strength * 0.15)
            elif (momentum['direction'] != market_type): expected_prob = 0.30
            else: expected_prob = 0.50

        # 3. ABOVE/BELOW Threshold Markets
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

    def calculate_expected_probability_calibrated(self, symbol: str, market_type: str,
                                                  threshold: Optional[float] = None,
                                                  momentum: Dict = None,
                                                  current_price: Optional[float] = None) -> Optional[float]:
        """
        CALIBRATED probability model (NEW v2.0)

        Fixes overconfidence issue where bot calculated >1.0 probabilities.

        Calibration data showed bot was overconfident by 30-36%:
        - Bot said 60-70%: Actually 33% (off by -29%)
        - Bot said 70-80%: Actually 47% (off by -28%)
        - Bot said 80-90%: Actually 56% (off by -31%)
        - Bot said >100%: Actually 81% (off by -36%)

        Changes from v1:
        - Reduced base confidence: 0.80 → 0.60 (at threshold)
        - Reduced distance bonus: 0.05 → 0.03 (40% reduction)
        - Reduced momentum bonus: 0.15 → 0.10 (33% reduction)
        - Reduced trend strength bonus: 0.15 → 0.10 (33% reduction)
        - Added calibration curve to final probability

        Args:
            symbol: Asset symbol (BTC, ETH, SOL, XRP)
            market_type: 'up', 'down', 'above', or 'below'
            threshold: Strike price/threshold
            momentum: Momentum data dict from analyze_momentum()
            current_price: Current spot price (optional, uses end_price if None)

        Returns:
            Expected probability (0.05-0.95) or None if cannot calculate
        """
        if not momentum:
            return None

        active_price = current_price if current_price is not None else momentum['end_price']

        # 1. UP/DOWN Markets (with threshold)
        if market_type in ['up', 'down'] and threshold:
            distance_pct = ((threshold - active_price) / active_price) * 100

            if market_type == 'up':
                # If already above threshold, YES is likely (reduced from 0.80 → 0.60)
                if active_price >= threshold:
                    expected_prob = 0.60
                else:
                    # Below threshold - how far away are we?
                    expected_prob = 0.45 - (distance_pct * 0.03)  # Reduced multiplier from 0.05 → 0.03
                    if momentum['direction'] == 'up':
                        expected_prob += 0.10  # Reduced bonus from 0.15 → 0.10
            else:  # 'down'
                # If already below threshold, YES is likely (reduced from 0.80 → 0.60)
                if active_price < threshold:
                    expected_prob = 0.60
                else:
                    # Above threshold - how far away are we?
                    expected_prob = 0.45 + (distance_pct * 0.03)  # Reduced multiplier
                    if momentum['direction'] == 'down':
                        expected_prob += 0.10  # Reduced bonus

        # 2. UP/DOWN Markets (fallback without threshold - momentum only)
        elif market_type in ['up', 'down']:
            percent_change = abs(momentum['percent_change'])
            trend_strength = momentum['trend_strength']

            if momentum['direction'] == 'up' and market_type == 'up':
                # Reduced bonuses
                expected_prob = 0.45 + min(percent_change * 3.5, 0.20) + (trend_strength * 0.10)
            elif momentum['direction'] == 'down' and market_type == 'down':
                expected_prob = 0.45 + min(percent_change * 3.5, 0.20) + (trend_strength * 0.10)
            elif (momentum['direction'] != market_type):
                expected_prob = 0.25  # Reduced from 0.30
            else:
                expected_prob = 0.45  # Reduced from 0.50

        # 3. ABOVE/BELOW Threshold Markets
        elif market_type in ['above', 'below'] and threshold:
            distance_pct = ((threshold - active_price) / active_price) * 100

            if market_type == 'above':
                if active_price >= threshold:
                    expected_prob = 0.60  # Reduced from 0.80
                else:
                    expected_prob = 0.45 - (distance_pct * 0.03)  # Reduced multiplier
                    if momentum['direction'] == 'up':
                        expected_prob += 0.10  # Reduced bonus
            else:  # 'below'
                if active_price <= threshold:
                    expected_prob = 0.60  # Reduced from 0.80
                else:
                    expected_prob = 0.45 + (distance_pct * 0.03)  # Reduced multiplier
                    if momentum['direction'] == 'down':
                        expected_prob += 0.10  # Reduced bonus
        else:
            return None

        # Apply calibration curve based on historical data
        # This maps bot's calculated probability to actual expected win rate
        # Extract direction from momentum
        momentum_direction = momentum.get('direction', 'unknown')
        calibrated_prob = self._apply_calibration_curve(expected_prob, momentum_direction)

        # Clamp to safe bounds
        return max(0.05, min(0.95, calibrated_prob))

    def _apply_calibration_curve(self, raw_prob: float, direction: str = 'down') -> float:
        """
        Apply calibration curve to map bot's probability to actual win rate.

        DYNAMIC CALIBRATION (v2.0):
        - Uses separate curves for UP vs DOWN trends
        - Auto-updates every N days from recent performance data
        - Falls back to static curve if insufficient data

        Based on historical analysis:
        - Raw 0.50-0.60 → Actual ~0.35 (too optimistic)
        - Raw 0.60-0.70 → Actual ~0.45
        - Raw 0.70-0.80 → Actual ~0.55
        - Raw 0.80-0.90 → Actual ~0.65
        - Raw 0.90-0.95 → Actual ~0.75

        Using piecewise linear interpolation for smooth calibration.

        Args:
            raw_prob: Bot's raw calculated probability
            direction: Momentum direction ('up' or 'down')

        Returns:
            Calibrated probability based on actual performance
        """
        # Select appropriate calibration curve based on direction
        if self.separate_curves_by_direction and direction == 'up':
            calibration_points = self.calibration_curve_up
        else:
            calibration_points = self.calibration_curve_down

        # Find the two points to interpolate between
        for i in range(len(calibration_points) - 1):
            x1, y1 = calibration_points[i]
            x2, y2 = calibration_points[i + 1]

            if x1 <= raw_prob <= x2:
                # Linear interpolation
                if x2 - x1 == 0:
                    return y1

                slope = (y2 - y1) / (x2 - x1)
                calibrated = y1 + slope * (raw_prob - x1)
                return calibrated

        # If beyond range, use last point
        return calibration_points[-1][1]

    def _default_calibration_curve(self) -> List[Tuple[float, float]]:
        """
        Return the default static calibration curve.
        Used as fallback when insufficient data for dynamic calibration.
        """
        return [
            (0.00, 0.00),  # Anchor at 0
            (0.50, 0.35),  # Bot says 50%, actually 35%
            (0.60, 0.45),  # Bot says 60%, actually 45%
            (0.70, 0.55),  # Bot says 70%, actually 55%
            (0.80, 0.65),  # Bot says 80%, actually 65%
            (0.90, 0.75),  # Bot says 90%, actually 75%
            (0.95, 0.82),  # Bot says 95%, actually 82%
            (1.00, 0.85),  # Bot says 100%, actually 85%
        ]

    def _maybe_recalibrate(self):
        """
        Check if it's time to recalibrate and update curves if needed.
        Supports schedule, drift, and hybrid modes.
        Called on startup and can be called periodically during runtime.
        """
        if not self.dynamic_recalibration_enabled:
            return

        should_recal = False
        reason = ""

        # Check cooldown (prevent too frequent recalibration)
        hours_since_last = (datetime.now() - self.last_recalibration).total_seconds() / 3600
        if hours_since_last < self.min_recalibration_interval_hours:
            return  # Within cooldown period

        # Mode-specific logic
        if self.recalibration_mode == 'schedule':
            # Fixed schedule only
            should_recal, reason = self._should_recalibrate_schedule()

        elif self.recalibration_mode == 'drift':
            # Drift-based only
            should_recal, reason = self._should_recalibrate_drift()

        elif self.recalibration_mode == 'hybrid':
            # Check both, trigger on either
            should_schedule, schedule_reason = self._should_recalibrate_schedule()
            should_drift, drift_reason = self._should_recalibrate_drift()

            if should_drift:
                should_recal = True
                reason = drift_reason
            elif should_schedule:
                should_recal = True
                reason = schedule_reason

        if should_recal:
            logger.info(f"🔄 Recalibration triggered: {reason}")
            self._recalibrate_from_data()

    def _should_recalibrate_schedule(self) -> tuple:
        """Check if recalibration is due based on fixed schedule"""
        if self.recalibration_mode == 'hybrid':
            days_since_last = (datetime.now() - self.last_recalibration).days
            if days_since_last >= self.max_recalibration_interval_days:
                return True, f"Max interval reached ({days_since_last} days)"
        else:
            days_since_last = (datetime.now() - self.last_recalibration).days
            if days_since_last >= self.recalibration_interval_days:
                return True, f"Scheduled recalibration ({days_since_last} days)"

        return False, ""

    def _should_recalibrate_drift(self) -> tuple:
        """Check if recalibration is due based on performance drift"""
        # Increment trade counter (called from probability calculation)
        # For now, check on every call to _maybe_recalibrate
        # In production, would track trades continuously

        try:
            drift_data = self._calculate_calibration_drift()

            if not drift_data:
                return False, ""

            # Check if either direction has significant drift
            for direction, drift in drift_data.items():
                if drift > self.drift_threshold_percent:
                    return True, f"{direction.upper()} drift {drift*100:.1f}% > {self.drift_threshold_percent*100:.1f}%"

            return False, ""

        except Exception as e:
            logger.warning(f"⚠️ Drift calculation failed: {e}")
            return False, ""

    def _calculate_calibration_drift(self) -> Optional[Dict[str, float]]:
        """
        Calculate drift between calibration curve predictions and actual performance.
        Returns dict with drift percentage for UP and DOWN trends.

        Drift = |Actual WR - Expected WR from calibration curve|

        Example:
          - Calibration says: Bot 70% → Expect 55% WR
          - Last 100 trades: Actual 68% WR
          - Drift = |68% - 55%| = 13%
        """
        try:
            csv_path = 'data/negative_edges/skipped_trades.csv'

            if not os.path.exists(csv_path):
                return None

            # Load recent trades
            df = pd.read_csv(csv_path)

            if len(df) == 0:
                return None

            # Get last N trades
            df = df.tail(self.drift_lookback_trades)

            # Filter to trades with known outcomes
            df = df[df['would_have_won'].notna()]

            if len(df) < self.min_drift_samples:
                return None

            # Convert outcome to boolean
            df['won'] = df['would_have_won'].astype(str).str.lower() == 'true'

            drift_by_direction = {}

            for direction in ['up', 'down']:
                direction_trades = df[df['momentum_direction'] == direction]

                if len(direction_trades) < self.min_drift_samples:
                    drift_by_direction[direction] = 0.0
                    continue

                # Calculate expected WR from calibration curve
                expected_wrs = []
                for _, trade in direction_trades.iterrows():
                    bot_prob = trade.get('bot_probability', 0.5)

                    # Use appropriate calibration curve
                    if direction == 'up':
                        curve = self.calibration_curve_up
                    else:
                        curve = self.calibration_curve_down

                    expected_wr = self._interpolate_curve(curve, bot_prob)
                    expected_wrs.append(expected_wr)

                avg_expected_wr = np.mean(expected_wrs)

                # Calculate actual WR
                actual_wr = direction_trades['won'].mean()

                # Calculate drift
                drift = abs(actual_wr - avg_expected_wr)
                drift_by_direction[direction] = drift

                # Log drift details
                logger.info(f"📊 {direction.upper()} Drift Check (last {len(direction_trades)} trades):")
                logger.info(f"   Expected WR (from curve): {avg_expected_wr*100:.1f}%")
                logger.info(f"   Actual WR: {actual_wr*100:.1f}%")
                logger.info(f"   Drift: {drift*100:.1f}% {'⚠️ THRESHOLD EXCEEDED' if drift > self.drift_threshold_percent else '✓ OK'}")

            return drift_by_direction

        except Exception as e:
            logger.error(f"❌ Drift calculation error: {e}", exc_info=True)
            return None

    def _recalibrate_from_data(self):
        """
        Recalibrate curves from recent performance data in skipped_trades.csv.
        Updates separate curves for UP and DOWN trends if enabled.
        """
        try:
            csv_path = 'data/negative_edges/skipped_trades.csv'

            if not os.path.exists(csv_path):
                logger.warning(f"⚠️ Recalibration skipped: {csv_path} not found")
                return

            # Load recent data
            df = pd.read_csv(csv_path)

            if len(df) == 0:
                logger.warning("⚠️ Recalibration skipped: No data in skipped_trades.csv")
                return

            # Filter to recent lookback window
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff_date = datetime.now() - timedelta(days=self.recalibration_lookback_days)
                df = df[df['timestamp'] >= cutoff_date]

            # Filter to trades with known outcomes
            df = df[df['would_have_won'].notna()]

            if len(df) < self.min_samples_for_recalibration:
                logger.warning(f"⚠️ Recalibration skipped: Only {len(df)} samples (need {self.min_samples_for_recalibration})")
                return

            # Convert would_have_won to boolean
            df['won'] = df['would_have_won'].astype(str).str.lower() == 'true'

            # Recalibrate separately for UP and DOWN if enabled
            if self.separate_curves_by_direction:
                # UP trends
                df_up = df[df['momentum_direction'] == 'up']
                if len(df_up) >= 50:  # Minimum per direction
                    new_curve_up = self._calculate_curve_from_bucket_data(df_up, 'bot_probability', 'won')
                    if new_curve_up and len(new_curve_up) >= 4:
                        old_curve_up = self.calibration_curve_up
                        self.calibration_curve_up = new_curve_up
                        logger.info(f"✅ UP calibration curve UPDATED from {len(df_up)} trades")
                        self._log_curve_comparison(old_curve_up, new_curve_up, "UP")
                    else:
                        logger.warning(f"⚠️ UP curve update failed: insufficient buckets")
                else:
                    logger.warning(f"⚠️ UP curve update skipped: only {len(df_up)} UP trades")

                # DOWN trends
                df_down = df[df['momentum_direction'] == 'down']
                if len(df_down) >= 50:  # Minimum per direction
                    new_curve_down = self._calculate_curve_from_bucket_data(df_down, 'bot_probability', 'won')
                    if new_curve_down and len(new_curve_down) >= 4:
                        old_curve_down = self.calibration_curve_down
                        self.calibration_curve_down = new_curve_down
                        logger.info(f"✅ DOWN calibration curve UPDATED from {len(df_down)} trades")
                        self._log_curve_comparison(old_curve_down, new_curve_down, "DOWN")
                    else:
                        logger.warning(f"⚠️ DOWN curve update failed: insufficient buckets")
                else:
                    logger.warning(f"⚠️ DOWN curve update skipped: only {len(df_down)} DOWN trades")

            else:
                # Single curve for all trends
                new_curve = self._calculate_curve_from_bucket_data(df, 'bot_probability', 'won')
                if new_curve and len(new_curve) >= 4:
                    old_curve = self.calibration_curve_down
                    self.calibration_curve_up = new_curve
                    self.calibration_curve_down = new_curve
                    logger.info(f"✅ Calibration curve UPDATED from {len(df)} trades")
                    self._log_curve_comparison(old_curve, new_curve, "ALL")
                else:
                    logger.warning(f"⚠️ Curve update failed: insufficient buckets")

            self.last_recalibration = datetime.now()

        except Exception as e:
            logger.error(f"❌ Recalibration error: {e}", exc_info=True)
            logger.info("📊 Keeping existing calibration curves")

    def _calculate_curve_from_bucket_data(self, df: pd.DataFrame,
                                          prob_col: str,
                                          outcome_col: str) -> Optional[List[Tuple[float, float]]]:
        """
        Calculate calibration curve from bucketed data.

        Args:
            df: DataFrame with bot probabilities and outcomes
            prob_col: Column name for bot's probability
            outcome_col: Column name for actual outcome (boolean)

        Returns:
            List of (bot_prob, actual_wr) tuples or None if insufficient data
        """
        calibration_points = [(0.00, 0.00)]  # Anchor at 0

        # Define probability buckets
        buckets = [
            (0.50, 0.60),
            (0.60, 0.70),
            (0.70, 0.80),
            (0.80, 0.90),
            (0.90, 0.95),
            (0.95, 1.00),
        ]

        for bucket_min, bucket_max in buckets:
            bucket_data = df[(df[prob_col] >= bucket_min) & (df[prob_col] < bucket_max)]

            if len(bucket_data) >= 10:  # Minimum sample size per bucket
                actual_wr = bucket_data[outcome_col].mean()
                bucket_midpoint = (bucket_min + bucket_max) / 2
                calibration_points.append((bucket_midpoint, actual_wr))

        # Add endpoint if we have high confidence data
        if len(df[df[prob_col] >= 0.95]) >= 10:
            actual_wr = df[df[prob_col] >= 0.95][outcome_col].mean()
            calibration_points.append((1.00, actual_wr))
        else:
            calibration_points.append((1.00, calibration_points[-1][1]))  # Extend last point

        return calibration_points if len(calibration_points) >= 4 else None

    def _log_curve_comparison(self, old_curve: List[Tuple[float, float]],
                              new_curve: List[Tuple[float, float]],
                              direction: str):
        """Log comparison of old vs new calibration curves"""
        logger.info(f"📊 {direction} Calibration Curve Comparison:")

        # Sample at key probability points
        test_probs = [0.55, 0.65, 0.75, 0.85]

        for prob in test_probs:
            old_cal = self._interpolate_curve(old_curve, prob)
            new_cal = self._interpolate_curve(new_curve, prob)
            diff = new_cal - old_cal
            sign = "+" if diff > 0 else ""
            logger.info(f"   Bot {prob*100:.0f}%: {old_cal*100:.1f}% → {new_cal*100:.1f}% ({sign}{diff*100:.1f}%)")

    def _interpolate_curve(self, curve: List[Tuple[float, float]], prob: float) -> float:
        """Helper to interpolate a value from a calibration curve"""
        for i in range(len(curve) - 1):
            x1, y1 = curve[i]
            x2, y2 = curve[i + 1]

            if x1 <= prob <= x2:
                if x2 - x1 == 0:
                    return y1
                slope = (y2 - y1) / (x2 - x1)
                return y1 + slope * (prob - x1)

        return curve[-1][1]
