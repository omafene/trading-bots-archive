"""
CF Benchmarks Real-Time Index (RTI) Feed
Kalshi uses CF Benchmarks for settlement, so we use similar data sources.

Uses requests with a persistent ThreadPoolExecutor to fetch from Coinbase, Binance,
and Kraken concurrently. Thread-local Sessions reuse SSL connections — no per-call
SSL context churn (which was causing ~40 MB/hr memory growth with aiohttp).
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class CFBenchmarksRTI:
    """
    Get real-time BTC/ETH/SOL/XRP prices.
    Aggregates Coinbase, Binance, and Kraken — median of available sources.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.price_cache = {}
        self.cache_ttl = 2  # 2 second cache
        self.last_exchange_prices = {}
        self.last_exchange_volumes = {}
        # Persistent executor — threads (and their SSL sessions) live for the bot's lifetime
        self._executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix='spot_feed')
        self._thread_local = threading.local()
        logger.info("✅ Spot price feed initialized — backend: requests")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_price_async(self, symbol: str) -> Optional[float]:
        """Async price fetch with caching. Called by _update_spot_prices."""
        if symbol in self.price_cache:
            cached_price, cached_time = self.price_cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price

        loop = asyncio.get_running_loop()
        price = await loop.run_in_executor(None, self._get_aggregated_price, symbol)

        if price:
            self.price_cache[symbol] = (price, time.time())
        return price

    def _get_price(self, symbol: str) -> Optional[float]:
        """Synchronous price fetch with caching. Called by momentum_analyzer etc."""
        if symbol in self.price_cache:
            cached_price, cached_time = self.price_cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price

        price = self._get_aggregated_price(symbol)
        if price:
            self.price_cache[symbol] = (price, time.time())
        return price

    def get_volume(self, symbol: str) -> Optional[float]:
        """Return aggregated 24h volume (Kraken source)."""
        volumes = list(self.last_exchange_volumes.get(symbol, {}).values())
        if not volumes:
            return None
        return sum(volumes) / len(volumes)

    def get_last_exchange_prices(self, symbol: str) -> Optional[Dict[str, float]]:
        """Individual exchange prices from last fetch (calibration analysis)."""
        return self.last_exchange_prices.get(symbol, {})

    # ------------------------------------------------------------------
    # requests backend
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """One persistent Session per thread — SSL context created once and reused."""
        if not hasattr(self._thread_local, 'session'):
            self._thread_local.session = requests.Session()
        return self._thread_local.session

    def _fetch_exchange_sync(self, exchange_name: str, url: str, symbol: str) -> Optional[Dict]:
        try:
            resp = self._get_session().get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if exchange_name == 'Coinbase':
                    return {'price': float(data['data']['amount']), 'volume': 0}
                elif exchange_name == 'Binance':
                    return {'price': float(data['price']), 'volume': 0}
                elif exchange_name == 'Kraken':
                    result = data.get('result', {})
                    if result:
                        first_key = next(iter(result))
                        price = float(result[first_key]['c'][0])
                        volume = float(result[first_key]['v'][1])
                        return {'price': price, 'volume': volume}
            return None
        except Exception as e:
            logger.debug(f"{exchange_name} error for {symbol}: {e}")
            return None

    def _get_aggregated_price(self, symbol: str) -> Optional[float]:
        """Concurrent fetch from all 3 exchanges via persistent thread pool."""
        if symbol == 'BTC':    k_pair = 'XXBTZUSD'
        elif symbol == 'ETH':  k_pair = 'XETHZUSD'
        elif symbol == 'XRP':  k_pair = 'XXRPZUSD'
        elif symbol == 'SOL':  k_pair = 'SOLUSD'
        elif symbol == 'DOGE': k_pair = 'XDGUSD'
        else:                   k_pair = f"{symbol}USD"

        exchange_names = ['Coinbase', 'Binance', 'Kraken']
        urls = [
            ('Coinbase', f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"),
            ('Binance',  f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"),
            ('Kraken',   f"https://api.kraken.com/0/public/Ticker?pair={k_pair}"),
        ]

        # Submit all 3 fetches concurrently to the persistent executor
        futures = [(name, self._executor.submit(self._fetch_exchange_sync, name, url, symbol))
                   for name, url in urls]
        results = {name: f.result() for name, f in futures}

        self.last_exchange_prices[symbol] = {
            name: r['price'] for name, r in results.items() if r is not None
        }
        self.last_exchange_volumes[symbol] = {
            name: r['volume'] for name, r in results.items()
            if r is not None and r['volume'] > 0
        }

        price_data = [r for r in results.values() if r is not None]
        if not price_data:
            logger.error(f"❌ Failed to get {symbol} price from any exchange")
            return None

        prices = sorted(r['price'] for r in price_data)
        n = len(prices)
        median_price = prices[n // 2] if n % 2 == 1 else (prices[n//2 - 1] + prices[n//2]) / 2

        logger.debug(f"✅ {symbol} aggregated: ${median_price:,.2f} from {len(prices)} sources")
        return median_price
