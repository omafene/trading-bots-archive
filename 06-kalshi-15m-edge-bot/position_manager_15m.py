"""
Unified Position Manager for 15-min Edge Bot
Integrated: Polling, Metadata-Sync, and Trailing Take Profit.
"""

import logging
import queue
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class PositionManager15m:
    def __init__(self, client, config: Dict, telegram=None, state_manager=None, kalshi_ws_feed=None):
        self.client = client
        self.config = config
        self.telegram = telegram
        self.state_manager = state_manager
        self.ws_feed = kalshi_ws_feed
        self.open_positions = []
        self.pending_orders: Dict[str, Dict] = {} # Metadata Storage
        self.expiry_seconds = config.get('strategy', {}).get('order_expiry_seconds', 60)
        self.slippage_buffer = config.get('strategy', {}).get('slippage_buffer', 0.08)
        self._initial_sync_done = False  # Guard: skip expiry notifications on first sync after restart
        self._positions_last_rest_sync = 0.0  # Timestamp of last get_positions() REST call
        self._entry_price_cache: Dict[str, float] = {}  # Survives cleanup_phantom_pending_orders()
        self.sl_fired_tickers: Dict[str, datetime] = {}  # ticker → market close_time; prevents re-entry after SL
        self._resolved_tickers: set = set()  # Tickers we've already sent a resolution notification for
        self._position_snapshot: Dict[str, Dict] = {}  # ticker → position data; survives API disappearance

    def get_total_position_count(self) -> int:
        """
        Get total positions including pending orders (in-flight).

        This prevents race conditions where orders are placed but not yet
        registered in open_positions, allowing the bot to exceed max_concurrent_trades.

        Returns:
            int: Sum of confirmed positions + pending orders
        """
        confirmed = len(self.open_positions)
        pending = len(self.pending_orders)

        if pending > 0:
            logger.debug(f"Position count: {confirmed} confirmed + {pending} pending = {confirmed + pending} total")

        return confirmed + pending

    def open_position(self, opportunity: Dict, size_dollars: float, order_type: str = "limit"):
        """Executes trade with high-speed Polling to confirm fills.

        Returns:
            tuple: (success: bool, order_id: str or None)
                - (True, order_id) when filled
                - (True, None) when polling timed out
                - (False, None) when order creation failed
        """
        ticker = opportunity['ticker']
        side = opportunity['recommended_side']
        entry_price = opportunity['entry_price']

        quantity = int(size_dollars / entry_price)
        if quantity < 1:
            return (False, None)

        logger.info(f"🚀 Executing {order_type.upper()} for {ticker} ({side.upper()})")

        try:
            order_params = {
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "order_type": order_type
            }

            # Use config slippage_buffer (aligned with edge calculation)
            # This ensures actual execution matches edge calculation assumptions
            price_cents = int((entry_price + self.slippage_buffer) * 100)
            order_params[f"{side}_price"] = price_cents

            if order_type == "market":
                order_params["time_in_force"] = "immediate_or_cancel"

            # Pre-submission counterparty depth check (WS cache, ~0ms).
            # For NO orders, YES bids are the counterparties; for YES orders, NO bids are.
            # If the counterparty side has vanished since the edge-detection depth check,
            # abort now rather than wasting a REST round-trip on a doomed IOC order.
            if order_type == "market" and self.ws_feed and self.ws_feed.is_connected:
                live_ob = self.ws_feed.get_orderbook(ticker)
                if live_ob:
                    counterparty_side = 'yes' if side == 'no' else 'no'
                    cp_orders = live_ob.get(counterparty_side, [])
                    cp_depth = cp_orders[0][1] if cp_orders else 0
                    min_depth = self.config.get('strategy', {}).get('min_order_book_depth', 0)
                    if cp_depth < min_depth:
                        logger.warning(f"⚡ Pre-submit abort {ticker}: counterparty depth vanished "
                                       f"({counterparty_side} depth={cp_depth} < {min_depth})")
                        return (False, None)

            result = self.client.create_order(**order_params)

            # FIX (2026-02-27): Kalshi POST /portfolio/orders returns {"order": {"order_id": "..."}}
            # The order_id is nested under the 'order' key, NOT at the top level.
            # Old code looked at top level only and always fell through to the 1s sleep + REST recovery:
            # Old: order_id = result.get('order_id') or result.get('id') if result else None
            if result:
                order_data = result.get('order', result)  # unwrap {"order": {...}} if present
                order_id = order_data.get('order_id') or order_data.get('id')
            else:
                order_id = None

            # CRITICAL FIX: Even if result is None, check Kalshi for the order
            if not order_id:
                logger.warning(f"⚠️ No order_id in response, checking Kalshi for recent {ticker} orders...")

                # Retry up to 3 times with 200ms gaps (max 600ms) instead of one blind 1s wait.
                # Kalshi usually registers the order within 200-400ms; early exit saves time.
                for _attempt in range(3):
                    time.sleep(0.2)

                    # Check BOTH resting AND filled orders (limit orders might fill immediately)
                    for status in ["resting", "filled"]:
                        if order_id:
                            break  # Already found it

                        recent_orders = self.client.get_orders(status=status)
                        if recent_orders:
                            now = datetime.now(timezone.utc)

                            for order in recent_orders:  # Check ALL orders
                                # Only check recent orders (last 60 seconds to account for clock skew)
                                created_time = order.get('created_time')
                                if created_time:
                                    try:
                                        created_at = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                                        if (now - created_at).total_seconds() > 60:
                                            continue  # Skip old orders
                                    except Exception as e:
                                        logger.debug(f"Could not parse timestamp: {e}")
                                        continue

                                if order.get('ticker') == ticker and order.get('side') == side:
                                    order_id = order.get('order_id')
                                    logger.info(f"✅ Found order in {status} orders (attempt {_attempt+1}): {order_id}")
                                    break

                    if order_id:
                        break  # Found it — no need for more attempts

            if order_id:
                # Save metadata BEFORE polling to prevent sync KeyError
                self.pending_orders[order_id] = {
                    **opportunity,
                    'side': side,
                    'entry_price': entry_price,  # Initial limit price
                    'peak_roi': 0,
                    'order_id': order_id
                }
                # Cache entry_price so it survives cleanup_phantom_pending_orders()
                self._entry_price_cache[ticker] = entry_price

                # --- FILL CONFIRMATION: WS-first, REST fallback ---
                ws_event, ws_msg = self._wait_for_ws_fill(order_id, timeout=0.8)

                if ws_event == 'filled':
                    count = ws_msg.get('count', 0)
                    logger.info(f"⚡ WS: Order {order_id} filled ({count} contracts)")

                    actual_fill = self._get_actual_fill_price(order_id, ticker, 'buy')
                    fill_price = actual_fill or entry_price
                    if actual_fill:
                        logger.info(f"📊 Actual fill price: ${actual_fill:.2f} (limit was ${entry_price:.2f})")

                    # Capture the live bid at fill time as SL reference (entry_bid).
                    # SL compares current_bid vs entry_bid (not fill_price) so it measures
                    # real market movement rather than the structural bid-ask spread gap.
                    # Without this, a wide spread causes SL to fire instantly after fill
                    # even though the market hasn't actually moved against the position.
                    entry_bid = None
                    if self.ws_feed and self.ws_feed.is_connected:
                        ob_at_fill = self.ws_feed.get_orderbook(ticker)
                        if ob_at_fill:
                            fill_bids = ob_at_fill.get(side.lower(), [])
                            if fill_bids:
                                entry_bid = fill_bids[0][0] / 100
                    if entry_bid:
                        logger.info(f"📊 Entry bid at fill: ${entry_bid:.2f} (SL reference, spread gap: ${fill_price - entry_bid:.2f})")
                    else:
                        logger.debug(f"⚠️ Could not capture entry_bid for {ticker} — SL will fall back to entry_price")

                    # Promote immediately to open_positions so the ticker lock stays
                    # active even if get_positions() REST lags (fix for race condition).
                    # sync_with_exchange() will overwrite with authoritative REST data.
                    if not any(p['ticker'] == ticker for p in self.open_positions):
                        meta = self.pending_orders.get(order_id, {})
                        pos_data = {
                            'ticker': ticker,
                            'side': side,
                            'entry_price': fill_price,
                            'entry_bid': entry_bid,   # bid at fill time — SL reference
                            'entry_time': time.time(),  # used to gate SL until sync corrects entry_price
                            'count': count or quantity,
                            'peak_roi': 0,
                            'symbol': meta.get('symbol') or opportunity.get('symbol'),
                            'threshold': meta.get('threshold') or opportunity.get('threshold'),
                            'market_type': meta.get('market_type') or opportunity.get('market_type'),
                            'order_id': order_id,
                            'close_time': opportunity.get('close_time'),  # market expiry for resolution detection
                        }
                        self.open_positions.append(pos_data)
                        # Snapshot survives API disappearance — used for resolution detection
                        self._position_snapshot[ticker] = pos_data
                        logger.info(f"⚡ {ticker} added to open_positions (provisional, REST will reconcile)")

                    # Safe to remove from pending_orders — now tracked in open_positions
                    self.pending_orders.pop(order_id, None)
                    self.sync_with_exchange()
                    return (True, order_id)

                if ws_event == 'canceled':
                    logger.error(f"❌ Order Canceled via WS (No liquidity)")
                    self.pending_orders.pop(order_id, None)
                    return (False, None)

                # WS timed out or not connected — REST fallback
                # Fewer attempts since we already waited ~2s for WS
                rest_attempts = 3 if (self.ws_feed and self.ws_feed.is_connected) else 6
                for attempt in range(rest_attempts):
                    time.sleep(0.3)
                    order_status = self.client.get_order(order_id)

                    if order_status is None:
                        logger.warning(f"⚠️ Polling returned None (attempt {attempt+1}/{rest_attempts})")
                        continue

                    status = order_status.get('status', '').lower()
                    filled = order_status.get('filled_count', 0)

                    if status == 'filled' or (status == 'canceled' and filled > 0):
                        logger.info(f"✅ Order Confirmed: {filled} contracts filled.")
                        actual_entry_price = self._get_actual_fill_price(order_id, ticker, 'buy')
                        if actual_entry_price:
                            self.pending_orders[order_id]['entry_price'] = actual_entry_price
                            logger.info(f"📊 Actual fill price: ${actual_entry_price:.2f} (limit was ${entry_price:.2f})")
                        self.sync_with_exchange(force_rest=True)
                        return (True, order_id)
                    if status == 'canceled' and filled == 0:
                        logger.error(f"❌ Order Canceled (No liquidity)")
                        self.pending_orders.pop(order_id, None)
                        return (False, None)

                logger.info(f"⏳ Order {order_id} submitted (Polling timed out)")
                self.sync_with_exchange(force_rest=True)
                return (True, None)

            # No order_id found - but check if position exists anyway (critical failsafe)
            logger.warning(f"⚠️ No order_id found, checking positions as final verification...")
            time.sleep(0.5)
            self.sync_with_exchange(force_rest=True)  # Force fresh sync

            # Check if we now have a position for this ticker
            for pos in self.open_positions:
                if pos.get('ticker') == ticker and pos.get('side') == side:
                    logger.info(f"✅ CRITICAL: Position found despite missing order_id! {ticker}")
                    return (True, pos.get('order_id'))

            # Truly no order or position found - confirmed failure
            logger.error(f"❌ Confirmed: No order or position found on Kalshi for {ticker}")
            return (False, None)

        except Exception as e:
            logger.error(f"❌ Execution error: {e}")

            # CRITICAL: Even on exception, verify with Kalshi with retry
            logger.warning(f"🔍 Exception occurred, verifying with Kalshi...")
            time.sleep(1)
            self._retry_sync(max_attempts=3)

            # Check if position appeared despite exception
            for pos in self.open_positions:
                if pos.get('ticker') == ticker:
                    logger.info(f"✅ Position found on Kalshi despite exception!")
                    return (True, pos.get('order_id'))

            return (False, None)

    def _retry_sync(self, max_attempts=3):
        """Sync with exponential backoff retry"""
        for attempt in range(1, max_attempts + 1):
            try:
                self.sync_with_exchange(force_rest=True)
                return True
            except Exception as e:
                if attempt < max_attempts:
                    wait = 2 ** attempt  # 2s, 4s, 8s
                    logger.warning(f"Sync failed (attempt {attempt}/{max_attempts}), retry in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"Sync failed after {max_attempts} attempts")
                    return False
        return False

    def sync_with_exchange(self, force_rest=False):
        """Syncs positions while preserving metadata from pending_orders.

        This is the SOURCE OF TRUTH - Kalshi's state overrides bot's assumptions.

        When WS is connected, get_positions() REST is throttled to every
        positions_sync_interval seconds (default 30s) to reduce API load.
        Pass force_rest=True to bypass the throttle (e.g. after a trade).
        """
        self.check_for_fills()
        self.cancel_stale_orders()
        self.cleanup_phantom_pending_orders()  # Remove failed orders

        # Throttle get_positions() REST when WS is maintaining state
        ws_active = self.ws_feed and self.ws_feed.is_connected
        interval = self.config.get('kalshi_ws', {}).get('positions_sync_interval', 30)
        now = time.time()
        if ws_active and not force_rest and (now - self._positions_last_rest_sync) < interval:
            logger.debug(
                f"⏭️ get_positions() throttled "
                f"({now - self._positions_last_rest_sync:.0f}s < {interval}s interval, WS active)"
            )
            return
        self._positions_last_rest_sync = now

        try:
            raw = self.client.get_positions()

            if raw is None:
                logger.error("⚠️ Failed to fetch positions from Kalshi")
                return
            raw_list = raw.get('market_positions', []) if isinstance(raw, dict) else raw
            
            new_positions = []
            for p in raw_list:
                ticker = p.get('ticker')
                raw_count = p.get('position', 0)
                # Kalshi API: position is SIGNED — positive = long YES, negative = long NO.
                # Old bug: `if count <= 0: continue` silently dropped all NO positions every sync.
                if raw_count == 0: continue
                api_side = 'yes' if raw_count > 0 else 'no'
                count = abs(raw_count)

                # --- FIX: Derive metadata to avoid KeyError ---
                # Search pending_orders or existing open_positions for the 'side'
                meta = next((o for oid, o in self.pending_orders.items() if o['ticker'] == ticker), None)
                if not meta:
                    meta = next((o for o in self.open_positions if o['ticker'] == ticker), None)

                # Use Kalshi's avg_cost (actual fill price) if available, otherwise use stored entry_price
                kalshi_avg_cost = p.get('avg_cost')
                if kalshi_avg_cost and kalshi_avg_cost > 0:
                    # Kalshi provides actual average fill price in cents
                    actual_entry_price = kalshi_avg_cost / 100
                    if meta and 'entry_price' in meta:
                        stored_price = meta['entry_price']
                        if abs(actual_entry_price - stored_price) > 0.01:  # Difference > 1 cent
                            logger.debug(f"Using Kalshi avg_cost ${actual_entry_price:.2f} instead of stored ${stored_price:.2f} for {ticker}")
                    entry_price = actual_entry_price
                else:
                    # Fallback to stored metadata, then entry_price_cache, then 0.50
                    entry_price = (meta['entry_price'] if meta and 'entry_price' in meta else None) \
                        or self._entry_price_cache.get(ticker) or 0.50

                new_positions.append({
                    'ticker': ticker,
                    'count': count,
                    'side': meta['side'] if meta else api_side,  # prefer stored meta; api_side as fallback
                    'entry_price': entry_price,  # Use actual Kalshi fill price
                    'entry_bid': meta.get('entry_bid') if meta else None,  # bid at fill time — preserved across syncs
                    'entry_time': meta.get('entry_time') if meta else None,  # preserved so 1s age guard works after sync
                    'peak_roi': meta.get('peak_roi', 0) if meta else 0,
                    # Stop-loss metadata
                    'symbol': meta.get('symbol') if meta else None,
                    'threshold': meta.get('threshold') if meta else None,
                    'market_type': meta.get('market_type') if meta else None,
                    'order_id': meta.get('order_id') if meta else None,
                    'close_time': meta.get('close_time') if meta else None,
                })

            if not self._initial_sync_done:
                self._initial_sync_done = True
                # On first sync after restart, mark any existing positions as already-known
                # so we don't spam resolution alerts for positions restored from state.
                for p in new_positions:
                    self._resolved_tickers.add(p['ticker'])
                logger.info("🔄 First sync after startup — skipping resolution notifications for restored positions")

            # Update snapshot with authoritative REST data for positions opened this session
            new_positions_by_ticker = {p['ticker']: p for p in new_positions}
            for ticker, snap in list(self._position_snapshot.items()):
                if ticker in new_positions_by_ticker:
                    # Merge REST data into snapshot (REST has authoritative count/entry_price)
                    rest_pos = new_positions_by_ticker[ticker]
                    self._position_snapshot[ticker].update({
                        'count': rest_pos.get('count', snap.get('count', 1)),
                        'entry_price': rest_pos.get('entry_price') or snap.get('entry_price', 0),
                        'close_time': rest_pos.get('close_time') or snap.get('close_time'),
                    })

            # Check if any tracked position's market window has closed.
            # PRIMARY: check positions still in API (normal path).
            # FALLBACK: check snapshotted positions that disappeared from API (Kalshi removes them fast).
            now_utc = datetime.now(timezone.utc)

            # Build combined set of positions to check for resolution
            positions_to_check = list(new_positions)
            for ticker, snap in self._position_snapshot.items():
                if ticker not in new_positions_by_ticker and ticker not in self._resolved_tickers:
                    # Position disappeared from API — check if market closed
                    close_time = snap.get('close_time')
                    if close_time:
                        if isinstance(close_time, str):
                            try:
                                close_time = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                            except Exception:
                                close_time = None
                        if close_time and now_utc >= close_time:
                            logger.info(f"🔍 Snapshotted position {ticker} gone from API, checking resolution...")
                            positions_to_check.append(snap)

            for pos in positions_to_check:
                ticker = pos['ticker']
                if ticker in self._resolved_tickers:
                    continue

                close_time = pos.get('close_time')
                if not close_time:
                    continue

                # Parse close_time if it's a string
                if isinstance(close_time, str):
                    try:
                        close_time = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                    except Exception:
                        continue

                # Only check markets that have closed (with 5s buffer for settlement lag)
                if now_utc < close_time:
                    continue

                try:
                    market = self.client.get_market(ticker)
                    if not market:
                        continue
                    result = market.get('result', '').lower()
                    status = market.get('status', '').lower()
                    if status not in ('finalized', 'settled', 'closed') or not result:
                        continue  # not settled yet

                    self._resolved_tickers.add(ticker)

                    side = pos.get('side', 'yes').lower()
                    entry_price = pos.get('entry_price', 0)
                    count = pos.get('count', 1)
                    won = (result == side)
                    exit_price = 1.00 if won else 0.00
                    pnl = (exit_price - entry_price) * count
                    roi_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    outcome_emoji = "✅" if won else "❌"
                    outcome_text = "WIN" if won else "LOSS"

                    logger.info(
                        f"{outcome_emoji} RESOLVED: {ticker} | {side.upper()} | "
                        f"Result: {result.upper()} | P&L: ${pnl:+.2f} ({roi_pct:+.1f}%)"
                    )

                    if self.telegram and self.telegram.enabled:
                        try:
                            symbol = pos.get('symbol', ticker.split('-')[0].replace('KX', '').replace('15M', ''))
                            balance = self.client.get_balance() or 0
                            self.telegram.send_message(
                                f"{outcome_emoji} <b>TRADE {outcome_text}</b>\n"
                                f"──────────────────\n"
                                f"<b>Asset:</b> {symbol} ({side.upper()})\n"
                                f"<b>Ticker:</b> <code>{ticker}</code>\n"
                                f"\n"
                                f"<b>Entry Price:</b> ${entry_price:.2f}\n"
                                f"<b>Result:</b> {result.upper()} → {'$1.00' if won else '$0.00'}\n"
                                f"<b>Contracts:</b> {count}\n"
                                f"\n"
                                f"<b>P&amp;L:</b> ${pnl:+.2f}\n"
                                f"<b>ROI:</b> {roi_pct:+.1f}%\n"
                                f"<b>New Balance:</b> ${balance:,.2f}\n"
                                f"\n"
                                f"⏰ <i>{datetime.now().strftime('%H:%M:%S ET')}</i>"
                            )
                        except Exception as e:
                            logger.error(f"Resolution Telegram error: {e}")
                except Exception as e:
                    logger.error(f"Error processing resolved position {ticker}: {e}")

            self.open_positions = new_positions
            logger.info(f"✅ Synced: {len(self.open_positions)} positions | Janitor run complete")
            self._sync_orderbook_subscriptions()

            # Log position details for transparency
            if self.open_positions:
                logger.debug(f"📊 Active positions:")
                for pos in self.open_positions:
                    ticker = pos.get('ticker', 'UNKNOWN')
                    side = pos.get('side', '?')
                    logger.debug(f"   • {ticker} ({side.upper()})")
        except Exception as e:
            logger.error(f"Position sync error: {e}")

    def manage_take_profit(self):
        """High-frequency check for ROI targets with Trailing logic."""
        if not self.config['strategy'].get('tp_enabled', True): return

        target_roi = self.config['strategy'].get('target_roi', 0.50)
        trail_pct = self.config['strategy'].get('tp_trail_percent', 0.05)

        for pos in self.open_positions:
            ticker = pos['ticker']
            # WS orderbook first (zero REST cost), fall back to REST
            if self.ws_feed and self.ws_feed.is_connected:
                ob = self.ws_feed.get_orderbook(ticker)
            else:
                ob = None
            if not ob:
                ob = self.client.get_orderbook(ticker)
            if not ob: continue

            # Get best bid (index 0 = highest price buyer willing to pay)
            bids = ob.get(pos['side'].lower(), [])
            if not bids: continue
            current_bid = bids[0][0] / 100  # best bid, not worst

            roi = (current_bid - pos['entry_price']) / pos['entry_price']

            logger.debug(
                f"📊 TP check {ticker} | side={pos['side']} "
                f"bid={current_bid:.4f} entry={pos['entry_price']:.4f} "
                f"ROI={roi:.1%} peak={pos.get('peak_roi', 0):.1%} target={target_roi:.0%}"
            )

            # Update Peak ROI for Trailing
            if roi > pos.get('peak_roi', 0):
                pos['peak_roi'] = roi
                logger.info(f"📈 {ticker} New Peak ROI: {roi:.1%}")

            # Exit Logic
            # Check peak_roi (not current roi) — once target was reached, trail from there.
            # Old bug: `if roi >= target_roi` meant TP could never fire once price dropped
            # below target, even with a huge drop from peak.
            if pos.get('peak_roi', 0) >= target_roi:
                drop_from_peak = pos['peak_roi'] - roi
                if drop_from_peak >= trail_pct:
                    peak_roi = pos['peak_roi']
                    logger.info(f"💰 TTP TRIGGERED: {ticker} (ROI: {roi:.1%}, Peak was: {peak_roi:.1%})")
                    pos['exit_reason'] = f"Trailing Take Profit (Peak: {peak_roi:.1%})"
                    # Accept 1 cent below current bid to absorb any movement between
                    # orderbook read and order submission (ensures IOC fills)
                    exit_price = max(round(current_bid - 0.01, 2), 0.01)
                    success = self.close_position(pos, exit_price=exit_price)

                    # Dedicated TP Telegram alert (separate from generic close notification)
                    if success and self.telegram and self.telegram.enabled:
                        try:
                            entry = pos.get('entry_price', 0)
                            count = pos.get('count', 1)
                            pnl = (exit_price - entry) * count
                            symbol = pos.get('symbol', ticker.split('-')[0])
                            self.telegram.send_message(
                                f"🎯 <b>TAKE PROFIT CLOSED</b>\n"
                                f"──────────────────\n"
                                f"<b>Asset:</b> {symbol} ({pos.get('side','').upper()})\n"
                                f"<b>Ticker:</b> <code>{ticker}</code>\n"
                                f"\n"
                                f"<b>Entry:</b> ${entry:.2f}\n"
                                f"<b>Exit:</b> ${exit_price:.2f}\n"
                                f"<b>Contracts:</b> {count}\n"
                                f"\n"
                                f"<b>Peak ROI:</b> {peak_roi:.1%}\n"
                                f"<b>Locked ROI:</b> {roi:.1%}\n"
                                f"<b>P&amp;L:</b> ${pnl:+.2f}\n"
                            )
                        except Exception as e:
                            logger.error(f"TP Telegram alert error: {e}")

    def manage_stop_loss(self):
        """
        ROI-based stop-loss: exit when position value drops max_loss_roi from entry.
        Uses the same orderbook path as manage_take_profit — WS-first, REST fallback.
        Works for all market types (above/below/up/down) and both sides.
        """
        if not self.config['strategy'].get('stop_loss_enabled', True):
            return

        max_loss_roi = self.config['strategy'].get('max_loss_roi', 0.30)  # exit at -30%

        for pos in self.open_positions:
            ticker = pos['ticker']
            # WS-first (zero REST cost), fall back to REST — same as TP
            if self.ws_feed and self.ws_feed.is_connected:
                ob = self.ws_feed.get_orderbook(ticker)
            else:
                ob = None
            if not ob:
                ob = self.client.get_orderbook(ticker)
            if not ob:
                continue

            bids = ob.get(pos['side'].lower(), [])
            if not bids:
                continue
            current_bid = bids[0][0] / 100

            # Use entry_bid (bid at fill time) as the SL reference when available.
            # This measures real market movement, not the structural spread gap.
            # Example: fill=$0.25, entry_bid=$0.16, current_bid=$0.16 → ROI=0% (no fire).
            # Without entry_bid: (0.16-0.25)/0.25 = -36% → false SL immediately after fill.
            # Fallback to entry_price for positions opened before this fix was deployed.
            #
            # OLD (spread-sensitive): roi = (current_bid - pos['entry_price']) / pos['entry_price']
            sl_reference = pos.get('entry_bid') or pos['entry_price']
            roi = (current_bid - sl_reference) / sl_reference

            logger.debug(
                f"🛡️ SL check {ticker} | side={pos['side']} "
                f"bid={current_bid:.4f} sl_ref={sl_reference:.4f} entry={pos['entry_price']:.4f} "
                f"ROI={roi:.1%} floor=-{max_loss_roi:.0%}"
            )

            if roi <= -max_loss_roi:
                logger.warning(f"🛑 STOP-LOSS TRIGGERED: {ticker} (ROI: {roi:.1%}, floor: -{max_loss_roi:.0%})")
                pos['exit_reason'] = f"Stop-Loss (ROI: {roi:.1%})"
                exit_price = max(round(current_bid - 0.01, 2), 0.01)
                success = self.close_position(pos, exit_price=exit_price)

                if success and self.telegram and self.telegram.enabled:
                    try:
                        entry = pos.get('entry_price', 0)
                        count = pos.get('count', 1)
                        pnl = (exit_price - entry) * count
                        symbol = pos.get('symbol', ticker.split('-')[0])
                        self.telegram.send_message(
                            f"🛑 <b>STOP-LOSS CLOSED</b>\n"
                            f"──────────────────\n"
                            f"<b>Asset:</b> {symbol} ({pos.get('side','').upper()})\n"
                            f"<b>Ticker:</b> <code>{ticker}</code>\n"
                            f"\n"
                            f"<b>Entry:</b> ${entry:.2f}\n"
                            f"<b>Exit:</b> ${exit_price:.2f}\n"
                            f"<b>ROI:</b> {roi:.1%}\n"
                            f"<b>Contracts:</b> {count}\n"
                            f"<b>P&amp;L:</b> ${pnl:+.2f}\n"
                        )
                    except Exception as e:
                        logger.error(f"SL Telegram alert error: {e}")

    def manage_exits(self):
        """
        Single-pass TP + SL: fetches orderbook ONCE per position then checks both.
        Called from the dedicated exit-watcher thread on every WS orderbook event.
        Uses REST for orderbook accuracy (not WS cache). Throttled to once per second
        to avoid rate-limiting — WS events may fire 5-10x/s during active markets.
        """
        tp_enabled   = self.config['strategy'].get('tp_enabled', True)
        sl_enabled   = self.config['strategy'].get('stop_loss_enabled', True)
        if not tp_enabled and not sl_enabled:
            return

        # Throttle: skip if last REST check was less than 1 second ago
        now = time.time()
        if now - getattr(self, '_last_exit_check', 0) < 1.0:
            return
        self._last_exit_check = now

        target_roi   = self.config['strategy'].get('target_roi', 0.50)
        trail_pct    = self.config['strategy'].get('tp_trail_percent', 0.05)
        max_loss_roi = self.config['strategy'].get('max_loss_roi', 0.30)

        for pos in list(self.open_positions):   # snapshot; close_position may mutate the list
            ticker = pos['ticker']

            # Always use REST for SL/TP decisions — accuracy over speed.
            # WS cache can be stale and trigger SL/TP on wrong prices.
            # Entry scanning still uses WS (speed matters there, not here).
            ob = self.client.get_orderbook(ticker)
            if not ob:
                continue

            bids = ob.get(pos['side'].lower(), [])
            if not bids:
                continue
            current_bid = bids[0][0] / 100

            entry_price = pos.get('entry_price', 0)
            if entry_price <= 0:
                continue

            # Skip TP/SL for the first 1s after fill — allows sync_with_exchange to
            # correct entry_price from Kalshi's avg_cost before we evaluate gain/loss.
            # Without this, a wrong (understated) entry_price can make ROI look like
            # +50% or -35% immediately, triggering TP or SL on a fresh position.
            age = time.time() - (pos.get('entry_time') or 0)
            if age < 1.0:
                continue

            # Use entry_bid as SL/TP reference when available (avoids instant exit from wide spreads).
            # entry_bid = live bid at fill time; entry_price = what we paid (may include sweep premium).
            sl_reference = pos.get('entry_bid') or entry_price
            roi = (current_bid - sl_reference) / sl_reference

            logger.debug(
                f"📊 Exit check {ticker} | side={pos['side']} "
                f"bid={current_bid:.4f} sl_ref={sl_reference:.4f} entry={entry_price:.4f} "
                f"ROI={roi:.1%} peak={pos.get('peak_roi', 0):.1%}"
            )

            # --- Trailing Take Profit ---
            if tp_enabled:
                if roi > pos.get('peak_roi', 0):
                    pos['peak_roi'] = roi
                    logger.info(f"📈 {ticker} New Peak ROI: {roi:.1%}")

                if pos.get('peak_roi', 0) >= target_roi:
                    drop_from_peak = pos['peak_roi'] - roi
                    if drop_from_peak >= trail_pct:
                        peak_roi = pos['peak_roi']
                        logger.info(f"💰 TTP TRIGGERED: {ticker} (ROI: {roi:.1%}, Peak: {peak_roi:.1%})")
                        pos['exit_reason'] = f"Trailing Take Profit (Peak: {peak_roi:.1%})"
                        exit_price = max(round(current_bid - 0.01, 2), 0.01)
                        success = self.close_position(pos, exit_price=exit_price)
                        if success and self.telegram and self.telegram.enabled:
                            try:
                                count  = pos.get('count', 1)
                                actual_exit = pos.get('actual_exit_price', exit_price)
                                pnl    = (actual_exit - entry_price) * count
                                symbol = pos.get('symbol', ticker.split('-')[0])
                                balance = self.client.get_balance()
                                balance_str = f"\n<b>Balance:</b> ${balance:.2f}" if balance else ""
                                self.telegram.send_message(
                                    f"💰 <b>TAKE PROFIT CLOSED</b>\n"
                                    f"──────────────────\n"
                                    f"<b>Asset:</b> {symbol} ({pos.get('side','').upper()})\n"
                                    f"<b>Ticker:</b> <code>{ticker}</code>\n\n"
                                    f"<b>Entry:</b> ${entry_price:.2f}\n"
                                    f"<b>Exit:</b> ${actual_exit:.2f}\n"
                                    f"<b>Peak ROI:</b> {peak_roi:.1%}\n"
                                    f"<b>Contracts:</b> {count}\n"
                                    f"<b>P&amp;L:</b> ${pnl:+.2f}"
                                    f"{balance_str}\n"
                                )
                            except Exception as e:
                                logger.error(f"TP Telegram alert error: {e}")
                        continue  # position handled; skip SL check this cycle

            # --- Stop Loss ---
            if sl_enabled:
                if roi <= -max_loss_roi:
                    logger.warning(f"🛑 STOP-LOSS TRIGGERED: {ticker} (ROI: {roi:.1%})")
                    pos['exit_reason'] = f"Stop-Loss (ROI: {roi:.1%})"
                    # Lock ticker until well after market close to prevent re-entry after SL.
                    # Store absolute expiry timestamp (avoids ET/UTC confusion from ticker parsing).
                    # 25 minutes covers any remaining time in a 15-min market plus buffer.
                    sl_lock_expiry = time.time() + 25 * 60
                    self.sl_fired_tickers[ticker] = sl_lock_expiry
                    logger.info(f"🔒 SL lock set for {ticker} for 25 minutes")
                    exit_price = max(round(current_bid - 0.01, 2), 0.01)
                    success = self.close_position(pos, exit_price=exit_price)
                    if success and self.telegram and self.telegram.enabled:
                        try:
                            count  = pos.get('count', 1)
                            # Use actual fill price if available (set by close_position), else orderbook price
                            actual_exit = pos.get('actual_exit_price', exit_price)
                            pnl    = (actual_exit - entry_price) * count
                            actual_roi = (actual_exit - sl_reference) / sl_reference if sl_reference > 0 else roi
                            symbol = pos.get('symbol', ticker.split('-')[0])
                            balance = self.client.get_balance()
                            balance_str = f"\n<b>Balance:</b> ${balance:.2f}" if balance else ""
                            self.telegram.send_message(
                                f"🛑 <b>STOP-LOSS CLOSED</b>\n"
                                f"──────────────────\n"
                                f"<b>Asset:</b> {symbol} ({pos.get('side','').upper()})\n"
                                f"<b>Ticker:</b> <code>{ticker}</code>\n\n"
                                f"<b>Entry:</b> ${entry_price:.2f}\n"
                                f"<b>Exit:</b> ${actual_exit:.2f}\n"
                                f"<b>ROI:</b> {actual_roi:.1%}\n"
                                f"<b>Contracts:</b> {count}\n"
                                f"<b>P&amp;L:</b> ${pnl:+.2f}"
                                f"{balance_str}\n"
                            )
                        except Exception as e:
                            logger.error(f"SL Telegram alert error: {e}")

    def _parse_close_time(self, ticker: str) -> Optional[datetime]:
        """Parse market close time from ticker, e.g. KXSOL15M-26MAR071745-45 → 2026-03-07 17:45 UTC"""
        try:
            parts = ticker.split('-')
            if len(parts) < 2:
                return None
            m = re.match(r'^(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})$', parts[1])
            if not m:
                return None
            yy, mon, dd, hh, mm = m.groups()
            return datetime.strptime(f"20{yy} {mon} {dd} {hh}:{mm}", "%Y %b %d %H:%M").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _extract_symbol_from_ticker(self, ticker: str) -> Optional[str]:
        """Extract symbol (BTC, ETH, SOL, XRP) from ticker"""
        if 'BTC' in ticker.upper():
            return 'BTC'
        elif 'ETH' in ticker.upper():
            return 'ETH'
        elif 'SOL' in ticker.upper():
            return 'SOL'
        elif 'XRP' in ticker.upper():
            return 'XRP'
        return None

    def _extract_threshold_from_ticker(self, ticker: str) -> Optional[float]:
        """Extract threshold from ticker (e.g., KXBTC15M-05FEB-1430-A95000 → 95000)"""
        import re
        # Look for pattern like A95000 or B95000 (Above/Below)
        match = re.search(r'[AB](\d+)', ticker)
        if match:
            return float(match.group(1))
        return None

    def _extract_market_type_from_ticker(self, ticker: str) -> Optional[str]:
        """Extract market type from ticker (A=above, B=below)"""
        if '-A' in ticker or 'ABOVE' in ticker.upper():
            return 'above'
        elif '-B' in ticker or 'BELOW' in ticker.upper():
            return 'below'
        elif '-U' in ticker or 'UP' in ticker.upper():
            return 'up'
        elif '-D' in ticker or 'DOWN' in ticker.upper():
            return 'down'
        return None

    def close_position(self, position, exit_price):
        """Exits position using an IOC limit sell order."""
        ticker = position['ticker']
        try:
            side = position['side'].lower()
            price_cents = int(exit_price * 100)
            logger.info(f"🔄 EXITING {ticker} at ${exit_price:.2f} (IOC limit sell)")

            # Build price kwarg — yes_price for YES side, no_price for NO side
            price_kwarg = {'yes_price': price_cents} if side == 'yes' else {'no_price': price_cents}

            # Create IOC limit sell order (action="sell" — fixes hardcoded "buy" bug)
            exit_order = self.client.create_order(
                ticker=ticker,
                side=side,
                quantity=position['count'],
                order_type="limit",
                action="sell",
                time_in_force="immediate_or_cancel",
                **price_kwarg
            )

            # Unwrap {"order": {"order_id": ...}} — same structure as entry order response
            if exit_order:
                exit_order_data = exit_order.get('order', exit_order)
            else:
                exit_order_data = {}

            if not exit_order_data or 'order_id' not in exit_order_data:
                logger.error(f"⚠️ Exit response missing order_id, verifying...")

                # Wait for order to process
                time.sleep(2)

                # Verify position actually closed
                positions = self.client.get_positions()
                still_exists = any(p.get('ticker') == ticker for p in positions)

                if not still_exists:
                    logger.info(f"✅ Position {ticker} confirmed closed despite response error")
                    # Remove from tracking
                    self.open_positions = [p for p in self.open_positions if p.get('ticker') != ticker]
                    return True
                else:
                    logger.error(f"❌ Position {ticker} still exists - exit truly failed")
                    return False

            order_id = exit_order_data['order_id']

            # Verify fill — WS-first, REST fallback
            fill_confirmed = False
            actual_exit_price = None

            ws_event, ws_msg = self._wait_for_ws_fill(order_id, timeout=1.5)
            if ws_event == 'filled':
                logger.info(f"⚡ WS: Exit confirmed for {ticker}")
                fill_confirmed = True
                actual_exit_price = self._get_actual_fill_price(order_id, ticker, 'sell')
                if actual_exit_price:
                    logger.info(f"📊 Actual exit fill: ${actual_exit_price:.2f} (orderbook was ${exit_price:.2f})")
            elif ws_event == 'canceled':
                logger.warning(f"⚠️ Exit order cancelled (WS): {ticker}")
            else:
                # WS timed out — REST fallback
                rest_attempts = 3 if (self.ws_feed and self.ws_feed.is_connected) else 5
                for attempt in range(rest_attempts):
                    time.sleep(0.3)
                    order_status = self.client.get_order(order_id)
                    if order_status:
                        status = order_status.get('status')
                        if status == 'executed':
                            logger.info(f"✅ Exit confirmed for {ticker}")
                            fill_confirmed = True
                            actual_exit_price = self._get_actual_fill_price(order_id, ticker, 'sell')
                            if actual_exit_price:
                                logger.info(f"📊 Actual exit fill: ${actual_exit_price:.2f} (orderbook was ${exit_price:.2f})")
                            break
                        elif status == 'canceled':
                            logger.warning(f"⚠️ Exit order cancelled: {ticker}")
                            break

            # Final verification — skip REST round-trip if WS already confirmed fill
            if fill_confirmed:
                still_exists = False  # trust WS event; sync_with_exchange will reconcile
            else:
                time.sleep(0.5)
                positions = self.client.get_positions()
                still_exists = any(p.get('ticker') == ticker for p in positions)

            if still_exists:
                logger.error(f"⚠️ Position {ticker} still exists after exit order!")
                # Don't remove from tracking yet
                return False

            # Use actual exit price if available, otherwise fall back to orderbook price
            final_exit_price = actual_exit_price if actual_exit_price else exit_price

            # Store actual fill price on position so caller (manage_exits) can reference it in Telegram
            position['actual_exit_price'] = final_exit_price

            # Calculate P&L with actual prices
            entry_price = position.get('entry_price', 0)
            if entry_price > 0:
                pnl_pct = ((final_exit_price - entry_price) / entry_price) * 100
                roi = pnl_pct  # Simplified ROI calculation

                # Log the close with P&L
                logger.info(f"💰 POSITION CLOSED: {ticker} | "
                           f"Entry: {entry_price:.0%} → Exit: {final_exit_price:.0%} | "
                           f"P&L: {pnl_pct:+.1f}% | ROI: {roi:+.1f}%")

                # NOTE: Telegram notification is sent by the CALLER (manage_exits TP/SL blocks),
                # not here, to avoid duplicate notifications and allow caller to show actual fill price.

            # Archive to state manager for historical tracking
            if self.state_manager:
                self.state_manager.remove_position(
                    ticker=ticker,
                    exit_price=exit_price,
                    exit_reason=position.get('exit_reason', 'manual_close')
                )

            self.sync_with_exchange(force_rest=True)
            return True
        except Exception as e:
            logger.error(f"❌ Exit error: {e}")
            return False

    def _get_actual_fill_price(self, order_id: str, ticker: str, action: str) -> Optional[float]:
        """
        Fetch actual fill price from Kalshi fills API.

        Args:
            order_id: Order ID to look up
            ticker: Market ticker
            action: 'buy' or 'sell'

        Returns:
            Average fill price in dollars, or None if not found
        """
        try:
            # Get recent fills for this order
            fills = self.client.get_fills(order_id=order_id, ticker=ticker, limit=50)

            if not fills:
                logger.warning(f"⚠️ No fills found for order {order_id}")
                return None

            # Filter fills for this specific order_id AND action.
            # The Kalshi fills API may return all fills for the ticker (other traders included)
            # even when order_id is passed — always filter client-side to avoid averaging
            # in unrelated fills (e.g. other traders' YES sells at 85¢ near expiry).
            relevant_fills = [
                f for f in fills
                if f.get('order_id') == order_id
                and f.get('action', '').lower() == action.lower()
            ]

            if not relevant_fills:
                logger.warning(f"⚠️ No {action} fills found for order {order_id}")
                return None

            # Calculate weighted average fill price.
            # 'price' field = YES price in 0-1 decimal — wrong for NO positions.
            # Use yes_price/no_price (cents) based on the fill's side instead.
            total_contracts = sum(f.get('count', 0) for f in relevant_fills)

            def _fill_price_cents(f: dict) -> float:
                side = f.get('side', 'yes').lower()
                if side == 'no':
                    return f.get('no_price', 0)
                return f.get('yes_price', 0)

            weighted_sum = sum(f.get('count', 0) * _fill_price_cents(f) for f in relevant_fills)

            if total_contracts == 0:
                return None

            avg_price_dollars = (weighted_sum / total_contracts) / 100

            logger.debug(f"Calculated avg fill price from {len(relevant_fills)} fills: ${avg_price_dollars:.2f}")
            return avg_price_dollars

        except Exception as e:
            logger.error(f"Error fetching fill price: {e}")
            return None

    # ------------------------------------------------------------------
    # WS helpers
    # ------------------------------------------------------------------

    def _wait_for_ws_fill(self, order_id: str, timeout: float = 2.0):
        """
        Wait for a WS fill or cancel event for a specific order.
        Watches both fill_queue and order_queue concurrently.
        Non-matching messages are requeued so nothing is lost.

        Returns:
            ('filled',   msg_dict)  — order filled
            ('canceled', msg_dict)  — order canceled with no fill
            (None,       None)      — WS not connected or timed out
        """
        if not self.ws_feed or not self.ws_feed.is_connected:
            return (None, None)

        deadline = time.time() + timeout
        fill_requeue = []
        order_requeue = []

        try:
            while time.time() < deadline:
                # Check fill queue
                try:
                    msg = self.ws_feed.fill_queue.get_nowait()
                    if msg.get('order_id') == order_id:
                        return ('filled', msg)
                    fill_requeue.append(msg)
                except queue.Empty:
                    pass

                # Check order queue for cancellations
                try:
                    msg = self.ws_feed.order_queue.get_nowait()
                    if msg.get('order_id') == order_id:
                        if msg.get('status') in ('canceled', 'cancelled'):
                            filled = msg.get('filled_count', msg.get('count', 0))
                            if not filled:
                                return ('canceled', msg)
                            # Partial fill then cancel — treat as filled
                            return ('filled', msg)
                    order_requeue.append(msg)
                except queue.Empty:
                    pass

                time.sleep(0.05)

            return (None, None)
        finally:
            for m in fill_requeue:
                self.ws_feed.fill_queue.put(m)
            for m in order_requeue:
                self.ws_feed.order_queue.put(m)

    def _sync_orderbook_subscriptions(self):
        """
        Keep WS orderbook subscriptions in sync with open positions.
        Called at end of sync_with_exchange() after open_positions is updated.
        Subscribe to tickers we now hold; unsubscribe from tickers we closed.
        """
        if not self.ws_feed or not self.ws_feed.is_connected:
            return
        current = {p['ticker'] for p in self.open_positions}
        subscribed = self.ws_feed._subscribed_orderbooks.copy()
        for ticker in current - subscribed:
            self.ws_feed.subscribe_orderbook(ticker)
            logger.debug(f"⚡ WS orderbook: subscribed {ticker}")
        for ticker in subscribed - current:
            self.ws_feed.unsubscribe_orderbook(ticker)
            logger.debug(f"⚡ WS orderbook: unsubscribed {ticker}")

    # --- KEEPING YOUR ORIGINAL UTILITIES ---
    def check_for_fills(self):
        if not self.pending_orders: return

        # Fast path: drain WS fill events (eliminates 30s+ REST lag)
        if self.ws_feed and self.ws_feed.is_connected:
            while True:
                try:
                    msg = self.ws_feed.fill_queue.get_nowait()
                    oid = msg.get('order_id')
                    if oid and oid in self.pending_orders:
                        opp = self.pending_orders.pop(oid)
                        logger.info(f"⚡ WS FILL: {opp['ticker']} @ {opp.get('entry_price')}")
                        if self.telegram:
                            self.telegram.send_message(f"🔔 **FILL CONFIRMED**\nTicker: {opp['ticker']}")
                except queue.Empty:
                    break
            return  # Skip REST poll while WS is connected

        # REST fallback (WS unavailable or not enabled)
        try:
            fills_resp = self.client._make_request("GET", "/portfolio/fills")
            if not fills_resp or 'fills' not in fills_resp: return
            fill_ids = {f.get('order_id') for f in fills_resp.get('fills', [])}
            for oid in list(self.pending_orders.keys()):
                if oid in fill_ids:
                    opp = self.pending_orders.pop(oid)
                    order_side = opp.get('side', 'UNKNOWN')
                    order_price = opp.get('entry_price', 'N/A')
                    logger.info(f"🎯 FILL CONFIRMED (async): {opp['ticker']} | "
                               f"{order_side.upper()} @ {order_price}")
                    if self.telegram:
                        self.telegram.send_message(f"🔔 **FILL CONFIRMED**\nTicker: {opp['ticker']}")
        except Exception as e: logger.error(f"Fill check error: {e}")

    def cancel_stale_orders(self):
        try:
            open_orders = self.client.get_orders(status="resting")
            if not open_orders: return
            now = datetime.now(timezone.utc)
            for order in open_orders:
                oid, ts_str = order.get('order_id'), order.get('created_time')
                if not ts_str: continue
                clean_ts = re.sub(r'(\.\d{6})\d+', r'\1', ts_str.replace('Z', '+00:00'))
                try: created_at = datetime.fromisoformat(clean_ts)
                except: created_at = datetime.fromisoformat(clean_ts.split('.')[0] + '+00:00')
                if (now - created_at).total_seconds() > self.expiry_seconds:
                    if self.client.cancel_order(oid):
                        self.pending_orders.pop(oid, None)
                        logger.info(f"🧹 JANITOR: Canceled {oid}")
        except Exception as e: logger.error(f"Janitor error: {e}")

    def cleanup_phantom_pending_orders(self):
        """
        Remove pending orders that don't exist on Kalshi.
        Fixes phantom orders from failed/rejected trades.
        WS order events are drained first for instant cancellation detection;
        REST cleanup still runs afterwards as belt-and-suspenders.
        """
        if not self.pending_orders:
            return 0

        # Pre-drain WS order events (instant cancellation detection)
        if self.ws_feed and self.ws_feed.is_connected:
            while True:
                try:
                    msg = self.ws_feed.order_queue.get_nowait()
                    oid = msg.get('order_id')
                    if oid and msg.get('status') in ('canceled', 'cancelled') and oid in self.pending_orders:
                        self.pending_orders.pop(oid, None)
                        ticker = msg.get('ticker', '?')
                        logger.info(f"⚡ WS CANCEL: {ticker} ({oid[:8]}...)")
                except queue.Empty:
                    break

        try:
            # Get all order IDs from Kalshi (check multiple statuses)
            kalshi_order_ids = set()

            for status in ["resting", "filled"]:
                orders = self.client.get_orders(status=status)
                if orders:
                    kalshi_order_ids.update(o.get('order_id') for o in orders if o.get('order_id'))

            # Find phantom orders (in pending_orders but not on Kalshi)
            phantom_orders = []
            for oid in list(self.pending_orders.keys()):
                if oid not in kalshi_order_ids:
                    ticker = self.pending_orders[oid].get('ticker', 'UNKNOWN')
                    phantom_orders.append((oid, ticker))
                    self.pending_orders.pop(oid, None)

            if phantom_orders:
                logger.warning(f"🧹 JANITOR: Removed {len(phantom_orders)} phantom pending orders")
                for oid, ticker in phantom_orders:
                    logger.debug(f"   • {ticker} (order_id: {oid[:8]}...)")

            return len(phantom_orders)

        except Exception as e:
            logger.error(f"Phantom cleanup error: {e}")
            return 0
