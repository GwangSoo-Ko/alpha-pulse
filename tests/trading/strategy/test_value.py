"""Value 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.value import ValueStrategy


class TestValueStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 5}
        self.strategy = ValueStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
            Stock(code="035720", name="카카오", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "value"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = ValueStrategy(ranker=self.ranker, config={})
        assert s.top_n == 15

    def test_factor_weights(self):
        """밸류 팩터 가중치 프리셋."""
        assert self.strategy.factor_weights["value"] == 0.4
        assert self.strategy.factor_weights["quality"] == 0.3
        assert self.strategy.factor_weights["momentum"] == 0.2
        assert self.strategy.factor_weights["flow"] == 0.1

    def test_generate_signals(self):
        """밸류 랭킹 기반 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=85.0,
                   factors={"value": 0.9}, strategy_id="value"),
            Signal(stock=self.universe[1], score=70.0,
                   factors={"value": 0.7}, strategy_id="value"),
            Signal(stock=self.universe[2], score=55.0,
                   factors={"value": 0.5}, strategy_id="value"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 30}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 3  # 3 < top_n=5
        assert signals[0].score == 85.0

    def test_neutral_boosts_score(self):
        """중립 시장에서 밸류 전략 강도 1.2배 증가."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"value": 0.8}, strategy_id="value"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "neutral", "pulse_score": 5}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert signals[0].score == 96.0  # 80 * 1.2
