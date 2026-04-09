"""OrderMonitor 테스트 — 주문 상태 추적 + 알림.

브로커 get_order_status를 폴링하여 체결 상태를 추적한다.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from alphapulse.trading.broker.monitor import OrderMonitor
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, OrderResult, Stock


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def sample_order(samsung):
    return Order(
        stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
        quantity=10, price=72000, strategy_id="momentum",
    )


class TestOrderMonitorInit:
    """OrderMonitor 초기화 테스트."""

    def test_creates_with_broker(self):
        """브로커와 콜백으로 초기화한다."""
        mock_broker = MagicMock()
        monitor = OrderMonitor(broker=mock_broker)
        assert monitor.broker is mock_broker
        assert monitor.pending_orders == {}

    def test_creates_with_callback(self):
        """체결 콜백을 등록한다."""
        mock_broker = MagicMock()
        mock_callback = MagicMock()
        monitor = OrderMonitor(broker=mock_broker, on_fill=mock_callback)
        assert monitor.on_fill is mock_callback


class TestTrackOrder:
    """주문 등록/추적 테스트."""

    def test_add_order(self, sample_order):
        """미체결 주문을 추적 목록에 등록한다."""
        mock_broker = MagicMock()
        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", sample_order)
        assert "ORD001" in monitor.pending_orders
        assert monitor.pending_orders["ORD001"] is sample_order

    def test_remove_order(self, sample_order):
        """체결 완료된 주문을 제거한다."""
        mock_broker = MagicMock()
        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", sample_order)
        monitor.remove_order("ORD001")
        assert "ORD001" not in monitor.pending_orders


class TestPollOrders:
    """주문 상태 폴링 테스트."""

    def test_poll_detects_fill(self, sample_order, samsung):
        """체결된 주문을 감지하고 콜백을 호출한다."""
        mock_broker = MagicMock()
        mock_callback = MagicMock()
        filled_result = OrderResult(
            order_id="ORD001",
            order=sample_order,
            status="filled",
            filled_quantity=10,
            filled_price=72000.0,
            commission=108.0,
            tax=0.0,
            filled_at=datetime.now(),
        )
        mock_broker.get_order_status.return_value = filled_result

        monitor = OrderMonitor(broker=mock_broker, on_fill=mock_callback)
        monitor.add_order("ORD001", sample_order)
        results = monitor.poll()

        assert len(results) == 1
        assert results[0].status == "filled"
        mock_callback.assert_called_once_with(filled_result)
        assert "ORD001" not in monitor.pending_orders

    def test_poll_keeps_pending(self, sample_order):
        """미체결 주문은 추적 목록에 유지한다."""
        mock_broker = MagicMock()
        pending_result = OrderResult(
            order_id="ORD001",
            order=sample_order,
            status="pending",
            filled_quantity=0,
            filled_price=0.0,
            commission=0.0,
            tax=0.0,
            filled_at=None,
        )
        mock_broker.get_order_status.return_value = pending_result

        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", sample_order)
        results = monitor.poll()

        assert len(results) == 0
        assert "ORD001" in monitor.pending_orders

    def test_poll_partial_fill(self, sample_order):
        """부분 체결도 콜백을 호출하지만 추적은 유지한다."""
        mock_broker = MagicMock()
        mock_callback = MagicMock()
        partial_result = OrderResult(
            order_id="ORD001",
            order=sample_order,
            status="partial",
            filled_quantity=5,
            filled_price=72000.0,
            commission=54.0,
            tax=0.0,
            filled_at=None,
        )
        mock_broker.get_order_status.return_value = partial_result

        monitor = OrderMonitor(broker=mock_broker, on_fill=mock_callback)
        monitor.add_order("ORD001", sample_order)
        results = monitor.poll()

        assert len(results) == 1
        assert results[0].status == "partial"
        mock_callback.assert_called_once_with(partial_result)
        # 부분 체결은 추적 유지
        assert "ORD001" in monitor.pending_orders

    def test_poll_rejected(self, sample_order):
        """거부된 주문은 추적에서 제거한다."""
        mock_broker = MagicMock()
        rejected_result = OrderResult(
            order_id="ORD001",
            order=sample_order,
            status="rejected",
            filled_quantity=0,
            filled_price=0.0,
            commission=0.0,
            tax=0.0,
            filled_at=None,
        )
        mock_broker.get_order_status.return_value = rejected_result

        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", sample_order)
        results = monitor.poll()

        assert len(results) == 1
        assert "ORD001" not in monitor.pending_orders

    def test_poll_multiple_orders(self, samsung):
        """여러 주문을 동시에 추적한다."""
        mock_broker = MagicMock()
        order1 = Order(stock=samsung, side="BUY", order_type="LIMIT",
                        quantity=10, price=72000, strategy_id="m")
        order2 = Order(stock=samsung, side="SELL", order_type="MARKET",
                        quantity=5, price=None, strategy_id="v")

        def get_status(oid):
            if oid == "ORD001":
                return OrderResult(
                    order_id="ORD001", order=order1, status="filled",
                    filled_quantity=10, filled_price=72000.0,
                    commission=108.0, tax=0.0, filled_at=datetime.now(),
                )
            return OrderResult(
                order_id="ORD002", order=order2, status="pending",
                filled_quantity=0, filled_price=0.0,
                commission=0.0, tax=0.0, filled_at=None,
            )

        mock_broker.get_order_status.side_effect = get_status

        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", order1)
        monitor.add_order("ORD002", order2)
        results = monitor.poll()

        assert len(results) == 1
        assert results[0].order_id == "ORD001"
        assert "ORD001" not in monitor.pending_orders
        assert "ORD002" in monitor.pending_orders

    def test_poll_error_handling(self, sample_order):
        """폴링 중 예외가 발생해도 다른 주문은 계속 추적한다."""
        mock_broker = MagicMock()
        mock_broker.get_order_status.side_effect = Exception("API 오류")

        monitor = OrderMonitor(broker=mock_broker)
        monitor.add_order("ORD001", sample_order)
        results = monitor.poll()

        assert len(results) == 0
        # 오류 발생해도 추적 유지
        assert "ORD001" in monitor.pending_orders


class TestGetSummary:
    """추적 현황 요약 테스트."""

    def test_summary_empty(self):
        """추적 주문이 없으면 빈 요약."""
        monitor = OrderMonitor(broker=MagicMock())
        summary = monitor.get_summary()
        assert summary["pending_count"] == 0
        assert summary["order_ids"] == []

    def test_summary_with_orders(self, sample_order):
        """추적 중인 주문 정보를 요약한다."""
        monitor = OrderMonitor(broker=MagicMock())
        monitor.add_order("ORD001", sample_order)
        monitor.add_order("ORD002", sample_order)
        summary = monitor.get_summary()
        assert summary["pending_count"] == 2
        assert set(summary["order_ids"]) == {"ORD001", "ORD002"}
