"""PerformanceAttribution 테스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.portfolio.attribution import PerformanceAttribution


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def kakao():
    return Stock(code="035720", name="카카오", market="KOSPI", sector="IT")


@pytest.fixture
def attribution():
    return PerformanceAttribution()


class TestStrategyAttribution:
    def test_single_strategy(self, attribution, samsung):
        """단일 전략 수익 기여도."""
        pos1 = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=73000, unrealized_pnl=100000,
            weight=0.50, strategy_id="momentum",
        )
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=5_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.50, strategy_id="momentum"),
            ],
            total_value=12_200_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[pos1], total_value=12_300_000,
            daily_return=0.82, cumulative_return=0.82, drawdown=0.0,
        )

        result = attribution.strategy_attribution(snap_prev, snap_curr)
        assert "momentum" in result
        assert result["momentum"] > 0

    def test_multi_strategy(self, attribution, samsung, kakao):
        """멀티 전략 수익 기여도 분리."""
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.40, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=50000, unrealized_pnl=0,
                         weight=0.25, strategy_id="value"),
            ],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=73000, unrealized_pnl=100000,
                         weight=0.41, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=49000, unrealized_pnl=-50000,
                         weight=0.24, strategy_id="value"),
            ],
            total_value=10_050_000, daily_return=0.5,
            cumulative_return=0.5, drawdown=0.0,
        )

        result = attribution.strategy_attribution(snap_prev, snap_curr)
        assert result["momentum"] > 0  # 삼성전자 상승
        assert result["value"] < 0     # 카카오 하락


class TestSectorAttribution:
    def test_sector_returns(self, attribution, samsung, kakao):
        """섹터별 수익 기여도."""
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.50, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=50000, unrealized_pnl=0,
                         weight=0.25, strategy_id="value"),
            ],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=73000, unrealized_pnl=100000,
                         weight=0.51, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=49000, unrealized_pnl=-50000,
                         weight=0.24, strategy_id="value"),
            ],
            total_value=10_050_000, daily_return=0.5,
            cumulative_return=0.5, drawdown=0.0,
        )

        result = attribution.sector_attribution(snap_prev, snap_curr)
        assert "반도체" in result
        assert "IT" in result
        assert result["반도체"] > 0
        assert result["IT"] < 0
