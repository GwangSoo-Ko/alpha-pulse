"""전략 기본 클래스(ABC).

모든 매매 전략은 이 클래스를 상속한다.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock


class BaseStrategy(ABC):
    """모든 전략의 기본 클래스.

    Attributes:
        strategy_id: 전략 고유 식별자.
        rebalance_freq: 리밸런싱 주기.
        config: 전략별 파라미터 딕셔너리.
    """

    strategy_id: str
    rebalance_freq: RebalanceFreq

    def __init__(self, config: dict) -> None:
        """BaseStrategy를 초기화한다.

        Args:
            config: 전략별 파라미터 (top_n, factor_weights 등).
        """
        self.config = config

    @abstractmethod
    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """종목별 매매 시그널을 생성한다.

        Args:
            universe: 투자 유니버스 종목 리스트.
            market_context: Market Pulse 등 시장 상황 딕셔너리.

        Returns:
            종목별 Signal 리스트 (점수순 정렬).
        """
        ...

    def should_rebalance(
        self,
        last_rebalance: str,
        current_date: str,
        market_context: dict,
    ) -> bool:
        """리밸런싱 시점인지 판단한다.

        Args:
            last_rebalance: 마지막 리밸런싱 날짜 (YYYYMMDD).
            current_date: 현재 날짜 (YYYYMMDD).
            market_context: Market Pulse 등 시장 상황 딕셔너리.

        Returns:
            리밸런싱해야 하면 True.
        """
        if self.rebalance_freq == RebalanceFreq.DAILY:
            return True
        elif self.rebalance_freq == RebalanceFreq.WEEKLY:
            dt = datetime.strptime(current_date, "%Y%m%d")
            return dt.weekday() == 0  # 월요일
        elif self.rebalance_freq == RebalanceFreq.SIGNAL_DRIVEN:
            return False  # 서브클래스에서 오버라이드
        return False
