"""PortfolioManager 통합 테스트."""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.portfolio.manager import PortfolioManager
from alphapulse.trading.portfolio.models import TargetPortfolio


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def manager():
    position_sizer = MagicMock()
    optimizer = MagicMock()
    rebalancer = MagicMock()
    cost_model = MagicMock()

    return PortfolioManager(
        position_sizer=position_sizer,
        optimizer=optimizer,
        rebalancer=rebalancer,
        cost_model=cost_model,
    )


class TestUpdateTarget:
    def test_generates_target_portfolio(self, manager, samsung):
        """전략 시그널로부터 TargetPortfolio를 산출한다."""
        signals = {
            "momentum": [
                Signal(stock=samsung, score=80.0,
                       factors={"momentum": 0.8},
                       strategy_id="momentum"),
            ],
        }
        allocations = {"momentum": 1.0}
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        manager.position_sizer.equal_weight.return_value = 1.0

        target = manager.update_target(
            strategy_signals=signals,
            allocations=allocations,
            current=current,
            prices={"005930": 72000},
        )

        assert isinstance(target, TargetPortfolio)
        assert "005930" in target.positions
        assert 0 < target.positions["005930"] <= 1.0
        assert target.date == "20260409"
        assert "momentum" in target.strategy_allocations

    def test_applies_allocation_ratio(self, manager, samsung):
        """전략 배분 비율을 적용한다."""
        signals = {
            "momentum": [
                Signal(stock=samsung, score=80.0,
                       factors={"momentum": 0.8},
                       strategy_id="momentum"),
            ],
        }
        allocations = {"momentum": 0.50}  # 50%만 배분
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        manager.position_sizer.equal_weight.return_value = 1.0

        target = manager.update_target(
            strategy_signals=signals,
            allocations=allocations,
            current=current,
            prices={"005930": 72000},
        )

        # 50% 배분 * 100% 종목 비중 = 50%
        assert target.positions["005930"] <= 0.50 + 0.01


class TestGenerateOrders:
    def test_delegates_to_rebalancer(self, manager, samsung):
        """Rebalancer에 위임한다."""
        target = TargetPortfolio(
            date="20260409",
            positions={"005930": 0.50},
            cash_weight=0.50,
            strategy_allocations={"momentum": 1.0},
        )
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        prices = {"005930": 72000}

        expected_orders = [
            Order(stock=samsung, side=Side.BUY, order_type="MARKET",
                  quantity=69, price=None, strategy_id="momentum"),
        ]
        manager.rebalancer.generate_orders.return_value = expected_orders

        orders = manager.generate_orders(
            target=target,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert orders == expected_orders
        manager.rebalancer.generate_orders.assert_called_once()
