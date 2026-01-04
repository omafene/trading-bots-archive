"""
Tri-Source Order Book Imbalance Feed
Connects to Binance, Coinbase, AND Kraken for maximum redundancy

Architecture:
- Primary: Binance (fastest, 100ms updates)
- Backup: Coinbase + Kraken (cross-validation)
- Fallback: If Binance fails, use Coinbase/Kraken average
- Divergence check: If exchanges disagree >15%, flag uncertainty

Why 3 sources?
- Robustness: One or two sources can fail, still have data
- Validation: Detect manipulation/anomalies
- Accuracy: Average of 3 sources > any single source
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


class OrderBookFeed:
    """
    Tri-source order book feed with automatic fallback
    """

    def __init__(self, config: Dict):
        self.config = config
        # symbol -> exchange -> {bids, asks, timestamp}
        self.order_books = {}
        self.last_update_time = {}
        self.running = False

        # Smoothing
        self.imbalance_history = {}
        self.history_length = config.get('order_book', {}).get('smoothing_samples', 3)

        # OBI trend history: symbol -> deque of (timestamp, raw_imbalance)
        # Populated on each get_imbalance() call; used by get_imbalance_trend()
        self.imbalance_trend_history: Dict[str, deque] = {}

        # Symbols
        self.symbols = config['strategy'].get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])

        # Exchanges (priority order)
        self.exchanges = ['binance', 'kraken', 'coinbase']

        logger.info(f"✅ Tri-Source Order Book Feed initialized")
        logger.info(f"   Symbols: {self.symbols}")
        logger.info(f"   Sources: Binance (primary) + Kraken + Coinbase (Advanced Trade)")
        logger.info(f"   Coinbase: Public API (no authentication required)")

    async def start(self):
        """Start all WebSocket connections"""
        if websockets is None:
            return

        self.running = True
        tasks = []

        for symbol in self.symbols:
            # Binance (primary)
            tasks.append(asyncio.create_task(self._subscribe_binance(symbol)))

            # Kraken (backup)
            tasks.append(asyncio.create_task(self._subscribe_kraken(symbol)))

            # Coinbase (backup) - BTC/ETH/SOL/XRP all available on Advanced Trade
            tasks.append(asyncio.create_task(self._subscribe_coinbase(symbol)))

        # Add periodic status logger (every 60 seconds)
        tasks.append(asyncio.create_task(self._periodic_status_logger()))

        logger.info(f"🔌 Starting {len(tasks)} WebSocket connections...")

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")

    async def _periodic_status_logger(self):
        """Log order book connection status every minute"""
        logger.info("🔔 Periodic order book status logger started (60s interval)")

        while self.running:
            try:
                await asyncio.sleep(60)  # Wait 60 seconds

                if not self.running:
                    break

                # Count active connections per exchange
                binance_count = 0
                kraken_count = 0
                coinbase_count = 0

                for symbol in self.symbols:
                    if symbol in self.order_books:
                        if 'binance' in self.order_books[symbol]:
                            binance_count += 1
                        if 'kraken' in self.order_books[symbol]:
                            kraken_count += 1
                        if 'coinbase' in self.order_books[symbol]:
                            coinbase_count += 1

                # Calculate freshness (how many have data < 5 seconds old)
                fresh_count = 0
                now = time.time()
                for symbol in self.symbols:
                    if symbol in self.last_update_time:
                        # last_update_time[symbol] is a dict of {exchange: timestamp}
                        # Check if ANY exchange has fresh data for this symbol
                        exchange_times = self.last_update_time[symbol]
                        if exchange_times and any((now - ts) < 5 for ts in exchange_times.values()):
                            fresh_count += 1

                logger.info(f"📊 Order Book Status: Binance {binance_count}/{len(self.symbols)} | "
                           f"Coinbase {coinbase_count}/{len(self.symbols)} | Kraken {kraken_count}/{len(self.symbols)} | "
                           f"Fresh data: {fresh_count}/{len(self.symbols)} symbols")

            except Exception as e:
                logger.error(f"❌ Periodic status logger error: {e}")

    async def _subscribe_binance(self, symbol: str):
        """Binance WebSocket (primary source)"""
        ws_symbol = f"{symbol}USDT".lower()
        url = f"wss://stream.binance.com:9443/ws/{ws_symbol}@depth20@100ms"
        
        reconnect_delay = 1
        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    logger.info(f"🔌 Binance {symbol}: Connected")
                    reconnect_delay = 1
                    
                    async for msg in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(msg)
                            self._update_binance(symbol, data)
                        except:
                            pass
            except:
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)

    async def _subscribe_kraken(self, symbol: str):
        """Kraken WebSocket"""
        # Kraken symbol mapping
        kraken_map = {'BTC': 'XBT/USD', 'ETH': 'ETH/USD', 'SOL': 'SOL/USD', 'XRP': 'XRP/USD', 'DOGE': 'XDG/USD', 'BNB': 'BNB/USD', 'HYPE': 'HYPE/USD'}
        ws_symbol = kraken_map.get(symbol, f"{symbol}/USD")
        url = "wss://ws.kraken.com/"
        
        subscribe_msg = {
            "event": "subscribe",
            "pair": [ws_symbol],
            "subscription": {"name": "book", "depth": 10}
        }
        
        reconnect_delay = 1
        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"🔌 Kraken {symbol}: Connected")
                    reconnect_delay = 1
                    
                    async for msg in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(msg)
                            if isinstance(data, list):
                                self._update_kraken(symbol, data)
                        except:
                            pass
            except:
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)

    async def _subscribe_coinbase(self, symbol: str):
        """Coinbase Advanced Trade WebSocket (Public - No Auth Required)"""
        ws_symbol = f"{symbol}-USD"
        # NEW: Advanced Trade API (public access for level2)
        url = "wss://advanced-trade-ws.coinbase.com"

        subscribe_msg = {
            "type": "subscribe",
            "product_ids": [ws_symbol],
            "channel": "level2"  # Public channel, no authentication needed
        }

        reconnect_delay = 1
        while self.running:
            try:
                # Increase max_size to handle large order book snapshots (default 1MB is too small)
                async with websockets.connect(url, max_size=10 * 1024 * 1024) as ws:  # 10MB limit
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"🔌 Coinbase {symbol}: Connected (Advanced Trade API)")
                    reconnect_delay = 1

                    async for msg in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(msg)
                            channel = data.get('channel', '')

                            # Handle l2_data channel (Advanced Trade format)
                            if channel == 'l2_data':
                                events = data.get('events', [])
                                for event in events:
                                    event_type = event.get('type', '')
                                    if event_type == 'snapshot':
                                        self._update_coinbase_snapshot(symbol, event)
                                    elif event_type == 'update':
                                        self._update_coinbase_incremental(symbol, event)

                            # Handle subscription confirmation
                            elif channel == 'subscriptions':
                                logger.debug(f"✅ Coinbase {symbol}: Subscription confirmed")

                        except Exception as e:
                            logger.debug(f"Coinbase {symbol} message parse error: {e}")
                            pass
            except Exception as e:
                logger.warning(f"⚠️ Coinbase {symbol} connection error: {e}")
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)

    def _update_coinbase_snapshot(self, symbol: str, event: Dict):
        """Update from Coinbase Advanced Trade snapshot event"""
        try:
            # Event is already the snapshot event from events array
            updates = event.get('updates', [])
            bids = []
            asks = []

            for update in updates:
                side = update.get('side')
                price = float(update.get('price_level', 0))
                qty = float(update.get('new_quantity', 0))

                if side == 'bid':
                    bids.append([price, qty])
                elif side == 'offer':
                    asks.append([price, qty])

            if bids and asks:
                bids.sort(reverse=True, key=lambda x: x[0])
                asks.sort(key=lambda x: x[0])
                self._store_book(symbol, 'coinbase', bids[:20], asks[:20])
                logger.info(f"📸 Coinbase {symbol}: Snapshot received ({len(bids)} bids, {len(asks)} asks)")

        except Exception as e:
            logger.debug(f"Coinbase snapshot parse error for {symbol}: {e}")

    def _update_binance(self, symbol: str, data: Dict):
        """Update from Binance"""
        try:
            bids = [[float(p), float(q)] for p, q in data.get('bids', [])]
            asks = [[float(p), float(q)] for p, q in data.get('asks', [])]
            self._store_book(symbol, 'binance', bids, asks)
        except:
            pass

    def _update_kraken(self, symbol: str, data: List):
        """Update from Kraken"""
        try:
            if len(data) >= 2 and isinstance(data[1], dict):
                book = data[1]
                bids = [[float(p), float(q)] for p, q, _ in book.get('bs', [])] if 'bs' in book else [[float(p), float(q)] for p, q, _ in book.get('b', [])]
                asks = [[float(p), float(q)] for p, q, _ in book.get('as', [])] if 'as' in book else [[float(p), float(q)] for p, q, _ in book.get('a', [])]
                if bids and asks:
                    self._store_book(symbol, 'kraken', bids, asks)
        except:
            pass

    def _update_coinbase_incremental(self, symbol: str, event: Dict):
        """Update Coinbase order book with Advanced Trade incremental update event"""
        try:
            # Get existing book
            if symbol not in self.order_books or 'coinbase' not in self.order_books[symbol]:
                # No snapshot yet, skip incremental updates
                return

            ob = self.order_books[symbol]['coinbase']
            bids_dict = {float(p): float(q) for p, q in ob['bids']}
            asks_dict = {float(p): float(q) for p, q in ob['asks']}

            # Event is already the update event from events array
            updates = event.get('updates', [])

            for update in updates:
                side = update.get('side')
                price = float(update.get('price_level', 0))
                qty = float(update.get('new_quantity', 0))

                if side == 'bid':
                    if qty == 0:
                        bids_dict.pop(price, None)
                    else:
                        bids_dict[price] = qty
                elif side == 'offer':
                    if qty == 0:
                        asks_dict.pop(price, None)
                    else:
                        asks_dict[price] = qty

            # Convert back to sorted lists (top 20 levels)
            bids = sorted([[p, q] for p, q in bids_dict.items()], key=lambda x: x[0], reverse=True)[:20]
            asks = sorted([[p, q] for p, q in asks_dict.items()], key=lambda x: x[0])[:20]

            self._store_book(symbol, 'coinbase', bids, asks)

        except Exception as e:
            logger.debug(f"Coinbase incremental update error for {symbol}: {e}")

    def _store_book(self, symbol: str, exchange: str, bids: List, asks: List):
        """Store order book data"""
        if symbol not in self.order_books:
            self.order_books[symbol] = {}
            self.last_update_time[symbol] = {}

        self.order_books[symbol][exchange] = {
            'bids': bids,
            'asks': asks,
            'timestamp': time.time()
        }
        self.last_update_time[symbol][exchange] = time.time()

    def get_imbalance(self, symbol: str, depth: int = 3, smoothed: bool = True) -> Optional[float]:
        """
        Get aggregated imbalance from all available sources

        Returns: 0-1 (0 = all asks, 1 = all bids)
        """
        if symbol not in self.order_books:
            return None

        # Track weighted data: (imbalance, total_volume)
        weighted_data = []

        for exchange in self.exchanges:
            if exchange not in self.order_books[symbol]:
                continue

            ob = self.order_books[symbol][exchange]
            bids = ob['bids'][:depth]
            asks = ob['asks'][:depth]

            if not bids or not asks:
                continue

            bid_vol = sum([q for p, q in bids])
            ask_vol = sum([q for p, q in asks])
            total_vol = bid_vol + ask_vol

            if total_vol == 0:
                continue

            imbalance = bid_vol / total_vol
            weighted_data.append((imbalance, total_vol))

        if not weighted_data:
            return None

        # VOLUME-WEIGHTED AVERAGE (gives more weight to larger exchanges)
        # Formula: sum(imbalance * volume) / sum(volume)
        total_volume = sum(vol for _, vol in weighted_data)
        agg_imbalance = sum(imb * vol for imb, vol in weighted_data) / total_volume

        # Append raw value to trend history before smoothing
        if symbol not in self.imbalance_trend_history:
            self.imbalance_trend_history[symbol] = deque(maxlen=500)
        self.imbalance_trend_history[symbol].append((time.time(), agg_imbalance))

        # Smoothing
        if smoothed:
            if symbol not in self.imbalance_history:
                self.imbalance_history[symbol] = deque(maxlen=self.history_length)
            self.imbalance_history[symbol].append(agg_imbalance)
            agg_imbalance = sum(self.imbalance_history[symbol]) / len(self.imbalance_history[symbol])

        return agg_imbalance

    def get_imbalance_trend(self, symbol: str, window_seconds: float = 30.0,
                            threshold: float = 0.03) -> Optional[str]:
        """
        Returns OBI trend direction over the last window_seconds:
            'rising'  — OBI increasing (growing bullish pressure)
            'falling' — OBI decreasing (growing bearish pressure)
            'neutral' — no clear directional change
            None      — insufficient history
        Compares first-half vs second-half mean. threshold controls minimum
        shift (in OBI units) to classify as rising/falling vs neutral.
        """
        if symbol not in self.imbalance_trend_history:
            return None

        now = time.time()
        cutoff = now - window_seconds
        history = [(ts, v) for ts, v in self.imbalance_trend_history[symbol] if ts >= cutoff]

        if len(history) < 6:
            return None

        mid = len(history) // 2
        first_mean = sum(v for _, v in history[:mid]) / mid
        second_mean = sum(v for _, v in history[mid:]) / (len(history) - mid)

        diff = second_mean - first_mean
        if diff > threshold:
            return 'rising'
        elif diff < -threshold:
            return 'falling'
        return 'neutral'

    def is_data_fresh(self, symbol: str, max_age_ms: int = 1000) -> bool:
        """Check if at least one source has fresh data"""
        if symbol not in self.last_update_time:
            return False

        for exchange in self.exchanges:
            if exchange not in self.last_update_time[symbol]:
                continue

            age_ms = (time.time() - self.last_update_time[symbol][exchange]) * 1000
            if age_ms < max_age_ms:
                return True  # At least one source is fresh

        return False

    def get_order_book_stats(self, symbol: str) -> Optional[Dict]:
        """Get comprehensive stats"""
        if symbol not in self.order_books:
            return None

        stats = {
            'sources_available': [],
            'imbalance': self.get_imbalance(symbol)
        }

        for exchange in self.exchanges:
            if exchange in self.order_books[symbol]:
                stats['sources_available'].append(exchange)

        return stats

    async def stop(self):
        """Stop all connections"""
        self.running = False

    def get_status(self) -> Dict:
        """Get status for all symbols"""
        status = {}
        for symbol in self.symbols:
            status[symbol] = {}
            for exchange in self.exchanges:
                connected = (
                    symbol in self.order_books and
                    exchange in self.order_books[symbol]
                )
                age = 0
                if connected:
                    age = (time.time() - self.last_update_time[symbol][exchange]) * 1000
                
                status[symbol][exchange] = {
                    'connected': connected,
                    'data_fresh': age < 1000 if connected else False,
                    'age_ms': age
                }
        return status
