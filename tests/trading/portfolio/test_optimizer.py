"""PortfolioOptimizer 테스트."""

import numpy as np
import pytest

from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer


@pytest.fixture
def optimizer():
    return PortfolioOptimizer()


@pytest.fixture
def cov_matrix():
    """2종목 공분산 행렬."""
    return np.array([
        [0.04, 0.01],  # 종목A: 변동성 20%
        [0.01, 0.09],  # 종목B: 변동성 30%
    ])


@pytest.fixture
def expected_returns():
    """2종목 기대수익률."""
    return np.array([0.10, 0.15])


class TestMeanVariance:
    def test_weights_sum_to_one(self, optimizer, expected_returns, cov_matrix):
        """비중 합계가 1.0이다."""
        weights = optimizer.mean_variance(expected_returns, cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_no_negative_weights(self, optimizer, expected_returns, cov_matrix):
        """롱 온리 -- 음수 비중 없음."""
        weights = optimizer.mean_variance(expected_returns, cov_matrix)
        assert all(w >= -1e-9 for w in weights)

    def test_max_weight_constraint(self, optimizer, expected_returns, cov_matrix):
        """종목당 최대 비중 제약."""
        weights = optimizer.mean_variance(
            expected_returns, cov_matrix, max_weight=0.60,
        )
        assert all(w <= 0.60 + 1e-6 for w in weights)

    def test_single_stock(self, optimizer):
        """1종목이면 비중 100%."""
        ret = np.array([0.10])
        cov = np.array([[0.04]])
        weights = optimizer.mean_variance(ret, cov)
        assert weights[0] == pytest.approx(1.0, abs=1e-4)


class TestRiskParity:
    def test_weights_sum_to_one(self, optimizer, cov_matrix):
        """비중 합계가 1.0이다."""
        weights = optimizer.risk_parity(cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_risk_contributions_equal(self, optimizer, cov_matrix):
        """리스크 기여도가 균등해야 한다."""
        weights = optimizer.risk_parity(cov_matrix)
        # 리스크 기여도 = w_i * (Sigma @ w)_i / sigma_p
        marginal = cov_matrix @ weights
        risk_contrib = weights * marginal
        # 균등 검증 (상대 오차 20% 이내)
        avg_rc = np.mean(risk_contrib)
        for rc in risk_contrib:
            assert abs(rc - avg_rc) / avg_rc < 0.20

    def test_low_vol_gets_more_weight(self, optimizer, cov_matrix):
        """변동성 낮은 종목이 더 큰 비중."""
        weights = optimizer.risk_parity(cov_matrix)
        assert weights[0] > weights[1]  # 종목A(20%) > 종목B(30%)


class TestMinVariance:
    def test_weights_sum_to_one(self, optimizer, cov_matrix):
        weights = optimizer.min_variance(cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_no_negative_weights(self, optimizer, cov_matrix):
        weights = optimizer.min_variance(cov_matrix)
        assert all(w >= -1e-9 for w in weights)


class TestSelectMethod:
    def test_strong_bullish(self, optimizer):
        ctx = {"pulse_signal": "strong_bullish", "pulse_score": 80}
        assert optimizer.select_method(ctx) == "mean_variance"

    def test_neutral(self, optimizer):
        ctx = {"pulse_signal": "neutral", "pulse_score": 0}
        assert optimizer.select_method(ctx) == "risk_parity"

    def test_strong_bearish(self, optimizer):
        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        assert optimizer.select_method(ctx) == "min_variance"
