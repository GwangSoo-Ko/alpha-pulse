"""Momentum 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.momentum import MomentumStrategy


class TestMomentumStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 3}
        self.strategy = MomentumStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
            Stock(code="035720", name="카카오", market="KOSPI"),
            Stock(code="051910", name="LG화학", market="KOSPI"),
            Stock(code="006400", name="삼성SDI", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "momentum"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = MomentumStrategy(ranker=self.ranker, config={})
        assert s.top_n == 20

    def test_generate_signals_bullish(self):
        """매수 우위 시 상위 N종목 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=90.0,
                   factors={"momentum": 0.9}, strategy_id="momentum"),
            Signal(stock=self.universe[1], score=75.0,
                   factors={"momentum": 0.7}, strategy_id="momentum"),
            Signal(stock=self.universe[2], score=60.0,
                   factors={"momentum": 0.6}, strategy_id="momentum"),
            Signal(stock=self.universe[3], score=40.0,
                   factors={"momentum": 0.4}, strategy_id="momentum"),
            Signal(stock=self.universe[4], score=20.0,
                   factors={"momentum": 0.2}, strategy_id="momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 3  # top_n=3
        assert signals[0].stock.code == "005930"
        self.ranker.rank.assert_called_once()

    def test_generate_signals_bearish_reduces_strength(self):
        """매도 우위 시 시그널 강도 축소 (0.5배)."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"momentum": 0.8}, strategy_id="momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bearish", "pulse_score": -40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) >= 1
        assert signals[0].score == 40.0  # 80 * 0.5

    def test_factor_weights(self):
        """모멘텀 팩터 가중치 프리셋."""
        assert self.strategy.factor_weights["momentum"] == 0.6
        assert self.strategy.factor_weights["flow"] == 0.3
        assert self.strategy.factor_weights["volatility"] == 0.1
