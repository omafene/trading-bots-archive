import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date

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

    def calculate_position_size(self, opportunity: Dict, current_balance: float) -> int:
        prob = opportunity['probability']
        odds = opportunity['expected_return']
        edge = prob - (1 - prob)
        kelly_fraction = (edge / (1 + odds)) if odds > 0 else 0
        conservative_fraction = kelly_fraction * self.capital_config['kelly_fraction']
        
        raw_size = current_balance * conservative_fraction
        return int(min(raw_size, self.capital_config['max_position_size']))

    def can_open_position(self, opportunity: Dict, current_positions: list, current_balance: float) -> tuple[bool, str]:
        # Simple limit checks
        if len(current_positions) >= self.capital_config['max_open_positions']:
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
