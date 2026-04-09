"""드로다운 관리자.

포트폴리오 고점 대비 하락률을 모니터링하고,
한도 초과 시 자동 디레버리징 주문을 생성한다.
"""

import logging

from alphapulse.trading.core.enums import DrawdownAction, OrderType, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot
from alphapulse.trading.risk.limits import RiskLimits

logger = logging.getLogger(__name__)


class DrawdownManager:
    """드로다운 모니터링 + 자동 디레버리징.

    Attributes:
        limits: 리스크 한도.
        peak_value: 포트폴리오 역대 최고 가치.
    """

    def __init__(self, limits: RiskLimits) -> None:
        """DrawdownManager를 초기화한다.

        Args:
            limits: 리스크 한도 설정.
        """
        self.limits = limits
        self.peak_value: float = 0.0

    def update_peak(self, current_value: float) -> None:
        """포트폴리오 고점을 갱신한다.

        Args:
            current_value: 현재 포트폴리오 총 가치.
        """
        self.peak_value = max(self.peak_value, current_value)

    def check(self, portfolio: PortfolioSnapshot) -> DrawdownAction:
        """드로다운 상태를 확인한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            DrawdownAction (NORMAL | WARN | DELEVERAGE).
        """
        self.update_peak(portfolio.total_value)

        if self.peak_value <= 0:
            return DrawdownAction.NORMAL

        drawdown = (self.peak_value - portfolio.total_value) / self.peak_value

        if drawdown < self.limits.max_drawdown_soft:
            return DrawdownAction.NORMAL
        elif drawdown < self.limits.max_drawdown_hard:
            logger.warning(
                "드로다운 경고: %.1f%% (소프트 한도: %.1f%%)",
                drawdown * 100,
                self.limits.max_drawdown_soft * 100,
            )
            return DrawdownAction.WARN
        else:
            logger.error(
                "드로다운 한도 초과: %.1f%% (하드 한도: %.1f%%) -> 디레버리징",
                drawdown * 100,
                self.limits.max_drawdown_hard * 100,
            )
            return DrawdownAction.DELEVERAGE

    def generate_deleverage_orders(
        self,
        portfolio: PortfolioSnapshot,
    ) -> list[Order]:
        """전 포지션 50% 축소 주문을 생성한다.

        손실이 큰 포지션부터 우선 매도한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            디레버리징 매도 주문 리스트.
        """
        if not portfolio.positions:
            return []

        # 손실 큰 순서로 정렬
        sorted_positions = sorted(
            portfolio.positions,
            key=lambda p: p.unrealized_pnl,
        )

        orders: list[Order] = []
        for pos in sorted_positions:
            sell_qty = pos.quantity // 2  # 50% 축소
            if sell_qty <= 0:
                continue
            orders.append(
                Order(
                    stock=pos.stock,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=sell_qty,
                    price=None,
                    strategy_id=pos.strategy_id,
                    reason="디레버리징: 드로다운 한도 초과 — 50% 축소",
                ),
            )

        return orders
