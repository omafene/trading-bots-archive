"""
Kalshi 15-Minute Edge Detection Bot
Finds mispriced BTC/ETH 15-minute markets and trades on significant edge
"""

import yaml
import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from kalshi_client import KalshiClient
from spot_price_feed import CFBenchmarksRTI
from momentum_analyzer import MomentumAnalyzer
from market_scanner_15m import Market15mScanner
from edge_detector import EdgeDetector
from position_manager_15m import PositionManager15m
from risk_manager import RiskManager
from telegram_notifier import TelegramNotifier

def setup_logging(config: dict):
    log_level = config['monitoring']['log_level']
    log_file = config['monitoring']['log_file']
    Path(log_file).parent.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
    )

class EdgeDetectionBot:
    def __init__(self, config_path: str = "config_15m.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        setup_logging(self.config)
        self.logger = logging.getLogger(__name__)
        
        self.telegram = TelegramNotifier(self.config, bot_controller=self)
        self.client = KalshiClient(self.config)
        self.spot_feed = CFBenchmarksRTI(self.config)
        self.momentum = MomentumAnalyzer(self.spot_feed)
        self.scanner = Market15mScanner(self.client, self.config)
        self.edge_detector = EdgeDetector(self.spot_feed, self.momentum, self.config)
        self.risk_manager = RiskManager(self.config, self.telegram)
        self.position_manager = PositionManager15m(self.client, self.config, self.telegram)
        
        self.running = False
        self.paused = self.config.get('bot', {}).get('paused', False)
    
    def start(self):
        if not self.client.authenticate():
            self.logger.error("❌ Authentication failed")
            return
        if self.telegram.enabled:
            self.telegram.start_command_listener()
        
        self.running = True
        self.logger.info("="*60)
        self.logger.info("🚀 15-MINUTE EDGE DETECTION BOT STARTED")
        self.logger.info("="*60)
        
        self.run_loop()


    def run_loop(self):
        """Integrated loop: High-priority Take Profit checks + Regular Market Scanning"""
        scan_interval = self.config['monitoring'].get('scan_interval', 30)
        spot_update_interval = self.config['monitoring'].get('spot_price_update_interval', 5)
        
        # --- NEW: TP Check Interval ---
        tp_check_interval = self.config['strategy'].get('tp_check_interval', 5)
        
        last_scan_time, last_spot_update, last_tp_check, iteration = 0, 0, 0, 0

        self.logger.info("🚀 Starting high-frequency run loop...")

        while self.running:
            now = time.time()

            # 1. Hourly Ticker Lock Reset (Existing Logic)
            if int(now) % 3600 < 10:
                self.edge_detector.reset_locks()

            try:
                # 2. HIGH-PRIORITY TAKE PROFIT CHECK
                # We use a dedicated timer so it runs independently of the sleep at the bottom
                if not self.paused and (now - last_tp_check >= tp_check_interval):
                    self.position_manager.manage_take_profit()
                    last_tp_check = now

                # 3. UPDATE SPOT PRICES & MOMENTUM (Existing Logic)
                if now - last_spot_update >= spot_update_interval:
                    self._update_spot_prices()
                    last_spot_update = now

                # 4. MAIN SCAN INTERVAL (Existing Logic)
                if now - last_scan_time >= scan_interval:
                    iteration += 1
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"🔍 SCAN CYCLE #{iteration}")
                    self.logger.info("="*60)

                    # Scan for new opportunities
                    markets = self.scanner.scan_opportunities()
                    self.logger.info(f"📊 Found {len(markets)} active 15-min markets")

                    # Detect Edges
                    opportunities = self.edge_detector.scan_for_edges(markets)

                    if opportunities:
                        self.logger.info(f"🎯 {len(opportunities)} markets with significant edge!")
                        for opp in opportunities:
                            self._display_opportunity(opp)

                        # Execute trades if not paused
                        if not self.paused:
                            self._process_opportunities(opportunities)
                        else:
                            self.logger.info("⏸️ Bot is PAUSED - observation mode")
                    else:
                        self.logger.info("⏭️ No significant edges found in this cycle.")

                    # Display updated portfolio status
                    self._show_portfolio_status()
                    last_scan_time = now

                # --- FIX: Reduced sleep for higher responsiveness ---
                # Sleeping for 1 second instead of 5 allows the TP timer to be much more accurate
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10) # Reduced recovery sleep

    def _update_spot_prices(self):
        """NEW: Run async price updates for BTC, ETH, and SOL concurrently"""
        active_symbols = self.config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL'])
        
        async def fetch_all():
            tasks = [self.spot_feed.get_price_async(s) for s in active_symbols]
            results = await asyncio.gather(*tasks)
            for i, price in enumerate(results):
                if price:
                    self.momentum.update_price_history(active_symbols[i], price=price)
        
        try:
            # We use a helper to run the async loop inside your existing structure
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(fetch_all())
            else:
                asyncio.run(fetch_all())
        except Exception as e:
            self.logger.debug(f"Async spot update failed: {e}")

    # All other methods (_display_opportunity, _process_opportunities, _show_portfolio_status) 
    # remain EXACTLY as they are in your edge_botPRESOL.py file.    

    def _display_opportunity(self, opp: dict):
        """Display opportunity and send Telegram alert if thresholds are met"""
        # 1. Log to console
        self.logger.info(f"\n🎯 {opp['ticker']} | {opp['recommended_side'].upper()} @ {opp['entry_price']:.0%} | Edge: {opp['edge_percent']:.1f}% | ROI: {opp['expected_roi']:.1f}%")
        self.logger.info(f"   Signal Strength: {opp['signal_strength']:.1f}/100")
        
        # 2. Restoration of your Telegram Notification Logic
        if self.telegram and self.telegram.enabled:
            telegram_config = self.config.get('telegram', {})
            # Read thresholds from config
            min_edge = telegram_config.get('min_edge_for_alert', 10.0)
            min_signal = telegram_config.get('min_signal_for_alert', 70)
            
            # Send alert if thresholds are met (even if bot is paused)
            if opp['edge_percent'] >= min_edge and opp['signal_strength'] >= min_signal:
                mom = opp['momentum']
                alert_msg = (
                    f"🎯 EDGE DETECTED\n"
                    f"\n"
                    f"📊 {opp['symbol']}: {opp['ticker']}\n"
                    f"⏰ Closes in {opp['minutes_to_close']:.0f} min\n"
                    f"\n"
                    f"💎 EDGE: {opp['edge_percent']:.1f}%\n"
                    f"Expected: {opp['expected_probability']:.0%} | Market: {opp['market_probability']:.0%}\n"
                    f"\n"
                    f"📈 {mom['direction'].upper()} {mom['percent_change']:+.2f}%\n"
                    f"💪 Signal: {opp['signal_strength']:.0f}/100\n"
                    f"\n"
                    f"💰 {opp['recommended_side'].upper()} @ {opp['entry_price']:.0%}\n"
                    f"ROI: {opp['expected_roi']:.0f}%\n"
                )
                
                if self.paused:
                    alert_msg += "\n\n⏸️  OBSERVATION MODE"
                
                self.telegram.send_message(alert_msg)
                self.logger.info("📱 Telegram alert sent")
 
    def _process_opportunities(self, opportunities: list):
        balance = self.client.get_balance()
        # Use existing positions to calculate slots
        current_positions = self.position_manager.open_positions
        
        order_type = self.config['strategy'].get('order_type', 'market')
        max_concurrent = self.config['strategy'].get('max_concurrent_trades', 4)
        available_slots = max_concurrent - len(current_positions)

        if available_slots <= 0:
            self.logger.info(f"🛑 MAX CONCURRENT TRADES REACHED")
            return

        for opp in opportunities[:available_slots]:
            max_pos_pct = self.config['strategy'].get('max_position_percent', 0.45)
            trade_size = (balance * max_pos_pct) / max_concurrent

            if trade_size < 1:
                self.logger.info(f"⚠️ Insufficient balance for {opp['ticker']}")
                continue

            # CLEAN EXECUTION: Only call this once!
            success = self.position_manager.open_position(opp, trade_size, order_type=order_type)
            if success:
                self.logger.info(f"✅ {opp['ticker']} trade processed successfully")
            else:
                self.logger.info(f"❌ Execution failed for {opp['ticker']}")

    def _run_cycle(self):
        """
        Helper method synchronized with actual class method names.
        Used for manual triggers or simplified testing.
        """
        # Ensure we use scan_opportunities to match your Scanner class
        markets = self.scanner.scan_opportunities() 
        opportunities = self.edge_detector.scan_for_edges(markets)
        
        if opportunities and not self.paused:
            self._process_opportunities(opportunities)

        # The Fix: Check profits
        self.position_manager.manage_take_profit()

        # Update logs
        self._show_portfolio_status()

    #def _run_cycle(self):
        # 1. Standard Scan & Entry Logic
        #opportunities = self.scanner.scan()
        #self._process_opportunities(opportunities)

        # 2. TAKE PROFIT CHECK
        # This ensures every cycle also looks for exits
        #self.position_manager.manage_take_profit()

        # 3. Standard Portfolio Sync
        #self._show_portfolio_status()

    def _show_portfolio_status(self):
        """Calculates exposure and triggers the Stale Order Janitor using config expiry"""
        balance = self.client.get_balance()

        # use config expiry for janitor instead of 60s
        expiry = self.config['strategy'].get("order_expiry_seconds", 30)

        # 1. Trigger the Janitor and Sync (This kills orders older than 60s)
        self.position_manager.sync_with_exchange()
        positions = self.position_manager.open_positions

        # 2. Calculate deployed cash
        total_deployed = 0
        for pos in positions:
            #cost = pos.get('position_cost') or pos.get('cost') or 0 if isinstance(pos, dict) else getattr(pos, 'cost', 0)
            #total_deployed += (cost / 100)
            # Kalshi sometimes uses 'cost_cents' or 'position_cost'
            cost_raw = pos.get('position_cost') or pos.get('cost') or pos.get('cost_cents', 0)
            total_deployed += (cost_raw / 10000)

        self.logger.info(f"\n💼 PORTFOLIO STATUS:")
        self.logger.info(f"   Cash: ${balance:,.2f}")
        self.logger.info(f"   Active Positions: {len(positions)}")
        self.logger.info(f"   Real Exposure: ${total_deployed:,.2f}")


    def stop(self): self.running = False

if __name__ == "__main__":
    EdgeDetectionBot().start()


