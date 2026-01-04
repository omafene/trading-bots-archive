#!/usr/bin/env python3
"""
Negative Edge Tracker - Logs all skipped opportunities for calibration analysis

Tracks skipped trades to identify where bot is too conservative and build
a feedback loop for continuous model improvement.

Features:
- Logs all negative/small edges with full context
- Tracks order book depth (crowd wisdom indicator)
- Records time of day, day of week for temporal patterns
- Captures volatility regime at time of skip
- Enables post-hoc outcome analysis and calibration
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class NegativeEdgeTracker:
    """Track skipped opportunities to calibrate model and improve edge detection"""

    def __init__(self, data_dir="data/negative_edges"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # CSV file for tracking
        self.csv_path = self.data_dir / "skipped_trades.csv"
        self._ensure_csv_exists()
        self._maybe_migrate_columns()

        # Signal analysis CSV — logs full signal data for every executed trade
        self.signal_analysis_path = self.data_dir.parent / "signal_analysis.csv"
        self._ensure_signal_analysis_exists()

        logger.info(f"✅ Negative edge tracker initialized: {self.csv_path}")

    def _ensure_csv_exists(self):
        """Create CSV with headers if doesn't exist"""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    # Identification
                    'timestamp',
                    'ticker',
                    'symbol',
                    'market_type',
                    'threshold',
                    'close_time',
                    'minutes_to_close',

                    # Market State
                    'spot_price',
                    'yes_market_price',
                    'no_market_price',
                    'yes_edge_pct',
                    'no_edge_pct',
                    'best_edge_pct',
                    'best_edge_side',

                    # Bot's Assessment
                    'yes_expected_prob',
                    'no_expected_prob',
                    'signal_strength',
                    'skip_reason',

                    # Momentum Context
                    'momentum_direction',
                    'momentum_pct',
                    'trend_strength',

                    # Crowd Wisdom
                    'order_book_depth_total',
                    'yes_depth',
                    'no_depth',
                    'depth_imbalance',
                    'bid_ask_spread',

                    # Volatility Regime
                    'realized_volatility',
                    'implied_volatility',
                    'vol_ratio',
                    'vol_regime',  # quiet/normal/explosive

                    # Temporal Patterns
                    'hour_of_day',
                    'day_of_week',
                    'time_bucket',  # morning/afternoon/evening

                    # Outcome Tracking
                    'outcome_checked',
                    'actual_outcome',
                    'would_have_won',
                    'theoretical_pnl',
                    'market_final_price',

                    # Advanced Metrics
                    'price_level_bucket',  # cheap/mid/expensive
                    'liquidity_score',
                    'market_efficiency_score',

                    # Signal Components (for validating individual signals)
                    'cex_obi_imbalance',    # CEX order book imbalance (0=bearish, 1=bullish, 0=n/a)
                    'stat_arb_adjustment',  # Stat-arb basis adjustment applied (+/- fraction)

                    # Source tracking
                    'trade_source',         # 'skipped' = hypothetical | 'actual' = real money trade
                ])
            logger.info(f"Created new tracking file: {self.csv_path}")

    def _ensure_signal_analysis_exists(self):
        """Create signal_analysis.csv with full schema if it doesn't exist or is empty."""
        headers = [
            'timestamp', 'ticker', 'symbol', 'side',
            'entry_price', 'edge_percent', 'expected_roi', 'signal_strength',
            'minutes_to_close', 'expected_probability',
            'momentum_pct', 'momentum_direction', 'r_squared', 'trend_strength',
            'depth', 'spread', 'vol_ratio', 'vol_regime', 'ob_imbalance',
            'outcome', 'won', 'pnl',
        ]
        if not self.signal_analysis_path.exists():
            with open(self.signal_analysis_path, 'w', newline='') as f:
                csv.writer(f).writerow(headers)
            logger.info(f"Created signal_analysis.csv: {self.signal_analysis_path}")
            return
        # If file exists but only has a header (empty from old trade_analyzer stub), rewrite header
        try:
            with open(self.signal_analysis_path, 'r') as f:
                existing = csv.reader(f)
                current_headers = next(existing, None)
            if current_headers != headers:
                # Migrate: read existing rows, add missing columns, rewrite
                with open(self.signal_analysis_path, 'r') as f:
                    dr = csv.DictReader(f)
                    existing_rows = list(dr)
                with open(self.signal_analysis_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                    writer.writeheader()
                    for row in existing_rows:
                        writer.writerow(row)
                logger.info(f"Migrated signal_analysis.csv to new schema ({len(existing_rows)} rows preserved)")
        except Exception as e:
            logger.warning(f"Could not migrate signal_analysis.csv: {e}")

    def log_skipped_trade(self, market: dict, reason: str, edge_data: dict = None):
        """
        Log a skipped trade opportunity with full context

        Args:
            market: Market data dict from scanner
            reason: Why skipped (e.g., "Negative Edge", "Low Signal")
            edge_data: Detailed edge calculation data including:
                - yes_edge_pct, no_edge_pct
                - yes_expected_prob, no_expected_prob
                - signal_strength
                - momentum data
                - volatility data
                - orderbook data
        """
        try:
            ticker = market.get('ticker', 'UNKNOWN')

            # Extract market details
            symbol = self._extract_symbol(ticker)
            # Use market data instead of parsing ticker (more reliable)
            market_type = market.get('market_type', 'unknown')
            threshold = market.get('threshold', 0)

            # Parse close time
            # Handle close_time as either datetime object or string
            close_time_raw = market.get('close_time')
            try:
                if isinstance(close_time_raw, datetime):
                    # Already a datetime object
                    close_time = close_time_raw
                elif isinstance(close_time_raw, str) and close_time_raw:
                    # String that needs parsing
                    close_time = datetime.fromisoformat(close_time_raw.replace('Z', '+00:00'))
                else:
                    # None or empty
                    close_time = None

                if close_time:
                    minutes_to_close = (close_time - datetime.now(timezone.utc)).total_seconds() / 60
                else:
                    minutes_to_close = 0
            except Exception as e:
                logger.debug(f"Could not parse close_time: {e}")
                close_time = None
                minutes_to_close = 0

            # Get edge data with defaults
            if edge_data is None:
                edge_data = {}

            yes_edge = edge_data.get('yes_edge_pct', 0)
            no_edge = edge_data.get('no_edge_pct', 0)
            best_edge = max(yes_edge, no_edge)
            best_side = 'yes' if yes_edge > no_edge else 'no'

            yes_price = edge_data.get('yes_price', 0)
            no_price = edge_data.get('no_price', 0)
            yes_prob = edge_data.get('yes_expected_prob', 0)
            no_prob = edge_data.get('no_expected_prob', 0)
            signal = edge_data.get('signal_strength', 0)
            spot = edge_data.get('spot_price', 0)

            # Momentum data
            mom_dir = edge_data.get('momentum_direction', 'unknown')
            mom_pct = edge_data.get('momentum_pct', 0)
            trend_strength = edge_data.get('trend_strength', 0)

            # Orderbook data (crowd wisdom)
            ob_data = edge_data.get('orderbook', {})
            yes_depth = ob_data.get('yes_depth', 0)
            no_depth = ob_data.get('no_depth', 0)
            total_depth = yes_depth + no_depth
            depth_imbalance = ob_data.get('depth_imbalance', 0)
            spread = ob_data.get('bid_ask_spread', 0)

            # Volatility regime
            vol_data = edge_data.get('volatility', {})
            realized_vol = vol_data.get('realized_vol', 0)
            implied_vol = vol_data.get('implied_vol', 0)
            vol_ratio = vol_data.get('vol_ratio', 1.0)
            vol_regime = vol_data.get('regime', 'normal')

            # Temporal patterns
            now = datetime.now(timezone.utc)
            hour = now.hour
            day_of_week = now.strftime('%A')

            # Time bucket
            if 0 <= hour < 12:
                time_bucket = 'morning'
            elif 12 <= hour < 18:
                time_bucket = 'afternoon'
            else:
                time_bucket = 'evening'

            # Price level bucket
            avg_price = (yes_price + no_price) / 2 if (yes_price + no_price) > 0 else 0.5
            if avg_price < 0.30:
                price_bucket = 'cheap'
            elif avg_price < 0.70:
                price_bucket = 'mid'
            else:
                price_bucket = 'expensive'

            # Liquidity score (simple: based on depth and spread)
            liquidity_score = self._calculate_liquidity_score(total_depth, spread)

            # Market efficiency score (how well-priced is this market?)
            efficiency_score = self._calculate_efficiency_score(spread, total_depth, abs(depth_imbalance))

            # Signal component values (for validating CEX OBI and stat-arb signals)
            cex_obi_imbalance = edge_data.get('cex_obi_imbalance', 0.0)
            stat_arb_adjustment = edge_data.get('stat_arb_adjustment', 0.0)

            # Write to CSV
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    # Identification
                    now.isoformat(),
                    ticker,
                    symbol,
                    market_type,
                    threshold,
                    close_time.isoformat() if close_time else '',
                    round(minutes_to_close, 1),

                    # Market State
                    round(spot, 2),
                    round(yes_price, 4),
                    round(no_price, 4),
                    round(yes_edge, 2),
                    round(no_edge, 2),
                    round(best_edge, 2),
                    best_side,

                    # Bot's Assessment
                    round(yes_prob, 4),
                    round(no_prob, 4),
                    round(signal, 1),
                    reason,

                    # Momentum
                    mom_dir,
                    round(mom_pct, 2),
                    round(trend_strength, 2),

                    # Crowd Wisdom
                    int(total_depth),
                    int(yes_depth),
                    int(no_depth),
                    round(depth_imbalance, 3),
                    round(spread, 4),

                    # Volatility
                    round(realized_vol, 4),
                    round(implied_vol, 4),
                    round(vol_ratio, 2),
                    vol_regime,

                    # Temporal
                    hour,
                    day_of_week,
                    time_bucket,

                    # Outcome (empty for now)
                    'False',  # outcome_checked
                    '',       # actual_outcome
                    '',       # would_have_won
                    0,        # theoretical_pnl
                    0,        # market_final_price

                    # Advanced
                    price_bucket,
                    round(liquidity_score, 2),
                    round(efficiency_score, 2),

                    # Signal Components
                    round(cex_obi_imbalance, 4) if cex_obi_imbalance else 0.0,
                    round(stat_arb_adjustment, 4),

                    # Source
                    'skipped',
                ])

            logger.debug(f"📝 Logged skipped: {ticker} ({reason}) - Best edge: {best_edge:.1f}% ({best_side})")

        except Exception as e:
            logger.error(f"Error logging skipped trade: {e}", exc_info=True)

    def log_actual_trade(self, opportunity: dict):
        """
        Log a trade the bot actually placed, using the same CSV as skipped trades.

        trade_source = 'actual' distinguishes these from hypothetical skipped entries.
        Outcome fields are left blank and filled later by OutcomeChecker, exactly
        like skipped trades.  The calibration engine then sees real-money outcomes
        alongside hypothetical ones when computing bucket probabilities.

        Args:
            opportunity: The opportunity dict returned by AdvancedEdgeDetector.analyze_market()
        """
        try:
            ticker = opportunity.get('ticker', 'UNKNOWN')
            symbol = opportunity.get('symbol', self._extract_symbol(ticker))
            market_type = opportunity.get('market_type', 'unknown')
            threshold = opportunity.get('threshold', 0)

            close_time_raw = opportunity.get('close_time')
            try:
                if isinstance(close_time_raw, datetime):
                    close_time = close_time_raw
                elif isinstance(close_time_raw, str) and close_time_raw:
                    close_time = datetime.fromisoformat(close_time_raw.replace('Z', '+00:00'))
                else:
                    close_time = None
                minutes_to_close = (close_time - datetime.now(timezone.utc)).total_seconds() / 60 if close_time else 0
            except Exception:
                close_time = None
                minutes_to_close = 0

            side = opportunity.get('recommended_side', 'yes')
            entry = opportunity.get('entry_price', 0)
            yes_price = opportunity.get('yes_ask', 0)
            no_price = opportunity.get('no_ask', 0)
            final_prob = opportunity.get('expected_probability', 0)
            yes_prob = final_prob if side == 'yes' else 1.0 - final_prob
            no_prob = 1.0 - yes_prob
            edge = opportunity.get('edge_percent', 0)
            yes_edge = edge if side == 'yes' else 0
            no_edge = edge if side == 'no' else 0
            signal = opportunity.get('signal_strength', 0)
            spot = opportunity.get('spot_price') or 0

            momentum = opportunity.get('momentum', {})
            mom_dir = momentum.get('direction', 'unknown')
            mom_pct = momentum.get('percent_change', 0)
            trend_strength = momentum.get('trend_strength', 0)
            realized_vol = momentum.get('volatility', 0)

            yes_depth = opportunity.get('yes_ask_size', 0)
            no_depth = opportunity.get('no_ask_size', 0)
            total_depth = yes_depth + no_depth
            spread = yes_price - opportunity.get('yes_bid', yes_price)

            vol_breakdown = opportunity.get('signal_breakdown', {}).get('vol_signal') or {}
            implied_vol = vol_breakdown.get('implied_vol', 0)
            vol_ratio = vol_breakdown.get('vol_ratio', 1.0)
            vol_regime = vol_breakdown.get('regime', 'normal')

            cex_obi = opportunity.get('ob_imbalance') or 0.0
            stat_arb = opportunity.get('signal_breakdown', {}).get('stat_arb_adjustment', 0)

            now = datetime.now(timezone.utc)
            hour = now.hour
            day_of_week = now.strftime('%A')
            time_bucket = 'morning' if hour < 12 else ('afternoon' if hour < 18 else 'evening')

            avg_price = (yes_price + no_price) / 2 if (yes_price + no_price) > 0 else 0.5
            price_bucket = 'cheap' if avg_price < 0.30 else ('expensive' if avg_price >= 0.70 else 'mid')
            liquidity_score = self._calculate_liquidity_score(total_depth, spread)
            efficiency_score = self._calculate_efficiency_score(spread, total_depth, 0)

            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    now.isoformat(), ticker, symbol, market_type, threshold,
                    close_time.isoformat() if close_time else '', round(minutes_to_close, 1),
                    round(spot, 2), round(yes_price, 4), round(no_price, 4),
                    round(yes_edge, 2), round(no_edge, 2), round(edge, 2), side,
                    round(yes_prob, 4), round(no_prob, 4), round(signal, 1), 'TRADED',
                    mom_dir, round(mom_pct, 4), round(trend_strength, 4),
                    int(total_depth), int(yes_depth), int(no_depth), 0, round(spread, 4),
                    round(realized_vol, 4), round(implied_vol, 4), round(vol_ratio, 2), vol_regime,
                    hour, day_of_week, time_bucket,
                    'False', '', '', 0, 0,
                    price_bucket, round(liquidity_score, 2), round(efficiency_score, 2),
                    round(cex_obi, 4), round(stat_arb, 4),
                    'actual',
                ])

            logger.info(f"📝 Logged actual trade: {ticker} ({side.upper()} @ {entry:.0%}) for calibration")

            # Also write to signal_analysis.csv with full signal detail for post-analysis
            try:
                r_squared = momentum.get('r_squared', 0)
                with open(self.signal_analysis_path, 'a', newline='') as f:
                    csv.writer(f).writerow([
                        now.isoformat(), ticker, symbol, side,
                        round(entry, 4), round(edge, 2), round(opportunity.get('expected_roi', 0), 2),
                        round(signal, 1),
                        round(minutes_to_close, 1), round(final_prob, 4),
                        round(mom_pct, 4), mom_dir, round(r_squared, 4), round(trend_strength, 4),
                        int(total_depth), round(spread, 4),
                        round(vol_ratio, 2), vol_regime, round(cex_obi, 4),
                        '', '', '',  # outcome, won, pnl — filled by update_outcome()
                    ])
                logger.debug(f"📊 Signal logged to signal_analysis.csv: {ticker}")
            except Exception as sig_e:
                logger.warning(f"Could not write to signal_analysis.csv: {sig_e}")

        except Exception as e:
            logger.error(f"Error logging actual trade: {e}", exc_info=True)

    def _maybe_migrate_columns(self):
        """Add new signal-component columns to existing CSV files that predate them."""
        new_cols = ['cex_obi_imbalance', 'stat_arb_adjustment', 'trade_source']
        if not self.csv_path.exists():
            return
        try:
            with open(self.csv_path, 'r', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
            if not headers or all(c in headers for c in new_cols):
                return  # File empty or already up to date

            # Read everything, add missing columns, write back
            with open(self.csv_path, 'r', newline='') as f:
                dr = csv.DictReader(f)
                old_fields = dr.fieldnames or []
                rows = list(dr)

            extra = [c for c in new_cols if c not in old_fields]
            new_fields = old_fields + extra
            # Default values for migrated columns on existing rows
            col_defaults = {'trade_source': 'skipped'}
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=new_fields)
                writer.writeheader()
                for row in rows:
                    for col in extra:
                        row[col] = col_defaults.get(col, '')
                    writer.writerow(row)
            logger.info(f"Migrated {self.csv_path}: added columns {extra} ({len(rows):,} rows preserved)")
        except Exception as e:
            logger.warning(f"CSV migration skipped: {e}")

    def _calculate_liquidity_score(self, depth: float, spread: float) -> float:
        """
        Calculate liquidity score 0-100

        Higher score = more liquid (easier to trade)
        """
        # Depth component (0-50 points)
        depth_score = min(depth / 20, 50)  # 1000+ depth = max 50 points

        # Spread component (0-50 points)
        spread_score = max(0, 50 - (spread * 500))  # 0.10 spread = 0 points

        return depth_score + spread_score

    def _calculate_efficiency_score(self, spread: float, depth: float, imbalance: float) -> float:
        """
        Calculate market efficiency score 0-100

        Higher score = more efficient pricing (trust market more)
        """
        # Tight spread = efficient
        spread_score = max(0, 40 - (spread * 400))  # 0-40 points

        # High depth = efficient
        depth_score = min(depth / 25, 30)  # 0-30 points

        # Balanced order book = efficient
        balance_score = max(0, 30 - (abs(imbalance) * 60))  # 0-30 points

        return spread_score + depth_score + balance_score

    def _extract_symbol(self, ticker: str) -> str:
        """Extract symbol from ticker"""
        if 'BTC' in ticker.upper():
            return 'BTC'
        elif 'ETH' in ticker.upper():
            return 'ETH'
        elif 'SOL' in ticker.upper():
            return 'SOL'
        elif 'XRP' in ticker.upper():
            return 'XRP'
        return 'UNKNOWN'

    def _extract_market_info(self, ticker: str):
        """Extract market type and threshold from ticker"""
        import re

        # Market type
        if '-A' in ticker or 'ABOVE' in ticker.upper():
            market_type = 'above'
        elif '-B' in ticker or 'BELOW' in ticker.upper():
            market_type = 'below'
        else:
            market_type = 'unknown'

        # Threshold
        match = re.search(r'[AB](\d+)', ticker)
        if match:
            threshold = float(match.group(1))
        else:
            threshold = 0

        return market_type, threshold

    def get_pending_outcomes(self):
        """Get all trades that need outcome checking (markets that have closed)"""
        pending = []

        try:
            if not self.csv_path.exists():
                return pending

            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['outcome_checked'] == 'False' and row['close_time']:
                        # Check if market has closed
                        try:
                            close_time = datetime.fromisoformat(row['close_time'])
                            if datetime.now(timezone.utc) > close_time:
                                pending.append(row)
                        except:
                            continue
        except Exception as e:
            logger.error(f"Error reading pending outcomes: {e}")

        return pending

    def update_outcome(self, ticker: str, actual_outcome: str, market_final_price: float = None):
        """
        Update the outcome for a skipped trade after market closes

        Args:
            ticker: Market ticker
            actual_outcome: 'yes' or 'no'
            market_final_price: Final settlement price (0 or 1.0)
        """
        try:
            # Read all rows
            rows = []
            if not self.csv_path.exists():
                return

            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Update matching rows
            update_count = 0
            would_have = None
            for row in rows:
                if row['ticker'] == ticker and row['outcome_checked'] == 'False':
                    row['outcome_checked'] = 'True'
                    row['actual_outcome'] = actual_outcome.lower()
                    row['market_final_price'] = market_final_price if market_final_price else 1.0 if actual_outcome.lower() == 'yes' else 0.0

                    # Determine if we would have won
                    best_side = row['best_edge_side']
                    row['would_have_won'] = 'True' if best_side == actual_outcome.lower() else 'False'

                    # Calculate theoretical P&L
                    if row['would_have_won'] == 'True':
                        # Won: profit = (1 - entry_price) * position_size
                        entry_price = float(row[f'{best_side}_market_price'])
                        position_size = 50  # Assume $50 position
                        profit = (1.0 - entry_price) * position_size
                        row['theoretical_pnl'] = round(profit, 2)
                    else:
                        # Lost: lose entire position
                        row['theoretical_pnl'] = -50

                    would_have = 'WON' if row['would_have_won'] == 'True' else 'LOST'
                    update_count += 1

            # Log once per ticker (not once per CSV row)
            updated = update_count > 0
            if updated:
                logger.info(f"✅ Updated outcome: {ticker} → {actual_outcome} (Would have {would_have}) [{update_count} rows]")

            # Write back to skipped_trades.csv
            if updated:
                with open(self.csv_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

            # Also update signal_analysis.csv for any matching actual-trade rows
            self._update_signal_analysis_outcome(ticker, actual_outcome, market_final_price)

        except Exception as e:
            logger.error(f"Error updating outcome: {e}", exc_info=True)

    def _update_signal_analysis_outcome(self, ticker: str, actual_outcome: str, market_final_price: float = None):
        """Fill outcome/won/pnl columns in signal_analysis.csv for a settled ticker."""
        try:
            if not self.signal_analysis_path.exists():
                return
            with open(self.signal_analysis_path, 'r') as f:
                dr = csv.DictReader(f)
                headers = dr.fieldnames or []
                rows = list(dr)

            updated = False
            for row in rows:
                if row['ticker'] == ticker and not row.get('outcome'):
                    row['outcome'] = actual_outcome.lower()
                    side = row.get('side', '')
                    row['won'] = 'True' if side == actual_outcome.lower() else 'False'
                    if row['won'] == 'True':
                        entry = float(row.get('entry_price', 0) or 0)
                        row['pnl'] = round((1.0 - entry) * 50, 2)  # approx $50 position
                    else:
                        entry = float(row.get('entry_price', 0) or 0)
                        row['pnl'] = round(-entry * 50, 2)
                    updated = True

            if updated:
                with open(self.signal_analysis_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
                logger.debug(f"📊 signal_analysis.csv outcome updated: {ticker} → {actual_outcome}")
        except Exception as e:
            logger.warning(f"Could not update signal_analysis.csv outcome for {ticker}: {e}")

    def get_stats(self):
        """Get summary statistics"""
        stats = {
            'total_tracked': 0,
            'outcomes_checked': 0,
            'pending_outcomes': 0
        }

        try:
            if not self.csv_path.exists():
                return stats

            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total_tracked'] += 1
                    if row['outcome_checked'] == 'True':
                        stats['outcomes_checked'] += 1
                    elif row['close_time']:
                        try:
                            close_time = datetime.fromisoformat(row['close_time'])
                            if datetime.now(timezone.utc) > close_time:
                                stats['pending_outcomes'] += 1
                        except:
                            pass
        except Exception as e:
            logger.error(f"Error getting stats: {e}")

        return stats
