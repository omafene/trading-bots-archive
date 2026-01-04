"""
Kalshi 15-Minute Edge Detection Bot
Finds mispriced BTC/ETH 15-minute markets and trades on significant edge
"""

import yaml
import logging
import time
import sys
import asyncio
import threading
from pathlib import Path
from datetime import datetime, timezone
from config_loader import load_config_with_env
from kalshi_client import KalshiClient
from spot_price_feed import CFBenchmarksRTI
from order_book_feed import OrderBookFeed
from momentum_analyzer import MomentumAnalyzer
from momentum_analyzer_v3 import MomentumAnalyzerV3
from momentum_analyzer_v4 import MomentumAnalyzerV4
from market_scanner_15m import Market15mScanner
from position_manager_15m import PositionManager15m
from risk_manager import RiskManager
from telegram_notifier import TelegramNotifier
from state_manager import StateManager
from dashboard import start_dashboard
from spot_feed_calibration_tracker import SpotFeedCalibrationTracker
from kalshi_ws_feed import KalshiWSFeed
from binance_price_feed import BinancePriceFeed

# Advanced multi-factor edge detection modules
from volatility_analyzer import VolatilityAnalyzer
from orderbook_analyzer import OrderbookAnalyzer
from basis_monitor import BasisMonitor
from edge_detector_advanced import AdvancedEdgeDetector
from outcome_checker import OutcomeChecker
from volume_tracker import VolumeTracker

def setup_logging(config: dict):
    from logging.handlers import RotatingFileHandler
    log_level = config['monitoring']['log_level']
    log_file = config['monitoring']['log_file']
    Path(log_file).parent.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(log_file, maxBytes=300*1024*1024, backupCount=5),
            logging.StreamHandler(sys.stdout)
        ]
    )

