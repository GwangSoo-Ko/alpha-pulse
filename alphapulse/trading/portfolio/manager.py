"""포트폴리오 매니저.

전략 시그널을 목표 포트폴리오로 변환하고 리밸런싱 주문을 생성한다.
PositionSizer, PortfolioOptimizer, Rebalancer를 통합한다.
"""

import logging

from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Signal
from alphapulse.trading.portfolio.models import TargetPortfolio
from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer
from alphapulse.trading.portfolio.position_sizer import PositionSizer
from alphapulse.trading.portfolio.rebalancer import Rebalancer

logger = logging.getLogger(__name__)


class PortfolioManager:
    """목표 포트폴리오 산출 및 리밸런싱 주문 생성 통합 관리자.

    Attributes:
        position_sizer: 포지션 사이징 도구.
        optimizer: 포트폴리오 최적화기.
        rebalancer: 리밸런서.
        cost_model: 거래 비용 모델.
    """

    def __init__(
        self,
        position_sizer: PositionSizer,
        optimizer: PortfolioOptimizer,
        rebalancer: Rebalancer,
        cost_model: CostModel,
    ) -> None:
        """PortfolioManager를 초기화한다.

        Args:
            position_sizer: 포지션 사이징 도구.
            optimizer: 포트폴리오 최적화기.
            rebalancer: 리밸런서.
            cost_model: 거래 비용 모델.
        """
        self.position_sizer = position_sizer
        self.optimizer = optimizer
        self.rebalancer = rebalancer
        self.cost_model = cost_model

    def update_target(
        self,
        strategy_signals: dict[str, list[Signal]],
        allocations: dict[str, float],
        current: PortfolioSnapshot,
        prices: dict[str, float],
    ) -> TargetPortfolio:
        """목표 포트폴리오를 산출한다.

        Args:
            strategy_signals: 전략ID → Signal 리스트.
            allocations: 전략ID → 배분 비율.
            current: 현재 포트폴리오 스냅샷.
            prices: 종목코드 → 현재가.

        Returns:
            TargetPortfolio (목표 비중, 현금 비중, 전략 배분).
        """
        target_weights: dict[str, float] = {}

        for strategy_id, signals in strategy_signals.items():
            alloc_ratio = allocations.get(strategy_id, 0.0)
            if alloc_ratio <= 0 or not signals:
                continue

            # 전략 내 종목별 균등 배분
            n_stocks = len(signals)
            per_stock_weight = self.position_sizer.equal_weight(n_stocks)

            for sig in signals:
                code = sig.stock.code
                # 전략 배분 비율 * 종목 내 비중
                weight = alloc_ratio * per_stock_weight
                # 기존 비중과 합산 (다수 전략이 동일 종목 보유 가능)
                target_weights[code] = target_weights.get(code, 0.0) + weight

        total_position_weight = sum(target_weights.values())
        cash_weight = max(0.0, 1.0 - total_position_weight)

        return TargetPortfolio(
            date=current.date,
            positions=target_weights,
            cash_weight=cash_weight,
            strategy_allocations=dict(allocations),
        )

    def generate_orders(
        self,
        target: TargetPortfolio,
        current: PortfolioSnapshot,
        prices: dict[str, float],
        strategy_id: str,
    ) -> list[Order]:
        """현재 → 목표 차이를 주문으로 변환한다.

        Args:
            target: 목표 포트폴리오 (TargetPortfolio).
            current: 현재 포트폴리오 스냅샷.
            prices: 종목코드 → 현재가.
            strategy_id: 전략 ID.

        Returns:
            Order 리스트.
        """
        return self.rebalancer.generate_orders(
            target_weights=target.positions,
            current=current,
            prices=prices,
            strategy_id=strategy_id,
        )
