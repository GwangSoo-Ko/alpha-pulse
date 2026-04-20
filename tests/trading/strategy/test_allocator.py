"""StrategyAllocator 테스트."""


from alphapulse.trading.core.models import StrategySynthesis
from alphapulse.trading.strategy.allocator import StrategyAllocator


class TestStrategyAllocator:
    def setup_method(self):
        self.base = {
            "topdown_etf": 0.30,
            "momentum": 0.40,
            "value": 0.30,
        }
        self.allocator = StrategyAllocator(base_allocations=self.base)

    def test_base_allocations(self):
        """기본 배분을 반환한다."""
        result = self.allocator.get_allocations()
        assert result == self.base

    def test_allocations_sum_to_one(self):
        """배분 합계는 1.0이다."""
        result = self.allocator.get_allocations()
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_get_capital(self):
        """전략별 할당 가능 자금."""
        capital = self.allocator.get_capital("momentum", total_capital=100_000_000)
        assert capital == 40_000_000  # 40%

    def test_adjust_strong_bullish(self):
        """강한 매수 → 종목 전략 비중 증가, ETF 비중 감소."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=80,
            ai_synthesis=None,
        )
        assert adjusted["momentum"] > self.base["momentum"]
        assert adjusted["topdown_etf"] < self.base["topdown_etf"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_adjust_strong_bearish(self):
        """강한 매도 → ETF 비중 증가, 종목 전략 비중 감소."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=-80,
            ai_synthesis=None,
        )
        assert adjusted["topdown_etf"] > self.base["topdown_etf"]
        assert adjusted["momentum"] < self.base["momentum"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_adjust_neutral(self):
        """중립 → 밸류 비중 증가."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=5,
            ai_synthesis=None,
        )
        assert adjusted["value"] >= self.base["value"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_ai_synthesis_adjustment(self):
        """AI 종합 판단의 allocation_adjustment를 반영한다."""
        synthesis = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.8,
            allocation_adjustment={
                "topdown_etf": 0.20,
                "momentum": 0.50,
                "value": 0.30,
            },
            stock_opinions=[],
            risk_warnings=[],
            reasoning="외국인 순매수 지속",
        )
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=40,
            ai_synthesis=synthesis,
        )
        # AI 조정이 반영되어 momentum이 증가해야 함
        assert adjusted["momentum"] > self.base["momentum"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_ai_low_conviction_ignored(self):
        """AI 확신도 0.3 미만 → AI 조정 무시."""
        synthesis = StrategySynthesis(
            market_view="불확실",
            conviction_level=0.2,
            allocation_adjustment={
                "topdown_etf": 0.10,
                "momentum": 0.80,
                "value": 0.10,
            },
            stock_opinions=[],
            risk_warnings=["확신도 매우 낮음"],
            reasoning="불확실",
        )
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=40,
            ai_synthesis=synthesis,
        )
        # 확신도 낮아서 AI 조정 무시 → 규칙 기반만 적용
        # momentum이 0.80까지 올라가지 않아야 함
        assert adjusted["momentum"] < 0.70

    def test_update_allocations(self):
        """배분 비율을 갱신한다."""
        new = {"topdown_etf": 0.40, "momentum": 0.30, "value": 0.30}
        self.allocator.update_allocations(new)
        assert self.allocator.get_allocations() == new
