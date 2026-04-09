"""OrderMonitor — 주문 상태 추적 + 체결 알림.

미체결 주문을 폴링(polling)으로 추적하고,
체결/거부 시 콜백을 호출한다.
"""

import logging
from typing import Callable

from alphapulse.trading.core.models import Order, OrderResult

logger = logging.getLogger(__name__)


class OrderMonitor:
    """주문 상태 추적기.

    브로커의 get_order_status()를 폴링하여 미체결 주문의 상태를 확인한다.
    체결(filled), 부분 체결(partial), 거부(rejected) 시 콜백을 호출한다.

    Attributes:
        broker: Broker Protocol 구현체.
        on_fill: 체결/부분체결 시 호출할 콜백 함수.
        pending_orders: 미체결 주문 딕셔너리 {order_id: Order}.
    """

    def __init__(
        self,
        broker,
        on_fill: Callable[[OrderResult], None] | None = None,
    ) -> None:
        """OrderMonitor를 초기화한다.

        Args:
            broker: Broker Protocol 구현체 (get_order_status 메서드 필요).
            on_fill: 체결/부분체결 시 호출할 콜백. None이면 콜백 없음.
        """
        self.broker = broker
        self.on_fill = on_fill
        self.pending_orders: dict[str, Order] = {}

    def add_order(self, order_id: str, order: Order) -> None:
        """미체결 주문을 추적 목록에 등록한다.

        Args:
            order_id: 주문번호.
            order: 주문 객체.
        """
        self.pending_orders[order_id] = order
        logger.info("주문 추적 등록: %s (%s %s %s주)",
                     order_id, order.side, order.stock.code, order.quantity)

    def remove_order(self, order_id: str) -> None:
        """주문을 추적 목록에서 제거한다.

        Args:
            order_id: 주문번호.
        """
        self.pending_orders.pop(order_id, None)
        logger.info("주문 추적 해제: %s", order_id)

    def poll(self) -> list[OrderResult]:
        """미체결 주문을 폴링하여 상태를 업데이트한다.

        체결(filled)/거부(rejected) 주문은 추적에서 제거한다.
        부분 체결(partial)은 콜백 호출 후 추적을 유지한다.

        Returns:
            상태가 변경된 주문 결과 리스트 (filled, partial, rejected).
        """
        changed: list[OrderResult] = []
        order_ids = list(self.pending_orders.keys())

        for order_id in order_ids:
            try:
                result = self.broker.get_order_status(order_id)
            except Exception as e:
                logger.warning("주문 상태 조회 실패: %s — %s", order_id, e)
                continue

            if result.status == "pending":
                continue

            changed.append(result)

            if result.status in ("filled", "rejected"):
                self.remove_order(order_id)

            if result.status in ("filled", "partial") and self.on_fill:
                try:
                    self.on_fill(result)
                except Exception as e:
                    logger.error("체결 콜백 오류: %s — %s", order_id, e)

        return changed

    def get_summary(self) -> dict:
        """미체결 주문 추적 현황을 요약한다.

        Returns:
            {"pending_count": int, "order_ids": list[str]}.
        """
        return {
            "pending_count": len(self.pending_orders),
            "order_ids": list(self.pending_orders.keys()),
        }
