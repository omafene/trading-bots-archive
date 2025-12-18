"""
Kalshi Endgame Sweep Bot - DUAL MODE VERSION
Supports both continuous scanning and clock-synchronized reset scanning
"""

import yaml
import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from kalshi_client import KalshiClient
from market_scanner import MarketScanner
from risk_manager import RiskManager
from position_manager import PositionManager
from telegram_notifier import TelegramNotifier
from spot_price_feed import SpotPriceFeed
from momentum_checker import MomentumChecker

def setup_logging(config: dict):
    log_level = config['monitoring']['log_level']
    log_file = config['monitoring']['log_file']
    Path(log_file).parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
    )

class EndgameSweepBot:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        setup_logging(self.config)
        self.logger = logging.getLogger(__name__)
        self.telegram = TelegramNotifier(self.config, bot_controller=self)
        self.client = KalshiClient(self.config)

        self.position_manager = PositionManager(self.client, self.config, self.telegram)
        self.risk_manager = RiskManager(self.config, self.telegram)

        # Spot price feed + momentum checker (mirrors kalshi_15m_bot setup)
        self.spot_feed = SpotPriceFeed()
        self.momentum_checker = MomentumChecker(self.config)
        self.scanner = MarketScanner(self.client, self.config,
                                     momentum_checker=self.momentum_checker)

        self.running = False
        self.paused = False

    def start(self):
        if not self.client.authenticate():
            self.logger.error("Auth failed")
            return
        if self.telegram.enabled:
            self.telegram.start_command_listener()
        self.running = True
        self.run_loop()

    def run_loop(self):
        """Main bot loop - dispatches to continuous or reset mode"""
        scan_mode = self.config['monitoring'].get('scan_mode', 'continuous')

        if scan_mode == 'reset':
            self.logger.info("🔥 CLOCK-SYNCHRONIZED MODE: Scanning first 60s of each 15-min cycle")
            self._run_reset_mode_loop()
        else:
            self.logger.info("📊 CONTINUOUS MODE: Scanning at regular intervals")
            self._run_continuous_mode_loop()

    def _run_continuous_mode_loop(self):
        """
        Continuous scanning mode (current 45-min endgame strategy)
        Scans every scan_interval seconds continuously
        """
        scan_interval = self.config['monitoring'].get('scan_interval', 60)
        order_check_interval = self.config['monitoring'].get('order_check_interval', 300)

        last_scan_time = 0
        last_order_check_time = 0
        iteration = 0

        self.logger.info("="*60)
        self.logger.info("🚀 BOT STARTED - CONTINUOUS MODE")
        self.logger.info("="*60)
        self.logger.info(f"Trading cycle: {scan_interval}s (scan + trade)")
        self.logger.info(f"Cleanup cycle: {order_check_interval}s ({order_check_interval/60:.0f} min - cancel orders)")
        self.logger.info("="*60)

        while self.running:
            try:
                iteration += 1
                now = time.time()

                # ============================================================
                # TRADING CYCLE (every scan_interval)
                # ============================================================
                if now - last_scan_time >= scan_interval:
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"📈 TRADING CYCLE #{iteration}")
                    self.logger.info("="*60)

                    # Step 0: Update spot price history for momentum filter
                    self._update_spot_prices()

                    # Step 1: Sync positions FIRST
                    self.position_manager.sync_with_exchange()

                    # Step 2: Get resting orders
                    resting_orders = self._get_resting_orders()

                    # Step 3: Scan for opportunities
                    scan_start = time.time()
                    opportunities = self.scanner.scan_opportunities()
                    scan_time = time.time() - scan_start

                    self.logger.info(f"✅ Scan complete in {scan_time:.1f}s")
                    self.logger.info(f"📊 Found {len(opportunities)} opportunities")

                    if opportunities:
                        summary = self.scanner.get_market_summary(opportunities)
                        self.logger.info(f"   Categories: {summary.get('categories', {})}")
                        self.logger.info(f"   Avg probability: {summary.get('avg_probability', 0):.1%}")

                    # Step 4: Get current balance and positions
                    balance = self.client.get_balance()
                    open_positions = self.position_manager.get_open_positions()

                    self.logger.info(f"💰 Balance: ${balance:,.2f}")
                    self.logger.info(f"📊 Positions: {len(open_positions)} | Resting: {len(resting_orders)}")

                    # Step 5: Filter duplicates
                    filtered_opps = self._filter_duplicates(
                        opportunities,
                        open_positions,
                        resting_orders
                    )

                    skipped = len(opportunities) - len(filtered_opps)
                    if skipped > 0:
                        self.logger.info(f"⏭️ Skipped {skipped} duplicates")

                    # Step 6: Process unique opportunities
                    if filtered_opps and not self.paused:
                        self.logger.info(f"📈 Processing {len(filtered_opps)} unique opportunities...")
                        self._process_opportunities(filtered_opps, open_positions, balance)
                    elif self.paused:
                        self.logger.info("⏸️ Bot is PAUSED")
                    elif not filtered_opps and opportunities:
                        self.logger.info("✅ All opportunities filtered as duplicates")

                    last_scan_time = now
                    self.logger.info(f"⏰ Next trading cycle in {scan_interval}s")

                # ============================================================
                # CLEANUP CYCLE (every order_check_interval)
                # ============================================================
                if now - last_order_check_time >= order_check_interval:
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"🧹 CLEANUP CYCLE")
                    self.logger.info("="*60)

                    cancelled = self.position_manager.cancel_all_resting_orders()
                    self.position_manager.sync_with_exchange()

                    balance = self.client.get_balance()
                    open_positions = self.position_manager.get_open_positions()
                    metrics = self.risk_manager.get_portfolio_metrics(open_positions, balance)

                    self.logger.info(f"💰 Portfolio Status:")
                    self.logger.info(f"   Cash Balance: ${balance:,.2f}")
                    self.logger.info(f"   Open Positions: {len(open_positions)}")
                    self.logger.info(f"   Total Deployed: ${metrics['total_deployed']:,.2f}")

                    last_order_check_time = now
                    self.logger.info(f"⏰ Next cleanup in {order_check_interval/60:.0f} minutes")

                # Sleep
                time.sleep(10)

            except KeyboardInterrupt:
                self.logger.info("\n🛑 Keyboard interrupt received")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"❌ Loop Error: {e}", exc_info=True)
                time.sleep(60)

        self.logger.info("👋 Bot stopped")

    def _run_reset_mode_loop(self):
        """
        Clock-synchronized scanning for 15-min reset markets
        Scans every 5 seconds for first 60 seconds of each 15-min cycle
        Then sleeps until next cycle
        """
        reset_interval = self.config['monitoring'].get('reset_interval', 900)  # 15 min
        scan_window = self.config['monitoring'].get('reset_scan_window', 60)   # 60 sec
        scan_freq = self.config['monitoring'].get('reset_scan_frequency', 5)   # 5 sec
        order_check_interval = self.config['monitoring'].get('order_check_interval', 300)

        last_order_check_time = 0
        iteration = 0

        self.logger.info("="*60)
        self.logger.info("🚀 BOT STARTED - RESET MODE")
        self.logger.info("="*60)
        self.logger.info(f"Reset interval: {reset_interval}s ({reset_interval/60:.0f} min)")
        self.logger.info(f"Scan window: {scan_window}s (first {scan_window}s of each cycle)")
        self.logger.info(f"Scan frequency: Every {scan_freq}s during window")
        self.logger.info("="*60)

        while self.running:
            try:
                iteration += 1
                now_dt = datetime.now(timezone.utc)
                now = time.time()

                # Calculate position in current cycle
                minutes = now_dt.minute
                seconds = now_dt.second

                # Check if at reset boundary (00, 15, 30, 45)
                minutes_into_cycle = minutes % (reset_interval / 60)
                seconds_into_cycle = (minutes_into_cycle * 60) + seconds

                # Are we in the scan window? (first 60 seconds of cycle)
                if seconds_into_cycle < scan_window:

                    self.logger.info(f"\n🔥 RESET WINDOW - {seconds_into_cycle:.0f}s into cycle")

                    # ============================================================
                    # TRADING CYCLE (during reset window)
                    # ============================================================
                    self.logger.info("="*60)
                    self.logger.info(f"📈 TRADING CYCLE #{iteration}")
                    self.logger.info("="*60)

                    # Update spot price history for momentum filter
                    self._update_spot_prices()

                    # Sync positions
                    self.position_manager.sync_with_exchange()

                    # Get resting orders
                    resting_orders = self._get_resting_orders()

                    # Scan for opportunities
                    scan_start = time.time()
                    opportunities = self.scanner.scan_opportunities()
                    scan_time = time.time() - scan_start

                    self.logger.info(f"✅ Scan complete in {scan_time:.1f}s")
                    self.logger.info(f"📊 Found {len(opportunities)} opportunities")

                    if opportunities:
                        summary = self.scanner.get_market_summary(opportunities)
                        self.logger.info(f"   Categories: {summary.get('categories', {})}")
                        self.logger.info(f"   Avg probability: {summary.get('avg_probability', 0):.1%}")

                    # Get current state
                    balance = self.client.get_balance()
                    open_positions = self.position_manager.get_open_positions()

                    self.logger.info(f"💰 Balance: ${balance:,.2f}")
                    self.logger.info(f"📊 Positions: {len(open_positions)} | Resting: {len(resting_orders)}")

                    # Filter duplicates
                    filtered_opps = self._filter_duplicates(
                        opportunities,
                        open_positions,
                        resting_orders
                    )

                    skipped = len(opportunities) - len(filtered_opps)
                    if skipped > 0:
                        self.logger.info(f"⏭️ Skipped {skipped} duplicates")

                    # Process opportunities
                    if filtered_opps and not self.paused:
                        self.logger.info(f"📈 Processing {len(filtered_opps)} opportunities...")
                        self._process_opportunities(filtered_opps, open_positions, balance)
                    elif self.paused:
                        self.logger.info("⏸️ Bot is PAUSED")

                    # Wait for next scan within window
                    self.logger.info(f"⏰ Next scan in {scan_freq}s")
                    time.sleep(scan_freq)

                else:
                    # ============================================================
                    # OUTSIDE SCAN WINDOW - Manage positions only
                    # ============================================================

                    # Calculate time until next reset
                    time_until_next = reset_interval - seconds_into_cycle

                    if iteration % 10 == 0:  # Log every 10 iterations
                        self.logger.info(f"💤 Outside scan window. Next reset in {time_until_next:.0f}s ({time_until_next/60:.1f}m)")

                    # Check if should cancel orders
                    if now - last_order_check_time >= order_check_interval:
                        self.logger.info("\n" + "="*60)
                        self.logger.info("🧹 CLEANUP CYCLE")
                        self.logger.info("="*60)

                        cancelled = self.position_manager.cancel_all_resting_orders()
                        self.position_manager.sync_with_exchange()

                        balance = self.client.get_balance()
                        open_positions = self.position_manager.get_open_positions()
                        metrics = self.risk_manager.get_portfolio_metrics(open_positions, balance)

                        self.logger.info(f"💰 Portfolio Status:")
                        self.logger.info(f"   Cash Balance: ${balance:,.2f}")
                        self.logger.info(f"   Open Positions: {len(open_positions)}")
                        self.logger.info(f"   Total Deployed: ${metrics['total_deployed']:,.2f}")

                        last_order_check_time = now
                        self.logger.info(f"⏰ Next cleanup in {order_check_interval/60:.0f} minutes")

                    # Sleep longer outside scan window
                    sleep_time = min(30, time_until_next)
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                self.logger.info("\n🛑 Keyboard interrupt received")
                self.running = False
                break

            except Exception as e:
                self.logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(10)

        self.logger.info("👋 Bot stopped")

    def _process_opportunities(self, opportunities, current_positions, balance):
        executed = 0
        for opp in opportunities[:5]:
            can_open, _ = self.risk_manager.can_open_position(opp, current_positions, balance)
            if can_open:
                size = self.risk_manager.calculate_position_size(opp, balance)
                if self.position_manager.open_position(opp, size):
                    executed += 1
        self.logger.info(f"✅ Executed {executed} trades.")

    def _get_resting_orders(self) -> list:
        """Get all resting orders to prevent duplicates"""
        try:
            response = self.client._make_request("GET", "/portfolio/orders",
                                                params={"status": "resting"})
            orders = response.get('orders', []) if response else []

            # Extract ticker info
            resting_list = []
            for order in orders:
                ticker = order.get('ticker')
                if ticker:
                    resting_list.append({
                        'ticker': ticker,
                        'side': order.get('side'),
                        'count': order.get('count')
                    })

            return resting_list

        except Exception as e:
            self.logger.error(f"Error getting resting orders: {e}")
            return []

    def _filter_duplicates(self, opportunities, positions, resting_orders) -> list:
        """Remove opportunities we already have positions/orders for"""

        # Build sets of tickers we already have
        position_tickers = {pos.get('ticker') for pos in positions if pos.get('ticker')}
        resting_tickers = {order.get('ticker') for order in resting_orders if order.get('ticker')}
        all_existing = position_tickers | resting_tickers

        if all_existing:
            self.logger.debug(f"Filtering against {len(all_existing)} existing tickers")

        # Filter out duplicates
        filtered = []
        for opp in opportunities:
            ticker = opp.get('ticker')

            if ticker in all_existing:
                in_pos = ticker in position_tickers
                in_rest = ticker in resting_tickers
                self.logger.debug(f"⏭️ Skip {ticker} (Pos:{in_pos} Rest:{in_rest})")
            else:
                filtered.append(opp)

        return filtered

    def _update_spot_prices(self):
        """Fetch current spot prices and push them into the momentum checker's history."""
        for symbol in MomentumChecker.TRACKED_SYMBOLS:
            price = self.spot_feed.get_price(symbol)
            if price:
                self.momentum_checker.update_price(symbol, price)
                self.logger.debug(f"  {symbol}: ${price:,.2f}")

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True
        return True

    def resume(self):
        self.paused = False
        return True

if __name__ == "__main__":
    EndgameSweepBot().start()
