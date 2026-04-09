"""KISBroker 테스트 — 실매매 Broker Protocol 구현.

KISClient는 mock으로 처리한다. AuditLogger도 mock.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.broker.kis_broker import KISBroker
from alphapulse.trading.broker.kis_client import KISClient
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, Stock


@pytest.fixture
def mock_client():
    """실전 모드 KISClient mock."""
    client = MagicMock(spec=KISClient)
    client.is_paper = False
    client.account_no = "12345678-01"
    return client


@pytest.fixture
def mock_audit():
    """AuditLogger mock."""
    return MagicMock()


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


class TestKISBrokerInit:
    """KISBroker 초기화 테스트."""

    def test_creates_with_live_client(self, mock_client, mock_audit):
        """실전 클라이언트로 생성한다."""
        broker = KISBroker(client=mock_client, audit=mock_audit)
        assert broker.client is mock_client

    def test_rejects_paper_client(self, mock_audit):
        """모의투자 클라이언트는 거부한다."""
        paper_client = MagicMock(spec=KISClient)
        paper_client.is_paper = True
        with pytest.raises(ValueError, match="실매매 브로커"):
            KISBroker(client=paper_client, audit=mock_audit)


class TestSubmitOrder:
    """주문 제출 테스트."""

    def test_buy_limit_order(self, mock_client, mock_audit, samsung):
        """지정가 매수 주문을 전달하고 OrderResult를 반환한다."""
        mock_client.place_order.return_value = {
            "rt_cd": "0",
            "output": {
                "ORNO": "0000123456",
                "ORD_TMD": "092530",
            },
        }
        broker = KISBroker(client=mock_client, audit=mock_audit)
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=10, price=72000, strategy_id="momentum",
            reason="팩터 상위",
        )
        result = broker.submit_order(order)
        assert result.order_id == "0000123456"
        assert result.order is order
        assert result.status == "pending"
        mock_client.place_order.assert_called_once_with(
            code="005930", side="BUY", qty=10,
            price=72000, order_type="LIMIT",
        )
        mock_audit.log_order.assert_called_once()

    def test_sell_market_order(self, mock_client, mock_audit, samsung):
        """시장가 매도 주문을 전달한다."""
        mock_client.place_order.return_value = {
            "rt_cd": "0",
            "output": {"ORNO": "0000123457"},
        }
        broker = KISBroker(client=mock_client, audit=mock_audit)
        order = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=5, price=None, strategy_id="value",
        )
        result = broker.submit_order(order)
        assert result.order_id == "0000123457"
        mock_client.place_order.assert_called_once_with(
            code="005930", side="SELL", qty=5,
            price=0, order_type="MARKET",
        )

    def test_rejected_order(self, mock_client, mock_audit, samsung):
        """거부된 주문은 status가 rejected이다."""
        mock_client.place_order.return_value = {
            "rt_cd": "1",
            "msg1": "주문 가능 금액 부족",
            "output": {},
        }
        broker = KISBroker(client=mock_client, audit=mock_audit)
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=10000, price=72000, strategy_id="momentum",
        )
        result = broker.submit_order(order)
        assert result.status == "rejected"
        assert result.filled_quantity == 0


class TestCancelOrder:
    """주문 취소 테스트."""

    def test_cancel_success(self, mock_client, mock_audit):
        """정상적으로 주문을 취소한다."""
        mock_client.cancel_order.return_value = {"rt_cd": "0"}
        broker = KISBroker(client=mock_client, audit=mock_audit)
        assert broker.cancel_order("0000123456") is True

    def test_cancel_failure(self, mock_client, mock_audit):
        """취소 실패 시 False를 반환한다."""
        mock_client.cancel_order.return_value = {"rt_cd": "1", "msg1": "이미 체결됨"}
        broker = KISBroker(client=mock_client, audit=mock_audit)
        assert broker.cancel_order("0000123456") is False


class TestGetPositions:
    """보유 종목 조회 테스트."""

    def test_get_positions_maps_to_position(self, mock_client, mock_audit):
        """KIS API 응답을 Position 데이터 모델로 변환한다."""
        mock_client.get_positions.return_value = [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "100",
                "pchs_avg_pric": "72000.00",
                "prpr": "73000",
                "evlu_pfls_amt": "100000",
            },
        ]
        broker = KISBroker(client=mock_client, audit=mock_audit)
        positions = broker.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.stock.code == "005930"
        assert pos.stock.name == "삼성전자"
        assert pos.quantity == 100
        assert pos.avg_price == 72000.0
        assert pos.current_price == 73000
        assert pos.unrealized_pnl == 100000

    def test_empty_positions(self, mock_client, mock_audit):
        """보유 종목이 없으면 빈 리스트를 반환한다."""
        mock_client.get_positions.return_value = []
        broker = KISBroker(client=mock_client, audit=mock_audit)
        assert broker.get_positions() == []


class TestGetBalance:
    """예수금 조회 테스트."""

    def test_get_balance(self, mock_client, mock_audit):
        """예수금 정보를 딕셔너리로 반환한다."""
        mock_client.get_balance.return_value = {
            "rt_cd": "0",
            "output": {
                "dnca_tot_amt": "50000000",
                "tot_evlu_amt": "108350000",
            },
        }
        broker = KISBroker(client=mock_client, audit=mock_audit)
        balance = broker.get_balance()
        assert "dnca_tot_amt" in balance or "output" in balance


class TestGetOrderStatus:
    """주문 상태 조회 테스트."""

    def test_get_order_status_filled(self, mock_client, mock_audit, samsung):
        """체결된 주문의 상태를 반환한다."""
        mock_client.get_order_history.return_value = [
            {
                "odno": "0000123456",
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "sll_buy_dvsn_cd": "02",
                "ord_qty": "10",
                "tot_ccld_qty": "10",
                "avg_prvs": "72000",
                "ord_dvsn_cd": "00",
            },
        ]
        broker = KISBroker(client=mock_client, audit=mock_audit)
        result = broker.get_order_status("0000123456")
        assert result.order_id == "0000123456"
        assert result.status == "filled"
        assert result.filled_quantity == 10
        assert result.filled_price == 72000.0
