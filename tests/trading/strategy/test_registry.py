"""StrategyRegistry 테스트."""

import pytest

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.registry import StrategyRegistry


class StubStrategy(BaseStrategy):
    """테스트용 스텁 전략."""

    strategy_id = "stub"
    rebalance_freq = RebalanceFreq.DAILY

    def generate_signals(self, universe, market_context):
        return []


class AnotherStub(BaseStrategy):
    strategy_id = "another"
    rebalance_freq = RebalanceFreq.WEEKLY

    def generate_signals(self, universe, market_context):
        return []


class TestStrategyRegistry:
    def setup_method(self):
        self.registry = StrategyRegistry()

    def test_register_and_get(self):
        """전략을 등록하고 조회한다."""
        strategy = StubStrategy(config={})
        self.registry.register(strategy)
        assert self.registry.get("stub") is strategy

    def test_get_unknown_raises(self):
        """미등록 전략 조회 시 KeyError."""
        with pytest.raises(KeyError):
            self.registry.get("unknown")

    def test_list_all(self):
        """등록된 전략 ID 목록을 반환한다."""
        self.registry.register(StubStrategy(config={}))
        self.registry.register(AnotherStub(config={}))
        ids = self.registry.list_all()
        assert sorted(ids) == ["another", "stub"]

    def test_list_all_empty(self):
        """빈 레지스트리는 빈 리스트."""
        assert self.registry.list_all() == []

    def test_register_duplicate_overwrites(self):
        """동일 ID 재등록 시 덮어쓴다."""
        s1 = StubStrategy(config={"v": 1})
        s2 = StubStrategy(config={"v": 2})
        self.registry.register(s1)
        self.registry.register(s2)
        assert self.registry.get("stub").config == {"v": 2}

    def test_contains(self):
        """전략 존재 여부 확인."""
        self.registry.register(StubStrategy(config={}))
        assert self.registry.contains("stub") is True
        assert self.registry.contains("missing") is False
