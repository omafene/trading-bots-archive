"""
Kalshi Endgame Sweep Bot - DUAL INTERVAL VERSION
- Scanner: Runs every scan_interval (default 10 min)
- Order Management: Runs every order_check_interval (default 2 min)
"""

import yaml
import logging
import time
import sys
from pathlib import Path
from datetime import datetime
from kalshi_client import KalshiClient
from market_scanner import MarketScanner
from risk_manager import RiskManager
from position_manager import PositionManager
from telegram_notifier import TelegramNotifier

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
        self.scanner = MarketScanner(self.client, self.config)
        self.risk_manager = RiskManager(self.config, self.telegram)

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
        # Dual interval system
        scan_interval = self.config['monitoring'].get('scan_interval', 600)  # Default 10 min
        order_check_interval = self.config['monitoring'].get('order_check_interval', 120)  # Default 2 min
        
        last_scan_time = 0
        last_order_check_time = 0
        
        iteration = 0
        
        self.logger.info("="*60)
        self.logger.info("🚀 BOT STARTED - DUAL INTERVAL MODE")
        self.logger.info("="*60)
        self.logger.info(f"Trading cycle: {scan_interval}s (scan + trade)")
        self.logger.info(f"Cleanup cycle: {order_check_interval}s ({order_check_interval/60:.0f} min - cancel orders)")
        self.logger.info("="*60)
        
        while self.running:
            try:
                iteration += 1
                now = time.time()
                
                # ============================================================
                # TRADING CYCLE (every scan_interval - FAST)
                # Sync + Scan + Get Balance + Trade
                # ============================================================
                if now - last_scan_time >= scan_interval:
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"📈 TRADING CYCLE #{iteration}")
                    self.logger.info("="*60)
                    
                    # Step 1: Sync positions FIRST (prevent duplicates!)
                    self.position_manager.sync_with_exchange()
                    
                    # Step 2: Scan for opportunities
                    scan_start = time.time()
                    opportunities = self.scanner.scan_opportunities()
                    scan_time = time.time() - scan_start
                    
                    self.logger.info(f"✅ Scan complete in {scan_time:.1f}s")
                    self.logger.info(f"📊 Found {len(opportunities)} opportunities")
                    
                    if opportunities:
                        summary = self.scanner.get_market_summary(opportunities)
                        self.logger.info(f"   Categories: {summary.get('categories', {})}")
                        self.logger.info(f"   Avg probability: {summary.get('avg_probability', 0):.1%}")
                    
                    # Step 3: Get current balance and positions
                    balance = self.client.get_balance()
                    open_positions = self.position_manager.get_open_positions()
                    
                    self.logger.info(f"💰 Balance: ${balance:,.2f} | Positions: {len(open_positions)}")
                    
                    # Step 4: Process opportunities (now safe from duplicates!)
                    if opportunities and not self.paused:
                        self.logger.info(f"📈 Processing {len(opportunities)} opportunities...")
                        self._process_opportunities(opportunities, open_positions, balance)
                    elif self.paused:
                        self.logger.info("⏸️ Bot is PAUSED - skipping trades")
                    
                    last_scan_time = now
                    self.logger.info(f"⏰ Next trading cycle in {scan_interval}s")
                
                # ============================================================
                # CLEANUP CYCLE (every order_check_interval - SLOW)
                # Cancel Resting Orders + Sync Positions
                # ============================================================
                if now - last_order_check_time >= order_check_interval:
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"🧹 CLEANUP CYCLE")
                    self.logger.info("="*60)
                    
                    # Step 1: Cancel stale resting orders
                    cancelled = self.position_manager.cancel_all_resting_orders()
                    
                    # Step 2: Sync positions with exchange
                    self.position_manager.sync_with_exchange()
                    
                    # Step 3: Get updated portfolio status
                    balance = self.client.get_balance()
                    open_positions = self.position_manager.get_open_positions()
                    metrics = self.risk_manager.get_portfolio_metrics(open_positions, balance)
                    
                    self.logger.info(f"💰 Portfolio Status:")
                    self.logger.info(f"   Cash Balance: ${balance:,.2f}")
                    self.logger.info(f"   Open Positions: {len(open_positions)}")
                    self.logger.info(f"   Total Deployed: ${metrics['total_deployed']:,.2f}")
                    
                    last_order_check_time = now
                    self.logger.info(f"⏰ Next cleanup in {order_check_interval/60:.0f} minutes")
                
                # Sleep briefly before next check
                time.sleep(10)  # Check every 10 seconds if it's time for scanner or orders
                
            except Exception as e:
                self.logger.error(f"❌ Loop Error: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 min on error

    def _process_opportunities(self, opportunities, current_positions, balance):
        executed = 0
        for opp in opportunities[:5]:
            can_open, _ = self.risk_manager.can_open_position(opp, current_positions, balance)
            if can_open:
                size = self.risk_manager.calculate_position_size(opp, balance)
                if self.position_manager.open_position(opp, size):
                    executed += 1
        self.logger.info(f"✅ Executed {executed} trades.")

    def stop(self): self.running = False
    def pause(self): self.paused = True; return True
    def resume(self): self.paused = False; return True

if __name__ == "__main__":
    EndgameSweepBot().start()
