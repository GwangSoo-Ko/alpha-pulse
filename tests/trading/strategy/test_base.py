"""BaseStrategy ABC 테스트."""

from abc import ABC

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy


class DummyStrategy(BaseStrategy):
    """테스트용 전략 구현체."""

    strategy_id = "dummy"
    rebalance_freq = RebalanceFreq.WEEKLY

    def generate_signals(self, universe, market_context):
        return [
            Signal(
                stock=universe[0],
                score=80.0,
                factors={"test": 0.8},
                strategy_id=self.strategy_id,
            )
        ]


class TestBaseStrategy:
    def test_is_abstract(self):
        """BaseStrategy는 ABC여야 한다."""
        assert issubclass(BaseStrategy, ABC)

    def test_cannot_instantiate_directly(self):
        """BaseStrategy를 직접 인스턴스화할 수 없다."""
        try:
            BaseStrategy(config={})
            assert False, "ABC를 직접 인스턴스화하면 안 된다"
        except TypeError:
            pass

    def test_subclass_works(self):
        """구현체는 정상 동작한다."""
        strategy = DummyStrategy(config={"top_n": 10})
        assert strategy.strategy_id == "dummy"
        assert strategy.rebalance_freq == RebalanceFreq.WEEKLY
        assert strategy.config == {"top_n": 10}

    def test_generate_signals(self):
        """시그널 생성이 올바르게 동작한다."""
        strategy = DummyStrategy(config={})
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        signals = strategy.generate_signals([stock], {})
        assert len(signals) == 1
        assert signals[0].score == 80.0
        assert signals[0].strategy_id == "dummy"

    def test_should_rebalance_daily(self):
        """DAILY 전략은 항상 True."""
        strategy = DummyStrategy(config={})
        strategy.rebalance_freq = RebalanceFreq.DAILY
        assert strategy.should_rebalance("20260406", "20260407", {}) is True

    def test_should_rebalance_weekly_monday(self):
        """WEEKLY 전략은 월요일에 True."""
        strategy = DummyStrategy(config={})
        # 2026-04-06은 월요일
        assert strategy.should_rebalance("20260401", "20260406", {}) is True

    def test_should_rebalance_weekly_non_monday(self):
        """WEEKLY 전략은 월요일이 아니면 False."""
        strategy = DummyStrategy(config={})
        # 2026-04-07은 화요일
        assert strategy.should_rebalance("20260406", "20260407", {}) is False
