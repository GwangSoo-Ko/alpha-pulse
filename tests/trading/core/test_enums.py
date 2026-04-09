"""Trading 열거형 테스트."""

from alphapulse.trading.core.enums import (
    DrawdownAction,
    OrderType,
    RebalanceFreq,
    RiskAction,
    Side,
    TradingMode,
)


class TestSide:
    def test_values(self):
        assert Side.BUY == "BUY"
        assert Side.SELL == "SELL"

    def test_is_string(self):
        assert isinstance(Side.BUY, str)


class TestOrderType:
    def test_values(self):
        assert OrderType.MARKET == "MARKET"
        assert OrderType.LIMIT == "LIMIT"


class TestTradingMode:
    def test_values(self):
        assert TradingMode.BACKTEST == "backtest"
        assert TradingMode.PAPER == "paper"
        assert TradingMode.LIVE == "live"


class TestRebalanceFreq:
    def test_values(self):
        assert RebalanceFreq.DAILY == "daily"
        assert RebalanceFreq.WEEKLY == "weekly"
        assert RebalanceFreq.SIGNAL_DRIVEN == "signal_driven"


class TestRiskAction:
    def test_values(self):
        assert RiskAction.APPROVE == "APPROVE"
        assert RiskAction.REDUCE_SIZE == "REDUCE_SIZE"
        assert RiskAction.REJECT == "REJECT"


class TestDrawdownAction:
    def test_values(self):
        assert DrawdownAction.NORMAL == "NORMAL"
        assert DrawdownAction.WARN == "WARN"
        assert DrawdownAction.DELEVERAGE == "DELEVERAGE"
