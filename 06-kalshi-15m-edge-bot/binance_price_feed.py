"""
Binance aggTrade WebSocket price feed for real-time spike detection.

Connects to wss://stream.binance.com/ws/{symbol}@aggTrade for each symbol.
Calls price_callback(symbol, price) on every qualifying tick.

Throttled to min_write_interval seconds per symbol so price_history buffer
size stays consistent with the REST-poll-based sizing in MomentumAnalyzer.
"""

import asyncio
import json
import logging
import time
from typing import Callable, List

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    logger.error("❌ 'websockets' library not found — BinancePriceFeed disabled")
    websockets = None

_SYMBOL_MAP = {
    'BTC':  'btcusdt',
    'ETH':  'ethusdt',
    'SOL':  'solusdt',
    'XRP':  'xrpusdt',
    'DOGE': 'dogeusdt',
    'BNB':  'bnbusdt',
    'HYPE': 'hypeusdt',
}


class BinancePriceFeed:
    """
    Real-time Binance aggTrade feed → price_callback(symbol, price).

    min_write_interval controls how often we write to price_history per symbol.
    Default 0.5s → 2 writes/s → a 4-second spike window gets ~8 data points.
    At 20-minute history that's 2,400 samples/symbol — within MomentumAnalyzer's
    1,200-sample default buffer (sized for 1s polling × 20 min).  Set
    min_write_interval to match spot_price_update_interval if you want to keep
    the exact same buffer depth, or double max_history_length in the analyzer.
    """

    def __init__(
        self,
        symbols: List[str],
        price_callback: Callable[[str, float], None],
        min_write_interval: float = 1.0,
    ):
        self.symbols = [s for s in symbols if s in _SYMBOL_MAP]
        self.price_callback = price_callback
        self.min_write_interval = min_write_interval
        self._last_write: dict = {}
        self.running = False

        skipped = [s for s in symbols if s not in _SYMBOL_MAP]
        if skipped:
            logger.warning(f"⚠️  BinancePriceFeed: no Binance mapping for {skipped}, skipping")
        logger.info(
            f"✅ BinancePriceFeed initialized — symbols: {self.symbols}, "
            f"throttle: {min_write_interval}s"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        if websockets is None:
            logger.error("Cannot start BinancePriceFeed: websockets library not installed")
            return
        self.running = True
        tasks = [self._subscribe(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self):
        self.running = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _subscribe(self, symbol: str):
        ws_symbol = _SYMBOL_MAP[symbol]
        url = f"wss://stream.binance.com:9443/ws/{ws_symbol}@aggTrade"
        reconnect_delay = 1

        while self.running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=10,
                ) as ws:
                    logger.info(f"🔌 BinancePriceFeed: connected {symbol}")
                    reconnect_delay = 1

                    async for raw in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(raw)
                            price = float(data['p'])
                            now = time.monotonic()
                            if now - self._last_write.get(symbol, 0) >= self.min_write_interval:
                                self._last_write[symbol] = now
                                self.price_callback(symbol, price)
                        except (KeyError, ValueError, json.JSONDecodeError):
                            pass
                        except Exception as e:
                            logger.debug(f"BinancePriceFeed {symbol} parse error: {e}")

            except Exception as e:
                if self.running:
                    logger.warning(
                        f"BinancePriceFeed {symbol} disconnected ({e}). "
                        f"Reconnecting in {reconnect_delay}s..."
                    )
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)
