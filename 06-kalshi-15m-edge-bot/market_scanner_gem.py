"""
Market Scanner v3.4 - Event-Based Edition
Combines high-reliability event-based scanning with new safety tier data.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class Market15mScanner:
    """Find active 15-minute crypto markets using the Event-Based approach."""

    def __init__(self, client: KalshiClient, config: Dict):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']
        
        logger.info("✅ 15-minute Event-Based scanner initialized (v3.4)")

    def scan_opportunities(self) -> List[Dict]:
        """
        Main scanning method - Finds 15-min markets by first locating their parent events.
        """
        # 1. Get parent events (e.g., KXBTC15M-26JAN052000)
        events = self._get_15min_events()
        
        logger.info(f"💓 HEARTBEAT: Found {len(events)} active 15m crypto events.")
        
        if not events:
            return []

        opportunities = []
        
        # 2. For each event, fetch its specific child markets
        for event in events:
            event_ticker = event.get('event_ticker')
            try:
                response = self.client._make_request("GET", "/markets", params={
                    "event_ticker": event_ticker,
                    "status": "open",
                    "limit": 100
                })

                if not response or 'markets' not in response:
                    continue

                for market in response['markets']:
                    opportunity = self._evaluate_market(market)
                    if opportunity:
                        opportunities.append(opportunity)

            except Exception as e:
                logger.error(f"Error fetching markets for event {event_ticker}: {e}")
                continue
        
        # 3. Handle Sorting safely (prevents NoneType errors)
        if opportunities:
            opportunities.sort(key=lambda x: (x.get('expected_return') or 0), reverse=True)

        logger.info(f"🔎 ANALYSIS: Scanned {len(opportunities)} strikes across {len(events)} events.")
        return opportunities

    def _get_15min_events(self) -> List[Dict]:
        """Fetches and filters for KXBTC15M/KXETH15M events."""
        now = datetime.now(timezone.utc)
        max_hrs = self.strategy_config.get('max_minutes_to_close', 60) / 60
        search_max = now + timedelta(hours=max_hrs)

        all_events = []
        cursor = None

        # Paginate to find all open crypto events
        for page in range(5):
            params = {"limit": 200, "status": "open", "min_close_ts": int(now.timestamp())}
            if cursor: params['cursor'] = cursor

            result = self.client._make_request("GET", "/events", params=params)
            if not result or 'events' not in result: break

            all_events.extend(result['events'])
            cursor = result.get('cursor')
            if not cursor: break

        fifteen_min_events = []
        for event in all_events:
            ticker = event.get('event_ticker', '')
            if 'KXBTC15M' in ticker or 'KXETH15M' in ticker:
                strike_str = event.get('strike_date')
                if strike_str:
                    try:
                        strike_date = datetime.fromisoformat(strike_str.replace('Z', '+00:00'))
                        if now <= strike_date <= search_max:
                            fifteen_min_events.append(event)
                    except: continue

        return fifteen_min_events

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        """Calculates TTE and captures depth/spread data for the EdgeDetector."""
        ticker = market.get('ticker')
        if not ticker: return None

        symbol = 'BTC' if 'BTC' in ticker else 'ETH' if 'ETH' in ticker else None
        if not symbol: return None

        # TTE Calculation
        close_time_str = market.get('close_time')
        if not close_time_str: return None
        now = datetime.now(timezone.utc)
        try:
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            tte_seconds = (close_time - now).total_seconds()
            minutes_to_close = tte_seconds / 60
        except: return None

        # Config Filter
        if not (self.strategy_config.get('min_minutes_to_close', 1) <= minutes_to_close <= self.strategy_config.get('max_minutes_to_close', 60)):
            return None

        # Orderbook Capture
        orderbook = self.client.get_orderbook(ticker)
        if not orderbook: return None

        yes_orders = orderbook.get('yes') or []
        no_orders = orderbook.get('no') or []
        if not yes_orders or not no_orders: return None

        return {
            'ticker': ticker,
            'title': market.get('title', ''),
            'symbol': symbol,
            'tte_seconds': tte_seconds,
            'minutes_to_close': minutes_to_close,
            'market_type': self._detect_market_type(market.get('title', '')),
            'threshold': market.get('strike_price') or market.get('cap'),
            'yes_bid': yes_orders[-1][0] / 100,
            'no_bid': no_orders[-1][0] / 100,
            'yes_ask': yes_orders[0][0] / 100,
            'no_ask': no_orders[0][0] / 100,
            'yes_ask_size': yes_orders[0][1],
            'no_ask_size': no_orders[0][1],
            'volume': market.get('volume', 0),
            'open_interest': market.get('open_interest', 0),
            'market': market,
            'expected_return': None # Will be filled by EdgeDetector
        }

    def _detect_market_type(self, title: str) -> str:
        t = title.lower()
        if 'up' in t and 'down' in t: return 'up_down'
        if 'up' in t: return 'up'
        if 'down' in t: return 'down'
        if 'above' in t or 'over' in t: return 'above'
        if 'below' in t or 'under' in t: return 'below'
        return 'unknown'
