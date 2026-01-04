import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class RiskManager:
    """Manages risk and position sizing using real-time API data"""

    def __init__(self, config: Dict, telegram_notifier=None):
        self.config = config
        self.capital_config = config['capital']
        self.risk_config = config['risk']
        self.telegram = telegram_notifier
        self.total_capital = self.capital_config['total_capital']
        self.daily_starting_balance = self.total_capital
        self.last_reset_date = date.today()

        # Drawdown circuit breaker
        self.max_drawdown_pct = self.risk_config.get('max_drawdown_pct', 0.15)  # Default 15%
        self.circuit_breaker_enabled = self.risk_config.get('circuit_breaker_enabled', True)
        self.state_file = Path('data/risk_state.json')
        self.state_file.parent.mkdir(exist_ok=True, parents=True)

        # Load or initialize peak balance and breaker state
        self.peak_balance = self._load_peak_balance()
        self.circuit_breaker_triggered = self._load_breaker_state()

        logger.info(f"✅ Risk manager initialized (Max DD: {self.max_drawdown_pct:.1%}, "
                   f"Peak: ${self.peak_balance:.2f}, Breaker: {'ACTIVE' if self.circuit_breaker_triggered else 'OK'})")

        # Alert user via Telegram if breaker is already active on startup
        if self.circuit_breaker_triggered and self.telegram and self.telegram.enabled:
            self._send_breaker_active_alert()

    def get_live_positions(self, kalshi_client) -> List[Any]:
        """Queries Kalshi directly to ensure we have zero 'ghost' capital."""
        try:
            response = kalshi_client.get_positions()
            # The SDK often returns a response object with a .market_positions list
            if hasattr(response, 'market_positions'):
                return response.market_positions
            if isinstance(response, dict):
                return response.get('market_positions', [])
            return []
        except Exception as e:
            logger.error(f"❌ API Position Fetch Failed: {e}")
            return []

    def get_portfolio_metrics(self, positions: Any, current_balance: float) -> Dict:
        """Calculates metrics using centi-cent conversion."""
        # 1. Standardize to a list
        clean_positions = []
        if isinstance(positions, list):
            clean_positions = positions
        elif hasattr(positions, 'market_positions'):
            clean_positions = positions.market_positions
        
        # 2. Extract total cost in centi-cents
        total_centi = 0
        for p in clean_positions:
            # Check every possible attribute name the SDK might use
            val = 0
            if isinstance(p, dict):
                val = p.get('position_cost') or p.get('cost') or p.get('market_exposure', 0)
            else:
                val = getattr(p, 'position_cost', 0) or getattr(p, 'cost', 0) or getattr(p, 'market_exposure', 0)
            
            # If the value is tiny (e.g. 74.64 instead of 746400), it's already in dollars
            # If it's large, it's centi-cents.
            total_centi += val

        # 3. Safe conversion
        # Most Kalshi API fields are in centi-cents (1/10,000). 
        # If total_centi is very high, divide. If it's already < 1000, it might be dollars.
        if total_centi > 5000: # Threshold: If > $0.50 in centi-cents
             total_deployed = total_centi / 10000
        else:
             total_deployed = total_centi

        utilization = total_deployed / self.total_capital if self.total_capital > 0 else 0

        return {
            'total_deployed': total_deployed,
            'available_capital': current_balance,
            'total_capital': self.total_capital,
            'total_at_risk': total_deployed,
            'utilization': utilization,
            'num_positions': len(clean_positions)
        }

    def calculate_position_size(self, opportunity: Dict, current_balance: float) -> float:
        """
        Calculate optimal position size using Kelly Criterion

        Kelly Formula: f* = (bp - q) / b
        Where:
            f* = fraction of capital to bet
            b = odds received on bet (profit/stake)
            p = probability of winning
            q = probability of losing (1-p)

        We use Quarter-Kelly for safety (divide by 4)
        """
        # Extract probability and entry price
        win_prob = opportunity.get('expected_win_prob', opportunity.get('expected_probability', 0.60))
        entry_price = opportunity.get('entry_price', 0.50)

        if entry_price <= 0 or entry_price >= 1:
            logger.warning(f"Invalid entry price: {entry_price}, using fixed size")
            return self._fixed_position_size(current_balance)

        # Calculate odds (how much profit per $1 risked)
        # If we buy at $0.40 (40 cents), we risk $0.40 to win $0.60
        # Odds = profit/stake = $0.60/$0.40 = 1.5
        odds = (1.0 - entry_price) / entry_price

        # Kelly formula
        p = win_prob
        q = 1 - p
        b = odds

        if b <= 0:
            logger.warning(f"Non-positive odds: {b}, using fixed size")
            return self._fixed_position_size(current_balance)

        kelly_fraction = (b * p - q) / b

        # Safeguards
        if kelly_fraction <= 0:
            logger.info(f"Negative Kelly ({kelly_fraction:.3f}), skipping trade")
            return 0

        kelly_multiplier = self.risk_config.get('kelly_multiplier', 0.25)
        kelly_mode = self.risk_config.get('kelly_mode', 'standard')

        if kelly_mode == 'reverse':
            # Reverse Kelly: invert the fraction within [0, 1]
            # High confidence (large kelly_fraction) → small bet
            # Low confidence (small kelly_fraction) → big bet
            # Hypothesis: bot may overestimate high-probability signals;
            # lower-confidence trades offer better payout multiples.
            capped = min(kelly_fraction, 1.0)
            adjusted_kelly = max(0.0, 1.0 - capped) * kelly_multiplier
        else:
            # Standard Kelly
            adjusted_kelly = kelly_fraction * kelly_multiplier

        # Determine balance to use for Kelly calculation
        use_config_balance = self.risk_config.get('use_config_balance_for_kelly', False)
        kelly_base_balance = self.total_capital if use_config_balance else current_balance

        # Calculate raw position size
        raw_size = kelly_base_balance * adjusted_kelly

        # Apply percentage cap
        max_position_pct = self.config['strategy'].get('max_position_percent', 0.10)
        pct_cap = kelly_base_balance * max_position_pct

        # Apply absolute dollar caps
        min_size = self.risk_config.get('min_position_size', 1.0)
        max_size = self.risk_config.get('max_position_size', float('inf'))

        # Apply all limits: min, max, percentage cap, and available balance
        final_size = max(min_size, min(raw_size, pct_cap, max_size, current_balance))

        balance_source = "config" if use_config_balance else "live API"
        logger.debug(f"Kelly sizing [{kelly_mode}]: prob={p:.2%}, odds={b:.2f}, "
                    f"kelly={kelly_fraction:.3f}, adjusted={adjusted_kelly:.3f}, "
                    f"base_balance=${kelly_base_balance:.2f} ({balance_source}), "
                    f"raw=${raw_size:.2f}, final=${final_size:.2f}")

        return final_size

    def _fixed_position_size(self, current_balance: float) -> float:
        """Fallback to fixed position sizing if Kelly fails"""
        max_concurrent = self.config['strategy'].get('max_concurrent_trades', 2)
        max_position_pct = self.config['strategy'].get('max_position_percent', 0.10)
        return (current_balance * max_position_pct) / max_concurrent

    def can_open_position(self, opportunity: Dict, current_positions: list, current_balance: float) -> tuple[bool, str]:
        # Simple limit checks
        max_concurrent = self.config['strategy'].get('max_concurrent_trades', 4)
        if len(current_positions) >= max_concurrent:
            return False, "Max positions reached"
        
        # Ticker check
        ticker = opportunity['ticker']
        for p in current_positions:
            p_ticker = p.get('ticker') if isinstance(p, dict) else getattr(p, 'ticker', '')
            if p_ticker == ticker:
                return False, f"Already holding {ticker}"
        
        return True, "Passed"

    def evaluate_position_risk(self, opportunity: Dict, position_size: int) -> Dict:
        return {
            'expected_value': (position_size * opportunity['expected_return']),
            'max_loss': position_size
        }

    # ===== DRAWDOWN CIRCUIT BREAKER METHODS =====

    def _load_peak_balance(self) -> float:
        """
        Load peak balance from state file, or initialize with current capital

        Auto-syncs with config total_capital:
        - If saved peak < total_capital: use total_capital (capital added)
        - If saved peak > total_capital * 2: use total_capital (likely capital withdrawn)
        - Otherwise: use saved peak (normal trading)
        """
        saved_peak = None

        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    saved_peak = state.get('peak_balance')
            except Exception as e:
                logger.warning(f"Failed to load peak balance: {e}")

        # Auto-sync logic
        if saved_peak is None:
            # First time - use config capital
            logger.info(f"📊 Initializing peak balance: ${self.total_capital:.2f} (from config)")
            return self.total_capital

        elif saved_peak < self.total_capital:
            # Config capital increased - assume deposit
            logger.info(f"📊 Capital increased in config: ${saved_peak:.2f} → ${self.total_capital:.2f}")
            logger.info(f"✅ Peak auto-synced to new capital amount")
            return self.total_capital

        elif saved_peak > self.total_capital * 2:
            # Saved peak way higher than config - assume withdrawal or config reset
            logger.warning(f"⚠️ Saved peak (${saved_peak:.2f}) much higher than config capital (${self.total_capital:.2f})")
            logger.info(f"✅ Peak reset to config capital (assuming withdrawal)")
            return self.total_capital

        else:
            # Normal case - use saved peak
            logger.info(f"📊 Loaded peak balance: ${saved_peak:.2f}")
            return saved_peak

    def _load_breaker_state(self) -> bool:
        """Load circuit breaker triggered state"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('circuit_breaker_triggered', False)
            except Exception as e:
                logger.warning(f"Failed to load breaker state: {e}")
        return False

    def _save_peak_balance(self):
        """Persist peak balance to disk"""
        try:
            state = {
                'peak_balance': self.peak_balance,
                'last_updated': datetime.now().isoformat(),
                'circuit_breaker_triggered': self.circuit_breaker_triggered
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save peak balance: {e}")

    def check_drawdown(self, current_balance: float, bot_controller=None) -> Tuple[bool, float]:
        """
        Check if current drawdown exceeds max threshold

        Returns:
            (breaker_triggered, drawdown_pct)
        """
        if not self.circuit_breaker_enabled:
            return False, 0.0

        # Handle None balance (API failure)
        if current_balance is None or current_balance <= 0:
            logger.warning("⚠️ Cannot check drawdown - balance is None or invalid")
            return self.circuit_breaker_triggered, 0.0

        # Update peak if we hit new high
        if current_balance > self.peak_balance:
            old_peak = self.peak_balance
            self.peak_balance = current_balance
            self._save_peak_balance()
            logger.info(f"🎉 New peak balance: ${self.peak_balance:.2f} (previous: ${old_peak:.2f})")

        # Calculate current drawdown
        if self.peak_balance <= 0:
            return False, 0.0

        drawdown = (self.peak_balance - current_balance) / self.peak_balance

        # Reset circuit breaker if we recovered (drawdown is 0 or negative)
        if drawdown <= 0 and self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = False
            self._save_peak_balance()
            logger.info("✅ Circuit breaker reset - recovered from drawdown")

        # Check if drawdown exceeds threshold
        if drawdown > self.max_drawdown_pct and not self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = True
            self._save_peak_balance()
            self._trigger_circuit_breaker(drawdown, current_balance, bot_controller)
            return True, drawdown

        # Log warning if approaching threshold
        warning_threshold = self.max_drawdown_pct * 0.8  # 80% of max (e.g., 12% if max is 15%)
        if drawdown > warning_threshold and not self.circuit_breaker_triggered:
            logger.warning(f"⚠️ Drawdown approaching limit: {drawdown:.1%} "
                          f"(threshold: {self.max_drawdown_pct:.1%})")

        return self.circuit_breaker_triggered, drawdown

    def _trigger_circuit_breaker(self, drawdown: float, current_balance: float,
                                 bot_controller=None):
        """
        Halt trading and send alerts when circuit breaker triggers

        Args:
            drawdown: Current drawdown percentage
            current_balance: Current account balance
            bot_controller: Reference to main bot (to pause trading)
        """
        logger.critical("=" * 60)
        logger.critical("🛑 CIRCUIT BREAKER TRIGGERED")
        logger.critical("=" * 60)
        logger.critical(f"Current Drawdown: {drawdown:.1%}")
        logger.critical(f"Max Allowed: {self.max_drawdown_pct:.1%}")
        logger.critical(f"Peak Balance: ${self.peak_balance:.2f}")
        logger.critical(f"Current Balance: ${current_balance:.2f}")
        logger.critical(f"Loss: ${self.peak_balance - current_balance:.2f}")
        logger.critical("=" * 60)
        logger.critical("🛑 TRADING HALTED - MANUAL REVIEW REQUIRED")
        logger.critical("=" * 60)

        # Pause the bot
        if bot_controller:
            if hasattr(bot_controller, 'state_lock'):
                with bot_controller.state_lock:
                    bot_controller.paused = True
            else:
                bot_controller.paused = True
            logger.critical("✅ Bot automatically paused")

        # Send Telegram alert
        if self.telegram and self.telegram.enabled:
            alert_msg = (
                f"🛑 <b>CIRCUIT BREAKER TRIGGERED</b>\n"
                f"──────────────────\n"
                f"<b>Drawdown:</b> {drawdown:.1%}\n"
                f"<b>Max Allowed:</b> {self.max_drawdown_pct:.1%}\n"
                f"\n"
                f"<b>Peak Balance:</b> ${self.peak_balance:.2f}\n"
                f"<b>Current Balance:</b> ${current_balance:.2f}\n"
                f"<b>Loss:</b> ${self.peak_balance - current_balance:.2f}\n"
                f"\n"
                f"🛑 <b>TRADING HALTED</b>\n"
                f"⚠️ <b>ACTION REQUIRED:</b>\n"
                f"1. Review recent trades\n"
                f"2. Check for strategy failure\n"
                f"3. Analyze market conditions\n"
                f"4. Manual resume required\n"
            )
            self.telegram.send_message(alert_msg)
            logger.critical("📱 Telegram alert sent")

    def _send_breaker_active_alert(self):
        """
        Send Telegram alert on startup if circuit breaker is already active.
        This ensures user is notified even if bot restarts while breaker is triggered.
        """
        alert_msg = (
            f"⚠️ <b>CIRCUIT BREAKER ACTIVE</b>\n"
            f"──────────────────\n"
            f"🔄 <b>Bot Restarted</b>\n"
            f"\n"
            f"<b>Peak Balance:</b> ${self.peak_balance:.2f}\n"
            f"<b>Max Drawdown:</b> {self.max_drawdown_pct:.1%}\n"
            f"\n"
            f"🛑 <b>Trading is HALTED</b>\n"
            f"\n"
            f"<b>To Resume:</b>\n"
            f"1. Send /resume to reset peak balance\n"
            f"2. Or wait for balance to recover\n"
            f"\n"
            f"💡 /resume will reset peak to current balance"
        )
        self.telegram.send_message(alert_msg)
        logger.info("📱 Circuit breaker status alert sent via Telegram")

    def get_drawdown_status(self, current_balance: float) -> Dict:
        """
        Get current drawdown metrics

        Returns:
            Dictionary with drawdown information
        """
        if current_balance is None or self.peak_balance <= 0:
            return {
                'peak_balance': self.peak_balance,
                'current_balance': current_balance,
                'drawdown': 0.0,
                'max_drawdown': self.max_drawdown_pct,
                'circuit_breaker_triggered': False,
                'distance_to_breaker': self.max_drawdown_pct
            }

        drawdown = (self.peak_balance - current_balance) / self.peak_balance
        distance_to_breaker = max(0, self.max_drawdown_pct - drawdown)

        return {
            'peak_balance': self.peak_balance,
            'current_balance': current_balance,
            'drawdown': drawdown,
            'max_drawdown': self.max_drawdown_pct,
            'circuit_breaker_triggered': self.circuit_breaker_triggered,
            'distance_to_breaker': distance_to_breaker,
            'loss_amount': self.peak_balance - current_balance
        }

    def reset_circuit_breaker(self, manual_override: bool = False):
        """
        Reset circuit breaker (use with caution!)

        Args:
            manual_override: If True, forces reset even if balance hasn't recovered
        """
        if manual_override:
            self.circuit_breaker_triggered = False
            self._save_peak_balance()
            logger.warning("⚠️ Circuit breaker manually reset (override)")
        else:
            logger.error("❌ Circuit breaker can only be reset by recovery or manual override")

    def reset_peak_balance(self, new_peak: Optional[float] = None):
        """
        Reset peak balance (e.g., after adding/withdrawing capital)

        Args:
            new_peak: New peak balance, or None to use current capital
        """
        old_peak = self.peak_balance
        self.peak_balance = new_peak if new_peak else self.total_capital
        self._save_peak_balance()
        logger.info(f"📊 Peak balance reset: ${old_peak:.2f} → ${self.peak_balance:.2f}")
