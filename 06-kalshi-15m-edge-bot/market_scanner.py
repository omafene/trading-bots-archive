import logging
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class Market15mScanner:
    def __init__(self, client: KalshiClient, config: Dict):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']

        # Cache events — Kalshi 15m events only change every 15 minutes,
        # no need to hit /events API on every 0.3s scan cycle
        self._event_cache: List[Dict] = []
        self._event_cache_time: float = 0.0
        self._event_cache_ttl: float = config.get('monitoring', {}).get('market_cache_ttl', 15.0)

    def scan_opportunities(self) -> List[Dict]:
        """Main scanning method using the reliable event-based approach."""
        logger.info("Scanning for 15-min market opportunities...")
        events = self._get_15min_events()
        
        if not events:
            logger.info("No active 15m events found.")
            return []

        opportunities = []
        for event in events:
            event_ticker = event.get('event_ticker')
            try:
                response = self.client._make_request("GET", "/markets", params={
                    "event_ticker": event_ticker, "status": "open", "limit": 100
                })
                if not response or 'markets' not in response: continue
                for market in response['markets']:
                    opp = self._evaluate_market(market)
                    if opp: opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error fetching markets for {event_ticker}: {e}")
                continue

        # Sort by expected_return safely
        if opportunities:
            opportunities.sort(key=lambda x: (x.get('expected_return') or 0), reverse=True)
            
        logger.info(f"✅ Found {len(opportunities)} active 15-min markets.")
        return opportunities

    def _get_15min_events(self) -> List[Dict]:
        """Fetches KXBTC15M/KXETH15M parent events with TTL cache."""
        now_mono = time.monotonic()
        if self._event_cache and (now_mono - self._event_cache_time) < self._event_cache_ttl:
            return self._event_cache

        now = datetime.now(timezone.utc)
        all_events = []
        cursor = None
        for page in range(5):
            params = {"limit": 200, "status": "open", "min_close_ts": int(now.timestamp())}
            if cursor: params['cursor'] = cursor
            result = self.client._make_request("GET", "/events", params=params)
            if not result or 'events' not in result: break
            all_events.extend(result['events'])
            cursor = result.get('cursor')
            if not cursor: break

        filtered = [e for e in all_events if ('KXBTC15M' in e.get('event_ticker', '') or 'KXETH15M' in e.get('event_ticker', ''))]
        self._event_cache = filtered
        self._event_cache_time = time.monotonic()
        return filtered

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        """Captures TTE and Orderbook Depth (contracts available at price)."""
        ticker = market.get('ticker')
        if not ticker: return None
        
        # FIX: Calculate high-precision TTE in seconds
        now = datetime.now(timezone.utc)
        close_time = datetime.fromisoformat(market['close_time'].replace('Z', '+00:00'))
        tte_seconds = (close_time - now).total_seconds()
        
        # DEPTH MONITOR: Capturing the sizes from the orderbook
        orderbook = self.client.get_orderbook(ticker)
        if not orderbook or not orderbook.get('yes') or not orderbook.get('no'): return None

        return {
            'ticker': ticker,
            'symbol': 'BTC' if 'BTC' in ticker else 'ETH',
            'tte_seconds': tte_seconds, # Critical fix for KeyError
            'threshold': market.get('strike_price') or market.get('cap'),
            'yes_bid': orderbook['yes'][-1][0] / 100,
            'yes_ask': orderbook['yes'][0][0] / 100,
            'yes_ask_size': orderbook['yes'][0][1], # Available YES contracts
            'no_bid': orderbook['no'][-1][0] / 100,
            'no_ask': orderbook['no'][0][0] / 100,
            'no_ask_size': orderbook['no'][0][1],   # Available NO contracts
            'market_type': 'above' if 'above' in market['title'].lower() else 'below',
            'market': market
        }
