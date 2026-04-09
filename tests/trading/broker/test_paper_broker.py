"""PaperBroker 테스트 — 한투 모의투자 Broker Protocol 구현.

KISClient는 mock으로 처리한다. AuditLogger도 mock.
PaperBroker는 KISBroker와 동일 구조이나 is_paper=True 클라이언트만 허용한다.
"""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.broker.kis_client import KISClient
from alphapulse.trading.broker.paper_broker import PaperBroker
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, Stock


@pytest.fixture
def mock_client():
    """모의투자 모드 KISClient mock."""
    client = MagicMock(spec=KISClient)
    client.is_paper = True
    client.account_no = "12345678-01"
    return client


@pytest.fixture
def mock_audit():
    return MagicMock()


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


class TestPaperBrokerInit:
    """PaperBroker 초기화 테스트."""

    def test_creates_with_paper_client(self, mock_client, mock_audit):
        """모의투자 클라이언트로 생성한다."""
        broker = PaperBroker(client=mock_client, audit=mock_audit)
        assert broker.client is mock_client

    def test_rejects_live_client(self, mock_audit):
        """실전 클라이언트는 거부한다."""
        live_client = MagicMock(spec=KISClient)
        live_client.is_paper = False
        with pytest.raises(ValueError, match="모의투자 브로커"):
            PaperBroker(client=live_client, audit=mock_audit)


class TestPaperSubmitOrder:
    """모의투자 주문 제출 테스트."""

    def test_buy_order(self, mock_client, mock_audit, samsung):
        """모의투자 서버에 매수 주문을 전달한다."""
        mock_client.place_order.return_value = {
            "rt_cd": "0",
            "output": {"ORNO": "V000123456"},
        }
        broker = PaperBroker(client=mock_client, audit=mock_audit)
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=10, price=72000, strategy_id="momentum",
        )
        result = broker.submit_order(order)
        assert result.order_id == "V000123456"
        assert result.status == "pending"
        mock_audit.log_order.assert_called_once()

    def test_sell_order(self, mock_client, mock_audit, samsung):
        """모의투자 서버에 매도 주문을 전달한다."""
        mock_client.place_order.return_value = {
            "rt_cd": "0",
            "output": {"ORNO": "V000123457"},
        }
        broker = PaperBroker(client=mock_client, audit=mock_audit)
        order = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=5, price=None, strategy_id="value",
        )
        result = broker.submit_order(order)
        assert result.order_id == "V000123457"


class TestPaperCancelOrder:
    """모의투자 주문 취소 테스트."""

    def test_cancel_success(self, mock_client, mock_audit):
        mock_client.cancel_order.return_value = {"rt_cd": "0"}
        broker = PaperBroker(client=mock_client, audit=mock_audit)
        assert broker.cancel_order("V000123456") is True


class TestPaperGetPositions:
    """모의투자 보유 종목 조회 테스트."""

    def test_get_positions(self, mock_client, mock_audit):
        """KIS 모의투자 API 응답을 Position으로 변환한다."""
        mock_client.get_positions.return_value = [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "50",
                "pchs_avg_pric": "71000.00",
                "prpr": "72500",
                "evlu_pfls_amt": "75000",
            },
        ]
        broker = PaperBroker(client=mock_client, audit=mock_audit)
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].stock.code == "005930"
        assert positions[0].quantity == 50
