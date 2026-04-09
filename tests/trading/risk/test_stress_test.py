"""StressTest 테스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.stress_test import StressResult, StressTest


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def kodex():
    return Stock(code="069500", name="KODEX 200", market="ETF")


@pytest.fixture
def stress():
    return StressTest()


@pytest.fixture
def portfolio(samsung, kodex):
    pos1 = Position(
        stock=samsung,
        quantity=100,
        avg_price=72000,
        current_price=72000,
        unrealized_pnl=0,
        weight=0.50,
        strategy_id="momentum",
    )
    pos2 = Position(
        stock=kodex,
        quantity=200,
        avg_price=35000,
        current_price=35000,
        unrealized_pnl=0,
        weight=0.50,
        strategy_id="topdown_etf",
    )
    return PortfolioSnapshot(
        date="20260409",
        cash=0,
        positions=[pos1, pos2],
        total_value=14_200_000,
        daily_return=0.0,
        cumulative_return=0.0,
        drawdown=0.0,
    )


class TestPredefinedScenarios:
    def test_scenarios_exist(self, stress):
        """사전 정의 시나리오가 존재한다."""
        assert "2020_covid" in stress.SCENARIOS
        assert "2022_rate_hike" in stress.SCENARIOS
        assert "flash_crash" in stress.SCENARIOS
        assert "won_crisis" in stress.SCENARIOS
        assert "sector_collapse" in stress.SCENARIOS

    def test_covid_scenario(self, stress, portfolio):
        """COVID-19 시나리오 실행."""
        result = stress.run(portfolio, "2020_covid")
        assert isinstance(result, StressResult)
        assert result.scenario_name == "2020_covid"
        assert result.estimated_loss < 0  # 손실 발생
        assert result.loss_pct < 0

    def test_flash_crash_scenario(self, stress, portfolio):
        """일간 급락 시나리오."""
        result = stress.run(portfolio, "flash_crash")
        assert result.estimated_loss < 0

    def test_sector_collapse_scenario(self, stress, portfolio):
        """특정 섹터 붕괴 시나리오."""
        result = stress.run(portfolio, "sector_collapse")
        assert isinstance(result, StressResult)
        assert result.scenario_name == "sector_collapse"
        assert result.estimated_loss < 0
        # 반도체 섹터 종목(삼성전자)이 더 큰 충격
        assert "005930" in result.contributions

    def test_result_has_contributions(self, stress, portfolio):
        """종목별 손실 기여도 포함."""
        result = stress.run(portfolio, "2020_covid")
        assert len(result.contributions) > 0

    def test_unknown_scenario_raises(self, stress, portfolio):
        """미정의 시나리오 -> KeyError."""
        with pytest.raises(KeyError):
            stress.run(portfolio, "unknown_scenario")


class TestRunAll:
    def test_runs_all_scenarios(self, stress, portfolio):
        """전 시나리오 일괄 실행."""
        results = stress.run_all(portfolio)
        assert len(results) == len(stress.SCENARIOS)
        assert all(isinstance(r, StressResult) for r in results.values())


class TestCustomScenario:
    def test_add_custom(self, stress, portfolio):
        """사용자 정의 시나리오 추가."""
        stress.add_custom_scenario(
            "china_crisis",
            {"kospi": -0.30, "kosdaq": -0.40, "desc": "중국 경제 위기"},
        )
        assert "china_crisis" in stress.SCENARIOS

        result = stress.run(portfolio, "china_crisis")
        assert result.estimated_loss < 0
