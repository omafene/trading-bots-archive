"""
Scan Kalshi for active 15-minute BTC/ETH markets
Uses /events endpoint like main bot, then fetches markets for each event
Updated with Depth Monitor (ask sizes).
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class Market15mScanner:
    def __init__(self, client: KalshiClient, config: Dict):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']
        self.filter_config = config.get('filters', {})
        self.risk_config = config['risk']
        logger.info("✅ 15-minute market scanner initialized (Depth Enabled)")

    def scan_opportunities(self) -> List[Dict]:
        logger.info("Scanning for 15-min market opportunities...")
        opportunities = []
        events = self._get_15min_events()
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

        if opportunities:
            opportunities.sort(key=lambda x: x.get('expected_return') or 0, reverse=True)
        return opportunities

    def _get_15min_events(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        max_hours = self.strategy_config.get('max_minutes_to_close', 60) / 60
        search_max = now + timedelta(hours=max_hours)
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
            except Exception as e: break

        fifteen_min_events = []
        for event in all_events:
            ticker = event.get('event_ticker', '')
            if 'KXBTC15M' not in ticker and 'KXETH15M' not in ticker: continue
            strike_str = event.get('strike_date')
            if strike_str:
                try:
                    strike_date = datetime.fromisoformat(strike_str.replace('Z', '+00:00'))
                    if now <= strike_date <= search_max: fifteen_min_events.append(event)
                except: continue
        return fifteen_min_events

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        ticker = market.get('ticker')
        if not ticker: return None
        symbol = 'BTC' if 'KXBTC' in ticker else 'ETH' if 'KXETH' in ticker else None
        if not symbol: return None

        close_time_str = market.get('close_time')
        if not close_time_str: return None
        now = datetime.now(timezone.utc)
        try:
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            minutes_to_close = (close_time - now).total_seconds() / 60
        except: return None

        if not (self.strategy_config.get('min_minutes_to_close', 5) <= minutes_to_close <= self.strategy_config.get('max_minutes_to_close', 60)):
            return None

        orderbook = self.client.get_orderbook(ticker)
        if not orderbook: return None
        yes_orders = orderbook.get('yes') or []
        no_orders = orderbook.get('no') or []
        if not yes_orders or not no_orders: return None

        # Capture sizes (Depth Monitor)
        return {
            'ticker': ticker, 'title': market.get('title', ''), 'symbol': symbol,
            'close_time': close_time, 'minutes_to_close': minutes_to_close,
            'market_type': self._detect_market_type(market.get('title', '')),
            'yes_bid': yes_orders[-1][0] / 100, 'no_bid': no_orders[-1][0] / 100,
            'yes_ask': yes_orders[0][0] / 100, 'no_ask': no_orders[0][0] / 100,
            'yes_ask_size': yes_orders[0][1], 'no_ask_size': no_orders[0][1], # Depth Monitor
            'threshold': market.get('strike_price') or market.get('cap'),
            'volume': market.get('volume', 0), 'market': market
        }

    def _detect_market_type(self, title: str) -> str:
        t = title.lower()
        if 'up' in t and 'down' in t: return 'up_down'
        if 'up' in t: return 'up'
        if 'down' in t: return 'down'
        if 'above' in t or 'over' in t: return 'above'
        if 'below' in t or 'under' in t: return 'below'
        return 'unknown'
    
    def get_market_summary(self, opportunities: List[Dict]) -> Dict:
        """Generates counts of how many edges were found per symbol."""
        if not opportunities:
            return {'count': 0, 'symbols': {}}
        
        symbols = {}
        for opp in opportunities:
            symbol = opp.get('symbol', 'Unknown')
            symbols[symbol] = symbols.get(symbol, 0) + 1
            
        return {
            'count': len(opportunities),
            'symbols': symbols
        }
