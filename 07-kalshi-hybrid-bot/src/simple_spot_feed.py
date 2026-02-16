"""
Simple Spot Price Feed
Gets current prices from Coinbase for BTC, ETH, SOL, XRP
"""

import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SimpleSpotFeed:
    """Simple spot price feed using Coinbase API."""

    def __init__(self, symbols: list):
        self.symbols = symbols
        self.base_url = "https://api.coinbase.com/v2/prices"
        logger.info(f"✅ Spot feed initialized for {symbols}")

    def _get_price(self, symbol: str) -> Optional[float]:
        """Get current spot price for a symbol."""

        try:
            # Map symbols to Coinbase pairs
            pair_map = {
                'BTC': 'BTC-USD',
                'ETH': 'ETH-USD',
                'SOL': 'SOL-USD',
                'XRP': 'XRP-USD'
            }

            pair = pair_map.get(symbol)
            if not pair:
                return None

            url = f"{self.base_url}/{pair}/spot"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                price = float(data['data']['amount'])
                return price
            else:
                logger.warning(f"Failed to get price for {symbol}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def get_last_exchange_prices(self, symbol: str) -> Dict:
        """Get prices from multiple exchanges (simplified version)."""

        price = self._get_price(symbol)

        return {
            'coinbase': price,
            'binance': price,  # Simplified - using same price
            'kraken': price
        }
