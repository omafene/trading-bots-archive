import logging
import time
import concurrent.futures
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

class Market15mScanner:
    def __init__(self, client: KalshiClient, config: Dict, spot_feed=None, feed_calibration_tracker=None, ws_feed=None):
        self.client = client
        self.config = config
        self.strategy_config = config['strategy']
        self.spot_feed = spot_feed
        self.feed_calibration_tracker = feed_calibration_tracker

        # Kalshi WS feed — set after WS connects, used for real-time orderbook cache
        self.ws_feed = ws_feed

        # Market list cache: avoids 4 REST calls every 2s scan cycle
        self._market_cache: List[Dict] = []
        self._market_cache_time: float = 0.0
        self._market_cache_ttl: float = config.get('monitoring', {}).get('market_cache_ttl', 10.0)

        # Track tickers already subscribed to WS orderbook channel
        self._subscribed_tickers: set = set()

        logger.info("✅ 15-minute market scanner initialized (dynamic symbols)")

    def scan_opportunities(self) -> List[Dict]:
        logger.info("Scanning for 15-min market opportunities...")
        opportunities = []
        markets = self._get_15min_markets()
        if not markets: return []

        for market in markets:
            try:
                opportunity = self._evaluate_market(market)
                if opportunity: opportunities.append(opportunity)
            except Exception as e:
                ticker = market.get('ticker', 'unknown')
                logger.error(f"Error evaluating market {ticker}: {e}")
                continue
        return opportunities

    def _get_15min_markets(self) -> List[Dict]:
        """
        Fetch open 15m markets with three speed optimizations:
          1. 10-second TTL cache    — skips REST entirely on most scan cycles
          2. Parallel fetch         — all symbols fetched concurrently (ThreadPoolExecutor)
          3. WS auto-subscribe      — new tickers are subscribed to real-time orderbook channel

        # Old implementation (sequential REST, no cache):
        # now = datetime.now(timezone.utc)
        # active_symbols = self.strategy_config.get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])
        # all_markets = []
        # for symbol in active_symbols:
        #     series_ticker = f'KX{symbol}15M'
        #     try:
        #         response = self.client._make_request("GET", "/markets", params={
        #             "series_ticker": series_ticker, "status": "open", "limit": 100
        #         })
        #         if not response or not isinstance(response, dict):
        #             continue
        #         markets_list = response.get('markets', [])
        #         if markets_list:
        #             logger.info(f"Found {len(markets_list)} open markets for {series_ticker}")
        #             all_markets.extend(markets_list)
        #     except Exception as e:
        #         logger.error(f"Error fetching markets for series {series_ticker}: {e}")
        #         continue
        # return all_markets
        """
        # --- Cache check (skip REST on most scan cycles) ---
        now = time.monotonic()
        if self._market_cache and (now - self._market_cache_time) < self._market_cache_ttl:
            logger.debug(
                f"📦 Market cache hit ({now - self._market_cache_time:.1f}s old, TTL={self._market_cache_ttl}s)"
            )
            return self._market_cache

        active_symbols = self.strategy_config.get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])

        def fetch_symbol(symbol: str) -> List[Dict]:
            series_ticker = f'KX{symbol}15M'
            try:
                response = self.client._make_request("GET", "/markets", params={
                    "series_ticker": series_ticker,
                    "status": "open",
                    "limit": 100
                })
                if response is None:
                    logger.warning(f"⚠️ API returned None for {series_ticker} (auth/network failure?)")
                    return []
                if not isinstance(response, dict):
                    logger.warning(f"⚠️ Unexpected response type for {series_ticker}: {type(response)} — {str(response)[:200]}")
                    return []
                markets = response.get('markets', [])
                if markets:
                    logger.info(f"Found {len(markets)} open markets for {series_ticker}")
                else:
                    logger.warning(f"⚠️ API returned 0 markets for {series_ticker} — response keys: {list(response.keys())}")
                return markets
            except Exception as e:
                logger.error(f"Error fetching markets for series {series_ticker}: {e}")
            return []

        # --- Parallel fetch: all symbols at once instead of sequentially ---
        all_markets: List[Dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_symbols)) as pool:
            for markets in pool.map(fetch_symbol, active_symbols):
                all_markets.extend(markets)

        # --- WS orderbook auto-subscribe for newly discovered tickers ---
        if self.ws_feed and self.ws_feed.is_connected:
            for market in all_markets:
                ticker = market.get('ticker')
                if ticker and ticker not in self._subscribed_tickers:
                    self.ws_feed.subscribe_orderbook(ticker)
                    self._subscribed_tickers.add(ticker)
                    logger.info(f"📡 WS orderbook subscribed: {ticker}")

        # --- Adaptive TTL ---
        # Short TTL (5s) when no market is in the 2-5 min trading window so we
        # discover newly opened markets quickly (they appear every 15 min).
        # Long TTL (30s) when a market IS in the window — the list is stable and
        # the WS feed handles orderbook updates, so REST re-fetches are wasted.
        min_time = self.strategy_config.get('min_minutes_to_close', 2)
        max_time = self.strategy_config.get('max_minutes_to_close', 5)
        now_dt = datetime.now(timezone.utc)
        in_window = False
        for m in all_markets:
            close_str = m.get('close_time', '')
            if close_str:
                try:
                    ct = datetime.fromisoformat(close_str.replace('Z', '+00:00'))
                    mtc = (ct - now_dt).total_seconds() / 60
                    if min_time <= mtc <= max_time:
                        in_window = True
                        break
                except Exception:
                    pass
        self._market_cache_ttl = 30.0 if in_window else 5.0
        logger.debug(f"📦 Cache TTL set to {self._market_cache_ttl:.0f}s ({'in window' if in_window else 'between windows'})")

        # Update cache
        self._market_cache = all_markets
        self._market_cache_time = now
        return all_markets

    def _evaluate_market(self, market: Dict) -> Optional[Dict]:
        ticker = market.get('ticker', '')
        active_symbols = self.strategy_config.get('symbols', ['BTC', 'ETH', 'SOL', 'XRP'])
        symbol = next((s for s in active_symbols if f'KX{s}' in ticker), None)
        if not symbol: return None
        
        close_time_str = market.get('close_time')
        if not close_time_str: return None
        now = datetime.now(timezone.utc)
        try:
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            minutes_to_close = (close_time - now).total_seconds() / 60
        except: return None

        # === FEED CALIBRATION: Track BEFORE time filter (for markets at open) ===
        if (self.feed_calibration_tracker and self.spot_feed and
            14.0 <= minutes_to_close <= 15.5):  # Market just opened

            title = market.get('title', '')
            detected_type = self._detect_market_type(title)

            # Only track UP/DOWN markets with floor_strike
            if detected_type in ['up', 'down', 'up_down']:
                threshold = market.get('floor_strike')

                if threshold:
                    try:
                        our_spot_price = self.spot_feed._get_price(symbol)
                        if our_spot_price:
                            # Get individual exchange prices for calibration analysis
                            exchange_prices = self.spot_feed.get_last_exchange_prices(symbol)
                            open_time_str = market.get('open_time', '')
                            self.feed_calibration_tracker.track_market_open(
                                ticker=ticker,
                                symbol=symbol,
                                floor_strike=threshold,
                                our_spot_price=our_spot_price,
                                market_open_time=open_time_str,
                                minutes_until_close=minutes_to_close,
                                exchange_prices=exchange_prices
                            )
                    except Exception as e:
                        logger.debug(f"Feed calibration tracking error for {ticker}: {e}")

        # --- Time filter for trading decisions ---
        min_time = self.strategy_config.get('min_minutes_to_close', 2)
        max_time = self.strategy_config.get('max_minutes_to_close', 15)

        if not (min_time <= minutes_to_close <= max_time):
            # This will now correctly skip markets at 13m if your max is 10
            return None

        # Try WS cache first (near-zero latency — real-time data already in memory).
        # Fall back to REST only when the WS cache has no data yet for this ticker.
        # Old: orderbook = self.client.get_orderbook(ticker)
        orderbook = None
        if self.ws_feed and self.ws_feed.is_connected:
            orderbook = self.ws_feed.get_orderbook(ticker)
            if orderbook:
                logger.debug(f"📡 WS orderbook cache hit: {ticker}")
            else:
                logger.debug(f"📡 WS cache miss for {ticker} — falling back to REST")
        if not orderbook:
            orderbook = self.client.get_orderbook(ticker)
        if not orderbook: return None
        yes_orders = orderbook.get('yes') or []
        no_orders = orderbook.get('no') or []
        if not yes_orders or not no_orders: return None

        # Extract threshold based on market type
        title = market.get('title', '')
        detected_type = self._detect_market_type(title)

        # For UP/DOWN markets, use floor_strike (the "price to beat")
        if detected_type in ['up', 'down', 'up_down']:
            threshold = market.get('floor_strike')

            # If not in list response, try individual market endpoint
            if threshold is None:
                try:
                    full_market = self.client.get_market(ticker)
                    if full_market:
                        threshold = full_market.get('floor_strike')
                except Exception as e:
                    logger.warning(f"Could not fetch floor_strike for {ticker}: {e}")
        else:
            # ABOVE/BELOW markets use strike_price or cap
            strike = market.get('strike_price')
            cap = market.get('cap')
            threshold = strike or cap

        logger.info(f"📋 Market Debug: {ticker}")
        logger.info(f"   Title: {title}")
        logger.info(f"   Detected type: {detected_type}")
        if detected_type in ['up', 'down', 'up_down']:
            logger.info(f"   Floor strike: {market.get('floor_strike')}")
        else:
            logger.info(f"   Strike price: {market.get('strike_price')}")
            logger.info(f"   Cap: {market.get('cap')}")
        logger.info(f"   Final threshold: {threshold}")

        return {
            'ticker': ticker, 'symbol': symbol, 'title': title,
            'close_time': close_time, 'minutes_to_close': minutes_to_close,
            'market_type': detected_type,
            'yes_bid': yes_orders[0][0] / 100,           # best YES bid (highest, index 0)
            'no_bid':  no_orders[0][0] / 100,            # best NO bid
            'yes_ask': (100 - no_orders[0][0]) / 100,   # true YES ask = cross spread via NO bids
            'no_ask':  (100 - yes_orders[0][0]) / 100,  # true NO ask = cross spread via YES bids
            'yes_ask_size': no_orders[0][1],             # NO bid depth = counterparties for YES buyers
            'no_ask_size':  yes_orders[0][1],            # YES bid depth = counterparties for NO buyers
            'threshold': threshold,
            'volume': market.get('volume', 0), 'market': market
        }

    def _detect_market_type(self, title: str) -> str:
        t = title.lower()
        if 'up' in t and 'down' in t: return 'up_down'
        if 'up' in t: return 'up'
        if 'down' in t: return 'down'
        if 'above' in t or 'over' in t: return 'above'
        if 'below' in t or 'under' in t: return 'below'
        return 'unknown'
