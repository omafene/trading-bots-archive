"""
Market Scanner
Identifies endgame sweep opportunities (75-99% probability markets)
"""

import logging
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class MarketScanner:
    """Scans Kalshi markets for endgame sweep opportunities"""

    def __init__(self, client: KalshiClient, config: Dict):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']
        self.filter_config = config.get('filters', {})
        self.risk_config = config['risk']

    def scan_opportunities(self) -> List[Dict]:
        logger.info("Scanning for endgame opportunities...")
        opportunities = []
        events = self._get_upcoming_events()
        if not events:
            return []

        for event in events:
            event_ticker = event.get('event_ticker')
            try:
                markets = self.client._make_request("GET", "/markets", params={
                    "event_ticker": event_ticker,
                    "status": "open",
                    "limit": 100
                })
                if not markets or 'markets' not in markets or markets['markets'] is None:
                    continue
                for market in markets['markets']:
                    opportunity = self._evaluate_market(market)
                    if opportunity:
                        opportunities.append(opportunity)
            except Exception as e:
                logger.error(f"Error fetching markets for event {event_ticker}: {e}")
                continue

        opportunities.sort(key=lambda x: x['expected_return'], reverse=True)
        return opportunities

    def _get_upcoming_events(self) -> List[Dict]:
        min_days = self.strategy_config.get('min_days_to_close', 1)
        max_days = self.strategy_config.get('max_days_to_close', 14)
        now = datetime.now(timezone.utc)
        now_ts = int(now.timestamp())
        min_date = now + timedelta(days=min_days)
        max_date = now + timedelta(days=max_days)

        all_events = []
        cursor = None
        for page in range(20):
            try:
                params = {"limit": 200, "status": "open", "min_close_ts": now_ts}
                if cursor: params['cursor'] = cursor
                result = self.client._make_request("GET", "/events", params=params)
                if not result or 'events' not in result: break
                all_events.extend(result['events'])
                cursor = result.get('cursor')
                if not cursor: break
            except Exception as e:
                logger.error(f"Error fetching events: {e}")
                break

        target_events = []
        for event in all_events:
            strike_str = event.get('strike_date')
            if not strike_str: continue
            try:
                strike_date = datetime.fromisoformat(strike_str.replace('Z', '+00:00'))
                if min_date <= strike_date <= max_date:
                    target_events.append(event)
            except: continue
        return target_events

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        """Evaluate market for BOTH YES and NO side opportunities"""
        ticker = market.get('ticker')
        if not ticker or not self._check_close_time(market) or not self._check_category(market):
            return None

        orderbook = self.client.get_orderbook(ticker)
        if not orderbook:
            return None

        # Get both YES and NO prices
        yes_orders = orderbook.get('yes', [])
        no_orders = orderbook.get('no', [])

        if not yes_orders and not no_orders:
            return None

        # Calculate probabilities
        best_yes_price = yes_orders[-1][0] / 100 if yes_orders else None
        best_no_price = no_orders[-1][0] / 100 if no_orders else None

        # Determine which side to trade
        min_prob = self.strategy_config['min_probability']
        max_prob = self.strategy_config['max_probability']

        side = None
        entry_price = None
        probability = None

        # Check YES side
        if best_yes_price and min_prob <= best_yes_price <= max_prob:
            side = 'yes'
            entry_price = best_yes_price
            probability = best_yes_price

        # Check NO side (only if YES didn't qualify AND not filtered)
        require_yes_only = self.filter_config.get('require_yes_side', False)
        if not side and not require_yes_only and best_no_price and min_prob <= best_no_price <= max_prob:
            side = 'no'
            entry_price = best_no_price
            probability = best_no_price

        # No qualifying side found
        if not side:
            return None

        # Calculate expected return
        expected_return = (1 - entry_price) / entry_price

        if expected_return < self.strategy_config['min_expected_return'] or not self._passes_filters(market, orderbook):
            return None

        # Calculate days to close
        close_time_str = market.get('close_time')
        days_to_close = 0
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                days_to_close = (close_time - datetime.now(timezone.utc)).total_seconds() / 86400
            except:
                pass

        return {
            'ticker': ticker,
            'title': market.get('title', ''),
            'category': market.get('category', ''),
            'close_time': market.get('close_time'),
            'days_to_close': days_to_close,
            'probability': probability,
            'entry_price': entry_price,
            'expected_return': expected_return,
            'side': side,  # Now can be 'yes' or 'no'
            'orderbook': orderbook,
            'market': market
        }

    def _check_close_time(self, market: Dict) -> bool:
        """Check if market is within time window (category-aware)"""
        close_time_str = market.get('close_time')
        if not close_time_str:
            return False
        
        try:
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            days_to_close = (close_time - datetime.now(timezone.utc)).days
            
            # Get category
            category = str(market.get('category', '')).lower()
            
            # Determine time window based on category
            if 'crypto' in category:
                # Use crypto-specific window (45 min)
                max_days = self.strategy_config.get('crypto_max_days', 0.031)
            else:
                # Use default window (60 min)
                max_days = self.strategy_config.get('max_days_to_close', 0.042)
            
            min_days = self.strategy_config.get('min_days_to_close', 0)
            
            # Check if within window
            in_window = min_days <= days_to_close <= max_days
            
            return in_window
            
        except Exception as e:
            logger.debug(f"Error parsing close time: {e}")
            return False

    def _check_category(self, market: Dict) -> bool:
        """Fixed Case-Insensitive Category & Weather Filter"""
        category = str(market.get('category', '')).lower()
        ticker = str(market.get('ticker', '')).lower()
        title = str(market.get('title', '')).lower()

        # Hard-block Weather (NYC/Chicago/Miami Highs/Lows)
        weather_prefixes = ()  # Empty = allow all weather
        if any(ticker.startswith(p) for p in weather_prefixes):
            return False

        if any(w in title or w in category for w in []):  # Empty = allow all
            return False

        # Blacklist (Case-Insensitive)
        blacklist = [c.lower() for c in self.risk_config.get('blacklist_categories', [])]
        if category in blacklist:
            return False

        # Strategy Allowed Categories
        strategy_cats = [c.lower() for c in self.strategy_config.get('categories', [])]
        if strategy_cats and category not in strategy_cats:
            return False

        return True

    def _passes_filters(self, market: Dict, orderbook: Dict) -> bool:
        """Quality filters for volume and liquidity"""
        min_volume = self.filter_config.get('min_volume', 0)
        if min_volume > 0 and market.get('volume', 0) < min_volume:
            return False

        min_liquidity = self.filter_config.get('min_liquidity', 0)
        if min_liquidity > 0:
            total_liq = sum(order[1] for order in orderbook.get('yes', []))
            if total_liq < min_liquidity:
                return False
        return True
    
    def get_market_summary(self, opportunities: List[Dict]) -> Dict:
        """
        Generate summary statistics for opportunities
        """
        if not opportunities:
            return {
                'count': 0,
                'avg_probability': 0,
                'avg_expected_return': 0,
                'categories': {}
            }

        categories = {}
        total_prob = 0
        total_return = 0

        for opp in opportunities:
            cat = opp.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
            total_prob += opp.get('probability', 0)
            total_return += opp.get('expected_return', 0)

        count = len(opportunities)
        return {
            'count': count,
            'avg_probability': total_prob / count if count > 0 else 0,
            'avg_expected_return': total_return / count if count > 0 else 0,
            'categories': categories
        }
