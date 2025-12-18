"""
Telegram Notifier
Sends trading alerts and updates via Telegram bot
Handles remote control commands with LIVE API status
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
        if not self.enabled: return
        self._clear_old_updates()
        self.running = True
        self.command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self.command_thread.start()
        logger.info("Telegram command listener started")

    def _clear_old_updates(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, params={"timeout": 1, "limit": 100}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    if updates:
                        self.last_update_id = max([u['update_id'] for u in updates])
                        logger.info("No old Telegram updates to clear")
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
                time.sleep(2)
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
                
                if chat_id == str(self.chat_id):
                    text = message.get('text', '').strip()
                    if text.startswith('/'):
                        logger.info(f"Received Telegram command: {text}")
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
        elif cmd == '/help':
            self._cmd_help()
        elif cmd == '/stop':
            self._cmd_stop()

    def _cmd_status(self):
        """Standardized Status using RiskManager metrics"""
        if not self.bot_controller:
            return
            
        try:
            bot = self.bot_controller
            balance = bot.client.get_balance() or 0
            
            # Get positions using the bot's managers for consistency
            positions = bot.position_manager.get_open_positions()
            metrics = bot.risk_manager.get_portfolio_metrics(positions, balance)

            state = "⏸️ PAUSED" if bot.paused else "▶️ ACTIVE"

            msg = (
                f"🤖 <b>LIVE BOT STATUS</b>\n"
                f"──────────────────\n"
                f"<b>State:</b> {state}\n"
                f"<b>API Balance:</b> ${balance:,.2f}\n"
                f"<b>Open Positions:</b> {len(positions)}\n"
                f"<b>Live Exposure:</b> ${metrics['total_deployed']:,.2f}\n"
                f"<b>Utilization:</b> {metrics['utilization']:.1%}\n"
            )

            if len(positions) > 0:
                msg += f"\n📊 <b>Active Trades:</b> {len(positions)} markets"
            else:
                msg += "\n✅ <b>Ghost Status:</b> No exposure."

            msg += f"\n\n⏰ <i>Updated: {self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
            self.send_message(msg)
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            self.send_message(f"❌ Error getting status: {str(e)}")

    def _cmd_positions(self):
        """List current trades with cost, side, and title"""
        if not self.bot_controller:
            return
            
        try:
            positions = self.bot_controller.position_manager.get_open_positions()
            
            if not positions:
                self.send_message("📭 No open positions.")
                return

            msg = f"📊 <b>OPEN POSITIONS ({len(positions)})</b>\n\n"
            
            for i, pos in enumerate(positions, 1):
                ticker = pos.get('ticker') if isinstance(pos, dict) else getattr(pos, 'ticker', 'Unknown')
                title = pos.get('title', '') if isinstance(pos, dict) else getattr(pos, 'title', '')
                side = pos.get('side', 'yes') if isinstance(pos, dict) else getattr(pos, 'side', 'yes')
                
                # Try to get cost from various SDK fields
                cost_raw = 0
                if isinstance(pos, dict):
                    cost_raw = pos.get('position_cost') or pos.get('cost') or 0
                else:
                    cost_raw = getattr(pos, 'position_cost', 0) or getattr(pos, 'cost', 0)

                cost_dollars = cost_raw / 10000 if cost_raw > 1000 else cost_raw
                
                side_emoji = "✅" if side.lower() == 'yes' else "❌"
                
                # Market ticker first, then title underneath
                msg += f"<b>{i}. <code>{ticker}</code></b>\n"
                if title:
                    msg += f"<i>{title[:60]}</i>\n"  # Truncate long titles
                
                msg += f"{side_emoji} Side: {side.upper()} | 💰 ${cost_dollars:,.2f}\n\n"

            self.send_message(msg)
            
        except Exception as e:
            logger.error(f"Error in positions command: {e}")
            self.send_message(f"❌ Error getting positions: {str(e)}")

    def _cmd_pause(self):
        if not self.bot_controller:
            return
        if self.bot_controller.pause():
            self.send_message("⏸️ <b>BOT PAUSED</b>\n\nBot will not open new positions.")

    def _cmd_resume(self):
        if not self.bot_controller:
            return
        if self.bot_controller.resume():
            self.send_message("▶️ <b>BOT RESUMED</b>\n\nBot is now actively trading.")

    def _cmd_balance(self):
        if not self.bot_controller:
            return
        try:
            balance = self.bot_controller.client.get_balance()
            if balance is not None:
                self.send_message(f"💰 <b>Current Balance:</b> ${balance:,.2f}")
            else:
                self.send_message("❌ Could not retrieve balance")
        except Exception as e:
            self.send_message(f"❌ Error: {str(e)}")

    def _cmd_stop(self):
        if not self.bot_controller:
            return
        self.send_message("🛑 <b>STOPPING BOT</b>\n\nShutting down gracefully...")
        self.bot_controller.stop()

    def _cmd_help(self):
        msg = (
            "🤖 <b>AVAILABLE COMMANDS</b>\n"
            "──────────────────\n"
            "/status - Show bot status\n"
            "/positions - List open positions\n"
            "/balance - Check account balance\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading\n"
            "/stop - Stop bot\n"
            "/help - Show this message"
        )
        self.send_message(msg)

    def _test_connection(self):
        try:
            self.send_message("🤖 <b>Kalshi Bot Connected</b>\n\nReady to trade!")
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            self.enabled = False

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        if not self.enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def notify_position_opened(self, position: Dict):
        """Enhanced notification showing side, probability, and key metrics"""
        side = position.get('side', 'yes').upper()
        prob = position.get('probability', 0)
        entry = position.get('entry_price', 0)
        exp_return = position.get('expected_return', 0)
        cost = position.get('cost', 0)
        ticker = position.get('ticker', 'Unknown')
        title = position.get('title', '')
        days = position.get('days_to_close', 0)
        
        # Emoji based on side
        side_emoji = "✅" if side == 'YES' else "❌"
        
        # Build title line (if available) - AFTER TICKER
        title_line = f"<i>{title}</i>\n" if title else ""
        
        msg = (
            f"🚀 <b>POSITION OPENED</b>\n"
            f"──────────────────\n"
            f"<b>Market:</b> <code>{ticker}</code>\n"
            f"{title_line}"
            f"{side_emoji} <b>Side:</b> {side}\n"
            f"📊 <b>Probability:</b> {prob:.1%}\n"
            f"💵 <b>Entry Price:</b> ${entry:.2f}\n"
            f"📈 <b>Expected Return:</b> {exp_return:.1%}\n"
            f"💰 <b>Position Size:</b> ${cost:,.2f}\n"
            f"⏱️ <b>Days to Close:</b> {days:.1f}\n"
            f"\n⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
        )
        self.send_message(msg)

    def notify_position_closed(self, position: Dict):
        """Enhanced close notification with side and profit details"""
        won = position.get('won', False)
        pnl = position.get('pnl', 0)
        ticker = position.get('ticker', 'Unknown')
        title = position.get('title', '')
        side = position.get('side', 'yes').upper()
        
        result_emoji = "🎉" if won else "😞"
        result_text = "WON" if won else "LOST"
        side_emoji = "✅" if side == 'YES' else "❌"
        
        # Build title line (if available) - AFTER TICKER
        title_line = f"<i>{title}</i>\n" if title else ""
        
        msg = (
            f"{result_emoji} <b>CLOSED - {result_text}</b>\n"
            f"──────────────────\n"
            f"<b>Market:</b> <code>{ticker}</code>\n"
            f"{title_line}"
            f"{side_emoji} <b>Side:</b> {side}\n"
            f"💰 <b>P&L:</b> ${pnl:+,.2f}\n"
            f"\n⏰ <i>{self._get_eastern_time().strftime('%H:%M:%S ET')}</i>"
        )
        self.send_message(msg)

    def notify_error(self, error_msg: str, details: Optional[str] = None):
        """Send error notification"""
        msg = f"⚠️ <b>ERROR ALERT</b>\n\n<b>Error:</b> {error_msg}"
        if details:
            msg += f"\n<b>Details:</b> {details[:200]}"  # Truncate long details
        msg += f"\n\n⏰ {self._get_eastern_time().strftime('%I:%M %p ET')}"
        self.send_message(msg)

    def notify_daily_summary(self, stats: Dict, portfolio_metrics: Dict):
        """Enhanced daily summary with more metrics"""
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = stats.get('total_pnl', 0)
        
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        msg = (
            f"📊 <b>DAILY SUMMARY</b>\n"
            f"──────────────────\n"
            f"<b>Total Trades:</b> {total_trades}\n"
            f"<b>Wins:</b> {wins} | <b>Losses:</b> {losses}\n"
            f"<b>Win Rate:</b> {win_rate:.1f}%\n"
            f"{pnl_emoji} <b>Total P&L:</b> ${total_pnl:+,.2f}\n"
            f"\n⏰ <i>{self._get_eastern_time().strftime('%I:%M %p ET')}</i>"
        )
        self.send_message(msg)

    def notify_opportunities_found(self, count: int, summary: Dict):
        """Optional: Notify when opportunities are found"""
        # Currently disabled to avoid spam
        # You can enable this if you want alerts when bot finds opportunities
        pass
