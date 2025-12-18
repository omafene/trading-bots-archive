import logging
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, client: KalshiClient, config: Dict, momentum_checker=None):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']
        self.filter_config = config.get('filters', {})
        self.risk_config = config['risk']
        self.momentum_checker = momentum_checker

    def scan_opportunities(self) -> List[Dict]:
        logger.info("Scanning for endgame opportunities...")
        opportunities = []
        events = self._get_upcoming_events()
        if not events: return []

        for event in events:
            event_ticker = event.get('event_ticker')
            try:
                response = self.client._make_request("GET", "/markets", params={
                    "event_ticker": event_ticker, "status": "open", "limit": 100
                })

                if not response or not isinstance(response, dict): continue
                markets_list = response.get('markets')
                if markets_list is None: continue

                for market in markets_list:
                    opportunity = self._evaluate_market(market)
                    if opportunity: opportunities.append(opportunity)
            except Exception as e:
                logger.error(f"Error fetching markets for event {event_ticker}: {e}")
                continue

        opportunities.sort(key=lambda x: x['expected_return'], reverse=True)
        return opportunities

    def _get_upcoming_events(self) -> List[Dict]:
        # We look for events from "Today" up to your max_days
        max_days = self.strategy_config.get('max_days_to_close', 14)
        now = datetime.now(timezone.utc)
        # We set search_min to the START of today so we don't miss today's crypto
        search_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
        search_max = now + timedelta(days=max_days + 1)

        all_events = []
        cursor = None
        for page in range(20):
            try:
                params = {"limit": 200, "status": "open", "min_close_ts": int(now.timestamp())}
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
                # If strike is today or in the future window, include it
                if search_min <= strike_date <= search_max:
                    target_events.append(event)
            except: continue
        return target_events

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        ticker = market.get('ticker')
        if not ticker:
            return None

        # ============================================================
        # Ticker keyword filter (e.g., BTC/ETH only)
        # ============================================================
        ticker_must_contain = self.risk_config.get('ticker_must_contain', [])

        if ticker_must_contain:
            # Check if ticker contains ANY of the required keywords
            ticker_upper = ticker.upper()

            has_required_keyword = any(
                keyword.upper() in ticker_upper
                for keyword in ticker_must_contain
            )

            if not has_required_keyword:
                logger.debug(f"⏭️ {ticker}: Missing required keywords {ticker_must_contain}")
                return None
        # ============================================================

        # ============================================================
        # Momentum / R² filter (if wired up via endgame_bot)
        # ============================================================
        if self.momentum_checker:
            passes, reason = self.momentum_checker.passes_filters(ticker)
            if not passes:
                logger.info(f"⏭️ {ticker}: Momentum filter skip — {reason}")
                return None
        # ============================================================

        if not self._check_close_time(market) or not self._check_category(market):
            return None

        orderbook = self.client.get_orderbook(ticker)
        if not orderbook: return None

        yes_orders = orderbook.get('yes') or []
        no_orders = orderbook.get('no') or []
        if not yes_orders and not no_orders: return None

        best_yes_price = yes_orders[-1][0] / 100 if yes_orders else None
        best_no_price = no_orders[-1][0] / 100 if no_orders else None

        min_prob = self.strategy_config['min_probability']
        max_prob = self.strategy_config['max_probability']
        side, entry_price, probability = None, None, None

        if best_yes_price and min_prob <= best_yes_price <= max_prob:
            side, entry_price, probability = 'yes', best_yes_price, best_yes_price

        require_yes_only = self.filter_config.get('require_yes_side', False)
        if not side and not require_yes_only and best_no_price and min_prob <= best_no_price <= max_prob:
            side, entry_price, probability = 'no', best_no_price, best_no_price

        if not side: return None

        expected_return = (1 - entry_price) / entry_price
        if expected_return < self.strategy_config['min_expected_return'] or not self._passes_filters(market, orderbook):
            return None

        close_time_str = market.get('close_time')
        days_to_close = 0
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                days_to_close = (close_time - datetime.now(timezone.utc)).total_seconds() / 86400
            except: pass

        return {
            'ticker': ticker, 'title': market.get('title', ''), 'category': market.get('category', ''),
            'close_time': market.get('close_time'), 'days_to_close': days_to_close,
            'probability': probability, 'entry_price': entry_price, 'expected_return': expected_return,
            'side': side, 'orderbook': orderbook, 'market': market
        }

    def _check_close_time(self, market: Dict) -> bool:
        close_time_str = market.get('close_time')
        if not close_time_str: return False
        try:
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            diff_in_days = (close_time - datetime.now(timezone.utc)).total_seconds() / 86400
            return self.strategy_config.get('min_days_to_close', 0) <= diff_in_days <= self.strategy_config.get('max_days_to_close', 14)
        except: return False

    def _check_category(self, market: Dict) -> bool:
        category = str(market.get('category', '')).lower()
        blacklist = [c.lower() for c in self.risk_config.get('blacklist_categories', [])]
        if category in blacklist: return False
        strategy_cats = [c.lower() for c in self.strategy_config.get('categories', [])]
        if strategy_cats and category not in strategy_cats: return False
        return True

    def _passes_filters(self, market: Dict, orderbook: Dict) -> bool:
        min_volume = self.filter_config.get('min_volume', 0)
        if min_volume > 0 and market.get('volume', 0) < min_volume: return False
        min_liquidity = self.filter_config.get('min_liquidity', 0)
        if min_liquidity > 0:
            yes_list = orderbook.get('yes') or []
            if sum(order[1] for order in yes_list) < min_liquidity: return False
        return True

    def get_market_summary(self, opportunities: List[Dict]) -> Dict:
        if not opportunities: return {'count': 0, 'avg_probability': 0, 'avg_expected_return': 0, 'categories': {}}
        categories = {}
        total_prob, total_return = 0, 0
        for opp in opportunities:
            cat = opp.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
            total_prob += opp.get('probability', 0)
            total_return += opp.get('expected_return', 0)
        count = len(opportunities)
        return {
            'count': count, 'avg_probability': total_prob / count,
            'avg_expected_return': total_return / count, 'categories': categories
        }
