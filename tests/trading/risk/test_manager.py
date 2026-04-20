"""RiskManager 통합 테스트."""


import pytest

from alphapulse.trading.core.enums import RiskAction, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.var import VaRCalculator


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def limits():
    return RiskLimits()


@pytest.fixture
def manager(limits):
    var_calc = VaRCalculator()
    drawdown_mgr = DrawdownManager(limits=limits)
    drawdown_mgr.update_peak(10_000_000)
    return RiskManager(
        limits=limits,
        var_calc=var_calc,
        drawdown_mgr=drawdown_mgr,
    )


class TestCheckOrder:
    def test_approve_normal_order(self, manager, samsung):
        """정상 주문 → APPROVE."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="LIMIT",
            quantity=5, price=72000, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )

        decision = manager.check_order(order, portfolio)
        assert decision.action == RiskAction.APPROVE

    def test_reject_position_weight_exceeded(self, manager, samsung):
        """종목 비중 한도 초과 → REDUCE_SIZE."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="LIMIT",
            quantity=200, price=72000, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        # 200 * 72000 = 14,400,000 > 10,000,000 * 10% = 1,000,000

        decision = manager.check_order(order, portfolio)
        assert decision.action in (RiskAction.REDUCE_SIZE, RiskAction.REJECT)

    def test_reject_during_warn_drawdown(self, manager, samsung):
        """WARN 드로다운 상태에서 매수 → REJECT."""
        manager.drawdown_mgr.update_peak(10_000_000)
        order = Order(
            stock=samsung, side=Side.BUY, order_type="LIMIT",
            quantity=5, price=72000, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=4_000_000,
            positions=[], total_value=8_900_000,
            daily_return=-1.0, cumulative_return=-5.0, drawdown=-11.0,
        )

        decision = manager.check_order(order, portfolio)
        assert decision.action == RiskAction.REJECT
        assert "드로다운" in decision.reason

    def test_allow_sell_during_warn(self, manager, samsung):
        """WARN 드로다운 상태에서 매도는 허용."""
        manager.drawdown_mgr.update_peak(10_000_000)
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.50, strategy_id="momentum",
        )
        order = Order(
            stock=samsung, side=Side.SELL, order_type="MARKET",
            quantity=50, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=4_000_000,
            positions=[pos], total_value=8_900_000,
            daily_return=-1.0, cumulative_return=-5.0, drawdown=-11.0,
        )

        decision = manager.check_order(order, portfolio)
        assert decision.action == RiskAction.APPROVE

    def test_reject_daily_loss_exceeded(self, manager, samsung):
        """일간 손실 한도 초과 → REJECT."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="LIMIT",
            quantity=5, price=72000, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=-3.5, cumulative_return=-5.0, drawdown=-5.0,
        )

        decision = manager.check_order(order, portfolio)
        assert decision.action == RiskAction.REJECT
        assert "일간" in decision.reason or "손실" in decision.reason

    def test_reject_min_cash_violation(self, manager, samsung):
        """최소 현금 비율 위반 → REJECT."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="LIMIT",
            quantity=10, price=72000, strategy_id="momentum",
        )
        # 현금 300,000 / 총자산 10,000,000 = 3% < 5%
        portfolio = PortfolioSnapshot(
            date="20260409", cash=300_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )

        decision = manager.check_order(order, portfolio)
        assert decision.action == RiskAction.REJECT


class TestCheckPortfolio:
    def test_returns_alerts(self, manager, samsung):
        """포트폴리오 전체 리스크 점검."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.80, strategy_id="momentum",  # 80% 집중
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[pos], total_value=9_200_000,
            daily_return=-1.0, cumulative_return=-3.0, drawdown=-8.0,
        )

        alerts = manager.check_portfolio(portfolio)
        assert len(alerts) >= 1  # 집중도 경고
