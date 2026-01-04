"""
Dual-Source Order Book Imbalance Feed
Connects to BOTH Binance and Coinbase for redundancy and accuracy

Key Improvements:
- Dual exchange feeds (Binance + Coinbase)
- Cross-validation (detect if exchanges disagree)
- Automatic fallback if one source fails
- Aggregated imbalance (average of both sources)

Philosophy:
- Single source = risky (one feed fails = blind)
- Dual source = robust (redundancy + validation)
- If exchanges disagree >20% = market uncertainty = veto
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, List
from collections import deque

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    logger.error("❌ 'websockets' library not found. Install with: pip install websockets")
    websockets = None


class DualSourceOrderBookFeed:
    """
    Real-time order book feed from Binance + Coinbase
    Provides redundancy and cross-validation
    """

    def __init__(self, config: Dict):
        self.config = config
        # Store order books per exchange: symbol -> exchange -> {bids, asks, timestamp}
        self.order_books = {}  # {symbol: {binance: {...}, coinbase: {...}}}
        self.last_update_time = {}  # {symbol: {binance: ts, coinbase: ts}}
        self.running = False

        # Imbalance history for smoothing
        self.imbalance_history = {}  # symbol -> exchange -> deque
        self.history_length = config.get('order_book', {}).get('smoothing_samples', 3)

        # Supported symbols
        self.symbols = config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])

        # Exchange priority (if one fails, use the other)
        self.exchanges = ['binance', 'coinbase']

        logger.info(f"✅ Dual-Source Order Book Feed initialized")
        logger.info(f"   Symbols: {self.symbols}")
        logger.info(f"   Sources: Binance + Coinbase")

        if websockets is None:
            logger.warning("⚠️  Order Book Feed disabled (websockets library not installed)")

    async def start(self):
        """Start WebSocket connections for all symbols on both exchanges"""
        if websockets is None:
            logger.error("Cannot start OrderBookFeed: websockets library not installed")
            return

        self.running = True

        # Create WebSocket tasks for both exchanges
        tasks = []
        for symbol in self.symbols:
            # Binance task
            binance_task = asyncio.create_task(
                self._subscribe_binance(symbol),
                name=f"binance_{symbol}"
            )
            tasks.append(binance_task)

            # Coinbase task
            coinbase_task = asyncio.create_task(
                self._subscribe_coinbase(symbol),
                name=f"coinbase_{symbol}"
            )
            tasks.append(coinbase_task)

        logger.info(f"🔌 Starting {len(tasks)} WebSocket connections...")

        # Run all connections concurrently
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ Order Book WebSocket error: {e}")

    async def _subscribe_binance(self, symbol: str):
        """Subscribe to Binance order book depth stream"""
        binance_symbol = f"{symbol}USDT".lower()
        ws_url = f"wss://stream.binance.com:9443/ws/{binance_symbol}@depth20@100ms"

        reconnect_delay = 1
        max_reconnect_delay = 60

        while self.running:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info(f"🔌 Binance: Connected to {symbol}")
                    reconnect_delay = 1

                    async for message in ws:
                        if not self.running:
                            break

                        try:
                            data = json.loads(message)
                            self._update_order_book(symbol, 'binance', data)
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            logger.debug(f"Binance {symbol} error: {e}")

            except Exception as e:
                logger.warning(f"⚠️  Binance {symbol} disconnected: {e}")
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    async def _subscribe_coinbase(self, symbol: str):
        """Subscribe to Coinbase level2 order book stream"""
        # Coinbase uses BTC-USD format
        coinbase_symbol = f"{symbol}-USD"
        ws_url = "wss://ws-feed.exchange.coinbase.com"

        # Subscribe message
        subscribe_msg = {
            "type": "subscribe",
            "product_ids": [coinbase_symbol],
            "channels": ["level2"]
        }

        reconnect_delay = 1
        max_reconnect_delay = 60

        while self.running:
            try:
                async with websockets.connect(ws_url) as ws:
                    # Send subscribe message
                    await ws.send(json.dumps(subscribe_msg))

                    logger.info(f"🔌 Coinbase: Connected to {symbol}")
                    reconnect_delay = 1

                    # Track if we received snapshot
                    snapshot_received = False

                    async for message in ws:
                        if not self.running:
                            break

                        try:
                            data = json.loads(message)
                            msg_type = data.get('type')

                            # Process snapshot or l2update
                            if msg_type == 'snapshot':
                                self._process_coinbase_snapshot(symbol, data)
                                snapshot_received = True
                            elif msg_type == 'l2update' and snapshot_received:
                                self._process_coinbase_update(symbol, data)

                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            logger.debug(f"Coinbase {symbol} error: {e}")

            except Exception as e:
                logger.warning(f"⚠️  Coinbase {symbol} disconnected: {e}")
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    def _update_order_book(self, symbol: str, exchange: str, data: Dict):
        """Update order book from Binance WebSocket data"""
        try:
            bids = [[float(price), float(qty)] for price, qty in data.get('bids', [])]
            asks = [[float(price), float(qty)] for price, qty in data.get('asks', [])]

            if symbol not in self.order_books:
                self.order_books[symbol] = {}
                self.last_update_time[symbol] = {}

            self.order_books[symbol][exchange] = {
                'bids': bids,
                'asks': asks,
                'timestamp': time.time()
            }

            self.last_update_time[symbol][exchange] = time.time()

        except Exception as e:
            logger.debug(f"Error updating {exchange} {symbol}: {e}")

    def _process_coinbase_snapshot(self, symbol: str, data: Dict):
        """Process Coinbase snapshot message"""
        try:
            # Coinbase snapshot format: {bids: [[price, size], ...], asks: [[price, size], ...]}
            bids = [[float(price), float(size)] for price, size in data.get('bids', [])[:20]]
            asks = [[float(price), float(size)] for price, size in data.get('asks', [])[:20]]

            # Sort: bids descending, asks ascending
            bids.sort(reverse=True, key=lambda x: x[0])
            asks.sort(key=lambda x: x[0])

            if symbol not in self.order_books:
                self.order_books[symbol] = {}
                self.last_update_time[symbol] = {}

            self.order_books[symbol]['coinbase'] = {
                'bids': bids,
                'asks': asks,
                'timestamp': time.time()
            }

            self.last_update_time[symbol]['coinbase'] = time.time()

        except Exception as e:
            logger.debug(f"Error processing Coinbase snapshot for {symbol}: {e}")

    def _process_coinbase_update(self, symbol: str, data: Dict):
        """Process Coinbase l2update (incremental update)"""
        # For simplicity, we'll request a new snapshot periodically
        # Full order book maintenance is complex - snapshots are easier
        pass

    def get_imbalance(self, symbol: str, depth: int = 3, smoothed: bool = True,
                     require_both: bool = False) -> Optional[float]:
        """
        Calculate aggregated order book imbalance from both exchanges

        Args:
            symbol: Crypto symbol
            depth: Number of levels to use
            smoothed: Apply moving average
            require_both: Require data from both exchanges (stricter)

        Returns:
            Aggregated imbalance (0-1) or None
        """
        if symbol not in self.order_books:
            return None

        imbalances = []

        # Calculate imbalance for each exchange
        for exchange in self.exchanges:
            if exchange not in self.order_books[symbol]:
                continue

            ob = self.order_books[symbol][exchange]
            bids = ob['bids'][:depth]
            asks = ob['asks'][:depth]

            if not bids or not asks:
                continue

            bid_vol = sum([qty for price, qty in bids])
            ask_vol = sum([qty for price, qty in asks])

            if bid_vol + ask_vol == 0:
                continue

            imbalance = bid_vol / (bid_vol + ask_vol)
            imbalances.append(imbalance)

        if not imbalances:
            return None

        # Require both sources if flag is set
        if require_both and len(imbalances) < 2:
            return None

        # Aggregate: Simple average
        agg_imbalance = sum(imbalances) / len(imbalances)

        # Apply smoothing if enabled
        if smoothed:
            if symbol not in self.imbalance_history:
                self.imbalance_history[symbol] = deque(maxlen=self.history_length)

            self.imbalance_history[symbol].append(agg_imbalance)
            agg_imbalance = sum(self.imbalance_history[symbol]) / len(self.imbalance_history[symbol])

        return agg_imbalance

    def get_imbalance_divergence(self, symbol: str, depth: int = 3) -> Optional[float]:
        """
        Calculate divergence between Binance and Coinbase imbalances
        High divergence = exchanges disagree = market uncertainty

        Returns:
            Absolute difference between exchange imbalances (0-1)
            None if data unavailable
        """
        if symbol not in self.order_books:
            return None

        imbalances = {}

        for exchange in self.exchanges:
            if exchange not in self.order_books[symbol]:
                continue

            ob = self.order_books[symbol][exchange]
            bids = ob['bids'][:depth]
            asks = ob['asks'][:depth]

            if not bids or not asks:
                continue

            bid_vol = sum([qty for price, qty in bids])
            ask_vol = sum([qty for price, qty in asks])

            if bid_vol + ask_vol == 0:
                continue

            imbalances[exchange] = bid_vol / (bid_vol + ask_vol)

        # Need both exchanges for divergence
        if len(imbalances) < 2:
            return None

        binance_imb = imbalances.get('binance', 0.5)
        coinbase_imb = imbalances.get('coinbase', 0.5)

        return abs(binance_imb - coinbase_imb)

    def get_order_book_stats(self, symbol: str) -> Optional[Dict]:
        """Get comprehensive stats from both exchanges"""
        if symbol not in self.order_books:
            return None

        stats = {
            'imbalance_binance': None,
            'imbalance_coinbase': None,
            'imbalance_aggregated': None,
            'divergence': None,
            'sources_available': [],
            'data_age_ms': {}
        }

        # Get per-exchange stats
        for exchange in self.exchanges:
            if exchange not in self.order_books[symbol]:
                continue

            stats['sources_available'].append(exchange)

            ob = self.order_books[symbol][exchange]
            data_age = (time.time() - ob['timestamp']) * 1000
            stats['data_age_ms'][exchange] = data_age

            # Calculate imbalance
            bids = ob['bids'][:3]
            asks = ob['asks'][:3]

            if bids and asks:
                bid_vol = sum([qty for price, qty in bids])
                ask_vol = sum([qty for price, qty in asks])

                if bid_vol + ask_vol > 0:
                    imbalance = bid_vol / (bid_vol + ask_vol)
                    stats[f'imbalance_{exchange}'] = imbalance

        # Aggregated metrics
        stats['imbalance_aggregated'] = self.get_imbalance(symbol, smoothed=True)
        stats['divergence'] = self.get_imbalance_divergence(symbol)

        return stats

    def is_data_fresh(self, symbol: str, max_age_ms: int = 1000,
                     require_both: bool = False) -> bool:
        """Check if order book data is recent"""
        if symbol not in self.last_update_time:
            return False

        fresh_count = 0

        for exchange in self.exchanges:
            if exchange not in self.last_update_time[symbol]:
                continue

            age_ms = (time.time() - self.last_update_time[symbol][exchange]) * 1000

            if age_ms < max_age_ms:
                fresh_count += 1

        if require_both:
            return fresh_count >= 2
        else:
            return fresh_count >= 1  # At least one source is fresh

    async def stop(self):
        """Stop WebSocket connections"""
        self.running = False
        logger.info("🔌 Order Book WebSocket stopped")

    def get_status(self) -> Dict:
        """Get connection status for all symbols and exchanges"""
        status = {}

        for symbol in self.symbols:
            status[symbol] = {}

            for exchange in self.exchanges:
                is_connected = (
                    symbol in self.order_books and
                    exchange in self.order_books[symbol]
                )

                age_ms = 0
                if is_connected:
                    age_ms = (time.time() - self.last_update_time[symbol][exchange]) * 1000

                status[symbol][exchange] = {
                    'connected': is_connected,
                    'data_fresh': age_ms < 1000 if is_connected else False,
                    'age_ms': age_ms
                }

        return status