class EdgeDetectionBot:
    def __init__(self, config_path: str = "config_15m.yaml"):
        # Load config with environment variable overrides for security
        self.config = load_config_with_env(config_path)
        
        setup_logging(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Initialize state management first
        self.state_manager = StateManager(state_dir="data")

        self.telegram = TelegramNotifier(self.config, bot_controller=self)
        self.client = KalshiClient(self.config)
        self.spot_feed = CFBenchmarksRTI(self.config)

        # Initialize order book feed (real-time CEX data)
        order_book_enabled = self.config.get('order_book', {}).get('enabled', False)
        if order_book_enabled:
            self.order_book_feed = OrderBookFeed(self.config)
            self.logger.info("📊 Order Book Feed enabled (WebSocket will start with bot)")
        else:
            self.order_book_feed = None
            self.logger.info("📊 Order Book Feed disabled")

        # Initialize momentum analyzer (v1/v2, v3, or v4)
        prob_model = self.config.get('strategy', {}).get('probability_model', 'v1')
        if prob_model == 'v4':
            self.momentum = MomentumAnalyzerV4(self.spot_feed, self.config)
            self.logger.info("📊 Using v4 Improved Mean Reversion probability model")
        elif prob_model == 'v3':
            self.momentum = MomentumAnalyzerV3(self.spot_feed, self.config)
            self.logger.info("📊 Using v3 Mean Reversion probability model")
        else:
            self.momentum = MomentumAnalyzer(self.spot_feed, self.config)
            self.logger.info(f"📊 Using {prob_model} probability model")

        # Initialize feed calibration tracker
        self.feed_calibration_tracker = SpotFeedCalibrationTracker()

        # Initialize scanner with spot feed and calibration tracker
        self.scanner = Market15mScanner(
            self.client,
            self.config,
            spot_feed=self.spot_feed,
            feed_calibration_tracker=self.feed_calibration_tracker
        )

        # Initialize advanced edge detection modules
        use_advanced = self.config['strategy'].get('use_advanced_edge_detection', True)
        if use_advanced:
            self.logger.info("🚀 Initializing ADVANCED multi-factor edge detection...")
            self.volatility_analyzer = VolatilityAnalyzer(window_minutes=15)
            self.orderbook_analyzer = OrderbookAnalyzer()
            self.basis_monitor = BasisMonitor()
            self.volume_tracker = VolumeTracker(self.config)  # V3 Elite: Volume divergence
            self.edge_detector = AdvancedEdgeDetector(
                self.spot_feed, self.momentum, self.volatility_analyzer,
                self.orderbook_analyzer, self.basis_monitor, self.config,
                order_book_feed=self.order_book_feed,  # CEX order book for imbalance filtering
                volume_tracker=self.volume_tracker  # V3 Elite: Volume divergence tracker
            )
            self.logger.info("✅ Advanced edge detection enabled (with V3 Elite MTF + Volume filters)")
        else:
            # Fallback to simple edge detector
            from edge_detector import EdgeDetector
            self.edge_detector = EdgeDetector(self.spot_feed, self.momentum, self.config, self.order_book_feed)
            self.logger.info("⚠️ Using simple edge detection (not recommended)")

        # Initialize Kalshi private WebSocket feed (real-time fills/orders/orderbooks)
        kalshi_ws_enabled = self.config.get('kalshi_ws', {}).get('enabled', False)
        if kalshi_ws_enabled:
            self.kalshi_ws_feed = KalshiWSFeed(self.config)
            self.logger.info("⚡ Kalshi WS Feed enabled (real-time fills/orders/orderbooks)")
        else:
            self.kalshi_ws_feed = None
            self.logger.info("⚡ Kalshi WS Feed disabled (REST polling only)")

        # Give scanner access to WS feed so it can use the real-time orderbook cache
        # and auto-subscribe new market tickers as they are discovered.
        # (scanner was constructed above before ws_feed existed, so we set it here)
        self.scanner.ws_feed = self.kalshi_ws_feed

        # Binance aggTrade WS — high-frequency price ticks for spike detection
        binance_feed_enabled = self.config.get('binance_price_feed', {}).get('enabled', False)
        if binance_feed_enabled:
            active_symbols = self.config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])
            throttle = self.config.get('binance_price_feed', {}).get('min_write_interval', 1.0)
            self.binance_price_feed = BinancePriceFeed(
                symbols=active_symbols,
                price_callback=lambda sym, px: self.momentum.update_price_history(sym, price=px),
                min_write_interval=throttle,
            )
            self.logger.info("📡 Binance price feed enabled (aggTrade → price history)")
        else:
            self.binance_price_feed = None
            self.logger.info("📡 Binance price feed disabled")

        self.risk_manager = RiskManager(self.config, self.telegram)
        self.position_manager = PositionManager15m(
            self.client, self.config, self.telegram, self.state_manager,
            kalshi_ws_feed=self.kalshi_ws_feed
        )

        # Outcome checker for calibration (if edge detector has tracker)
        if hasattr(self.edge_detector, 'neg_edge_tracker') and self.edge_detector.neg_edge_tracker:
            self.outcome_checker = OutcomeChecker(self.client, self.edge_detector.neg_edge_tracker)
            self.logger.info("✅ Outcome checker initialized for model calibration")
        else:
            self.outcome_checker = None

        self.running = False
        self.paused = self.config.get('bot', {}).get('paused', False)
        self.state_lock = threading.Lock()  # Thread-safe state management
        self._cached_balance: float = 0.0
        self._cached_balance_time: float = 0.0
        self._balance_cache_ttl: float = 15.0  # seconds
    
    def start(self):
        if not self.client.authenticate():
            self.logger.error("❌ Authentication failed")
            return

        # Restore positions from disk (crash recovery)
        self.state_manager.restore_positions_to_manager(self.position_manager)

        # Update peak balance in risk manager
        peak = self.state_manager.get_peak_balance()
        if peak > 0:
            self.risk_manager.peak_balance = peak

        if self.telegram.enabled:
            self.telegram.start_command_listener()

        # Start performance dashboard
        if self.config.get('monitoring', {}).get('dashboard_enabled', True):
            dashboard_port = self.config.get('monitoring', {}).get('dashboard_port', 8080)
            start_dashboard(self, port=dashboard_port)

        self.running = True
        self.logger.info("="*60)
        self.logger.info("🚀 15-MINUTE EDGE DETECTION BOT STARTED")
        self.logger.info("="*60)

        stats = self.state_manager.get_stats()
        self.logger.info(f"📊 Session stats: {stats['trades_today']} trades today, "
                        f"{stats['trades_total']} total, uptime: {stats['bot_uptime']}")

        # Start both WebSocket feeds simultaneously (parallel, not sequential)
        if self.order_book_feed:
            self.logger.info("🔌 Starting Order Book WebSocket connections...")
            self.order_book_task = threading.Thread(
                target=self._run_order_book_feed,
                daemon=True
            )
            self.order_book_task.start()

        if self.kalshi_ws_feed:
            self.logger.info("⚡ Starting Kalshi WS feed (private portfolio channel)...")
            self.kalshi_ws_thread = threading.Thread(
                target=self._run_kalshi_ws_feed,
                daemon=True
            )
            self.kalshi_ws_thread.start()

        if self.binance_price_feed:
            self.logger.info("📡 Starting Binance aggTrade price feed...")
            self.binance_price_thread = threading.Thread(
                target=self._run_binance_price_feed,
                daemon=True,
                name="binance_price_feed",
            )
            self.binance_price_thread.start()

        # Poll once for both feeds instead of two sequential sleep(2) calls
        if self.order_book_feed or self.kalshi_ws_feed:
            deadline = time.time() + 5
            while time.time() < deadline:
                ob_ok = (not self.order_book_feed or
                         any(s['connected'] for sym in self.order_book_feed.get_status().values()
                             for s in sym.values()))
                ws_ok = not self.kalshi_ws_feed or self.kalshi_ws_feed.is_connected
                if ob_ok and ws_ok:
                    break
                time.sleep(0.1)

        if self.order_book_feed:
            status = self.order_book_feed.get_status()
            connected = sum(
                1 for symbol_status in status.values()
                for exchange_status in symbol_status.values()
                if exchange_status['connected']
            )
            total_connections = len(status) * len(self.order_book_feed.exchanges)
            self.logger.info(f"✅ Order Book Feed: {connected}/{total_connections} connections established")

        if self.kalshi_ws_feed:
            self.logger.info(f"✅ Kalshi WS: {self.kalshi_ws_feed.get_status()}")

            # Pre-warm: subscribe to orderbooks for all currently open 15m markets.
            # This ensures the WS cache is hot before the first scan cycle runs,
            # so _evaluate_market() gets real-time data immediately (not REST fallback).
            if self.kalshi_ws_feed.is_connected:
                self.logger.info("📡 Pre-warming WS orderbook subscriptions...")
                initial_markets = self.scanner._get_15min_markets()
                n_subscribed = len(self.scanner._subscribed_tickers)
                self.logger.info(f"📡 WS orderbooks pre-subscribed: {n_subscribed} tickers across {len(initial_markets)} markets")

        # Dedicated exit-watcher: checks TP/SL on every WS orderbook event,
        # independent of the scan loop so close latency is never blocked by scanning.
        self.exit_watcher_thread = threading.Thread(
            target=self._run_exit_watcher,
            daemon=True,
            name="exit_watcher",
        )
        self.exit_watcher_thread.start()
        self.logger.info("⚡ Exit watcher thread started (event-driven TP/SL)")

        self.run_loop()

    def _run_kalshi_ws_feed(self):
        """Run Kalshi private WS feed in a dedicated async event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.kalshi_ws_feed.start())
        except Exception as e:
            self.logger.error(f"❌ Kalshi WS Feed error: {e}", exc_info=True)
        finally:
            loop.close()

    def _run_binance_price_feed(self):
        """Run Binance aggTrade price feed in a dedicated async event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.binance_price_feed.start())
        except Exception as e:
            self.logger.error(f"❌ Binance price feed error: {e}", exc_info=True)
        finally:
            loop.close()

    def _run_order_book_feed(self):
        """Run order book WebSocket feed in async event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.order_book_feed.start())
        except Exception as e:
            self.logger.error(f"❌ Order Book Feed error: {e}", exc_info=True)
        finally:
            loop.close()

    def _run_exit_watcher(self):
        """
        Dedicated high-frequency thread: fires manage_exits() on every Kalshi WS
        orderbook update (or every 0.5 s as fallback). Completely independent of the
        scan loop so TP/SL latency is never gated by slow scans or API calls.
        """
        while self.running:
            try:
                # Wake on any orderbook change (best case ~0 ms); fall back to 0.1 s poll
                if self.kalshi_ws_feed and self.kalshi_ws_feed.is_connected:
                    self.kalshi_ws_feed.orderbook_updated.wait(timeout=0.1)
                    self.kalshi_ws_feed.orderbook_updated.clear()
                else:
                    time.sleep(0.1)

                with self.state_lock:
                    is_paused = self.paused

                if not is_paused and self.position_manager.open_positions:
                    self.position_manager.manage_exits()
            except Exception as e:
                self.logger.error(f"Exit watcher error: {e}")
                time.sleep(1)

    def run_loop(self):
        """Integrated loop: High-priority Take Profit checks + Regular Market Scanning"""
        scan_interval = self.config['monitoring'].get('scan_interval', 30)
        spot_update_interval = self.config['monitoring'].get('spot_price_update_interval', 5)
        
        last_scan_time, last_spot_update, iteration = 0, 0, 0
        last_outcome_check = time.time()  # Don't block scan loop on startup — run in background thread

        # Outcome checking interval (from config)
        outcome_check_interval = self.config.get('calibration', {}).get('check_outcomes_interval', 3600)

        self.logger.info("🚀 Starting high-frequency run loop...")
        active_symbols = self.config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])
        self.logger.info(f"📊 Background price collection active for {', '.join(active_symbols)} (every {spot_update_interval}s)")
        self.logger.info(f"   Price history will build from candle start for accurate R² calculation")
        if self.outcome_checker:
            self.logger.info(f"📊 Outcome checking enabled (every {outcome_check_interval}s)")
            def _startup_outcome_check():
                try:
                    checked = self.outcome_checker.check_pending_outcomes(max_checks=50, stop_flag=lambda: self.running)
                    if checked > 0:
                        self.logger.info(f"📊 Startup backfill: {checked} outcomes checked")
                except Exception as e:
                    self.logger.error(f"Error in startup outcome check: {e}", exc_info=True)
            threading.Thread(target=_startup_outcome_check, daemon=True, name="startup_outcome_check").start()

        while self.running:
            now = time.time()

            # 1. Periodic Outcome Checking (Calibration)
            if self.outcome_checker and (now - last_outcome_check >= outcome_check_interval):
                try:
                    checked = self.outcome_checker.check_pending_outcomes(max_checks=50, stop_flag=lambda: self.running)
                    if checked > 0:
                        self.logger.info(f"📊 Calibration: Checked {checked} market outcomes")
                    last_outcome_check = now
                except Exception as e:
                    self.logger.error(f"Error checking outcomes: {e}", exc_info=True)
                    last_outcome_check = now  # Don't retry immediately

            try:
                # 2. UPDATE SPOT PRICES & MOMENTUM (Existing Logic)
                # (TP/SL handled by dedicated exit_watcher thread)
                if now - last_spot_update >= spot_update_interval:
                    self._update_spot_prices()
                    last_spot_update = now

                # 3. MAIN SCAN INTERVAL (Existing Logic)
                if now - last_scan_time >= scan_interval:
                    iteration += 1
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"🔍 SCAN CYCLE #{iteration}")
                    self.logger.info("="*60)

                    # Log order book status every minute (every other scan cycle if scan_interval=30s)
                    if self.order_book_feed and iteration % 2 == 0:
                        status = self.order_book_feed.get_status()
                        binance_active = sum(1 for s in status if 'binance' in status[s])
                        coinbase_active = sum(1 for s in status if 'coinbase' in status[s])
                        kraken_active = sum(1 for s in status if 'kraken' in status[s])
                        total_symbols = len(status)
                        self.logger.info(f"📊 Order Book: Binance {binance_active}/{total_symbols} | "
                                       f"Coinbase {coinbase_active}/{total_symbols} | "
                                       f"Kraken {kraken_active}/{total_symbols}")

                    # Reset ticker locks from actual positions (prevents phantom locks)
                    self._reset_ticker_locks_from_positions()

                    # Batch-fetch all spot prices before scanning (optimization)
                    self._update_spot_prices()

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
                        with self.state_lock:
                            is_paused = self.paused

                        if not is_paused:
                            self._process_opportunities(opportunities)
                        else:
                            self.logger.info("⏸️ Bot is PAUSED - observation mode")
                    else:
                        self.logger.info("⏭️ No significant edges found in this cycle.")

                    # Display updated portfolio status
                    self._show_portfolio_status()
                    last_scan_time = now

                # Event-driven sleep: wake immediately on WS orderbook update.
                # 0.1s timeout so scan never lags more than 100ms even if
                # the exit-watcher thread already consumed the orderbook_updated event.
                if self.kalshi_ws_feed:
                    self.kalshi_ws_feed.orderbook_updated.wait(timeout=0.1)
                    self.kalshi_ws_feed.orderbook_updated.clear()
                else:
                    time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"❌ Error in main loop: {e}")
                time.sleep(3)

    def _update_spot_prices(self):
        """Background price collection for full candle R² data"""
        active_symbols = self.config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])

        async def fetch_all():
            tasks = [self.spot_feed.get_price_async(s) for s in active_symbols]
            results = await asyncio.gather(*tasks)
            collected = []
            for i, price in enumerate(results):
                if price:
                    symbol = active_symbols[i]
                    self.momentum.update_price_history(symbol, price=price)
                    # Get sample count for this symbol
                    sample_count = len(self.momentum.price_history.get(symbol, []))
                    collected.append(f"{symbol}:{sample_count}")

            if collected:
                self.logger.debug(f"📊 Price history updated: {', '.join(collected)} samples")

        try:
            # Run async price fetching in a new event loop
            asyncio.run(fetch_all())
        except Exception as e:
            self.logger.warning(f"⚠️ Spot price update failed: {e}")

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
                # Get R² and confidence
                r_squared = mom.get('r_squared', 0)
                confidence = mom.get('confidence', 'unknown')

                # R² emoji indicator
                if r_squared >= 0.7:
                    r2_emoji = "🟢"  # High confidence
                elif r_squared >= 0.4:
                    r2_emoji = "🟡"  # Medium confidence
                else:
                    r2_emoji = "🔴"  # Low confidence

                # Order book imbalance line (only shown if data available)
                ob_imbalance = opp.get('ob_imbalance')
                if ob_imbalance is not None:
                    ob_emoji = "🟢" if ob_imbalance > 0.60 else "🔴" if ob_imbalance < 0.40 else "⚪"
                    ob_line = f"{ob_emoji} Order Imbalance: {ob_imbalance:.2%}\n"
                else:
                    ob_line = ""

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
                    f"{r2_emoji} R²: {r_squared:.2f} ({confidence})\n"
                    f"💪 Signal: {opp['signal_strength']:.0f}/100\n"
                    f"{ob_line}"
                    f"\n"
                    f"💰 {opp['recommended_side'].upper()} @ {opp['entry_price']:.0%}\n"
                    f"ROI: {opp['expected_roi']:.0f}%\n"
                )

                with self.state_lock:
                    is_paused = self.paused

                if is_paused:
                    alert_msg += "\n\n⏸️  OBSERVATION MODE"

                threading.Thread(
                    target=self.telegram.send_message,
                    args=(alert_msg,),
                    daemon=True,
                    name="telegram-alert"
                ).start()
                self.logger.info("📱 Telegram alert sent (async)")

    def _reset_ticker_locks_from_positions(self):
        """
        Reset ticker locks based on VERIFIED Kalshi state + time-based protection.

        Locks are ONLY cleared if:
        1. No position exists on Kalshi AND
        2. No pending order exists AND
        3. Minimum lock duration has passed (default 30s)

        This prevents race conditions from Kalshi API lag.
        """
        # STEP 1: Sync with Kalshi FIRST (before clearing locks)
        self.position_manager.sync_with_exchange()
        self.logger.debug("✅ Synced with Kalshi before lock reset")

        # STEP 2: Build set of tickers that have positions/orders on Kalshi
        kalshi_tickers = set()

        # From confirmed positions
        for pos in self.position_manager.open_positions:
            ticker = pos.get('ticker')
            if ticker:
                kalshi_tickers.add(ticker)

        # From pending orders (still in flight)
        for oid, meta in self.position_manager.pending_orders.items():
            ticker = meta.get('ticker')
            if ticker:
                kalshi_tickers.add(ticker)

        # STEP 3: Rebuild locks intelligently (don't clear first!)
        old_locks = self.edge_detector.traded_tickers.copy()
        new_locks = set()

        # Keep locks that have Kalshi positions/orders
        new_locks.update(kalshi_tickers)

        # CRITICAL: Handle preventive locks (time-based, user-configurable duration)
        preventive_locked_tickers = []
        now = time.time()
        min_duration = self.edge_detector.min_lock_duration

        for ticker, lock_time in list(self.edge_detector.preventive_lock_timestamps.items()):
            time_since_lock = now - lock_time

            if time_since_lock < min_duration:
                # Lock still active
                new_locks.add(ticker)
                preventive_locked_tickers.append(ticker)
                self.logger.debug(f"🔒 Keeping preventive lock on {ticker} "
                                f"({min_duration - time_since_lock:.0f}s remaining)")
            else:
                # Lock expired - safe to retry
                self.edge_detector.preventive_lock_timestamps.pop(ticker, None)
                self.logger.info(f"🔓 Preventive lock expired for {ticker} (can retry after {min_duration}s)")

        # CRITICAL: Handle api_lag_protection (ticker_trade_timestamps) — second independent layer
        api_lag_locked_tickers = []
        if self.edge_detector.api_lag_protection_enabled:
            for ticker, trade_time in list(self.edge_detector.ticker_trade_timestamps.items()):
                time_since_trade = now - trade_time
                if time_since_trade < min_duration:
                    new_locks.add(ticker)
                    api_lag_locked_tickers.append(ticker)
                else:
                    # Expired — only remove if Kalshi also has no position
                    if ticker not in kalshi_tickers:
                        self.edge_detector.ticker_trade_timestamps.pop(ticker, None)

        # CRITICAL: Handle SL-fired locks — hold for 25 minutes after SL fires to prevent re-entry.
        # Values are absolute expiry timestamps (time.time() + 25*60) — avoids ET/UTC parsing issues.
        sl_locked_tickers = []
        for ticker, expiry in list(self.position_manager.sl_fired_tickers.items()):
            if now < expiry:
                new_locks.add(ticker)
                sl_locked_tickers.append(ticker)
            else:
                del self.position_manager.sl_fired_tickers[ticker]
                self.logger.info(f"🔓 SL lock expired for {ticker}")

        # STEP 4: Update the actual locks
        self.edge_detector.traded_tickers = new_locks

        # STEP 5: Logging
        positions_count = len(self.position_manager.open_positions)
        pending_count = len(self.position_manager.pending_orders)
        preventive_locked_count = len(preventive_locked_tickers)
        api_lag_locked_count = len(api_lag_locked_tickers)
        sl_locked_count = len(sl_locked_tickers)

        self.logger.info(f"🔓 Ticker locks: {len(old_locks)} → {len(new_locks)} "
                        f"({positions_count} positions + {pending_count} pending + "
                        f"{preventive_locked_count} preventive + {api_lag_locked_count} api_lag"
                        f"{f' + {sl_locked_count} sl' if sl_locked_count else ''})")

        # Log tickers that were unlocked
        unlocked = old_locks - new_locks
        if unlocked:
            self.logger.info(f"   ✅ Unlocked {len(unlocked)} tickers: {', '.join(unlocked)}")

        # Log preventive locks if any
        if preventive_locked_tickers:
            self.logger.debug(f"   🔒 Preventively locked: {', '.join(preventive_locked_tickers)}")
        if api_lag_locked_tickers:
            self.logger.debug(f"   🔒 API-lag locked: {', '.join(api_lag_locked_tickers)}")

    def _process_opportunities(self, opportunities: list):
        # 1. Get the Hard Limit from Config
        max_concurrent = self.config['strategy'].get('max_concurrent_trades', 4)
        order_type = self.config['strategy'].get('order_type', 'market')

        # Use cached balance to avoid REST round-trip on the hot path.
        # Cache TTL is 15s — stale by at most one trade cycle, acceptable vs latency cost.
        now = time.monotonic()
        if (now - self._cached_balance_time) > self._balance_cache_ttl:
            self._cached_balance = self.client.get_balance()
            self._cached_balance_time = now
        balance = self._cached_balance

        # 2. Correlation Filter (Existing Logic)
        if self.config['strategy'].get('correlation_filter_enabled', False):
            self.logger.info("🛡️ Correlation Filter ACTIVE: Selecting only top signal.")
            opportunities = opportunities[:1]

        # Log starting state
        locked_count = len(self.edge_detector.traded_tickers)
        self.logger.info(f"🔒 Starting opportunity processing: "
                        f"{len(opportunities)} opportunities, "
                        f"{locked_count} tickers already locked")

        for opp in opportunities:
            ticker = opp['ticker']

            # CONSERVATIVE FIX: Lock ticker PREVENTIVELY before any processing
            # Prevents duplicates even if API is slow or responses lost
            if ticker not in self.edge_detector.traded_tickers:
                self.edge_detector.traded_tickers.add(ticker)
                # IMMEDIATELY add to preventive locks (before trade attempt)
                self.edge_detector.preventive_lock_timestamps[ticker] = time.time()
                # Record timestamp for time-based lock protection (if enabled)
                if self.edge_detector.api_lag_protection_enabled:
                    self.edge_detector.ticker_trade_timestamps[ticker] = time.time()
                lock_duration = self.edge_detector.min_lock_duration
                self.logger.info(f"🔒 PREVENTIVE LOCK: {ticker} (locked for {lock_duration}s)")
            else:
                self.logger.info(f"⏭️ SKIP: {ticker} (already locked from previous attempt)")
                continue

            # Check if we already have a position or pending order for this ticker
            if ticker in [p.get('ticker') for p in self.position_manager.open_positions]:
                self.logger.debug(f"⏭️ {ticker} skip: Already in open_positions")
                # Keep lock - will be cleared by Kalshi verification
                continue

            if ticker in [meta.get('ticker') for meta in self.position_manager.pending_orders.values()]:
                self.logger.debug(f"⏭️ {ticker} skip: Already in pending_orders")
                # Keep lock - will be cleared by Kalshi verification
                continue

            # --- CRITICAL: RE-CHECK SLOTS INSIDE THE LOOP ---
            current_count = self.position_manager.get_total_position_count()
            if current_count >= max_concurrent:
                confirmed = len(self.position_manager.open_positions)
                pending = len(self.position_manager.pending_orders)
                self.logger.info(f"🛑 LIMIT REACHED: {current_count}/{max_concurrent} total "
                                f"({confirmed} confirmed + {pending} pending)")

                # Verify positions match expectations
                if pending > 0:
                    self.logger.debug(f"Pending orders: {list(self.position_manager.pending_orders.keys())}")
                if confirmed > 0:
                    tickers = [p.get('ticker', 'UNKNOWN') for p in self.position_manager.open_positions]
                    self.logger.debug(f"Open positions: {tickers}")

                break # Stop processing any further opportunities

            # Use Kelly Criterion for dynamic position sizing (balance fetched once above)
            trade_size = self.risk_manager.calculate_position_size(opp, balance)

            if trade_size < 1:
                self.logger.info(f"⚠️ Insufficient balance or negative Kelly for {opp['ticker']}")
                continue

            self.logger.info(f"💰 Position size for {opp['ticker']}: ${trade_size:.2f} "
                           f"(Kelly-based, {trade_size/balance:.1%} of balance)")

            # Lock already acquired at top of loop - no need to lock again here
            success, order_id = self.position_manager.open_position(opp, trade_size, order_type=order_type)

            # CRITICAL: Verify with Kalshi after trade attempt
            self.position_manager.sync_with_exchange()

            if success:
                self._cached_balance_time = 0.0  # Invalidate cache — balance changed after fill
                if order_id:
                    self.logger.info(f"✅ TRADE EXECUTED: {opp['ticker']} | "
                                   f"{opp['recommended_side'].upper()} @ {opp['entry_price']:.0%} | "
                                   f"Depth: {opp.get('depth', '?')} | "
                                   f"Expected ROI: {opp['expected_roi']:.1f}%")
                    if self.telegram and self.telegram.enabled:
                        try:
                            new_balance = self.client.get_balance() or 0
                            entry_price = opp['entry_price']
                            contracts = trade_size / entry_price if entry_price else 0
                            self.telegram.notify_position_opened({
                                'ticker': opp['ticker'],
                                'symbol': opp.get('symbol', opp['ticker']),
                                'side': opp['recommended_side'],
                                'entry_price': entry_price,
                                'contracts': contracts,
                                'cost': trade_size,
                                'current_balance': new_balance,
                            })
                        except Exception as e:
                            self.logger.error(f"Error sending position opened notification: {e}")
                else:
                    self.logger.warning(f"⏳ Order submitted for {opp['ticker']} but not yet confirmed")

                # Log actual trade for calibration (outcome filled in later by OutcomeChecker)
                if hasattr(self.edge_detector, 'neg_edge_tracker') and self.edge_detector.neg_edge_tracker:
                    self.edge_detector.neg_edge_tracker.log_actual_trade(opp)

                # Save position to state (crash recovery)
                self._sync_positions_to_state()
                self.state_manager.increment_trades_today()

                # Brief pause — sync_with_exchange inside open_position already refreshed state
                time.sleep(0.3)
            else:
                self.logger.error(f"❌ Order creation failed for {opp['ticker']}")
                # open_position returns (False, None) only on confirmed zero-fill outcomes:
                # IOC canceled (no liquidity), pre-submit depth abort, or insufficient size.
                # Ambiguous/timeout cases return (True, None) and keep the lock.
                # So it is safe to release the lock here — there is nothing to double-fill.
                self.edge_detector.preventive_lock_timestamps.pop(ticker, None)
                self.edge_detector.ticker_trade_timestamps.pop(ticker, None)
                self.edge_detector.traded_tickers.discard(ticker)
                self.logger.info(f"🔓 Lock released for {ticker} (confirmed no fill — eligible for retry)")
 
    def _run_cycle(self):
        """
        Helper method synchronized with actual class method names.
        Used for manual triggers or simplified testing.
        """
        # Ensure we use scan_opportunities to match your Scanner class
        markets = self.scanner.scan_opportunities()
        opportunities = self.edge_detector.scan_for_edges(markets)

        with self.state_lock:
            is_paused = self.paused

        if opportunities and not is_paused:
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

        # 3. Check circuit breaker (max drawdown protection)
        breaker_triggered, drawdown = self.risk_manager.check_drawdown(balance, bot_controller=self)

        # 4. Display portfolio status
        pending_count = len(self.position_manager.pending_orders)
        total_count = len(positions) + pending_count

        self.logger.info(f"\n💼 PORTFOLIO STATUS:")
        if balance is not None:
            self.logger.info(f"   Cash: ${balance:,.2f}")
        else:
            self.logger.info(f"   Cash: [API Error - Unable to fetch]")
        self.logger.info(f"   Active Positions: {len(positions)}")
        if pending_count > 0:
            self.logger.info(f"   Pending Orders: {pending_count}")
            self.logger.info(f"   Total Exposure: {total_count} positions")
        self.logger.info(f"   Real Exposure: ${total_deployed:,.2f}")

        # 5. Display drawdown status
        dd_status = self.risk_manager.get_drawdown_status(balance)
        self.logger.info(f"\n📊 DRAWDOWN STATUS:")
        self.logger.info(f"   Peak Balance: ${dd_status['peak_balance']:,.2f}")
        self.logger.info(f"   Current Drawdown: {dd_status['drawdown']:.1%}")
        self.logger.info(f"   Max Allowed: {dd_status['max_drawdown']:.1%}")
        self.logger.info(f"   Distance to Breaker: {dd_status['distance_to_breaker']:.1%}")

        if breaker_triggered:
            self.logger.critical(f"\n🛑 CIRCUIT BREAKER ACTIVE - Trading halted!")
            self.logger.critical(f"   Manual review required. Use /resume after fixing issue.")


    def _sync_positions_to_state(self):
        """Sync current positions to persistent state"""
        for pos in self.position_manager.open_positions:
            self.state_manager.save_position(pos)

    def stop(self):
        """Stop bot and save final state"""
        self.running = False
        self._sync_positions_to_state()
        self.logger.info("💾 Final state saved")

if __name__ == "__main__":
    EdgeDetectionBot().start()


