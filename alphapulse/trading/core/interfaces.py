"""Trading 시스템 Protocol 인터페이스.

모든 서브시스템은 이 인터페이스를 통해 소통한다.
구현체 교체가 자유롭다 (예: SimBroker → KISBroker).
"""

from typing import Protocol, runtime_checkable

from alphapulse.trading.core.models import (
    OHLCV,
    Order,
    OrderResult,
    PortfolioSnapshot,
    Position,
    RiskAlert,
    RiskDecision,
    Signal,
    Stock,
)


@runtime_checkable
class DataProvider(Protocol):
    """종목 데이터 소스 인터페이스."""

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """일봉 데이터를 조회한다."""
        ...

    def get_financials(self, code: str) -> dict:
        """재무제표 데이터를 조회한다."""
        ...

    def get_investor_flow(self, code: str, days: int) -> dict:
        """종목별 투자자 수급을 조회한다."""
        ...

    def get_short_interest(self, code: str, days: int) -> dict:
        """공매도/신용 잔고를 조회한다."""
        ...


@runtime_checkable
class StrategyProtocol(Protocol):
    """매매 전략 인터페이스.

    모든 전략 구현체는 이 Protocol을 따른다.
    """
    strategy_id: str
    rebalance_freq: str

    def generate_signals(self, universe: list[Stock],
                          market_context: dict) -> list[Signal]:
        """종목별 매매 시그널을 생성한다."""
        ...


@runtime_checkable
class RiskChecker(Protocol):
    """리스크 검증 인터페이스.

    주문 및 포트폴리오의 리스크를 검증한다.
    """

    def check_order(self, order: Order,
                     portfolio: PortfolioSnapshot) -> RiskDecision:
        """개별 주문의 리스크를 검증한다."""
        ...

    def check_portfolio(self, portfolio: PortfolioSnapshot) -> list[RiskAlert]:
        """포트폴리오 전체 리스크를 검증한다."""
        ...


@runtime_checkable
class Broker(Protocol):
    """주문 집행 인터페이스."""

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 제출한다."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """주문을 취소한다."""
        ...

    def get_balance(self) -> dict:
        """계좌 잔고를 조회한다."""
        ...

    def get_positions(self) -> list[Position]:
        """보유 포지션을 조회한다."""
        ...

    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태를 조회한다."""
        ...
