"""Trading 시스템 핵심 데이터 모델 정의."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class Stock:
    """종목 식별 정보. 불변 값 객체."""

    code: str
    name: str
    market: str
    sector: str = ""


@dataclass
class OHLCV:
    """일봉 OHLCV 데이터."""

    date: str
    open: int
    high: int
    low: int
    close: int
    volume: int
    market_cap: int = 0


@dataclass
class Position:
    """보유 포지션 상태."""

    stock: Stock
    quantity: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    weight: float
    strategy_id: str


@dataclass
class Order:
    """주문 요청 데이터."""

    stock: Stock
    side: str
    order_type: str
    quantity: int
    price: Optional[float]
    strategy_id: str
    reason: str = ""


@dataclass
class Signal:
    """전략 매매 시그널."""

    stock: Stock
    score: float
    factors: dict[str, float]
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioSnapshot:
    """포트폴리오 스냅샷 (일일 기준)."""

    date: str
    cash: float
    positions: list[Position]
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float


@dataclass
class StockOpinion:
    """AI 에이전트 종목 의견."""

    stock: Stock
    action: str
    reason: str
    confidence: float


@dataclass
class StrategySynthesis:
    """전략 종합 판단 결과 (AI 에이전트 출력)."""

    market_view: str
    conviction_level: float
    allocation_adjustment: dict[str, Any]
    stock_opinions: list[StockOpinion]
    risk_warnings: list[str]
    reasoning: str


@dataclass
class OrderResult:
    """주문 체결 결과."""

    order_id: str
    order: Order
    status: str
    filled_quantity: int
    filled_price: float
    commission: float
    tax: float
    filled_at: datetime


@dataclass
class RiskDecision:
    """리스크 검증 결정."""

    action: str
    reason: str
    adjusted_quantity: Optional[int]


@dataclass
class RiskAlert:
    """리스크 경보 알림."""

    level: str
    category: str
    message: str
    current_value: float
    limit_value: float
