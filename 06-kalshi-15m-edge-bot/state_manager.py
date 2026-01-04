"""
Persistent State Management
Saves critical bot state to disk to survive crashes and restarts
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent bot state across restarts"""

    def __init__(self, state_dir: str = "data"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True, parents=True)

        self.state_file = self.state_dir / "bot_state.json"
        self.backup_file = self.state_dir / "bot_state_backup.json"

        self.state_lock = Lock()
        self.state = self._load_state()

        logger.info(f"✅ State manager initialized (file: {self.state_file})")

    def _load_state(self) -> Dict:
        """Load state from disk, or initialize if not exists"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"📂 Loaded state: {len(state.get('positions', {}))} positions, "
                               f"peak=${state.get('peak_balance', 0):.2f}")
                    return state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                # Try backup
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, 'r') as f:
                            state = json.load(f)
                            logger.warning("⚠️ Loaded from backup state file")
                            return state
                    except Exception as e2:
                        logger.error(f"Backup also failed: {e2}")

        # Initialize new state
        return {
            'positions': {},
            'closed_positions': [],
            'peak_balance': 0,
            'trades_today': 0,
            'trades_total': 0,
            'last_scan_time': None,
            'bot_started_at': datetime.now(timezone.utc).isoformat(),
            'last_saved_at': None
        }

    def _save_state(self):
        """Save state to disk with backup"""
        try:
            with self.state_lock:
                # Create backup of current state
                if self.state_file.exists():
                    import shutil
                    shutil.copy2(self.state_file, self.backup_file)

                # Save new state
                self.state['last_saved_at'] = datetime.now(timezone.utc).isoformat()

                with open(self.state_file, 'w') as f:
                    json.dump(self.state, f, indent=2)

                logger.debug("💾 State saved to disk")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    # === POSITION MANAGEMENT ===

    def save_position(self, position: Dict):
        """Save open position to state"""
        with self.state_lock:
            ticker = position.get('ticker')
            if not ticker:
                return

            self.state['positions'][ticker] = {
                **position,
                'saved_at': datetime.now(timezone.utc).isoformat()
            }

        self._save_state()
        logger.debug(f"💾 Saved position: {ticker}")

    def remove_position(self, ticker: str, exit_price: Optional[float] = None,
                       exit_reason: Optional[str] = None):
        """Remove position and archive to closed_positions"""
        with self.state_lock:
            if ticker in self.state['positions']:
                position = self.state['positions'].pop(ticker)

                # Archive to closed positions
                closed_position = {
                    **position,
                    'closed_at': datetime.now(timezone.utc).isoformat(),
                    'exit_price': exit_price,
                    'exit_reason': exit_reason
                }

                # Calculate P&L if we have exit price
                if exit_price and position.get('entry_price'):
                    pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
                    closed_position['pnl_pct'] = pnl_pct

                self.state['closed_positions'].append(closed_position)

                # Keep only last 100 closed positions
                if len(self.state['closed_positions']) > 100:
                    self.state['closed_positions'] = self.state['closed_positions'][-100:]

                self.state['trades_total'] += 1

        self._save_state()
        logger.debug(f"💾 Archived position: {ticker}")

    def get_positions(self) -> Dict[str, Dict]:
        """Get all open positions"""
        with self.state_lock:
            return dict(self.state['positions'])

    def get_closed_positions(self, limit: int = 20) -> List[Dict]:
        """Get recent closed positions"""
        with self.state_lock:
            return list(self.state['closed_positions'][-limit:])

    # === BALANCE TRACKING ===

    def update_peak_balance(self, balance: float):
        """Update peak balance if new high"""
        with self.state_lock:
            if balance > self.state.get('peak_balance', 0):
                old_peak = self.state.get('peak_balance', 0)
                self.state['peak_balance'] = balance
                logger.info(f"🎉 New peak balance: ${balance:.2f} (was ${old_peak:.2f})")
        self._save_state()

    def get_peak_balance(self) -> float:
        """Get peak balance"""
        with self.state_lock:
            return self.state.get('peak_balance', 0)

    # === TRADING METRICS ===

    def increment_trades_today(self):
        """Increment today's trade count"""
        with self.state_lock:
            self.state['trades_today'] = self.state.get('trades_today', 0) + 1
        self._save_state()

    def reset_daily_stats(self):
        """Reset daily statistics (call at midnight)"""
        with self.state_lock:
            self.state['trades_today'] = 0
        self._save_state()
        logger.info("🔄 Daily stats reset")

    def get_stats(self) -> Dict:
        """Get current statistics"""
        with self.state_lock:
            return {
                'trades_today': self.state.get('trades_today', 0),
                'trades_total': self.state.get('trades_total', 0),
                'open_positions': len(self.state.get('positions', {})),
                'peak_balance': self.state.get('peak_balance', 0),
                'bot_uptime': self._calculate_uptime()
            }

    def _calculate_uptime(self) -> str:
        """Calculate bot uptime"""
        started_at = self.state.get('bot_started_at')
        if not started_at:
            return "Unknown"

        try:
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - start

            hours = delta.total_seconds() / 3600
            if hours < 1:
                return f"{delta.total_seconds() / 60:.0f}m"
            elif hours < 24:
                return f"{hours:.1f}h"
            else:
                days = delta.days
                return f"{days}d {hours % 24:.0f}h"
        except:
            return "Unknown"

    # === METADATA ===

    def update_last_scan_time(self):
        """Update last scan timestamp"""
        with self.state_lock:
            self.state['last_scan_time'] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def get_last_scan_time(self) -> Optional[str]:
        """Get last scan timestamp"""
        with self.state_lock:
            return self.state.get('last_scan_time')

    # === RECOVERY ===

    def restore_positions_to_manager(self, position_manager):
        """Restore positions from state to position manager"""
        positions = self.get_positions()

        if not positions:
            logger.info("No positions to restore")
            return

        logger.info(f"🔄 Restoring {len(positions)} positions from disk...")

        restored = []
        for ticker, pos_data in positions.items():
            # Convert state format to position manager format
            position = {
                'ticker': pos_data.get('ticker'),
                'side': pos_data.get('side', 'yes'),
                'entry_price': pos_data.get('entry_price', 0),
                'count': pos_data.get('count', 0),
                'peak_roi': pos_data.get('peak_roi', 0),
                'symbol': pos_data.get('symbol'),
                'threshold': pos_data.get('threshold'),
                'market_type': pos_data.get('market_type')
            }
            restored.append(position)

        position_manager.open_positions = restored
        logger.info(f"✅ Restored {len(restored)} positions")

    # === EXPORT ===

    def export_to_csv(self, output_file: str = "data/trade_history.csv"):
        """Export closed positions to CSV"""
        import csv

        closed = self.get_closed_positions(limit=1000)
        if not closed:
            logger.warning("No closed positions to export")
            return

        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True, parents=True)

        with open(output_path, 'w', newline='') as f:
            fieldnames = [
                'ticker', 'symbol', 'side', 'entry_price', 'exit_price',
                'pnl_pct', 'entry_time', 'closed_at', 'exit_reason'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')

            writer.writeheader()
            for pos in closed:
                writer.writerow({
                    'ticker': pos.get('ticker', ''),
                    'symbol': pos.get('symbol', ''),
                    'side': pos.get('side', ''),
                    'entry_price': pos.get('entry_price', 0),
                    'exit_price': pos.get('exit_price', 0),
                    'pnl_pct': pos.get('pnl_pct', 0),
                    'entry_time': pos.get('saved_at', ''),
                    'closed_at': pos.get('closed_at', ''),
                    'exit_reason': pos.get('exit_reason', '')
                })

        logger.info(f"📊 Exported {len(closed)} trades to {output_path}")
