"""PaperBroker — 한투 모의투자 API Broker Protocol 구현체.

KISBroker와 동일 구조이나, 모의투자 서버(openapivts)에 접속하는
KISClient(is_paper=True)만 허용한다.
실제 자금이 이동하지 않으므로 실매매 전 전략 검증에 사용한다.
"""

import logging
from datetime import datetime

from alphapulse.trading.broker.kis_client import KISClient
from alphapulse.trading.core.models import Order, OrderResult, Position, Stock

logger = logging.getLogger(__name__)


class PaperBroker:
    """한투 모의투자 브로커.

    Broker Protocol을 구현한다. 모의투자 클라이언트(is_paper=True)만 허용한다.

    Attributes:
        client: KIS REST API 클라이언트 (모의투자).
        audit: 감사 추적 로거.
    """

    def __init__(self, client: KISClient, audit) -> None:
        """PaperBroker를 초기화한다.

        Args:
            client: KIS REST API 클라이언트 (is_paper=True 필수).
            audit: AuditLogger 인스턴스.

        Raises:
            ValueError: 실전 클라이언트를 전달한 경우.
        """
        if not client.is_paper:
            raise ValueError(
                "모의투자 브로커에 실전 클라이언트를 사용할 수 없습니다. "
                "is_paper=True인 KISClient를 전달하세요."
            )
        self.client = client
        self.audit = audit

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 모의투자 서버에 제출한다.

        Args:
            order: 매매 주문.

        Returns:
            주문 결과. API 성공 시 status="pending", 실패 시 status="rejected".
        """
        try:
            raw = self.client.place_order(
                code=order.stock.code,
                side=order.side,
                qty=order.quantity,
                price=int(order.price) if order.price else 0,
                order_type=order.order_type,
            )
        except Exception as e:
            logger.error("모의투자 주문 제출 실패: %s", e)
            result = OrderResult(
                order_id="",
                order=order,
                status="rejected",
                filled_quantity=0,
                filled_price=0.0,
                commission=0.0,
                tax=0.0,
                filled_at=None,
            )
            self.audit.log_order(order, result)
            return result

        rt_cd = raw.get("rt_cd", "1")
        output = raw.get("output", {})

        if rt_cd == "0":
            order_id = output.get("ORNO", "")
            result = OrderResult(
                order_id=order_id,
                order=order,
                status="pending",
                filled_quantity=0,
                filled_price=0.0,
                commission=0.0,
                tax=0.0,
                filled_at=None,
            )
        else:
            result = OrderResult(
                order_id="",
                order=order,
                status="rejected",
                filled_quantity=0,
                filled_price=0.0,
                commission=0.0,
                tax=0.0,
                filled_at=None,
            )

        self.audit.log_order(order, result)
        return result

    def cancel_order(self, order_id: str) -> bool:
        """주문을 취소한다.

        Args:
            order_id: 주문번호.

        Returns:
            취소 성공 여부.
        """
        try:
            raw = self.client.cancel_order(order_no=order_id)
            return raw.get("rt_cd") == "0"
        except Exception as e:
            logger.error("모의투자 주문 취소 실패: %s %s", order_id, e)
            return False

    def get_balance(self) -> dict:
        """예수금/자산 정보를 조회한다.

        Returns:
            예수금 정보 딕셔너리.
        """
        return self.client.get_balance()

    def get_positions(self) -> list[Position]:
        """보유 종목을 Position 데이터 모델로 반환한다.

        Returns:
            보유 포지션 리스트.
        """
        raw_positions = self.client.get_positions()
        positions = []
        for raw in raw_positions:
            pos = self._to_position(raw)
            positions.append(pos)
        return positions

    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 체결 상태를 조회한다.

        Args:
            order_id: 주문번호.

        Returns:
            주문 체결 결과.
        """
        today = datetime.now().strftime("%Y%m%d")
        orders = self.client.get_order_history(date=today)

        for raw in orders:
            if raw.get("odno") == order_id:
                return self._parse_order_status(raw)

        return OrderResult(
            order_id=order_id,
            order=Order(
                stock=Stock(code="", name="", market=""),
                side="BUY", order_type="MARKET",
                quantity=0, price=None, strategy_id="",
            ),
            status="pending",
            filled_quantity=0,
            filled_price=0.0,
            commission=0.0,
            tax=0.0,
            filled_at=None,
        )

    def _to_position(self, raw: dict) -> Position:
        """KIS API 응답을 Position 데이터 모델로 변환한다."""
        stock = Stock(
            code=raw.get("pdno", ""),
            name=raw.get("prdt_name", ""),
            market="KOSPI",
        )
        return Position(
            stock=stock,
            quantity=int(raw.get("hldg_qty", "0")),
            avg_price=float(raw.get("pchs_avg_pric", "0")),
            current_price=float(raw.get("prpr", "0")),
            unrealized_pnl=float(raw.get("evlu_pfls_amt", "0")),
            weight=0.0,
            strategy_id="",
        )

    def _parse_order_status(self, raw: dict) -> OrderResult:
        """KIS 주문 내역을 OrderResult로 변환한다."""
        order_id = raw.get("odno", "")
        ord_qty = int(raw.get("ord_qty", "0"))
        filled_qty = int(raw.get("tot_ccld_qty", "0"))
        filled_price = float(raw.get("avg_prvs", "0"))

        if filled_qty == 0:
            status = "pending"
        elif filled_qty >= ord_qty:
            status = "filled"
        else:
            status = "partial"

        side_code = raw.get("sll_buy_dvsn_cd", "02")
        side = "SELL" if side_code == "01" else "BUY"

        stock = Stock(
            code=raw.get("pdno", ""),
            name=raw.get("prdt_name", ""),
            market="KOSPI",
        )
        order = Order(
            stock=stock,
            side=side,
            order_type="LIMIT",
            quantity=ord_qty,
            price=filled_price if filled_price > 0 else None,
            strategy_id="",
        )

        return OrderResult(
            order_id=order_id,
            order=order,
            status=status,
            filled_quantity=filled_qty,
            filled_price=filled_price,
            commission=0.0,
            tax=0.0,
            filled_at=datetime.now() if status == "filled" else None,
        )
