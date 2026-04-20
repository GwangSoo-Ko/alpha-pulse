"""RiskReport 테스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.limits import RiskAlert
from alphapulse.trading.risk.report import RiskReport, RiskReportGenerator


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def generator():
    return RiskReportGenerator()


@pytest.fixture
def portfolio(samsung):
    pos = Position(
        stock=samsung, quantity=100, avg_price=72000,
        current_price=73000, unrealized_pnl=100000,
        weight=0.50, strategy_id="momentum",
    )
    return PortfolioSnapshot(
        date="20260409", cash=5_000_000,
        positions=[pos], total_value=12_300_000,
        daily_return=0.82, cumulative_return=8.3, drawdown=-2.1,
    )


class TestRiskReport:
    def test_creation(self):
        report = RiskReport(
            date="20260409",
            drawdown_pct=2.1,
            drawdown_status="NORMAL",
            var_95=0.018,
            cvar_95=0.025,
            alerts=[],
            stress_results={},
            sector_concentration={"반도체": 0.50},
        )
        assert report.date == "20260409"
        assert report.var_95 == 0.018

    def test_has_alerts(self):
        alert = RiskAlert(
            level="WARNING", category="concentration",
            message="반도체 섹터 50%", current_value=0.50,
            limit_value=0.30,
        )
        report = RiskReport(
            date="20260409", drawdown_pct=2.1,
            drawdown_status="NORMAL", var_95=0.018,
            cvar_95=0.025, alerts=[alert],
            stress_results={}, sector_concentration={},
        )
        assert len(report.alerts) == 1
        assert report.alerts[0].level == "WARNING"


class TestRiskReportGenerator:
    def test_generate_sector_concentration(self, generator, portfolio):
        """섹터 집중도 계산."""
        concentration = generator.calculate_sector_concentration(portfolio)
        assert "반도체" in concentration
        assert concentration["반도체"] == pytest.approx(0.50, abs=0.01)

    def test_generate_report(self, generator, portfolio):
        """리포트 생성."""
        report = generator.generate(
            portfolio=portfolio,
            drawdown_status="NORMAL",
            var_95=0.018,
            cvar_95=0.025,
            stress_results={},
        )
        assert isinstance(report, RiskReport)
        assert report.date == "20260409"

    def test_concentration_alert(self, generator, portfolio):
        """섹터 집중도 경고 생성."""
        alerts = generator.check_concentration_alerts(
            portfolio, max_sector_weight=0.30,
        )
        # 반도체 50% > 30% 한도
        assert len(alerts) >= 1
        assert alerts[0].category == "concentration"
