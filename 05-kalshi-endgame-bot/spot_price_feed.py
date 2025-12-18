"""
Spot price feed for kalshi_bot (synchronous, requests-based).
Fetches BTC/ETH/SOL/XRP prices from Coinbase, Binance, and Kraken; returns median.
Mirrors the behaviour of kalshi_15m_bot/spot_price_feed.py without the aiohttp dep.
"""

import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 3  # seconds per exchange request


class SpotPriceFeed:
    """Sync spot price feed using requests. Returns median from up to 3 exchanges."""

    def __init__(self):
        self.price_cache: Dict[str, tuple] = {}
        self.cache_ttl = 5  # seconds
        self.session = requests.Session()
        logger.info("✅ SpotPriceFeed initialized (sync/requests, sources: Coinbase/Binance/Kraken)")

    def get_price(self, symbol: str) -> Optional[float]:
        """Return latest spot price, cached for cache_ttl seconds."""
        if symbol in self.price_cache:
            cached_price, cached_time = self.price_cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price

        price = self._fetch_median(symbol)
        if price:
            self.price_cache[symbol] = (price, time.time())
        return price

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_median(self, symbol: str) -> Optional[float]:
        prices = []
        for fetcher in (self._coinbase, self._binance, self._kraken):
            p = fetcher(symbol)
            if p:
                prices.append(p)

        if not prices:
            logger.warning(f"No {symbol} price from any exchange")
            return None

        prices.sort()
        n = len(prices)
        median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2
        logger.debug(f"{symbol} price: ${median:,.2f} ({len(prices)} sources)")
        return median

    def _coinbase(self, symbol: str) -> Optional[float]:
        try:
            url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
            r = self.session.get(url, timeout=_TIMEOUT)
            return float(r.json()['data']['amount'])
        except Exception as e:
            logger.debug(f"Coinbase {symbol}: {e}")
            return None

    def _binance(self, symbol: str) -> Optional[float]:
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
            r = self.session.get(url, timeout=_TIMEOUT)
            return float(r.json()['price'])
        except Exception as e:
            logger.debug(f"Binance {symbol}: {e}")
            return None

    def _kraken(self, symbol: str) -> Optional[float]:
        try:
            k_map = {'BTC': 'XXBTZUSD', 'ETH': 'XETHZUSD', 'XRP': 'XXRPZUSD'}
            pair = k_map.get(symbol, f"{symbol}USD")
            url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
            r = self.session.get(url, timeout=_TIMEOUT)
            result = r.json().get('result', {})
            if result:
                first_key = next(iter(result))
                return float(result[first_key]['c'][0])
        except Exception as e:
            logger.debug(f"Kraken {symbol}: {e}")
        return None
