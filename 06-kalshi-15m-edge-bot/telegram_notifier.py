"""
Telegram Notifier (v4.0)
Sends trading alerts and updates via Telegram bot.
Fixed: Remote control commands correctly toggle the 'paused' attribute.
"""

import requests
import logging
import threading
import time
from typing import Dict, Optional, List, Any
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles Telegram notifications and commands for trading events"""

    def __init__(self, config: Dict, bot_controller=None):
        self.config = config
        self.telegram_config = config.get('telegram', {})
        self.enabled = self.telegram_config.get('enabled', False)
        self.bot_controller = bot_controller

        self.last_update_id = 0
        self.command_thread = None
        self.running = False

        if self.enabled:
            self.bot_token = self.telegram_config.get('bot_token')
            self.chat_id = self.telegram_config.get('chat_id')

            if not self.bot_token or not self.chat_id:
                logger.warning("Telegram enabled but bot_token or chat_id missing.")
                self.enabled = False
            else:
                logger.info("Telegram alerts enabled")
                self._test_connection()

    def _get_eastern_time(self) -> datetime:
        return datetime.now(ZoneInfo("America/New_York"))

    def start_command_listener(self):
        """Starts the command listener in a background daemon thread."""
        if not self.enabled: return
        self._clear_old_updates()
        self.running = True
        self.command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self.command_thread.start()
        logger.info("📱 Telegram command listener started in background")

    def _clear_old_updates(self):
        """Consume any old messages so the bot doesn't execute stale commands on startup."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, params={"timeout": 1, "limit": 100}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    if updates:
                        self.last_update_id = max([u['update_id'] for u in updates])
                        logger.info(f"Cleared {len(updates)} old Telegram updates")
        except Exception as e:
            logger.debug(f"Error clearing updates: {e}")

    def stop_command_listener(self):
        self.running = False
        if self.command_thread:
            self.command_thread.join(timeout=2)

    def _command_loop(self):
        while self.running:
            try:
                self._check_for_commands()
                time.sleep(2) # Poll every 2 seconds
            except Exception as e:
                logger.error(f"Error in command loop: {e}")
                time.sleep(5)

    def _check_for_commands(self):
        if not self.running: return
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 10,
                "allowed_updates": ["message"]
            }
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                return
            
            data = response.json()
            for update in data.get('result', []):
                self.last_update_id = update['update_id']
                message = update.get('message', {})
                chat_id = str(message.get('chat', {}).get('id', ''))
                
                # Security: Only respond to your specific Chat ID
                if chat_id == str(self.chat_id):
                    text = message.get('text', '').strip()
                    if text.startswith('/'):
                        logger.info(f"📩 Telegram command: {text}")
                        self._handle_command(text)
                        
        except Exception as e:
            logger.error(f"Error checking commands: {e}")

    def _handle_command(self, command: str):
        cmd = command.lower().split()[0]

        if cmd == '/status':
            self._cmd_status()
        elif cmd == '/pause':
            self._cmd_pause()
        elif cmd == '/resume':
            self._cmd_resume()
        elif cmd == '/balance':
            self._cmd_balance()
        elif cmd == '/positions':
            self._cmd_positions()
        elif cmd == '/resetlocks':
            self._cmd_resetlocks()
        elif cmd == '/resetpeak':
            self._cmd_resetpeak()
        elif cmd == '/restart':
            self._cmd_restart()
        elif cmd == '/recalibrate':
            self._cmd_recalibrate()
        elif cmd == '/help':
            self._cmd_help()
        elif cmd == '/stop':
            self._cmd_stop()

    def _cmd_status(self):
        if not self.bot_controller: return
        try:
            bot = self.bot_controller
            balance = bot.client.get_balance() or 0
            positions = bot.position_manager.open_positions  # Access attribute, not method

            with bot.state_lock:
                is_paused = bot.paused

            state = "⏸️ PAUSED" if is_paused else "▶️ ACTIVE"

            msg = (
                f"🤖 <b>LIVE BOT STATUS</b>\n"
                f"──────────────────\n"
                f"<b>State:</b> {state}\n"
                f"<b>API Balance:</b> ${balance:,.2f}\n"
                f"<b>Open Positions:</b> {len(positions)}\n"
            )
            
            if len(positions) > 0:
                msg += f"\n📊 <b>Active Trades:</b> {len(positions)} markets"
            
            msg += f"\n\n⏰ <i>Updated: {self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
            self.send_message(msg)
        except Exception as e:
            self.send_message(f"❌ Error getting status: {str(e)}")

    def _cmd_pause(self):
        """Fix: Toggles the bot's paused attribute directly with thread safety"""
        if not self.bot_controller: return
        with self.bot_controller.state_lock:
            self.bot_controller.paused = True
        self.send_message("⏸️ <b>BOT PAUSED</b>\n\nNew trades will be logged but not executed.")
        logger.info("Bot paused via Telegram")

    def _cmd_resume(self):
        """Resumes bot and resets circuit breaker + peak balance if breaker was triggered"""
        if not self.bot_controller: return

        # Check if circuit breaker was triggered
        risk_manager = self.bot_controller.risk_manager
        was_breaker_active = risk_manager.circuit_breaker_triggered

        if was_breaker_active:
            # Get current balance and reset peak to current level
            try:
                current_balance = self.bot_controller.client.get_balance()
                if current_balance and current_balance > 0:
                    old_peak = risk_manager.peak_balance
                    risk_manager.reset_peak_balance(current_balance)
                    risk_manager.reset_circuit_breaker(manual_override=True)

                    msg = (
                        f"▶️ <b>BOT RESUMED</b>\n"
                        f"──────────────────\n"
                        f"🔄 <b>Circuit Breaker Reset</b>\n"
                        f"📊 <b>Peak Balance Reset</b>\n"
                        f"\n"
                        f"<b>Old Peak:</b> ${old_peak:.2f}\n"
                        f"<b>New Peak:</b> ${current_balance:.2f}\n"
                        f"<b>Fresh Start:</b> 0% drawdown\n"
                        f"\n"
                        f"✅ Bot is now scanning and trading actively."
                    )
                    self.send_message(msg)
                    logger.info(f"Bot resumed via Telegram - Circuit breaker reset, peak reset from ${old_peak:.2f} to ${current_balance:.2f}")
                else:
                    self.send_message("⚠️ Could not get balance - please try again")
                    return
            except Exception as e:
                logger.error(f"Error resetting breaker/peak: {e}")
                self.send_message(f"❌ Error resetting: {str(e)}")
                return

        # Resume bot
        with self.bot_controller.state_lock:
            self.bot_controller.paused = False

        if not was_breaker_active:
            self.send_message("▶️ <b>BOT RESUMED</b>\n\nBot is now scanning and trading actively.")
            logger.info("Bot resumed via Telegram")

    def _cmd_stop(self):
        if not self.bot_controller: return
        self.send_message("🛑 <b>STOPPING BOT</b>\n\nShutting down gracefully...")
        self.bot_controller.stop()

    def _cmd_restart(self):
        """Restart the bot via pm2 (instant, equivalent to `pm2 restart`)"""
        import subprocess
        self.send_message("🔄 <b>RESTARTING BOT</b>\n\nRestarting via pm2...")
        logger.info("Bot restart initiated via Telegram")
        subprocess.Popen(['pm2', 'restart', 'kalshi-bot-15m'])

    def _cmd_positions(self):
        if not self.bot_controller: return
        try:
            positions = self.bot_controller.position_manager.open_positions  # Access attribute, not method
            if not positions:
                self.send_message("📭 No open positions.")
                return

            msg = f"📊 <b>OPEN POSITIONS ({len(positions)})</b>\n\n"
            for i, pos in enumerate(positions, 1):
                ticker = pos.get('ticker') or "Unknown"
                side = pos.get('side', 'yes').upper()
                side_emoji = "✅" if side == 'YES' else "❌"
                msg += f"<b>{i}. <code>{ticker}</code></b>\n{side_emoji} Side: {side}\n\n"
            self.send_message(msg)
        except Exception as e:
            self.send_message(f"❌ Error: {str(e)}")

    def _cmd_balance(self):
        if not self.bot_controller: return
        try:
            balance = self.bot_controller.client.get_balance()
            self.send_message(f"💰 <b>Balance:</b> ${balance:,.2f}")
        except Exception as e:
            self.send_message(f"❌ Error: {str(e)}")

    def _cmd_resetlocks(self):
        """Reset all ticker locks (allows retrying previously locked tickers)"""
        if not self.bot_controller: return
        try:
            # Get counts before reset
            preventive_count = len(self.bot_controller.edge_detector.preventive_lock_timestamps)
            regular_count = len(self.bot_controller.edge_detector.traded_tickers)

            # Reset all locks
            self.bot_controller.edge_detector.reset_locks()

            msg = (
                f"♻️ <b>LOCKS RESET</b>\n"
                f"──────────────────\n"
                f"✅ Cleared {preventive_count} preventive locks\n"
                f"✅ Cleared {regular_count} ticker locks\n"
                f"\n💡 All tickers can now be traded again.\n"
                f"\n⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
            )
            self.send_message(msg)
            logger.info(f"Ticker locks reset via Telegram (preventive: {preventive_count}, regular: {regular_count})")
        except Exception as e:
            self.send_message(f"❌ Error resetting locks: {str(e)}")
            logger.error(f"Error in /resetlocks command: {e}")

    def _cmd_resetpeak(self):
        """Reset peak balance to current live Kalshi balance."""
        if not self.bot_controller: return
        try:
            balance = self.bot_controller.client.get_balance()
            if not balance or balance <= 0:
                self.send_message("❌ Could not fetch live balance. Peak not changed.")
                return

            old_peak = self.bot_controller.risk_manager.peak_balance
            self.bot_controller.risk_manager.peak_balance = balance
            self.bot_controller.risk_manager._save_peak_balance()

            msg = (
                f"🔄 <b>PEAK BALANCE RESET</b>\n"
                f"──────────────────\n"
                f"<b>Old Peak:</b> ${old_peak:,.2f}\n"
                f"<b>New Peak:</b> ${balance:,.2f} (current balance)\n"
                f"\n💡 Drawdown % is now calculated from ${balance:,.2f}\n"
                f"\n⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
            )
            self.send_message(msg)
            logger.info(f"Peak balance reset via Telegram: ${old_peak:.2f} → ${balance:.2f}")
        except Exception as e:
            self.send_message(f"❌ Error resetting peak: {str(e)}")
            logger.error(f"Error in /resetpeak command: {e}")

    def _cmd_recalibrate(self):
        """Recompute v4 step-function base probabilities from skipped_trades.csv."""
        if not self.bot_controller:
            return

        momentum = getattr(self.bot_controller, 'momentum', None)
        if not hasattr(momentum, 'recalibrate'):
            self.send_message(
                "⚠️ <b>/recalibrate requires probability_model: v4</b>\n\n"
                "Current model does not support recalibration."
            )
            return

        self.send_message(
            "🔄 <b>Recalibrating...</b>\n\n"
            "Reading skipped_trades.csv with exponential time-decay weighting.\n"
            "This may take a few seconds."
        )

        try:
            result = momentum.recalibrate()
        except Exception as e:
            self.send_message(f"❌ <b>Recalibration error:</b> {str(e)}")
            logger.error(f"Error in /recalibrate: {e}")
            return

        if not result['success']:
            self.send_message(f"❌ <b>Recalibration failed:</b>\n{result['reason']}")
            return

        # Human-readable bucket labels
        bucket_labels = [
            ">3σ above  ",
            "1.5–3σ above",
            "0.7–1.5σ above",
            "0–0.7σ above",
            "0–0.7σ below",
            "0.7–1.5σ below",
            "1.5–3σ below",
            ">3σ below  ",
        ]

        old = result['old_probs']
        new = result['new_probs']

        lines = []
        changed = 0
        for i, (o, n, label) in enumerate(zip(old, new, bucket_labels)):
            delta = n - o
            if abs(delta) >= 0.005:
                arrow = "↑" if delta > 0 else "↓"
                lines.append(f"<code>{label}</code>  {o:.3f} {arrow} <b>{n:.3f}</b>  ({delta:+.3f})")
                changed += 1
            else:
                lines.append(f"<code>{label}</code>  {o:.3f} → {n:.3f}")

        body = "\n".join(lines)
        summary = f"{changed} bucket(s) updated" if changed else "no changes (model was already calibrated)"

        msg = (
            f"✅ <b>RECALIBRATION COMPLETE</b>\n"
            f"──────────────────\n"
            f"{body}\n\n"
            f"<i>{summary}</i>\n"
            f"⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
        )
        self.send_message(msg)
        logger.info(f"Recalibration complete via Telegram ({changed} buckets changed)")

    def _cmd_help(self):
        msg = (
            "🤖 <b>AVAILABLE COMMANDS</b>\n"
            "──────────────────\n"
            "/status - Bot health & state\n"
            "/positions - List active trades\n"
            "/balance - Check wallet\n"
            "/resetlocks - Clear all ticker locks\n"
            "/resetpeak - Reset peak balance to current balance\n"
            "/recalibrate - Refit v4 probability model from outcome data\n"
            "/pause - Pause execution\n"
            "/resume - Start execution\n"
            "/restart - Restart bot\n"
            "/stop - Shutdown bot\n"
            "/help - Show this list"
        )
        self.send_message(msg)

    def _test_connection(self):
        try:
            self.send_message("🤖 <b>Kalshi Bot Connected</b>\n\nReady to trade!")
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            self.enabled = False

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled: return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def send_trade_alert(self, position_data: Dict):
        return self.notify_position_opened(position_data)

    def notify_position_opened(self, position: Dict):
        ticker = position.get('ticker', 'Unknown')
        symbol = position.get('symbol', ticker)
        side = position.get('side', 'yes').upper()
        entry = position.get('entry_price', 0)
        contracts = position.get('contracts', 0)
        cost = position.get('cost', 0)
        balance = position.get('current_balance', 0)
        msg = (
            f"🚀 <b>POSITION OPENED - CONFIRMED</b>\n"
            f"──────────────────\n"
            f"<b>Market:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Ticker:</b> <code>{ticker}</code>\n"
            f"\n"
            f"<b>Entry Price:</b> ${entry:.2f}\n"
            f"<b>Contracts:</b> {contracts:.2f}\n"
            f"<b>Total Cost:</b> ${cost:.2f}\n"
            f"\n"
            f"<b>New Balance:</b> ${balance:,.2f}\n"
            f"\n"
            f"✅ <i>Confirmed by Kalshi</i>\n"
            f"⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
        )
        self.send_message(msg)

    def notify_position_closed(self, position: Dict, exit_price: float, account_balance: float = None):
        """
        Send detailed notification when a position is closed.

        Args:
            position: Position dict with ticker, side, entry_price, count, exit_reason (optional)
            exit_price: The price at which position was closed
            account_balance: Current account balance (optional)
        """
        ticker = position.get('ticker', 'Unknown')
        side = position.get('side', 'yes').upper()
        entry_price = position.get('entry_price', 0)
        count = position.get('count', 1)
        exit_reason = position.get('exit_reason', None)

        # Calculate financial metrics
        original_cost = entry_price * count
        payout = exit_price * count
        pnl_dollars = payout - original_cost
        roi_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Format market name from ticker (e.g., KXBTC15M-05FEB-1430-A95000 -> BTC 15min)
        market_name = self._format_market_name(ticker, side)

        # Choose emoji based on outcome
        if roi_pct > 0:
            outcome_emoji = "💰"
            outcome_text = "PROFIT"
        elif roi_pct < 0:
            outcome_emoji = "📉"
            outcome_text = "LOSS"
        else:
            outcome_emoji = "⚖️"
            outcome_text = "BREAKEVEN"

        msg = (
            f"{outcome_emoji} <b>ORDER CLOSED - {outcome_text}</b>\n"
            f"──────────────────\n"
            f"<b>Market:</b> {market_name}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Ticker:</b> <code>{ticker}</code>\n"
        )

        # Add exit reason if available
        if exit_reason:
            msg += f"<b>Reason:</b> {exit_reason}\n"

        msg += (
            f"\n"
            f"<b>Entry Price:</b> ${entry_price:.2f}\n"
            f"<b>Exit Price:</b> ${exit_price:.2f}\n"
            f"<b>Contracts:</b> {count}\n"
            f"\n"
            f"<b>Original Cost:</b> ${original_cost:.2f}\n"
            f"<b>Payout:</b> ${payout:.2f}\n"
            f"<b>P&L:</b> ${pnl_dollars:+.2f}\n"
            f"<b>ROI:</b> {roi_pct:+.1f}%\n"
        )

        # Add account balance if provided
        if account_balance is not None:
            msg += f"\n<b>New Balance:</b> ${account_balance:,.2f}\n"

        msg += f"\n⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"

        self.send_message(msg)

    def _format_market_name(self, ticker: str, side: str) -> str:
        """
        Format ticker into readable market name.
        Examples:
            KXBTC15M-05FEB-1430-A95000 YES -> BTC Above $95,000 - 15min YES
            KXETH15M-05FEB-1430-B3500 NO -> ETH Below $3,500 - 15min NO
            KXBTC15M-05FEB-1430-U95000 NO -> BTC Up or Down - 15min NO
        """
        # Extract symbol
        if 'BTC' in ticker.upper():
            symbol = 'BTC'
        elif 'ETH' in ticker.upper():
            symbol = 'ETH'
        elif 'SOL' in ticker.upper():
            symbol = 'SOL'
        else:
            symbol = ticker.split('-')[0].replace('KX', '').replace('15M', '')

        # Extract market type and threshold
        if '-A' in ticker:
            # Above market (e.g., A95000)
            import re
            match = re.search(r'A(\d+)', ticker)
            threshold = f"${int(match.group(1)):,}" if match else ""
            market_type = f"Above {threshold}"
        elif '-B' in ticker:
            # Below market
            import re
            match = re.search(r'B(\d+)', ticker)
            threshold = f"${int(match.group(1)):,}" if match else ""
            market_type = f"Below {threshold}"
        elif '-U' in ticker or '-D' in ticker:
            # Up/Down market
            market_type = "Up or Down"
        else:
            market_type = ""

        return f"{symbol} {market_type} - 15min {side}"
