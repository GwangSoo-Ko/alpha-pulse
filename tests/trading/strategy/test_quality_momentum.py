"""QualityMomentum 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.quality_momentum import QualityMomentumStrategy


class TestQualityMomentumStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 5}
        self.strategy = QualityMomentumStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "quality_momentum"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = QualityMomentumStrategy(ranker=self.ranker, config={})
        assert s.top_n == 15

    def test_factor_weights(self):
        """퀄리티+모멘텀 복합 가중치."""
        assert self.strategy.factor_weights["quality"] == 0.35
        assert self.strategy.factor_weights["momentum"] == 0.35
        assert self.strategy.factor_weights["flow"] == 0.2
        assert self.strategy.factor_weights["volatility"] == 0.1

    def test_generate_signals(self):
        """랭킹 기반 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=88.0,
                   factors={"quality": 0.9, "momentum": 0.8},
                   strategy_id="quality_momentum"),
            Signal(stock=self.universe[1], score=72.0,
                   factors={"quality": 0.7, "momentum": 0.7},
                   strategy_id="quality_momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 2
        assert signals[0].score == 88.0

    def test_strong_bearish_halves_and_reduces(self):
        """강한 매도 우위 → 시그널 강도 0.3배 축소."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"quality": 0.8, "momentum": 0.8},
                   strategy_id="quality_momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert signals[0].score == 24.0  # 80 * 0.3
