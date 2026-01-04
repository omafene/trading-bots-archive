"""
Kalshi Private WebSocket Feed

Subscribes to real-time fill, order, and per-ticker orderbook events.
Eliminates the 30s+ Kalshi REST API lag that causes duplicate-trade race conditions.

Architecture:
- Runs in a daemon thread (same pattern as order_book_feed.py)
- fill_queue / order_queue: thread-safe queue.Queue consumed by main thread
- latest_orderbook: per-ticker cache updated in real-time, read by manage_take_profit()
- Dynamic subscribe_orderbook() / unsubscribe_orderbook() for open positions only
- Auto-reconnects with exponential backoff (1s → 60s)
- REST polling resumes automatically when is_connected=False (graceful fallback)
"""

import asyncio
import base64
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    logger.error("❌ 'websockets' library not found. Install with: pip install websockets")
    websockets = None

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    logger.error("❌ 'cryptography' library not found. Install with: pip install cryptography")
    hashes = serialization = padding = default_backend = None


class KalshiWSFeed:
    """
    Private Kalshi WebSocket feed for real-time fill, order, and orderbook events.

    Public interface:
        fill_queue          : queue.Queue  — items are fill msg dicts
        order_queue         : queue.Queue  — items are order msg dicts
        latest_orderbook    : dict         — {ticker: {'yes': [[p,c],...], 'no': [...]}}
        is_connected        : bool         — True when logged in and subscribed
        start()             : coroutine    — run via asyncio event loop in daemon thread
        subscribe_orderbook(ticker)        — subscribe to live Kalshi orderbook for ticker
        unsubscribe_orderbook(ticker)      — unsubscribe and clear cached data
        get_orderbook(ticker)              — returns cached ob in REST-compatible format
        get_status()        : dict         — connected, queue sizes, subscribed tickers
    """

    WS_PATH = "/trade-api/ws/v2"

    def __init__(self, config: Dict):
        self.config = config
        self.fill_queue: queue.Queue = queue.Queue()
        self.order_queue: queue.Queue = queue.Queue()
        self.is_connected: bool = False
        self.running: bool = True

        # Orderbook cache: ticker -> {yes: {price_cents: count}, no: {price_cents: count}}
        self.latest_orderbook: Dict[str, Dict] = {}
        self._subscribed_orderbooks: set = set()
        self._orderbook_lock = threading.Lock()

        # Event-driven scan signal: set whenever any orderbook update arrives.
        # The main loop waits on this instead of sleeping a fixed interval,
        # so it reacts immediately to orderbook changes rather than on a clock tick.
        self.orderbook_updated = threading.Event()

        # Async internals for sending commands from the main (sync) thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws = None  # current websockets connection
        self._cmd_id = 2  # 1=login, 2=fill+order subscribe; dynamically allocated above
        self._cmd_lock = threading.Lock()

        ws_cfg = config.get('kalshi_ws', {})
        self._reconnect_delay_base = ws_cfg.get('reconnect_delay', 1)
        self._max_reconnect_delay = ws_cfg.get('max_reconnect_delay', 60)

        use_demo = config['api'].get('use_demo', False)

        # Derive WS URL from the same host as the REST base URL so auth backend matches.
        # e.g. https://api.elections.kalshi.com/trade-api/v2 → wss://api.elections.kalshi.com/trade-api/ws/v2
        import re as _re
        rest_url = config['api'].get('demo_url' if use_demo else 'base_url', '')
        ws_url = _re.sub(r'^https?://', 'wss://', rest_url)
        ws_url = _re.sub(r'/trade-api/v2.*', self.WS_PATH, ws_url)
        self._ws_url = ws_url

        # Mirror KalshiClient credential selection
        if use_demo:
            self._api_key = config['api'].get('demo_api_key_id', '')
            key_path = config['api'].get('demo_private_key_path', '')
        else:
            self._api_key = config['api'].get('api_key_id', '')
            key_path = config['api'].get('private_key_path', '')

        self._private_key = None
        if key_path:
            self._load_private_key(key_path)

        env_label = 'demo' if use_demo else 'prod'
        logger.info(f"✅ KalshiWSFeed initialized ({env_label}): {self._ws_url}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_private_key(self, key_path: str):
        """Load RSA private key from PEM file (same as KalshiClient)."""
        if serialization is None:
            return
        try:
            path = Path(key_path)
            if not path.exists():
                logger.error(f"KalshiWSFeed: Private key not found: {key_path}")
                return
            with open(path, 'rb') as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            logger.info("KalshiWSFeed: Private key loaded")
        except Exception as e:
            logger.error(f"KalshiWSFeed: Failed to load private key: {e}")

    def _make_login_cmd(self) -> dict:
        """Build RSA-PSS signed login command (mirrors KalshiClient._get_signed_headers)."""
        timestamp = str(int(time.time() * 1000))
        message = timestamp + "GET" + self.WS_PATH
        signature = self._private_key.sign(
            message.encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return {
            "id": 1,
            "cmd": "login",
            "params": {
                "api_key": self._api_key,
                "signature": base64.b64encode(signature).decode('utf-8'),
                "timestamp": timestamp
            }
        }

    def _next_cmd_id(self) -> int:
        with self._cmd_lock:
            self._cmd_id += 1
            return self._cmd_id

    # ------------------------------------------------------------------
    # Orderbook: public API (called from main thread)
    # ------------------------------------------------------------------

    def subscribe_orderbook(self, ticker: str):
        """Subscribe to live orderbook for a ticker. Safe to call from main thread."""
        if ticker in self._subscribed_orderbooks:
            return
        self._subscribed_orderbooks.add(ticker)
        if self._loop and self._ws and self.is_connected:
            asyncio.run_coroutine_threadsafe(
                self._async_subscribe_orderbook([ticker]), self._loop
            )

    def unsubscribe_orderbook(self, ticker: str):
        """Unsubscribe and clear cached data. Safe to call from main thread."""
        self._subscribed_orderbooks.discard(ticker)
        with self._orderbook_lock:
            self.latest_orderbook.pop(ticker, None)
        if self._loop and self._ws and self.is_connected:
            asyncio.run_coroutine_threadsafe(
                self._async_unsubscribe_orderbook([ticker]), self._loop
            )

    def get_orderbook(self, ticker: str) -> Optional[Dict]:
        """
        Return cached orderbook in REST-compatible format:
            {'yes': [[price_cents, count], ...], 'no': [[price_cents, count], ...]}
        Yes side sorted descending (best bid first). Returns None if not cached.
        """
        with self._orderbook_lock:
            raw = self.latest_orderbook.get(ticker)
            if not raw:
                return None
            yes = sorted([[p, c] for p, c in raw['yes'].items() if c > 0], reverse=True)
            no  = sorted([[p, c] for p, c in raw['no'].items()  if c > 0], reverse=True)
        if not yes and not no:
            return None
        return {'yes': yes, 'no': no}

    # ------------------------------------------------------------------
    # Orderbook: async senders (run on WS event loop)
    # ------------------------------------------------------------------

    async def _async_subscribe_orderbook(self, tickers: list):
        if self._ws:
            await self._ws.send(json.dumps({
                "id": self._next_cmd_id(),
                "cmd": "subscribe",
                "params": {"channels": ["orderbook_delta"], "market_tickers": tickers}
            }))
            logger.debug(f"KalshiWSFeed: subscribed orderbook for {tickers}")

    async def _async_unsubscribe_orderbook(self, tickers: list):
        if self._ws:
            await self._ws.send(json.dumps({
                "id": self._next_cmd_id(),
                "cmd": "unsubscribe",
                "params": {"channels": ["orderbook_delta"], "market_tickers": tickers}
            }))
            logger.debug(f"KalshiWSFeed: unsubscribed orderbook for {tickers}")

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, msg: dict):
        """Route inbound WS messages to queues or orderbook cache."""
        msg_type = msg.get('type', '')
        data = msg.get('msg', {})

        if msg_type == 'fill':
            self.fill_queue.put(data)
            logger.debug(f"⚡ WS fill: {data.get('ticker')} order={str(data.get('order_id',''))[:8]}")

        elif msg_type == 'order':
            self.order_queue.put(data)
            logger.debug(f"⚡ WS order: {data.get('ticker')} status={data.get('status')}")

        elif msg_type in ('orderbook_snapshot', 'orderbook_delta'):
            self._apply_orderbook_update(data, snapshot=(msg_type == 'orderbook_snapshot'))

        # subscription confirmations / heartbeats silently ignored

    def _apply_orderbook_update(self, data: dict, snapshot: bool):
        """
        Apply a Kalshi orderbook snapshot or delta to latest_orderbook.

        Kalshi sends [[price_cents, count], ...] lists for each side.
        A delta entry with count=0 means remove that price level.
        """
        ticker = data.get('market_ticker') or data.get('ticker')
        if not ticker:
            return

        with self._orderbook_lock:
            if snapshot or ticker not in self.latest_orderbook:
                self.latest_orderbook[ticker] = {'yes': {}, 'no': {}}

            ob = self.latest_orderbook[ticker]

            for side in ('yes', 'no'):
                for entry in data.get(side, []):
                    try:
                        price, count = int(entry[0]), int(entry[1])
                        if count == 0:
                            ob[side].pop(price, None)
                        else:
                            ob[side][price] = count
                    except (IndexError, TypeError, ValueError):
                        pass

        # Signal the main loop that fresh orderbook data is available.
        # Uses non-blocking set() — safe to call from asyncio thread.
        self.orderbook_updated.set()

    # ------------------------------------------------------------------
    # Async connection loop
    # ------------------------------------------------------------------

    def _make_auth_headers(self) -> dict:
        """
        Build signed HTTP headers for the WebSocket upgrade request.
        Kalshi requires the same headers as REST API calls on the initial
        HTTP 101 Upgrade — the login command alone is not sufficient.
        """
        timestamp = str(int(time.time() * 1000))
        message = timestamp + "GET" + self.WS_PATH
        signature = self._private_key.sign(
            message.encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode('utf-8'),
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }

    async def _connect_and_run(self):
        """Single connection lifecycle: connect → login → subscribe → receive."""
        auth_headers = self._make_auth_headers()
        async with websockets.connect(self._ws_url, additional_headers=auth_headers) as ws:
            self._ws = ws

            # Auth is handled by HTTP headers in the upgrade request.
            # No login command needed on this endpoint.

            # Subscribe to fill + order channels
            await ws.send(json.dumps({
                "id": 2,
                "cmd": "subscribe",
                "params": {"channels": ["fill", "order"]}
            }))

            # 3. Re-subscribe to any orderbook tickers from before reconnect
            if self._subscribed_orderbooks:
                await self._async_subscribe_orderbook(list(self._subscribed_orderbooks))

            self.is_connected = True
            logger.info("⚡ KalshiWSFeed: Connected — fill+order+orderbook subscribed")

            # 4. Event loop
            try:
                async for raw in ws:
                    if not self.running:
                        break
                    try:
                        self._handle_message(json.loads(raw))
                    except Exception as e:
                        logger.debug(f"KalshiWSFeed parse error: {e}")
            finally:
                self._ws = None
                self.is_connected = False

    async def start(self):
        """
        Main async entry point — run in a daemon thread:

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(feed.start())
        """
        if websockets is None or self._private_key is None:
            logger.error("KalshiWSFeed: Cannot start — missing websockets library or private key")
            return

        self._loop = asyncio.get_event_loop()
        reconnect_delay = self._reconnect_delay_base

        while self.running:
            try:
                await self._connect_and_run()
                reconnect_delay = self._reconnect_delay_base
            except Exception as e:
                self.is_connected = False
                logger.warning(
                    f"KalshiWSFeed: Disconnected ({e}). Reconnecting in {reconnect_delay}s..."
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)

    # ------------------------------------------------------------------
    # Public status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            'connected': self.is_connected,
            'fill_queue_size': self.fill_queue.qsize(),
            'order_queue_size': self.order_queue.qsize(),
            'orderbook_tickers': len(self._subscribed_orderbooks),
        }
