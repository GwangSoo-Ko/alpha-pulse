"""DrawdownManager 테스트."""

import pytest

from alphapulse.trading.core.enums import DrawdownAction, Side
from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def limits():
    return RiskLimits(max_drawdown_soft=0.10, max_drawdown_hard=0.15)


@pytest.fixture
def manager(limits):
    return DrawdownManager(limits=limits)


class TestCheckDrawdown:
    def test_normal_state(self, manager):
        """드로다운 미발생 -> NORMAL."""
        snap = PortfolioSnapshot(
            date="20260409",
            cash=5_000_000,
            positions=[],
            total_value=10_000_000,
            daily_return=0.5,
            cumulative_return=5.0,
            drawdown=-2.0,
        )
        manager.update_peak(10_000_000)
        action = manager.check(snap)
        assert action == DrawdownAction.NORMAL

    def test_warn_state(self, manager):
        """소프트 한도 초과 -> WARN."""
        manager.update_peak(10_000_000)
        # 10% 하락 -> 9,000,000
        snap = PortfolioSnapshot(
            date="20260409",
            cash=4_000_000,
            positions=[],
            total_value=8_900_000,
            daily_return=-1.1,
            cumulative_return=-5.0,
            drawdown=-11.0,
        )
        action = manager.check(snap)
        assert action == DrawdownAction.WARN

    def test_deleverage_state(self, manager):
        """하드 한도 초과 -> DELEVERAGE."""
        manager.update_peak(10_000_000)
        # 16% 하락 -> 8,400,000
        snap = PortfolioSnapshot(
            date="20260409",
            cash=3_000_000,
            positions=[],
            total_value=8_400_000,
            daily_return=-2.0,
            cumulative_return=-10.0,
            drawdown=-16.0,
        )
        action = manager.check(snap)
        assert action == DrawdownAction.DELEVERAGE

    def test_peak_updates(self, manager):
        """고점이 자동 갱신된다."""
        manager.update_peak(10_000_000)
        manager.update_peak(11_000_000)
        assert manager.peak_value == 11_000_000

    def test_peak_does_not_decrease(self, manager):
        """고점은 감소하지 않는다."""
        manager.update_peak(10_000_000)
        manager.update_peak(9_000_000)
        assert manager.peak_value == 10_000_000


class TestGenerateDeleverageOrders:
    def test_deleverage_orders(self, manager, samsung):
        """전 포지션 50% 축소 주문 생성."""
        pos = Position(
            stock=samsung,
            quantity=100,
            avg_price=72000,
            current_price=60000,
            unrealized_pnl=-1200000,
            weight=0.70,
            strategy_id="momentum",
        )
        snap = PortfolioSnapshot(
            date="20260409",
            cash=2_000_000,
            positions=[pos],
            total_value=8_000_000,
            daily_return=-3.0,
            cumulative_return=-20.0,
            drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 50  # 100의 50%
        assert "디레버리지" in orders[0].reason or "축소" in orders[0].reason

    def test_no_positions_no_orders(self, manager):
        """포지션 없으면 주문 없음."""
        snap = PortfolioSnapshot(
            date="20260409",
            cash=8_000_000,
            positions=[],
            total_value=8_000_000,
            daily_return=-3.0,
            cumulative_return=-20.0,
            drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)
        assert len(orders) == 0

    def test_orders_sorted_by_loss(self, manager, samsung):
        """손실 큰 포지션부터 매도."""
        kakao = Stock(code="035720", name="카카오", market="KOSPI")
        pos1 = Position(
            stock=samsung,
            quantity=100,
            avg_price=72000,
            current_price=60000,
            unrealized_pnl=-1200000,
            weight=0.40,
            strategy_id="momentum",
        )
        pos2 = Position(
            stock=kakao,
            quantity=50,
            avg_price=50000,
            current_price=48000,
            unrealized_pnl=-100000,
            weight=0.30,
            strategy_id="value",
        )
        snap = PortfolioSnapshot(
            date="20260409",
            cash=2_000_000,
            positions=[pos2, pos1],  # 의도적으로 카카오 먼저
            total_value=8_000_000,
            daily_return=-3.0,
            cumulative_return=-20.0,
            drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)
        # 삼성전자 (-1,200,000)가 카카오 (-100,000)보다 먼저
        assert orders[0].stock.code == "005930"
