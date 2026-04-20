"""CorrelationAnalyzer 테스트."""

import numpy as np
import pandas as pd
import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.correlation import CorrelationAnalyzer


@pytest.fixture
def analyzer():
    return CorrelationAnalyzer()


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def hynix():
    return Stock(code="000660", name="SK하이닉스", market="KOSPI", sector="반도체")


@pytest.fixture
def kakao():
    return Stock(code="035720", name="카카오", market="KOSPI", sector="IT")


class TestCalculateCorrelationMatrix:
    def test_identity_for_same_stock(self, analyzer):
        """동일 종목은 상관계수 1.0."""
        np.random.seed(42)
        returns_data = {
            "005930": np.random.normal(0, 0.02, 60),
        }
        corr = analyzer.calculate_correlation_matrix(returns_data)
        assert corr.shape == (1, 1)
        assert corr.iloc[0, 0] == pytest.approx(1.0)

    def test_two_stocks(self, analyzer):
        """2종목 상관 행렬 크기와 대칭성."""
        np.random.seed(42)
        base = np.random.normal(0, 0.02, 60)
        returns_data = {
            "005930": base + np.random.normal(0, 0.005, 60),
            "000660": base + np.random.normal(0, 0.005, 60),
        }
        corr = analyzer.calculate_correlation_matrix(returns_data)
        assert corr.shape == (2, 2)
        assert corr.iloc[0, 1] == pytest.approx(corr.iloc[1, 0])

    def test_high_correlation(self, analyzer):
        """높은 상관관계 감지."""
        np.random.seed(42)
        base = np.random.normal(0, 0.02, 60)
        returns_data = {
            "005930": base,
            "000660": base * 1.1 + np.random.normal(0, 0.001, 60),
        }
        corr = analyzer.calculate_correlation_matrix(returns_data)
        assert corr.iloc[0, 1] > 0.8


class TestCheckConcentration:
    def test_high_correlation_alert(self, analyzer, samsung, hynix):
        """높은 상관관계 종목 집중 시 경고."""
        pos1 = Position(
            stock=samsung,
            quantity=100,
            avg_price=72000,
            current_price=72000,
            unrealized_pnl=0,
            weight=0.40,
            strategy_id="momentum",
        )
        pos2 = Position(
            stock=hynix,
            quantity=50,
            avg_price=180000,
            current_price=180000,
            unrealized_pnl=0,
            weight=0.40,
            strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409",
            cash=2_000_000,
            positions=[pos1, pos2],
            total_value=10_000_000,
            daily_return=0.0,
            cumulative_return=0.0,
            drawdown=0.0,
        )
        # 높은 상관관계 행렬
        corr_matrix = pd.DataFrame(
            [[1.0, 0.95], [0.95, 1.0]],
            index=["005930", "000660"],
            columns=["005930", "000660"],
        )

        alerts = analyzer.check_concentration(portfolio, corr_matrix)
        assert len(alerts) >= 1
        assert alerts[0].category == "correlation"

    def test_low_correlation_no_alert(self, analyzer, samsung, kakao):
        """낮은 상관관계면 경고 없음."""
        pos1 = Position(
            stock=samsung,
            quantity=100,
            avg_price=72000,
            current_price=72000,
            unrealized_pnl=0,
            weight=0.30,
            strategy_id="momentum",
        )
        pos2 = Position(
            stock=kakao,
            quantity=50,
            avg_price=50000,
            current_price=50000,
            unrealized_pnl=0,
            weight=0.20,
            strategy_id="value",
        )
        portfolio = PortfolioSnapshot(
            date="20260409",
            cash=5_000_000,
            positions=[pos1, pos2],
            total_value=10_000_000,
            daily_return=0.0,
            cumulative_return=0.0,
            drawdown=0.0,
        )
        corr_matrix = pd.DataFrame(
            [[1.0, 0.20], [0.20, 1.0]],
            index=["005930", "035720"],
            columns=["005930", "035720"],
        )

        alerts = analyzer.check_concentration(portfolio, corr_matrix)
        assert len(alerts) == 0
