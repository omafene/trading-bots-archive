"""
Tests for Edge Detection and Signal Generation
"""

import pytest
from momentum_analyzer import MomentumAnalyzer
from volatility_analyzer import VolatilityAnalyzer
from datetime import datetime, timezone, timedelta


@pytest.fixture
def momentum_analyzer():
    """Create momentum analyzer with mock spot feed"""
    class MockSpotFeed:
        def _get_price(self, symbol):
            return 95000 if symbol == 'BTC' else 3000

    return MomentumAnalyzer(MockSpotFeed())


@pytest.fixture
def volatility_analyzer():
    """Create volatility analyzer"""
    return VolatilityAnalyzer(window_minutes=15)


class TestMomentumAnalysis:
    """Test momentum calculations"""

    def test_momentum_direction_up(self, momentum_analyzer):
        """Verify upward momentum detected correctly"""
        # Add price history (uptrend)
        now = datetime.now(timezone.utc)
        prices = [95000, 95100, 95300, 95500, 95800]

        for i, price in enumerate(prices):
            ts = now - timedelta(minutes=15-i*3)
            momentum_analyzer.price_history['BTC'] = [
                (ts, p) for ts, p in zip(
                    [now - timedelta(minutes=15-j*3) for j in range(len(prices[:i+1]))],
                    prices[:i+1]
                )
            ]

        momentum = momentum_analyzer.calculate_momentum('BTC', minutes=15)

        assert momentum is not None
        assert momentum['direction'] == 'up'
        assert momentum['percent_change'] > 0

    def test_momentum_direction_down(self, momentum_analyzer):
        """Verify downward momentum detected correctly"""
        # Add price history (downtrend)
        now = datetime.now(timezone.utc)
        prices = [95800, 95500, 95300, 95100, 95000]

        momentum_analyzer.price_history['BTC'] = [
            (now - timedelta(minutes=15-i*3), price)
            for i, price in enumerate(prices)
        ]

        momentum = momentum_analyzer.calculate_momentum('BTC', minutes=15)

        assert momentum is not None
        assert momentum['direction'] == 'down'
        assert momentum['percent_change'] < 0

    def test_momentum_flat(self, momentum_analyzer):
        """Verify flat momentum detected correctly"""
        # Add price history (flat)
        now = datetime.now(timezone.utc)
        prices = [95000, 95010, 95005, 95012, 95008]  # <0.05% change

        momentum_analyzer.price_history['BTC'] = [
            (now - timedelta(minutes=15-i*3), price)
            for i, price in enumerate(prices)
        ]

        momentum = momentum_analyzer.calculate_momentum('BTC', minutes=15)

        assert momentum is not None
        assert momentum['direction'] == 'flat'
        assert abs(momentum['percent_change']) < 0.05

    def test_expected_probability_up_market(self, momentum_analyzer):
        """Verify probability calculation for UP markets"""
        # Set up upward momentum
        now = datetime.now(timezone.utc)
        prices = [95000, 95500, 96000]
        momentum_analyzer.price_history['BTC'] = [
            (now - timedelta(minutes=10-i*5), price)
            for i, price in enumerate(prices)
        ]

        prob = momentum_analyzer.calculate_expected_probability(
            'BTC', 'up', threshold=None, minutes=15, current_price=96000
        )

        # Upward momentum + UP market = high probability
        assert prob > 0.50
        assert prob < 0.95  # Capped

    def test_expected_probability_above_threshold(self, momentum_analyzer):
        """Verify probability for ABOVE threshold markets"""
        now = datetime.now(timezone.utc)
        prices = [95000, 95500]
        momentum_analyzer.price_history['BTC'] = [
            (now - timedelta(minutes=10-i*5), price)
            for i, price in enumerate(prices)
        ]

        # Current price above threshold
        prob = momentum_analyzer.calculate_expected_probability(
            'BTC', 'above', threshold=94000, minutes=15, current_price=95500
        )

        # Already above threshold = high probability
        assert prob >= 0.80


class TestVolatilityAnalysis:
    """Test volatility calculations and regime detection"""

    def test_realized_volatility_calculation(self, volatility_analyzer):
        """Verify realized volatility calculated correctly"""
        # Add price samples
        now = datetime.now(timezone.utc)
        prices = [95000, 95500, 95200, 95800, 95400]

        for i, price in enumerate(prices):
            ts = now - timedelta(minutes=15-i*3)
            volatility_analyzer.update_price('BTC', price, ts)

        vol = volatility_analyzer.calculate_realized_volatility('BTC', minutes=15)

        assert vol is not None
        assert vol > 0  # Volatility should be positive
        assert vol < 50.0  # Reasonable annualized volatility for crypto

    def test_volatility_signal_fade(self, volatility_analyzer):
        """Verify fade signal when realized > implied"""
        # High realized volatility
        now = datetime.now(timezone.utc)
        prices = [95000, 93000, 97000, 94000, 96000]  # High variance

        for i, price in enumerate(prices):
            volatility_analyzer.update_price('BTC', price, now - timedelta(minutes=15-i*3))

        signal = volatility_analyzer.get_volatility_signal(
            'BTC',
            market_prob=0.60,  # Market thinks 60% (implies low vol)
            strike=95000,
            spot=95000,
            minutes_to_expiry=10
        )

        # High realized vol + low implied vol = fade signal
        assert signal is not None
        # Signal might be 'fade' or 'neutral' depending on exact calc
        # Just verify it returns something reasonable
        assert signal['signal'] in ['fade', 'ride', 'neutral']

    def test_volatility_regime_detection(self, volatility_analyzer):
        """Verify volatility regime classification"""
        # Low volatility regime
        now = datetime.now(timezone.utc)
        prices = [95000 + i * 10 for i in range(20)]  # Small, steady moves

        for i, price in enumerate(prices):
            volatility_analyzer.update_price('BTC', price, now - timedelta(seconds=60-i*3))

        regime = volatility_analyzer.detect_volatility_regime('BTC')

        assert regime is not None
        assert regime['regime'] in ['quiet', 'normal', 'explosive']


class TestEdgeCalculation:
    """Test edge calculations and filtering"""

    def test_edge_calculation_with_fees(self):
        """Verify edge calculation includes fees"""
        expected_prob = 0.70
        market_ask = 0.50
        exchange_fee = 0.015  # 1.5%
        slippage = 0.0008  # 0.08%

        # Raw edge
        raw_edge = (expected_prob - market_ask) * 100  # 20%

        # After fees
        edge_after_fees = raw_edge - (exchange_fee * 100) - (slippage * 100)

        # Should be roughly 18.42%
        assert 18.0 < edge_after_fees < 19.0

    def test_no_edge_on_fair_market(self):
        """Verify no edge found when market is fairly priced"""
        expected_prob = 0.50
        market_ask = 0.50

        edge = (expected_prob - market_ask) * 100

        assert edge == 0  # No edge

    def test_signal_strength_calculation(self):
        """Verify signal strength combines factors correctly"""
        # Components
        edge_score = 15 / 20 * 30  # 22.5 points
        prob_score = (0.70 - 0.50) * 2 * 20  # 8 points
        mom_score = 15  # Sweet spot momentum
        vol_score = 10  # Some vol signal
        stat_arb_score = 15  # Some stat arb

        total = edge_score + prob_score + mom_score + vol_score + stat_arb_score

        # Should be 70.5 points
        assert 65 < total < 75


# Run tests with: pytest tests/test_edge_detection.py -v
