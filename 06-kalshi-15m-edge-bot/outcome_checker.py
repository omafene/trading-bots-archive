#!/usr/bin/env python3
"""
Outcome Checker - Verifies market results after close

Queries Kalshi API to determine actual outcomes of tracked markets,
enabling calibration analysis and model improvement.
"""

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class OutcomeChecker:
    """Check outcomes of closed markets to validate model predictions"""

    def __init__(self, client, tracker):
        """
        Initialize outcome checker

        Args:
            client: KalshiClient instance
            tracker: NegativeEdgeTracker instance
        """
        self.client = client
        self.tracker = tracker
        self.last_check_time = 0

    def check_pending_outcomes(self, max_checks=20, stop_flag=None):
        """
        Check outcomes for all closed markets that haven't been checked yet

        Args:
            max_checks: Maximum number of markets to check per call (rate limiting)

        Returns:
            Number of outcomes checked
        """
        try:
            pending = self.tracker.get_pending_outcomes()

            if not pending:
                logger.debug("No pending outcomes to check")
                return 0

            # Deduplicate by ticker — same market can have many CSV rows (one per scan cycle)
            seen_tickers = set()
            unique_pending = []
            for row in pending:
                if row['ticker'] not in seen_tickers:
                    seen_tickers.add(row['ticker'])
                    unique_pending.append(row)

            logger.info(f"📊 Checking outcomes for {len(unique_pending)} closed markets ({len(pending)} total rows)...")

            checked_count = 0
            for i, row in enumerate(unique_pending[:max_checks]):
                if stop_flag is not None and not stop_flag():
                    logger.info("Outcome check interrupted (bot stopping)")
                    break

                ticker = row['ticker']

                # Rate limiting
                if i > 0 and i % 5 == 0:
                    time.sleep(1)  # Pause every 5 requests

                # Get market result
                outcome = self.get_market_result(ticker)

                if outcome:
                    # Update tracker
                    self.tracker.update_outcome(ticker, outcome)
                    checked_count += 1
                else:
                    logger.warning(f"Could not determine outcome for {ticker}")

            logger.info(f"✅ Checked {checked_count} outcomes")
            return checked_count

        except Exception as e:
            logger.error(f"Error checking pending outcomes: {e}", exc_info=True)
            return 0

    def get_market_result(self, ticker: str):
        """
        Query Kalshi for market settlement result

        Args:
            ticker: Market ticker

        Returns:
            'yes' or 'no', or None if cannot determine
        """
        try:
            # Get market details
            market = self.client.get_market(ticker)

            if not market:
                logger.debug(f"Market not found: {ticker}")
                return None

            # Check market status
            status = market.get('status', '').lower()

            if status not in ['closed', 'settled', 'finalized']:
                logger.debug(f"Market {ticker} not settled yet (status: {status})")
                return None

            # Get settlement value
            # Kalshi uses different fields depending on market type
            result = market.get('result')
            if result:
                result_lower = result.lower()
                if result_lower in ['yes', 'true', '1']:
                    return 'yes'
                elif result_lower in ['no', 'false', '0']:
                    return 'no'

            # Alternative: check settle_value or final price
            settle_value = market.get('settle_value')
            if settle_value is not None:
                if settle_value == 1 or settle_value == 100:
                    return 'yes'
                elif settle_value == 0:
                    return 'no'

            # Alternative: check last_price (for binary markets, 0 or 100)
            last_price = market.get('last_price')
            if last_price is not None:
                if last_price >= 99:  # YES settled
                    return 'yes'
                elif last_price <= 1:  # NO settled
                    return 'no'

            logger.warning(f"Could not parse settlement for {ticker}: {market.get('result')}")
            return None

        except Exception as e:
            logger.error(f"Error getting market result for {ticker}: {e}")
            return None

    def run_periodic_check(self, interval_seconds=3600):
        """
        Run periodic outcome checking (call from main bot loop)

        Args:
            interval_seconds: How often to check (default: 1 hour)

        Returns:
            Number of outcomes checked, or 0 if not time yet
        """
        now = time.time()

        if now - self.last_check_time < interval_seconds:
            return 0  # Not time yet

        self.last_check_time = now

        logger.info("⏰ Running periodic outcome check...")
        return self.check_pending_outcomes()
