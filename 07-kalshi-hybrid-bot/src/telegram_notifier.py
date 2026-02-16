"""
Telegram Notifier
Sends notifications about bot activity via Telegram.
Handles interactive commands (/help, /status, etc.)
"""

import logging
import requests
import threading
import time
from typing import Dict, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self, config: Dict):
        self.config = config.get('notifications', {}).get('telegram', {})
        self.alerts_config = config.get('notifications', {}).get('alerts', {})

        self.enabled = self.config.get('enabled', False)
        self.bot_token = self.config.get('bot_token', '')
        self.chat_id = self.config.get('chat_id', '')

        # Command handlers
        self.bot_instance = None  # Will be set by main bot
        self.last_update_id = 0
        self.command_thread = None
        self.running = False

        if self.enabled:
            if not self.bot_token or not self.chat_id:
                logger.warning("⚠️  Telegram enabled but missing bot_token or chat_id")
                self.enabled = False
            else:
                logger.info("✅ Telegram notifications enabled")
                self._send_test_message()
                self._start_command_listener()
        else:
            logger.info("📴 Telegram notifications disabled")

    def _send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send a message via Telegram."""

        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def _send_test_message(self):
        """Send test message on startup."""

        msg = (
            "🚀 *Kalshi Hybrid Bot Started*\n\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            "Status: Online ✅\n\n"
            "I'll notify you about opportunities and trades!"
        )

        self._send_message(msg)

    def notify_opportunity_found(self, opportunity: Dict, in_paper_mode: bool = True):
        """Notify when an opportunity is found."""

        if not self.alerts_config.get('on_trade', True):
            return

        mode_emoji = "🎲" if opportunity['mode'] == 'lottery' else "⚖️"
        paper_tag = "📝 PAPER MODE" if in_paper_mode else "💰 LIVE"

        msg = (
            f"{mode_emoji} *Opportunity Found* {paper_tag}\n\n"
            f"*Market:* `{opportunity['ticker']}`\n"
            f"*Mode:* {opportunity['mode'].upper()}\n"
            f"*Symbol:* {opportunity['symbol']}\n\n"
            f"*Entry:* ${opportunity['entry_price']:.2f}\n"
            f"*Size:* {opportunity['position_size']} contracts\n"
            f"*Cost:* ${opportunity['total_cost']:.2f}\n\n"
            f"*Win Probability:* {opportunity['probability']:.1%}\n"
            f"*Expected Value:* {opportunity['expected_value']:.1%}\n"
            f"*Momentum:* {opportunity['momentum_pct']:.2%}\n\n"
            f"*Closes in:* {opportunity['minutes_to_close']:.1f} minutes"
        )

        self._send_message(msg)

    def notify_trade_executed(self, trade: Dict):
        """Notify when a trade is executed."""

        if not self.alerts_config.get('on_trade', True):
            return

        msg = (
            f"✅ *Trade Executed*\n\n"
            f"*Market:* `{trade['ticker']}`\n"
            f"*Side:* {trade['side'].upper()}\n"
            f"*Price:* ${trade['entry_price']:.2f}\n"
            f"*Quantity:* {trade['quantity']} contracts\n"
            f"*Total Cost:* ${trade['total_cost']:.2f}\n\n"
            f"*Expected Profit:* ${trade.get('expected_profit', 0):.2f}"
        )

        self._send_message(msg)

    def notify_trade_closed(self, trade: Dict, profit: float, won: bool):
        """Notify when a trade closes."""

        if won and not self.alerts_config.get('on_win', True):
            return

        if not won and not self.alerts_config.get('on_loss', False):
            return

        emoji = "🎉" if won else "❌"
        outcome = "WON" if won else "LOST"

        msg = (
            f"{emoji} *Trade {outcome}*\n\n"
            f"*Market:* `{trade['ticker']}`\n"
            f"*Entry:* ${trade['entry_price']:.2f}\n"
            f"*Quantity:* {trade['quantity']} contracts\n\n"
            f"*Profit/Loss:* ${profit:+.2f}\n"
            f"*ROI:* {(profit / trade['total_cost']) * 100:+.1f}%"
        )

        self._send_message(msg)

    def notify_daily_summary(self, summary: Dict):
        """Send daily performance summary."""

        if not self.alerts_config.get('on_daily_summary', True):
            return

        msg = (
            f"📊 *Daily Summary*\n\n"
            f"*Date:* {summary['date']}\n\n"
            f"*Opportunities:* {summary['opportunities_found']}\n"
            f"*Trades:* {summary['trades_executed']}\n"
            f"*Wins:* {summary['wins']} ({summary['win_rate']:.1%})\n"
            f"*Losses:* {summary['losses']}\n\n"
            f"*Total Profit:* ${summary['total_profit']:+.2f}\n"
            f"*ROI:* {summary['roi']:.1%}\n\n"
            f"*Balance:* ${summary['ending_balance']:.2f}"
        )

        self._send_message(msg)

    def notify_error(self, error_msg: str):
        """Notify about errors."""

        if not self.alerts_config.get('on_error', True):
            return

        msg = (
            f"⚠️ *Bot Error*\n\n"
            f"```\n{error_msg[:500]}\n```\n\n"
            f"Check logs for details"
        )

        self._send_message(msg)

    def notify_bot_stopped(self):
        """Notify when bot stops."""

        msg = (
            f"🛑 *Bot Stopped*\n\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"Status: Offline"
        )

        self._send_message(msg)
        self._stop_command_listener()

    def set_bot_instance(self, bot):
        """Set reference to main bot for command handling."""
        self.bot_instance = bot

    def _start_command_listener(self):
        """Start background thread to listen for Telegram commands."""

        if not self.enabled:
            return

        self.running = True
        self.command_thread = threading.Thread(target=self._poll_commands, daemon=True)
        self.command_thread.start()
        logger.info("✅ Telegram command listener started")

    def _stop_command_listener(self):
        """Stop command listener."""

        self.running = False
        if self.command_thread:
            self.command_thread.join(timeout=2)

    def _poll_commands(self):
        """Poll for Telegram commands."""

        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {
                    'offset': self.last_update_id + 1,
                    'timeout': 10,
                    'allowed_updates': ['message']
                }

                response = requests.get(url, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('ok') and data.get('result'):
                        for update in data['result']:
                            self.last_update_id = update['update_id']
                            self._handle_update(update)

            except Exception as e:
                logger.debug(f"Error polling commands: {e}")
                time.sleep(5)

            time.sleep(1)

    def _handle_update(self, update: Dict):
        """Handle incoming Telegram update."""

        try:
            message = update.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            text = message.get('text', '')

            # Only respond to messages from configured chat
            if str(chat_id) != str(self.chat_id):
                return

            # Handle commands
            if text.startswith('/'):
                self._handle_command(text.lower())

        except Exception as e:
            logger.error(f"Error handling update: {e}")

    def _handle_command(self, command: str):
        """Handle Telegram bot command."""

        command = command.split()[0]  # Get first word only

        if command == '/help':
            self._send_help()
        elif command == '/status':
            self._send_status()
        elif command == '/balance':
            self._send_balance()
        elif command == '/config':
            self._send_config()
        elif command == '/stats':
            self._send_stats()
        elif command == '/pause':
            self._toggle_pause(True)
        elif command == '/resume':
            self._toggle_pause(False)
        else:
            msg = f"Unknown command: {command}\n\nSend /help for available commands"
            self._send_message(msg)

    def _send_help(self):
        """Send help message with available commands."""

        msg = (
            "🤖 *Kalshi Hybrid Bot Commands*\n\n"
            "*Status & Info:*\n"
            "/help - Show this help message\n"
            "/status - Bot status and mode\n"
            "/balance - Account balance\n"
            "/config - Current configuration\n"
            "/stats - Performance statistics\n\n"
            "*Control:*\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading\n\n"
            "*Tips:*\n"
            "• You'll get notifications for every opportunity\n"
            "• Paper mode = notifications only, no trades\n"
            "• Live mode = real trades executed\n\n"
            "Questions? Check the logs:\n"
            "`./bot-control.sh logs`"
        )

        self._send_message(msg)

    def _send_status(self):
        """Send current bot status."""

        if not self.bot_instance:
            self._send_message("⚠️ Bot instance not available")
            return

        paused = self.bot_instance.paused
        mode = self.bot_instance.edge_detector.mode

        msg = (
            f"📊 *Bot Status*\n\n"
            f"*Mode:* {mode.upper()}\n"
            f"*Status:* {'⏸️ PAUSED (Paper Trading)' if paused else '▶️ LIVE TRADING'}\n"
            f"*Price Range:* ${self.bot_instance.edge_detector.min_price:.2f} - "
            f"${self.bot_instance.edge_detector.max_price:.2f}\n\n"
            f"*Active Filters:*\n"
            f"✅ Volume confirmation\n"
            f"✅ Order book imbalance\n"
            f"✅ Regime detection\n"
            f"✅ Execution protection\n\n"
            f"*Symbols:* {', '.join(self.bot_instance.config['strategy']['symbols'])}\n"
            f"*Scan Interval:* {self.bot_instance.config['bot']['scan_interval_seconds']}s"
        )

        self._send_message(msg)

    def _send_balance(self):
        """Send account balance (placeholder)."""

        msg = (
            f"💰 *Account Balance*\n\n"
            f"_Balance info will be available once_\n"
            f"_position tracking is implemented_\n\n"
            f"For now, check your Kalshi account directly"
        )

        self._send_message(msg)

    def _send_config(self):
        """Send current configuration."""

        if not self.bot_instance:
            self._send_message("⚠️ Bot instance not available")
            return

        config = self.bot_instance.config['strategy']

        msg = (
            f"⚙️ *Configuration*\n\n"
            f"*Mode:* {self.bot_instance.edge_detector.mode.upper()}\n"
            f"*Price Range:* ${config['entry_price_range']['min']:.2f} - "
            f"${config['entry_price_range']['max']:.2f}\n\n"
            f"*Time Window:* {config['time_window']['min_minutes_to_close']}-"
            f"{config['time_window']['max_minutes_to_close']} minutes\n\n"
            f"*Volume:* {'✅' if config['volume']['enabled'] else '❌'} "
            f"({config['volume']['min_volume_ratio']}x min)\n"
            f"*Orderbook:* {'✅' if config['orderbook']['enabled'] else '❌'} "
            f"({config['orderbook']['min_imbalance']:.0%} min)\n"
            f"*Regime:* {'✅' if config['regime']['enabled'] else '❌'} "
            f"(trending only)\n\n"
            f"*Risk Limits:*\n"
            f"• Max daily loss: ${self.bot_instance.config['capital']['max_daily_loss']}\n"
            f"• Max weekly loss: ${self.bot_instance.config['capital']['max_weekly_loss']}"
        )

        self._send_message(msg)

    def _send_stats(self):
        """Send performance statistics (placeholder)."""

        msg = (
            f"📈 *Performance Stats*\n\n"
            f"_Statistics will be available once_\n"
            f"_position tracking is implemented_\n\n"
            f"For now:\n"
            f"• Check logs for opportunities found\n"
            f"• Track Telegram notifications\n\n"
            f"Command: `./bot-control.sh logs`"
        )

        self._send_message(msg)

    def _toggle_pause(self, pause: bool):
        """Toggle bot pause state."""

        if not self.bot_instance:
            self._send_message("⚠️ Bot instance not available")
            return

        if pause and self.bot_instance.paused:
            msg = "⏸️ Bot is already paused"
        elif not pause and not self.bot_instance.paused:
            msg = "▶️ Bot is already running"
        else:
            self.bot_instance.paused = pause

            if pause:
                msg = (
                    "⏸️ *Bot Paused*\n\n"
                    "Trading halted. Bot will continue scanning\n"
                    "but won't execute trades.\n\n"
                    "Send /resume to continue trading"
                )
            else:
                msg = (
                    "▶️ *Bot Resumed*\n\n"
                    "⚠️ *LIVE TRADING ACTIVE*\n\n"
                    "Bot will now execute real trades!\n\n"
                    "Send /pause to stop trading"
                )

        self._send_message(msg)
