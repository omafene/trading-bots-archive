"""
Simplified Position Manager for 15-min Edge Bot
Fixed: Robust timestamp parsing and improved Fill/Success detection.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class PositionManager15m:
    def __init__(self, client, config: Dict, telegram=None):
        self.client = client
        self.config = config
        self.telegram = telegram
        self.open_positions = []
        self.pending_orders: Dict[str, Dict] = {}
        self.expiry_seconds = config.get('strategy', {}).get('order_expiry_seconds', 60)

    def open_position(self, opportunity: Dict, size_dollars: float, order_type: str = "limit") -> bool:
        """Executes trade and tracks order ID for fill monitoring."""
        ticker = opportunity['ticker']
        side = opportunity['recommended_side']
        entry_price = opportunity['entry_price']
        
        quantity = int(size_dollars / entry_price)
        if quantity < 1: return False
        
        logger.info(f"🚀 Executing {order_type.upper()} order for {ticker}")
        
        try:
            order_params = {
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "order_type": order_type
            }

            # Buffer logic: 2 cents for Limit, 1 cent for Market IOC
            buffer = 0.06 if order_type == "limit" else 0.10
            price_cents = int((entry_price + buffer) * 100)
            order_params[f"{side}_price"] = price_cents

            if order_type == "market":
                order_params["time_in_force"] = "immediate_or_cancel"
                logger.info(f"   Mode: IOC | Protection: {price_cents}¢")

            result = self.client.create_order(**order_params)
            
            # FIXED: Return True if order_id exists, even if not yet filled
            if result and (result.get('order_id') or result.get('id')):
                order_id = result.get('order_id') or result.get('id')
                status = result.get('status', 'unknown')
                
                # Track for fill confirmations
                self.pending_orders[order_id] = opportunity
                logger.info(f"✅ Order {order_id} submitted (Status: {status})")
                return True
            return False
        
        except Exception as e:
            logger.error(f"❌ Order execution failed: {e}")
            return False

    def check_for_fills(self):
        """Polls fills to catch partial or late fills and notify Telegram."""
        if not self.pending_orders: return
        try:
            fills_resp = self.client._make_request("GET", "/portfolio/fills")
            if not fills_resp or 'fills' not in fills_resp: return
            
            fill_ids = {f.get('order_id') for f in fills_resp.get('fills', [])}
            for oid in list(self.pending_orders.keys()):
                if oid in fill_ids:
                    opp = self.pending_orders.pop(oid)
                    logger.info(f"🎯 FILL CONFIRMED: {opp['ticker']}")
                    if self.telegram:
                        self.telegram.send_message(f"🔔 **FILL CONFIRMED**\nTicker: {opp['ticker']}\nSide: {opp['recommended_side'].upper()}")
        except Exception as e:
            logger.error(f"Fill check error: {e}")

    def cancel_stale_orders(self):
        """Janitor cleanup with robust timestamp handling."""
        try:
            open_orders = self.client.get_orders(status="resting")
            if not open_orders: return
            now = datetime.now(timezone.utc)
            for order in open_orders:
                oid = order.get('order_id')
                ts_str = order.get('created_time')
                if not ts_str: continue

                # Truncate irregular sub-second digits for Python parsing
                clean_ts = re.sub(r'(\.\d{6})\d+', r'\1', ts_str.replace('Z', '+00:00'))
                try:
                    created_at = datetime.fromisoformat(clean_ts)
                except ValueError:
                    created_at = datetime.fromisoformat(clean_ts.split('.')[0] + '+00:00')

                if (now - created_at).total_seconds() > self.expiry_seconds:
                    if self.client.cancel_order(oid):
                        self.pending_orders.pop(oid, None)
                        logger.info(f"🧹 JANITOR: Canceled stale order {oid}")
        except Exception as e:
            logger.error(f"❌ Janitor error: {e}")

    def get_open_positions(self):
        try:
            raw = self.client.get_positions()
            # Filter for active contracts
            self.open_positions = [p for p in raw if (p.get('position') or 0) > 0]
            return self.open_positions
        except Exception as e:
            logger.error(f"Position sync error: {e}")
            return []

    def sync_with_exchange(self):
        self.check_for_fills()
        self.cancel_stale_orders()
        self.get_open_positions()
        logger.info(f"✅ Synced: {len(self.open_positions)} positions | Janitor run complete")


    def manage_take_profit(self):
        """
        Scans all open positions and exits if the target ROI is reached.
        """
        # 1. THE TOGGLE: Check config first
        if not self.config.get('strategy', {}).get('tp_enabled', False):
            return

        # 2. GET OPEN POSITIONS: Hits /portfolio/positions
        positions = self.get_open_positions() # Ensure this method calls the API
        target_roi = self.config.get('strategy', {}).get('target_roi', 0.50)

        for pos in positions:
            ticker = pos.get('market_ticker') # Kalshi uses 'market_ticker' in positions
            side = pos.get('side', 'yes').lower()
            
            # entry_price is what you paid (in cents)
            entry_price = pos.get('average_price', 0) / 100 
            if entry_price <= 0: continue

            try:
                # 3. GET LIVE BID: What can we sell for right now?
                market = self.client.get_market(ticker)
                # If you hold YES, you must sell to the YES_BID
                current_bid = market.get(f'{side}_bid', 0) / 100
                
                if current_bid <= 0: continue

                # ROI Calculation: (Sell Price - Buy Price) / Buy Price
                current_roi = (current_bid - entry_price) / entry_price
                
                if current_roi >= target_roi:
                    logger.info(f"💰 TP TRIGGERED: {ticker} | ROI: {current_roi:.1%}")
                    
                    # 4. EXECUTE SELL: 'action: sell' reduces your position
                    self.client.create_order(
                        ticker=ticker,
                        side=side,
                        action='sell', 
                        quantity=pos.get('position', 0),
                        order_type='market'
                    )

                    if self.telegram:
                        self.telegram.send_message(f"✅ **TP EXECUTED**\n{ticker}\nROI: {current_roi:.1%}")
            except Exception as e:
                logger.error(f"Error checking TP for {ticker}: {e}")
