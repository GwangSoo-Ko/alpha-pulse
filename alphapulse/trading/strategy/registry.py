"""전략 레지스트리.

전략 인스턴스를 등록/조회하는 중앙 관리자.
"""

from alphapulse.trading.strategy.base import BaseStrategy


class StrategyRegistry:
    """전략 등록/조회 레지스트리.

    Attributes:
        _strategies: strategy_id → BaseStrategy 매핑.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> None:
        """전략을 등록한다.

        Args:
            strategy: 등록할 전략 인스턴스.
        """
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> BaseStrategy:
        """전략을 조회한다.

        Args:
            strategy_id: 전략 고유 식별자.

        Returns:
            등록된 전략 인스턴스.

        Raises:
            KeyError: 미등록 전략.
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"미등록 전략: {strategy_id}")
        return self._strategies[strategy_id]

    def list_all(self) -> list[str]:
        """등록된 전략 ID 목록을 반환한다."""
        return list(self._strategies.keys())

    def contains(self, strategy_id: str) -> bool:
        """전략 등록 여부를 확인한다.

        Args:
            strategy_id: 전략 고유 식별자.

        Returns:
            등록되어 있으면 True.
        """
        return strategy_id in self._strategies
