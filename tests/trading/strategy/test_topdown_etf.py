"""TopDownETF 전략 테스트."""

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy


class TestTopDownETFStrategy:
    def setup_method(self):
        self.strategy = TopDownETFStrategy(config={})
        self.etf_universe = [
            Stock(code="122630", name="KODEX 레버리지", market="ETF"),
            Stock(code="069500", name="KODEX 200", market="ETF"),
            Stock(code="153130", name="KODEX 단기채권", market="ETF"),
            Stock(code="114800", name="KODEX 인버스", market="ETF"),
            Stock(code="252670", name="KODEX 200선물인버스2X", market="ETF"),
        ]

    def test_is_base_strategy(self):
        """BaseStrategy를 상속한다."""
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "topdown_etf"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.SIGNAL_DRIVEN

    def test_strong_bullish_signals(self):
        """강한 매수 시그널 → 레버리지 + KODEX 200."""
        ctx = {"pulse_signal": "strong_bullish", "pulse_score": 80}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0
        codes = [s.stock.code for s in signals]
        assert "122630" in codes  # 레버리지
        assert all(s.score > 0 for s in signals)

    def test_strong_bearish_signals(self):
        """강한 매도 시그널 → 인버스 + 채권 + 현금."""
        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        codes = [s.stock.code for s in signals]
        assert "252670" in codes  # 인버스2X
        assert "153130" in codes  # 단기채권

    def test_neutral_signals(self):
        """중립 시그널 → 채권 + KODEX 200 소량."""
        ctx = {"pulse_signal": "neutral", "pulse_score": 0}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0
        # 채권이 가장 높은 비중
        bond_signal = [s for s in signals if s.stock.code == "153130"]
        assert len(bond_signal) == 1

    def test_should_rebalance_on_signal_change(self):
        """시그널 레벨 변경 시 리밸런싱."""
        assert self.strategy.should_rebalance_signal_driven(
            prev_signal="neutral", curr_signal="strong_bullish"
        ) is True

    def test_no_rebalance_same_signal(self):
        """시그널 레벨 동일하면 리밸런싱 안 함."""
        assert self.strategy.should_rebalance_signal_driven(
            prev_signal="neutral", curr_signal="neutral"
        ) is False

    def test_unknown_signal_fallback(self):
        """알 수 없는 시그널 → neutral로 폴백."""
        ctx = {"pulse_signal": "unknown_signal", "pulse_score": 0}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0  # neutral 매핑 적용
