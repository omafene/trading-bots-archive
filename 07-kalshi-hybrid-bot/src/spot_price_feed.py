"""
CF Benchmarks Real-Time Index (RTI) Feed
Kalshi uses CF Benchmarks for settlement, so we use similar data sources.
Updated: Asynchronous concurrent fetching for BTC, ETH, and SOL.
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)

class CFBenchmarksRTI:
    """
    Get real-time BTC/ETH/SOL prices
    CF Benchmarks aggregates from major exchanges.
    We replicate this by aggregating Coinbase, Binance, and Kraken.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.price_cache = {}
        self.cache_ttl = 2  # 2 second cache
        self.last_exchange_prices = {}  # Store individual exchange prices for calibration
        logger.info("✅ Async Spot price feed initialized (BTC, ETH, SOL, XRP)")

    async def get_price_async(self, symbol: str) -> Optional[float]:
        """Async method to get spot price with caching"""
        cache_key = symbol
        if cache_key in self.price_cache:
            cached_price, cached_time = self.price_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price
        
        price = await self._get_aggregated_price_async(symbol)
        if price:
            self.price_cache[cache_key] = (price, time.time())
        return price

    async def _fetch_exchange(self, session, url, exchange_name, symbol):
        try:
            async with session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if exchange_name == 'Coinbase':
                        return float(data['data']['amount'])
                    elif exchange_name == 'Binance':
                        return float(data['price'])
                    elif exchange_name == 'Kraken':
                        # Handle Kraken's specific naming conventions
                        # Kraken uses XBT for BTC, so just take first result key
                        result = data.get('result', {})
                        if result:
                            first_key = next(iter(result))
                            return float(result[first_key]['c'][0])
                return None
        except Exception as e:
            logger.debug(f"{exchange_name} error for {symbol}: {e}")
            return None

    async def _get_aggregated_price_async(self, symbol: str) -> Optional[float]:
        """Concurrent fetch from all 3 exchanges"""
        if symbol == 'BTC': k_pair = 'XXBTZUSD'
        elif symbol == 'ETH': k_pair = 'XETHZUSD'
        elif symbol == 'XRP': k_pair = 'XXRPZUSD'
        else: k_pair = f"{symbol}USD" # Standard for SOL

        urls = [
            ('Coinbase', f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"),
            ('Binance', f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"),
            ('Kraken', f"https://api.kraken.com/0/public/Ticker?pair={k_pair}")
        ]

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_exchange(session, url, name, symbol) for name, url in urls]
            results = await asyncio.gather(*tasks)

        # Store individual exchange prices (for calibration analysis)
        exchange_names = ['Coinbase', 'Binance', 'Kraken']
        self.last_exchange_prices[symbol] = {
            name: price for name, price in zip(exchange_names, results) if price is not None
        }

        prices = [p for p in results if p is not None]
        if not prices:
            logger.error(f"❌ Failed to get {symbol} price from any exchange")
            return None

        prices.sort()
        n = len(prices)
        if n % 2 == 1:
            # Odd number: take middle value
            median_price = prices[n // 2]
        else:
            # Even number: average the two middle values (proper median)
            median_price = (prices[n // 2 - 1] + prices[n // 2]) / 2

        logger.debug(f"✅ {symbol} aggregated: ${median_price:,.2f} from {len(prices)} sources")
        return median_price

    def _get_price(self, symbol: str) -> Optional[float]:
        """Synchronous wrapper for legacy compatibility"""
        try:
            # Create a new event loop to avoid conflicts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_price_async(symbol))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"Error getting {symbol} price: {e}")
            return None

    def get_last_exchange_prices(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get individual exchange prices from last fetch (for calibration analysis)"""
        return self.last_exchange_prices.get(symbol, {})
