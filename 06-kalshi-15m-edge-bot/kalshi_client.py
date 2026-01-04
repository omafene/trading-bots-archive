"""
Kalshi API Client
Handles authentication and all API interactions with Kalshi
"""

import requests
import logging
import json
import time
import base64
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class KalshiClient:
    """Client for interacting with Kalshi API"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.use_demo = config['api']['use_demo']
        self.base_url = config['api']['demo_url'] if self.use_demo else config['api']['base_url']
        
        # API key authentication (both demo and production)
        if self.use_demo:
            self.api_key_id = config['api'].get('demo_api_key_id')
            self.private_key_path = config['api'].get('demo_private_key_path')
        else:
            # Production uses API keys too
            self.api_key_id = config['api'].get('api_key_id')
            self.private_key_path = config['api'].get('private_key_path')
        
        self.private_key = None

        # Auth tokens
        self.token = None
        self.token_expiry = None
        self.member_id = None

        # Persistent HTTP session with connection pooling.
        # Reuses TCP+TLS connections across calls — saves ~50-150ms per request
        # vs the old requests.request() which opened a new connection every time.
        # pool_connections=10 keeps 10 host-level pools (one per host, we only use one).
        # pool_maxsize=10 allows up to 10 simultaneous live connections (covers parallel fetches).
        # Old: used requests.request() — no session, no connection reuse.
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # Load private key if we have a path
        if self.private_key_path:
            self._load_private_key()
        
    def _load_private_key(self):
        """Load RSA private key from file"""
        try:
            key_path = Path(self.private_key_path)
            if not key_path.exists():
                logger.error(f"Private key file not found: {self.private_key_path}")
                return
            
            with open(key_path, 'rb') as key_file:
                self.private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            logger.info("Successfully loaded private key")
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
        
    def authenticate(self) -> bool:
        """
        Authenticate with Kalshi using API keys
        Works for both demo and production
        Returns True if successful, False otherwise
        """
        return self._authenticate_with_api_key()
    
    def _authenticate_with_api_key(self) -> bool:
        """Authenticate using API key (demo and production)"""
        try:
            if not self.private_key:
                logger.error("Private key not loaded")
                return False
            
            # For Kalshi, we use the API key ID directly
            # No need to hit /login endpoint
            self.token = self.api_key_id
            self.token_expiry = datetime.now() + timedelta(days=365)  # API keys don't expire
            
            logger.info(f"Successfully authenticated with API key: {self.api_key_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"API key authentication failed: {e}")
            return False
    
    def _get_signed_headers(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        """
        Create signed headers for API key authentication
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (full path including /trade-api/v2)
            body: Request body (optional)
        
        Returns:
            Headers dictionary with signature
        """
        timestamp = str(int(time.time() * 1000))
        
        # Strip query parameters from path before signing
        path_without_query = path.split('?')[0]
        
        # Create message to sign: timestamp + method + path
        # Note: body is NOT included in Kalshi's signing
        message = timestamp + method.upper() + path_without_query
        
        # Sign the message with private key using PSS padding (required by Kalshi)
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Encode signature to base64
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Return headers
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature_b64,
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }
    
    def _ensure_authenticated(self):
        """Ensure we have a valid token, refresh if needed"""
        if not self.token or datetime.now() >= self.token_expiry:
            logger.info("Token expired or missing, re-authenticating...")
            self.authenticate()
    
    def _make_request(self, method: str, endpoint: str, timeout=None, **kwargs) -> Optional[Dict]:
        """
        Make authenticated API request with retry logic and timeout
        """

        # Get timeout from config if not provided
        if timeout is None:
            timeout = self.config.get('api', {}).get('timeout', 10)
            # Reads from config.yaml under api.timeout, defaults to 10 if not found

        self._ensure_authenticated()

        url = f"{self.base_url}{endpoint}"

        # Check we have private key
        if not self.private_key:
            logger.error("No private key available for signing")
            return None

        max_retries = self.config['execution']['retry_attempts']

        for attempt in range(max_retries + 1):
            try:
                # Generate fresh headers with new signature for each attempt
                # For signing, we need the full path including /trade-api/v2
                full_path = f"/trade-api/v2{endpoint}"
                headers = self._get_signed_headers(method, full_path, kwargs.get('json'))

                # Use persistent session (reuses TCP+TLS connection)
                # Old: response = requests.request(method=method, url=url, ...)
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ Timeout after {timeout}s on {method} {endpoint}")

                # For order creation, verify submission instead of assuming failure
                if endpoint == "/portfolio/orders" and method == "POST":
                    logger.info("Timeout on order creation - verifying submission...")
                    time.sleep(2)  # Give Kalshi time to process

                    # Try to find order in recent orders
                    ticker = kwargs.get('json', {}).get('ticker')
                    side = kwargs.get('json', {}).get('side')

                    if ticker and side:
                        try:
                            recent = self._make_request("GET", "/portfolio/orders", params={"status": "resting"})
                            if recent and 'orders' in recent:
                                for order in recent['orders']:
                                    if order.get('ticker') == ticker and order.get('side') == side:
                                        logger.info(f"✅ Found order after timeout: {order.get('order_id')}")
                                        return {"order": order}  # Return the found order
                        except Exception as e:
                            logger.error(f"Error verifying order after timeout: {e}")

                    logger.warning("Could not verify order after timeout")

                return None

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif e.response.status_code == 401:  # Unauthorized
                    logger.warning(f"401 Unauthorized on attempt {attempt + 1}, re-authenticating...")
                    self.authenticate()
                    continue
                else:
                    logger.error(f"HTTP error: {e}")
                    logger.error(f"Status code: {e.response.status_code}")
                    logger.error(f"Response: {e.response.text}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(self.config['execution']['retry_delay'])
                    continue
                return None

        return None
    
    def get_markets(self, 
                    status: str = "open",
                    category: Optional[str] = None,
                    limit: int = 1000) -> List[Dict]:
        """
        Get all markets matching criteria
        
        Args:
            status: Market status (open, closed, settled)
            category: Market category filter (optional)
            limit: Maximum number of markets to return
        
        Returns:
            List of market dictionaries
        """
        params = {
            "status": status,
            "limit": limit
        }
        
        if category:
            params["category"] = category
        
        result = self._make_request("GET", "/markets", params=params)
        
        if result and 'markets' in result:
            return result['markets']
        return []
    
    def get_market(self, ticker: str) -> Optional[Dict]:
        """
        Get details for a specific market
        
        Args:
            ticker: Market ticker symbol
        
        Returns:
            Market dictionary or None
        """
        result = self._make_request("GET", f"/markets/{ticker}")
        
        if result and 'market' in result:
            return result['market']
        return None
    
    def get_orderbook(self, ticker: str, depth: int = 5) -> Optional[Dict]:
        """
        Get orderbook for a market
        
        Args:
            ticker: Market ticker symbol
            depth: Number of price levels to return
        
        Returns:
            Orderbook dictionary with yes/no bids and asks
        """
        params = {"depth": depth}
        result = self._make_request("GET", f"/markets/{ticker}/orderbook", params=params)
        
        if result and 'orderbook' in result:
            return result['orderbook']
        # New API format: orderbook_fp with yes_dollars/no_dollars (ascending decimal strings)
        # Normalize to the old format: {'yes': [[price_cents, qty], ...], 'no': [...]} descending
        if result and 'orderbook_fp' in result:
            fp = result['orderbook_fp']
            def parse_side(entries):
                parsed = [[round(float(e[0]) * 100), round(float(e[1]))] for e in entries]
                return list(reversed(parsed))  # ascending → descending (best bid first)
            return {
                'yes': parse_side(fp.get('yes_dollars', [])),
                'no':  parse_side(fp.get('no_dollars', [])),
            }
        if result:
            logger.warning(
                f"⚠️ Unknown orderbook format for {ticker} — keys: {list(result.keys())}. "
                f"Kalshi may have changed their API. Raw sample: {str(result)[:300]}"
            )
        return None
    
    def get_balance(self) -> Optional[float]:
        """
        Get current account balance

        Returns:
            Available balance in dollars
        """
        result = self._make_request("GET", "/portfolio/balance")
        if result:
            logger.debug(f"Balance API response: {result}")
            return result.get('balance', 0) / 100  # Convert cents to dollars
        else:
            logger.error("Failed to get balance - API returned None")
        return None
    

    def create_order(self, ticker: str, side: str, quantity: int, order_type: str = "limit", **kwargs) -> Optional[Dict]:
        payload = {
            "ticker": ticker,
            "action": kwargs.get("action", "buy"),
            "side": side.lower(),
            "count": int(quantity),
            "type": order_type.lower()
        }

        # Set Time In Force (GTC is default, we pass IOC for Market orders)
        if "time_in_force" in kwargs:
            payload["time_in_force"] = kwargs["time_in_force"]

        # Map price correctly
        if "yes_price" in kwargs:
            payload["yes_price"] = int(kwargs["yes_price"])
        elif "no_price" in kwargs:
            payload["no_price"] = int(kwargs["no_price"])

        logger.info(f"Submitting {order_type} {side} order for {ticker} (TIF: {payload.get('time_in_force', 'gtc')})")
        return self._make_request("POST", "/portfolio/orders", json=payload)

    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Get a specific order by ID

        Args:
            order_id: Order ID to retrieve

        Returns:
            Order dictionary or None
        """
        result = self._make_request("GET", f"/portfolio/orders/{order_id}")

        if result and 'order' in result:
            return result['order']
        return None

    def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """
        Get user's orders

        Args:
            status: Filter by order status (optional)

        Returns:
            List of order dictionaries
        """
        params = {}
        if status:
            params["status"] = status

        result = self._make_request("GET", "/portfolio/orders", params=params)

        if result and 'orders' in result:
            return result['orders']
        return []
    
    def get_positions(self) -> List[Dict]:
        """
        Get user's current positions.
        Updated to handle Kalshi V2 market/event split.
        """
        result = self._make_request("GET", "/portfolio/positions")

        if not result:
            return []

        # Extract both types of positions
        m_pos = result.get('market_positions', [])
        e_pos = result.get('event_positions', [])

        # Combine them into one list for the bot to process
        all_positions = m_pos + e_pos

        logger.info(f"Found {len(all_positions)} total positions ({len(m_pos)} market, {len(e_pos)} event)")
        return all_positions

    def get_fills(self, ticker: Optional[str] = None, order_id: Optional[str] = None,
                  min_ts: Optional[int] = None, max_ts: Optional[int] = None,
                  limit: int = 100) -> List[Dict]:
        """
        Get fill history (executed trades).

        Args:
            ticker: Filter by specific ticker
            order_id: Filter by specific order ID
            min_ts: Minimum timestamp (Unix milliseconds)
            max_ts: Maximum timestamp (Unix milliseconds)
            limit: Maximum number of fills to return (default 100)

        Returns:
            List of fill dictionaries containing:
                - order_id: Order that was filled
                - ticker: Market ticker
                - side: 'yes' or 'no'
                - count: Number of contracts filled
                - price: Fill price in cents (divide by 100 for dollars)
                - action: 'buy' or 'sell'
                - created_time: When fill occurred
        """
        params = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if order_id:
            params["order_id"] = order_id
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        result = self._make_request("GET", "/portfolio/fills", params=params)

        if result and 'fills' in result:
            return result['fills']
        return []

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if successful
        """
        result = self._make_request("DELETE", f"/portfolio/orders/{order_id}")
        return result is not None
