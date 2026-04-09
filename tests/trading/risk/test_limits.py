"""RiskLimits, RiskDecision, RiskAlert 테스트."""

from alphapulse.trading.core.enums import RiskAction
from alphapulse.trading.risk.limits import RiskAlert, RiskDecision, RiskLimits


class TestRiskLimits:
    def test_defaults(self):
        """기본값 확인."""
        limits = RiskLimits()
        assert limits.max_position_weight == 0.10
        assert limits.max_sector_weight == 0.30
        assert limits.max_etf_leverage == 0.20
        assert limits.max_total_exposure == 1.0
        assert limits.max_drawdown_soft == 0.10
        assert limits.max_drawdown_hard == 0.15
        assert limits.max_daily_loss == 0.03
        assert limits.min_cash_ratio == 0.05
        assert limits.max_single_order_pct == 0.05
        assert limits.max_order_to_volume == 0.10
        assert limits.max_portfolio_var_95 == 0.03

    def test_custom_values(self):
        """커스텀 값 지정."""
        limits = RiskLimits(
            max_position_weight=0.05,
            max_drawdown_hard=0.20,
        )
        assert limits.max_position_weight == 0.05
        assert limits.max_drawdown_hard == 0.20
        # 나머지는 기본값
        assert limits.max_sector_weight == 0.30


class TestRiskDecision:
    def test_approve(self):
        """승인 결정."""
        d = RiskDecision(
            action=RiskAction.APPROVE,
            reason="모든 한도 이내",
            adjusted_quantity=None,
        )
        assert d.action == RiskAction.APPROVE
        assert d.adjusted_quantity is None

    def test_reduce_size(self):
        """수량 축소."""
        d = RiskDecision(
            action=RiskAction.REDUCE_SIZE,
            reason="종목 비중 한도 초과",
            adjusted_quantity=50,
        )
        assert d.action == RiskAction.REDUCE_SIZE
        assert d.adjusted_quantity == 50

    def test_reject(self):
        """거부."""
        d = RiskDecision(
            action=RiskAction.REJECT,
            reason="일간 손실 한도 초과",
            adjusted_quantity=None,
        )
        assert d.action == RiskAction.REJECT


class TestRiskAlert:
    def test_creation(self):
        alert = RiskAlert(
            level="WARNING",
            category="drawdown",
            message="드로다운 -8% 접근",
            current_value=0.08,
            limit_value=0.10,
        )
        assert alert.level == "WARNING"
        assert alert.category == "drawdown"
        assert alert.current_value == 0.08
