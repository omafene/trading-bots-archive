"""
Kalshi Hybrid Bot - Main Orchestrator
Unified trading bot that adapts strategy based on entry price range.
"""

import os
import sys
import yaml
import logging
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from kalshi_client import KalshiClient
from simple_spot_feed import SimpleSpotFeed
from volume_analyzer import VolumeAnalyzer
from regime_detector import RegimeDetector
from unified_edge_detector import UnifiedEdgeDetector
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HybridBot:
    """Main trading bot orchestrator."""

    def __init__(self, config_path: str):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize components
        logger.info("🚀 Initializing Kalshi Hybrid Bot...")

        # API Client
        self.client = KalshiClient(self.config)

        # Spot price feed
        self.spot_feed = SimpleSpotFeed(self.config['strategy']['symbols'])

        # Volume analyzer
        self.volume_analyzer = VolumeAnalyzer(self.config)

        # Regime detector
        self.regime_detector = RegimeDetector(self.config)

        # Unified edge detector
        self.edge_detector = UnifiedEdgeDetector(
            config=self.config,
            spot_feed=self.spot_feed,
            volume_analyzer=self.volume_analyzer,
            regime_detector=self.regime_detector
        )

        # Telegram notifier
        self.telegram = TelegramNotifier(self.config)
        self.telegram.set_bot_instance(self)  # Enable command handling

        # State
        self.is_running = False
        self.paused = self.config['bot']['paused']

        logger.info("✅ Hybrid Bot initialized successfully!")
        logger.info(f"   Mode: {self.edge_detector.mode.upper()}")
        logger.info(f"   Symbols: {self.config['strategy']['symbols']}")
        logger.info(f"   Paused: {self.paused}")

    def start(self):
        """Start the trading bot."""

        logger.info("=" * 70)
        logger.info("🎯 KALSHI HYBRID BOT STARTING")
        logger.info("=" * 70)

        self.is_running = True
        scan_interval = self.config['bot']['scan_interval_seconds']

        while self.is_running:
            try:
                if self.paused:
                    logger.info("⏸️  Bot is PAUSED (paper trading mode)")
                    time.sleep(scan_interval)
                    continue

                # Scan for opportunities
                self._scan_cycle()

                # Sleep before next scan
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                logger.info("⚠️  Received stop signal")
                self.stop()
                break

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(scan_interval)

    def _scan_cycle(self):
        """One complete scan cycle."""

        logger.info("\n" + "=" * 70)
        logger.info(f"🔍 SCANNING FOR OPPORTUNITIES - {datetime.utcnow().strftime('%H:%M:%S')}")
        logger.info("=" * 70)

        # Get active markets
        markets = self._get_active_markets()

        if not markets:
            logger.info("   No active markets found")
            return

        logger.info(f"   Found {len(markets)} active 15m markets")

        # Evaluate each market
        opportunities = []

        for market in markets:
            try:
                # Prepare market data
                market_data = self._prepare_market_data(market)

                if not market_data:
                    continue

                # Evaluate through all filters
                opportunity = self.edge_detector.evaluate_opportunity(market_data)

                if opportunity:
                    opportunities.append(opportunity)

                    # Send Telegram notification
                    self.telegram.notify_opportunity_found(opportunity, in_paper_mode=self.paused)

            except Exception as e:
                ticker = market.get('ticker', 'unknown')
                logger.error(f"Error evaluating {ticker}: {e}")
                continue

        # Report results
        logger.info("\n" + "-" * 70)
        logger.info(f"📊 SCAN COMPLETE: {len(opportunities)} opportunities found")

        if opportunities:
            for opp in opportunities:
                logger.info(f"\n   🎯 {opp['ticker']}")
                logger.info(f"      Mode: {opp['mode'].upper()}")
                logger.info(f"      Entry: ${opp['entry_price']:.2f} x {opp['position_size']} = ${opp['total_cost']:.2f}")
                logger.info(f"      Win Prob: {opp['probability']:.1%}")
                logger.info(f"      Expected Value: {opp['expected_value']:.1%}")

            if not self.paused:
                logger.info("\n   📝 TODO: Implement order execution")

        logger.info("=" * 70)

    def _get_active_markets(self):
        """Get all active 15m markets."""

        all_markets = []

        for symbol in self.config['strategy']['symbols']:
            series_ticker = f'KX{symbol}15M'

            try:
                response = self.client._make_request("GET", "/markets", params={
                    "series_ticker": series_ticker,
                    "status": "open",
                    "limit": 100
                })

                if response and 'markets' in response:
                    all_markets.extend(response['markets'])

            except Exception as e:
                logger.error(f"Error fetching markets for {symbol}: {e}")
                continue

        return all_markets

    def _prepare_market_data(self, market: dict) -> dict:
        """Prepare market data for evaluation."""

        try:
            ticker = market['ticker']

            # Get orderbook
            orderbook = self.client.get_orderbook(ticker)

            if not orderbook or not orderbook.get('yes') or not orderbook.get('no'):
                return None

            yes_orders = orderbook['yes']
            no_orders = orderbook['no']

            # Get symbol
            symbol = None
            for s in self.config['strategy']['symbols']:
                if f'KX{s}' in ticker:
                    symbol = s
                    break

            if not symbol:
                return None

            # Get threshold
            threshold = market.get('floor_strike') or market.get('strike_price') or market.get('cap')

            # Parse close time
            close_time_str = market.get('close_time')
            if not close_time_str:
                return None

            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            minutes_to_close = (close_time - datetime.utcnow().replace(tzinfo=close_time.tzinfo)).total_seconds() / 60

            # Update price history for regime detection
            spot_price = self.spot_feed._get_price(symbol)
            if spot_price:
                self.regime_detector.update_price_history(symbol, spot_price)

            # Update volume history
            volume = market.get('volume', 0)
            self.volume_analyzer.update_volume_history(symbol, volume)

            return {
                'ticker': ticker,
                'symbol': symbol,
                'title': market.get('title', ''),
                'close_time': close_time,
                'minutes_to_close': minutes_to_close,
                'yes_bid': yes_orders[-1][0] / 100 if yes_orders else 0,
                'yes_ask': yes_orders[0][0] / 100 if yes_orders else 1,
                'no_bid': no_orders[-1][0] / 100 if no_orders else 0,
                'no_ask': no_orders[0][0] / 100 if no_orders else 1,
                'yes_ask_size': yes_orders[0][1] if yes_orders else 0,
                'no_ask_size': no_orders[0][1] if no_orders else 0,
                'threshold': threshold,
                'volume': volume,
                'orderbook': orderbook
            }

        except Exception as e:
            logger.error(f"Error preparing market data: {e}")
            return None

    def stop(self):
        """Stop the bot gracefully."""

        logger.info("\n🛑 Stopping Hybrid Bot...")
        self.is_running = False
        logger.info("✅ Bot stopped successfully")


def main():
    """Main entry point."""

    config_path = Path(__file__).parent.parent / 'config.yaml'

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    bot = HybridBot(str(config_path))
    bot.start()


if __name__ == "__main__":
    main()
