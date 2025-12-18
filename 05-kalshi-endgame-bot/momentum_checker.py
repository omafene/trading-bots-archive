"""
Slim momentum checker for kalshi_bot.

Maintains a rolling price history per symbol and computes:
  - Linear-regression slope (momentum)
  - R² (trend quality / linearity)
  - percent_change over the lookback window

Mirrors the core logic of kalshi_15m_bot/momentum_analyzer.py without the
calibration engine, OHLC aggregator, or async dependencies.
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MomentumChecker:
    """Rolling price history + momentum / R² calculation."""

    # Maps a substring found in a Kalshi ticker to a spot symbol
    TICKER_SYMBOL_MAP = [
        ('BTC', 'BTC'),
        ('ETH', 'ETH'),
        ('SOL', 'SOL'),
        ('XRP', 'XRP'),
    ]

    # All symbols we track spot prices for
    TRACKED_SYMBOLS = ['BTC', 'ETH', 'SOL', 'XRP']

    def __init__(self, config: Dict):
        strat = config['strategy']
        scan_interval = config['monitoring'].get('scan_interval', 10)

        # Keep 20 min of price history at the current scan rate
        buffer_minutes = 20
        self.max_history_length = int((buffer_minutes * 60) / scan_interval) + 10

        # Filter knobs (read from config)
        self.r_squared_filter_enabled: bool = strat.get('r_squared_filter_enabled', False)
        self.min_r_squared: float = strat.get('min_r_squared', 0.3)
        self.r_squared_lookback_minutes: int = strat.get('r_squared_lookback_minutes', 5)
        self.min_momentum_pct_enabled: bool = strat.get('min_momentum_pct_enabled', False)
        self.min_momentum_pct: Optional[float] = strat.get('min_momentum_pct', None)

        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}

        logger.info(
            f"✅ MomentumChecker initialized — "
            f"R²_filter={self.r_squared_filter_enabled}, "
            f"min_R²={self.min_r_squared}, "
            f"lookback={self.r_squared_lookback_minutes}min, "
            f"min_momentum={self.min_momentum_pct}%"
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @classmethod
    def ticker_to_symbol(cls, ticker: str) -> Optional[str]:
        """Map a Kalshi ticker to a spot symbol, or None if not crypto."""
        ticker_upper = ticker.upper()
        for keyword, symbol in cls.TICKER_SYMBOL_MAP:
            if keyword in ticker_upper:
                return symbol
        return None

    def update_price(self, symbol: str, price: float) -> None:
        """Append one spot price sample to the rolling history."""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        now = datetime.now(timezone.utc)
        self.price_history[symbol].append((now, price))
        # Trim to max_history_length
        if len(self.price_history[symbol]) > self.max_history_length:
            self.price_history[symbol] = self.price_history[symbol][-self.max_history_length:]

    def calculate_momentum(self, symbol: str) -> Optional[Dict]:
        """
        Run linear regression over the last r_squared_lookback_minutes of data.

        Returns a dict with:
            r_squared       — goodness-of-fit [0, 1]
            percent_change  — regression-based % move over the window
            direction       — 'up' | 'down' | 'flat'
            slope           — $/second
            num_samples     — number of data points used

        Returns None if there is not enough data yet.
        """
        if symbol not in self.price_history:
            return None

        now = datetime.now(timezone.utc)
        if self.r_squared_lookback_minutes is None:
            recent = list(self.price_history[symbol])
        else:
            cutoff = now - timedelta(minutes=self.r_squared_lookback_minutes)
            recent = [(ts, p) for ts, p in self.price_history[symbol] if ts >= cutoff]

        if len(recent) < 5:
            logger.debug(f"{symbol}: only {len(recent)} samples in last "
                         f"{self.r_squared_lookback_minutes}min (need 5+)")
            return None

        prices = np.array([p for _, p in recent])
        times = np.array([(ts - recent[0][0]).total_seconds() for ts, _ in recent])

        # Linear regression: price ≈ slope * time + intercept
        slope, intercept = np.polyfit(times, prices, 1)

        # R² — how well does the line fit?
        predictions = slope * times + intercept
        ss_res = np.sum((prices - predictions) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = max(0.0, min(1.0, 1 - ss_res / ss_tot)) if ss_tot > 0 else 0.0

        # % change over the regression window (mirrors 15m bot formula)
        duration_seconds = times[-1]
        start_price = prices[0]
        percent_change = (
            (slope * duration_seconds / start_price) * 100
            if start_price > 0 else 0.0
        )

        if abs(percent_change) < 0.05:
            direction = 'flat'
        elif slope > 0:
            direction = 'up'
        else:
            direction = 'down'

        return {
            'r_squared': r_squared,
            'percent_change': percent_change,
            'direction': direction,
            'slope': slope,
            'num_samples': len(recent),
        }

    def passes_filters(self, ticker: str) -> Tuple[bool, str]:
        """
        Check whether a Kalshi ticker passes the momentum + R² gate.

        Returns (True, "") if:
          - no filters are active, OR
          - ticker is not a crypto market (NASD, HIGH, etc.), OR
          - there's not enough price history yet (don't block — let it through), OR
          - both filters pass.

        Returns (False, reason_string) if any filter rejects the trade.
        """
        filters_active = self.r_squared_filter_enabled or self.min_momentum_pct_enabled
        if not filters_active:
            return True, ""

        symbol = self.ticker_to_symbol(ticker)
        if symbol is None:
            return True, ""  # Not a crypto ticker — no momentum gate

        momentum = self.calculate_momentum(symbol)
        if momentum is None:
            return True, ""  # Still building history — don't block

        r_sq = momentum['r_squared']
        pct = abs(momentum['percent_change'])

        if self.r_squared_filter_enabled and r_sq < self.min_r_squared:
            return False, (
                f"R²={r_sq:.2f} < {self.min_r_squared:.2f} (noisy {symbol} trend)"
            )

        if self.min_momentum_pct_enabled and self.min_momentum_pct and pct < self.min_momentum_pct:
            return False, (
                f"Momentum={pct:.3f}% < {self.min_momentum_pct:.3f}% "
                f"(weak {symbol} trend, dir={momentum['direction']})"
            )

        return True, ""
