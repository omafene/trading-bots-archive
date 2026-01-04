"""
Tests for Risk Management: Kelly sizing, stop-loss, circuit breaker
"""

import pytest
from risk_manager import RiskManager


@pytest.fixture
def risk_config():
    """Standard risk configuration for tests"""
    return {
        'capital': {
            'total_capital': 500
        },
        'strategy': {
            'max_position_percent': 0.10,
            'max_concurrent_trades': 4,
            'stop_loss_enabled': True,
            'stop_loss_pct': 0.05
        },
        'risk': {
            'kelly_multiplier': 0.25,
            'min_position_size': 1.0,
            'circuit_breaker_enabled': True,
            'max_drawdown_pct': 0.15,
            'max_per_category': 1.0,
            'ticker_must_contain': [],
            'blacklist_categories': [],
            'stop_loss_enabled': True,
            'stop_loss_pct': 0.05
        }
    }


@pytest.fixture
def risk_manager(risk_config):
    """Create risk manager instance"""
    return RiskManager(risk_config, telegram_notifier=None)


class TestKellySizing:
    """Test Kelly Criterion position sizing"""

    def test_kelly_basic_calculation(self, risk_manager):
        """Verify Kelly formula works correctly"""
        opportunity = {
            'expected_win_prob': 0.70,  # 70% win probability
            'entry_price': 0.40  # 40 cents
        }
        balance = 500

        size = risk_manager.calculate_position_size(opportunity, balance)

        # Kelly should be positive
        assert size > 0

        # Should respect Quarter-Kelly (max ~12.5% of balance)
        assert size <= balance * 0.125

        # Should respect 10% cap
        assert size <= balance * 0.10

    def test_kelly_respects_cap(self, risk_manager):
        """Verify Kelly respects max_position_percent cap"""
        opportunity = {
            'expected_win_prob': 0.90,  # Very high edge
            'entry_price': 0.20  # Cheap entry
        }
        balance = 500

        size = risk_manager.calculate_position_size(opportunity, balance)

        # Should be capped at 10% = $50
        assert size <= 50.0

    def test_kelly_negative_ev_returns_zero(self, risk_manager):
        """Verify Kelly returns 0 for negative EV bets"""
        opportunity = {
            'expected_win_prob': 0.40,  # 40% win prob
            'entry_price': 0.60  # 60 cent entry = negative EV
        }
        balance = 500

        size = risk_manager.calculate_position_size(opportunity, balance)

        # Should return 0 for negative EV
        assert size == 0

    def test_kelly_respects_min_size(self, risk_manager):
        """Verify Kelly respects minimum position size"""
        opportunity = {
            'expected_win_prob': 0.51,  # Tiny edge
            'entry_price': 0.49
        }
        balance = 500

        size = risk_manager.calculate_position_size(opportunity, balance)

        # Should be at least $1 (if not zero)
        if size > 0:
            assert size >= 1.0

    def test_kelly_scales_with_balance(self, risk_manager):
        """Verify Kelly scales position size with balance"""
        opportunity = {
            'expected_win_prob': 0.70,
            'entry_price': 0.40
        }

        size_500 = risk_manager.calculate_position_size(opportunity, 500)
        size_1000 = risk_manager.calculate_position_size(opportunity, 1000)

        # Size should scale roughly proportionally
        assert size_1000 > size_500
        assert size_1000 / size_500 >= 1.5  # At least 1.5x larger


class TestCircuitBreaker:
    """Test max drawdown circuit breaker"""

    def test_circuit_breaker_triggers_at_threshold(self, risk_manager):
        """Verify circuit breaker triggers at correct drawdown"""
        # Set peak balance
        risk_manager.peak_balance = 500

        # Drop below threshold (15% = $425)
        current_balance = 424

        triggered, drawdown = risk_manager.check_drawdown(current_balance)

        assert triggered == True
        assert drawdown > 0.15  # Over 15%

    def test_circuit_breaker_does_not_trigger_below_threshold(self, risk_manager):
        """Verify circuit breaker doesn't trigger prematurely"""
        risk_manager.peak_balance = 500
        current_balance = 430  # 14% drawdown

        triggered, drawdown = risk_manager.check_drawdown(current_balance)

        assert triggered == False
        assert drawdown < 0.15

    def test_circuit_breaker_updates_peak(self, risk_manager):
        """Verify peak balance updates on new highs"""
        risk_manager.peak_balance = 500
        new_balance = 550

        risk_manager.check_drawdown(new_balance)

        assert risk_manager.peak_balance == 550

    def test_circuit_breaker_resets_on_recovery(self, risk_manager):
        """Verify circuit breaker resets when balance recovers"""
        risk_manager.peak_balance = 500
        risk_manager.circuit_breaker_triggered = True

        # Recover above peak
        new_balance = 510
        triggered, _ = risk_manager.check_drawdown(new_balance)

        assert risk_manager.circuit_breaker_triggered == False
        assert risk_manager.peak_balance == 510


class TestPositionLimits:
    """Test position size and concurrency limits"""

    def test_respects_max_concurrent_trades(self, risk_manager):
        """Verify can_open_position respects max concurrent limit"""
        current_positions = [
            {'ticker': 'KXBTC1'},
            {'ticker': 'KXBTC2'},
            {'ticker': 'KXBTC3'},
            {'ticker': 'KXBTC4'}  # 4 positions = max
        ]

        opportunity = {'ticker': 'KXBTC5'}

        can_open, reason = risk_manager.can_open_position(
            opportunity, current_positions, 500
        )

        assert can_open == False
        assert "Max positions" in reason

    def test_allows_position_below_limit(self, risk_manager):
        """Verify can_open_position allows when below limit"""
        current_positions = [
            {'ticker': 'KXBTC1'},
            {'ticker': 'KXBTC2'}  # Only 2 positions
        ]

        opportunity = {'ticker': 'KXBTC3'}

        can_open, reason = risk_manager.can_open_position(
            opportunity, current_positions, 500
        )

        assert can_open == True

    def test_rejects_duplicate_ticker(self, risk_manager):
        """Verify can_open_position rejects duplicate tickers"""
        current_positions = [
            {'ticker': 'KXBTC1'}
        ]

        opportunity = {'ticker': 'KXBTC1'}  # Duplicate

        can_open, reason = risk_manager.can_open_position(
            opportunity, current_positions, 500
        )

        assert can_open == False
        assert "Already holding" in reason


# Run tests with: pytest tests/test_risk_management.py -v
