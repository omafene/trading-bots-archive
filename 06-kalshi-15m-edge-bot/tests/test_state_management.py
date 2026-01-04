"""
Tests for Persistent State Management
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from state_manager import StateManager


@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def state_manager(temp_state_dir):
    """Create state manager with temp directory"""
    return StateManager(state_dir=temp_state_dir)


class TestStateInitialization:
    """Test state initialization and loading"""

    def test_creates_new_state_if_none_exists(self, state_manager):
        """Verify new state created if file doesn't exist"""
        assert state_manager.state is not None
        assert 'positions' in state_manager.state
        assert 'peak_balance' in state_manager.state

    def test_loads_existing_state(self, temp_state_dir):
        """Verify loads existing state from disk"""
        # Create existing state
        state_file = Path(temp_state_dir) / "bot_state.json"
        existing_state = {
            'positions': {'TEST1': {'ticker': 'TEST1'}},
            'peak_balance': 600,
            'trades_total': 50
        }

        with open(state_file, 'w') as f:
            json.dump(existing_state, f)

        # Load it
        sm = StateManager(state_dir=temp_state_dir)

        assert sm.state['peak_balance'] == 600
        assert sm.state['trades_total'] == 50
        assert 'TEST1' in sm.state['positions']

    def test_falls_back_to_backup_on_corrupt_main(self, temp_state_dir):
        """Verify loads backup if main state is corrupted"""
        state_file = Path(temp_state_dir) / "bot_state.json"
        backup_file = Path(temp_state_dir) / "bot_state_backup.json"

        # Corrupt main state
        with open(state_file, 'w') as f:
            f.write("{ invalid json")

        # Valid backup
        with open(backup_file, 'w') as f:
            json.dump({'peak_balance': 500, 'positions': {}}, f)

        # Should load backup
        sm = StateManager(state_dir=temp_state_dir)
        assert sm.state['peak_balance'] == 500


class TestPositionManagement:
    """Test position saving and loading"""

    def test_save_position(self, state_manager):
        """Verify position saved to state"""
        position = {
            'ticker': 'KXBTC15M-TEST',
            'side': 'yes',
            'entry_price': 0.40,
            'symbol': 'BTC'
        }

        state_manager.save_position(position)

        # Check saved to state
        assert 'KXBTC15M-TEST' in state_manager.state['positions']
        saved = state_manager.state['positions']['KXBTC15M-TEST']
        assert saved['side'] == 'yes'
        assert saved['entry_price'] == 0.40

    def test_remove_position_archives_it(self, state_manager):
        """Verify removed position archived to closed_positions"""
        position = {
            'ticker': 'TEST1',
            'side': 'yes',
            'entry_price': 0.40
        }

        state_manager.save_position(position)
        state_manager.remove_position('TEST1', exit_price=0.60, exit_reason='take_profit')

        # Should be removed from open positions
        assert 'TEST1' not in state_manager.state['positions']

        # Should be in closed positions
        closed = state_manager.state['closed_positions']
        assert len(closed) > 0
        assert closed[-1]['ticker'] == 'TEST1'
        assert closed[-1]['exit_reason'] == 'take_profit'

    def test_calculates_pnl_on_close(self, state_manager):
        """Verify P&L calculated when position closed"""
        position = {
            'ticker': 'TEST1',
            'entry_price': 0.40
        }

        state_manager.save_position(position)
        state_manager.remove_position('TEST1', exit_price=0.60)

        closed = state_manager.state['closed_positions'][-1]
        assert 'pnl_pct' in closed
        # (0.60 - 0.40) / 0.40 * 100 = 50%
        assert abs(closed['pnl_pct'] - 50.0) < 0.1

    def test_limits_closed_positions_to_100(self, state_manager):
        """Verify only keeps last 100 closed positions"""
        # Add 150 positions
        for i in range(150):
            pos = {'ticker': f'TEST{i}', 'entry_price': 0.40}
            state_manager.save_position(pos)
            state_manager.remove_position(f'TEST{i}', exit_price=0.50)

        # Should only keep 100
        assert len(state_manager.state['closed_positions']) == 100


class TestBalanceTracking:
    """Test peak balance tracking"""

    def test_updates_peak_on_new_high(self, state_manager):
        """Verify peak updates on new balance high"""
        state_manager.update_peak_balance(500)
        assert state_manager.get_peak_balance() == 500

        state_manager.update_peak_balance(550)
        assert state_manager.get_peak_balance() == 550

    def test_does_not_update_peak_on_lower_balance(self, state_manager):
        """Verify peak doesn't update when balance drops"""
        state_manager.update_peak_balance(500)
        state_manager.update_peak_balance(450)

        # Peak should still be 500
        assert state_manager.get_peak_balance() == 500


class TestStatistics:
    """Test trading statistics"""

    def test_increments_trades_today(self, state_manager):
        """Verify trade counter increments"""
        initial = state_manager.state.get('trades_today', 0)

        state_manager.increment_trades_today()
        assert state_manager.state['trades_today'] == initial + 1

        state_manager.increment_trades_today()
        assert state_manager.state['trades_today'] == initial + 2

    def test_reset_daily_stats(self, state_manager):
        """Verify daily stats reset correctly"""
        state_manager.state['trades_today'] = 50
        state_manager.reset_daily_stats()

        assert state_manager.state['trades_today'] == 0

    def test_get_stats_returns_correct_data(self, state_manager):
        """Verify get_stats returns expected data"""
        state_manager.state['trades_today'] = 10
        state_manager.state['trades_total'] = 100
        state_manager.update_peak_balance(500)

        stats = state_manager.get_stats()

        assert stats['trades_today'] == 10
        assert stats['trades_total'] == 100
        assert stats['peak_balance'] == 500
        assert 'bot_uptime' in stats


class TestPersistence:
    """Test state persistence to disk"""

    def test_state_persists_across_instances(self, temp_state_dir):
        """Verify state survives across state manager instances"""
        # Create first instance and save data
        sm1 = StateManager(state_dir=temp_state_dir)
        sm1.save_position({'ticker': 'TEST1', 'side': 'yes'})
        sm1.update_peak_balance(600)

        # Create second instance (simulates restart)
        sm2 = StateManager(state_dir=temp_state_dir)

        # Should load same data
        assert 'TEST1' in sm2.state['positions']
        assert sm2.get_peak_balance() == 600

    def test_backup_created_on_save(self, temp_state_dir):
        """Verify backup file created"""
        sm = StateManager(state_dir=temp_state_dir)
        sm.save_position({'ticker': 'TEST1'})

        # Force another save to create backup
        sm.save_position({'ticker': 'TEST2'})

        backup_file = Path(temp_state_dir) / "bot_state_backup.json"
        assert backup_file.exists()


# Run tests with: pytest tests/test_state_management.py -v
