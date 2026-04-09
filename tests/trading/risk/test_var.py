"""VaRCalculator 테스트."""

import numpy as np
import pytest

from alphapulse.trading.risk.var import VaRCalculator


@pytest.fixture
def calc():
    return VaRCalculator()


@pytest.fixture
def normal_returns():
    """정규분포 유사 수익률 시계열 (평균 0, 표준편차 ~2%)."""
    np.random.seed(42)
    return np.random.normal(0.0, 0.02, 250)


class TestHistoricalVaR:
    def test_95_confidence(self, calc, normal_returns):
        """95% 신뢰수준 Historical VaR."""
        var = calc.historical_var(normal_returns, confidence=0.95)
        assert var > 0
        assert 0.01 < var < 0.10  # 합리적 범위

    def test_99_confidence_higher(self, calc, normal_returns):
        """99% VaR > 95% VaR."""
        var_95 = calc.historical_var(normal_returns, confidence=0.95)
        var_99 = calc.historical_var(normal_returns, confidence=0.99)
        assert var_99 > var_95


class TestParametricVaR:
    def test_single_asset(self, calc):
        """단일 자산 파라메트릭 VaR."""
        weights = np.array([1.0])
        cov = np.array([[0.04]])  # 변동성 20%
        var = calc.parametric_var(weights, cov, confidence=0.95)
        assert var > 0

    def test_two_assets(self, calc):
        """2종목 파라메트릭 VaR."""
        weights = np.array([0.5, 0.5])
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        var = calc.parametric_var(weights, cov, confidence=0.95)
        assert var > 0

    def test_diversification_reduces_var(self, calc):
        """분산 투자 시 VaR 감소."""
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        # 집중 투자
        var_conc = calc.parametric_var(np.array([1.0, 0.0]), cov)
        # 분산 투자
        var_div = calc.parametric_var(np.array([0.5, 0.5]), cov)
        assert var_div < var_conc


class TestCVaR:
    def test_cvar_greater_than_var(self, calc, normal_returns):
        """CVaR >= VaR (꼬리 리스크 반영)."""
        var = calc.historical_var(normal_returns, confidence=0.95)
        cvar = calc.cvar(normal_returns, confidence=0.95)
        assert cvar >= var

    def test_cvar_positive(self, calc, normal_returns):
        """CVaR는 양수."""
        cvar = calc.cvar(normal_returns, confidence=0.95)
        assert cvar > 0
