import logging
import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self, client, config, telegram=None):
        self.client = client
        self.config = config
        self.telegram = telegram
        self.positions_file = Path("data/positions.json")
        Path("data").mkdir(exist_ok=True)
        self.positions = self._load_positions()

    def cancel_all_resting_orders(self) -> int:
        """Cancels all 'resting' orders to free up capital using V2 Batch Cancel."""
        logger.info("🧹 SEARCHING FOR RESTING ORDERS...")
        try:
            response = self.client._make_request("GET", "/portfolio/orders", params={"status": "resting"})
            resting_orders = response.get('orders', [])
            if not resting_orders:
                logger.info("✨ No resting orders found.")
                return 0

            order_ids = [o['order_id'] for o in resting_orders]
            logger.info(f"🗑️ Batch canceling {len(order_ids)} orders...")
            self.client._make_request("DELETE", "/portfolio/orders/batched", json={"ids": order_ids})
            logger.info(f"✅ Purged {len(order_ids)} orders.")
            return len(order_ids)
        except Exception as e:
            logger.error(f"❌ Batch cancel failed: {e}")
            return 0

    def sync_with_exchange(self) -> bool:
        """Calculates real-time dollar exposure using V2 fields."""
        logger.info("📡 SYNCING PORTFOLIO...")
        try:
            found_positions = self.client.get_positions()
            active_on_kalshi = []
            total_deployed = 0.0

            for data in found_positions:
                qty = data.get('position', 0)
                if qty == 0: continue

                ticker = data.get('ticker') or data.get('market_ticker')
                exposure_str = data.get('market_exposure_dollars') or data.get('total_traded_dollars', "0.0")
                pos_cost = abs(float(exposure_str))
                total_deployed += pos_cost

                active_on_kalshi.append({
                    'ticker': ticker,
                    'side': 'yes' if qty > 0 else 'no',
                    'quantity': abs(qty),
                    'cost': round(pos_cost, 2),
                    'avg_price': round(pos_cost / abs(qty), 2) if qty != 0 else 0
                })

            self.positions = active_on_kalshi
            self._save_positions()
            logger.info(f"✅ Sync Complete: {len(self.positions)} active positions. Total Deployed: ${total_deployed:.2f}")
            return True
        except Exception as e:
            logger.error(f"❌ Sync Failed: {e}")
            return False

    def open_position(self, opp: Dict, size: int) -> bool:
        """Places a real limit order on Kalshi V2 with correct YES/NO price handling."""
        ticker = opp['ticker']
        side = opp.get('side', 'yes')
        price_cents = int(opp['entry_price'] * 100)
        client_id = str(uuid.uuid4())

        logger.info(f"🛒 PLACING ORDER: {size}x {ticker} @ {price_cents}c ({side.upper()} side)")
        
        try:
            # Build order payload with correct price field based on side
            order_payload = {
                "ticker": ticker,
                "action": "buy",
                "side": side,
                "count": int(size),
                "type": "limit",
                "client_order_id": client_id
            }
            
            # CRITICAL FIX: Use yes_price for YES, no_price for NO
            if side == 'yes':
                order_payload["yes_price"] = price_cents
            else:
                order_payload["no_price"] = price_cents
            
            logger.debug(f"Order payload: {json.dumps(order_payload, indent=2)}")
            
            response = self.client._make_request("POST", "/portfolio/orders", json=order_payload)
            
            if response and 'order' in response:
                order_id = response['order'].get('order_id')
                logger.info(f"✅ Order Accepted: {order_id}")
                
                # Send Telegram notification with full position details
                if self.telegram:
                    position_data = {
                        'ticker': ticker,
                        'title': opp.get('title', ''),
                        'side': side,
                        'probability': opp.get('probability', 0),
                        'entry_price': opp.get('entry_price', 0),
                        'expected_return': opp.get('expected_return', 0),
                        'cost': size * opp.get('entry_price', 0),
                        'days_to_close': opp.get('days_to_close', 0)
                    }
                    self.telegram.notify_position_opened(position_data)
                
                return True
            else:
                logger.error(f"❌ Order rejected or invalid response: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Order Failed for {ticker}: {e}")
            if self.telegram:
                self.telegram.notify_error(f"Order failed for {ticker}", str(e))
            return False

    def _load_positions(self):
        if self.positions_file.exists():
            try:
                with open(self.positions_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading positions: {e}")
        return []

    def _save_positions(self):
        try:
            with open(self.positions_file, 'w') as f:
                json.dump(self.positions, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving positions: {e}")

    def get_open_positions(self):
        return self.positions

    def print_summary(self):
        """Print portfolio summary"""
        if not self.positions:
            logger.info("No open positions")
            return
        
        total_cost = sum(p.get('cost', 0) for p in self.positions)
        logger.info(f"Open Positions: {len(self.positions)} | Total Deployed: ${total_cost:.2f}")
