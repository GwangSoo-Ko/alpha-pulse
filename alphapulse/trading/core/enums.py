"""Trading 시스템 열거형 정의."""

from enum import StrEnum


class Side(StrEnum):
    """매매 방향."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """주문 유형."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TradingMode(StrEnum):
    """실행 모드."""

    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class RebalanceFreq(StrEnum):
    """리밸런싱 주기."""

    DAILY = "daily"
    WEEKLY = "weekly"
    SIGNAL_DRIVEN = "signal_driven"


class RiskAction(StrEnum):
    """리스크 검증 결과."""

    APPROVE = "APPROVE"
    REDUCE_SIZE = "REDUCE_SIZE"
    REJECT = "REJECT"


class DrawdownAction(StrEnum):
    """드로다운 대응 수준."""

    NORMAL = "NORMAL"
    WARN = "WARN"
    DELEVERAGE = "DELEVERAGE"
