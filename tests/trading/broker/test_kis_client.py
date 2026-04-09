"""KIS REST API 클라이언트 테스트.

모든 API 호출은 mock으로 처리한다. 실제 KIS 서버에 요청하지 않는다.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.broker.kis_client import KISClient


class TestKISClientInit:
    """KISClient 초기화 테스트."""

    def test_paper_base_url(self):
        """모의투자 서버 URL을 사용한다."""
        client = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
            is_paper=True,
        )
        assert client.base_url == "https://openapivts.koreainvestment.com:29443"
        assert client.is_paper is True

    def test_live_base_url(self):
        """실전 서버 URL을 사용한다."""
        client = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
            is_paper=False,
        )
        assert client.base_url == "https://openapi.koreainvestment.com:9443"
        assert client.is_paper is False

    def test_initial_token_empty(self):
        """초기 토큰은 빈 문자열이다."""
        client = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
        )
        assert client._access_token == ""
        assert client._token_expires is None

    def test_account_parsed(self):
        """계좌번호에서 앞 8자리와 뒤 2자리를 분리한다."""
        client = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
        )
        assert client._account_prefix == "12345678"
        assert client._account_suffix == "01"


class TestTokenManagement:
    """OAuth 토큰 관리 테스트."""

    @pytest.fixture
    def client(self):
        return KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
            is_paper=True,
        )

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_get_access_token(self, mock_post, client):
        """토큰 발급 API를 호출하고 결과를 저장한다."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new_token_abc",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )
        token = client.get_access_token()
        assert token == "new_token_abc"
        assert client._access_token == "new_token_abc"
        assert client._token_expires is not None
        mock_post.assert_called_once()

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_token_reuse_when_valid(self, mock_post, client):
        """유효 기간 내 토큰은 재발급하지 않는다."""
        client._access_token = "existing_token"
        client._token_expires = datetime.now() + timedelta(hours=12)
        token = client.get_access_token()
        assert token == "existing_token"
        mock_post.assert_not_called()

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_token_refresh_when_expired(self, mock_post, client):
        """만료된 토큰은 재발급한다."""
        client._access_token = "old_token"
        client._token_expires = datetime.now() - timedelta(hours=1)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_token",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )
        token = client.get_access_token()
        assert token == "refreshed_token"
        mock_post.assert_called_once()

    def test_headers_include_token(self, client):
        """_headers()는 인증 헤더를 포함한다."""
        client._access_token = "my_token"
        client._token_expires = datetime.now() + timedelta(hours=12)
        headers = client._headers()
        assert headers["authorization"] == "Bearer my_token"
        assert headers["appkey"] == "test_key"
        assert headers["appsecret"] == "test_secret"
        assert headers["Content-Type"] == "application/json; charset=utf-8"


class TestOrderAPI:
    """주문 API 테스트."""

    @pytest.fixture
    def client(self):
        c = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
            is_paper=True,
        )
        c._access_token = "valid_token"
        c._token_expires = datetime.now() + timedelta(hours=12)
        return c

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_place_buy_order(self, mock_post, client):
        """매수 주문을 제출한다."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "msg_cd": "APBK0013",
                "msg1": "주문 전송 완료",
                "output": {
                    "KRX_FWDG_ORD_ORGNO": "91252",
                    "ORNO": "0000123456",
                    "ORD_TMD": "092530",
                },
            },
        )
        result = client.place_order(
            code="005930", side="BUY", qty=10,
            price=72000, order_type="LIMIT",
        )
        assert result["rt_cd"] == "0"
        assert result["output"]["ORNO"] == "0000123456"
        mock_post.assert_called_once()

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_place_sell_order(self, mock_post, client):
        """매도 주문을 제출한다."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output": {"ORNO": "0000123457"},
            },
        )
        result = client.place_order(
            code="005930", side="SELL", qty=5,
            price=73000, order_type="LIMIT",
        )
        assert result["rt_cd"] == "0"

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_place_market_order(self, mock_post, client):
        """시장가 주문은 가격을 0으로 전송한다."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output": {"ORNO": "0000123458"},
            },
        )
        result = client.place_order(
            code="005930", side="BUY", qty=10,
            price=0, order_type="MARKET",
        )
        assert result["rt_cd"] == "0"

    @patch("alphapulse.trading.broker.kis_client.requests.post")
    def test_cancel_order(self, mock_post, client):
        """주문을 취소한다."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "msg1": "주문 취소 완료",
            },
        )
        result = client.cancel_order(order_no="0000123456")
        assert result["rt_cd"] == "0"
        mock_post.assert_called_once()


class TestQueryAPI:
    """잔고/체결 조회 API 테스트."""

    @pytest.fixture
    def client(self):
        c = KISClient(
            app_key="test_key",
            app_secret="test_secret",
            account_no="12345678-01",
            is_paper=True,
        )
        c._access_token = "valid_token"
        c._token_expires = datetime.now() + timedelta(hours=12)
        return c

    @patch("alphapulse.trading.broker.kis_client.requests.get")
    def test_get_balance(self, mock_get, client):
        """예수금을 조회한다."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output": {
                    "dnca_tot_amt": "50000000",
                    "tot_evlu_amt": "108350000",
                },
            },
        )
        result = client.get_balance()
        assert result["output"]["dnca_tot_amt"] == "50000000"

    @patch("alphapulse.trading.broker.kis_client.requests.get")
    def test_get_positions(self, mock_get, client):
        """보유 종목을 조회한다."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output1": [
                    {
                        "pdno": "005930",
                        "prdt_name": "삼성전자",
                        "hldg_qty": "100",
                        "pchs_avg_pric": "72000.00",
                        "prpr": "73000",
                        "evlu_pfls_amt": "100000",
                    },
                ],
            },
        )
        result = client.get_positions()
        assert len(result) == 1
        assert result[0]["pdno"] == "005930"

    @patch("alphapulse.trading.broker.kis_client.requests.get")
    def test_get_order_history(self, mock_get, client):
        """당일 주문 내역을 조회한다."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output": [
                    {
                        "odno": "0000123456",
                        "pdno": "005930",
                        "sll_buy_dvsn_cd": "02",
                        "ord_qty": "10",
                        "tot_ccld_qty": "10",
                        "avg_prvs": "72000",
                        "ord_dvsn_cd": "00",
                    },
                ],
            },
        )
        result = client.get_order_history(date="20260409")
        assert len(result) == 1
        assert result[0]["odno"] == "0000123456"

    @patch("alphapulse.trading.broker.kis_client.requests.get")
    def test_get_current_price(self, mock_get, client):
        """현재가를 조회한다."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "rt_cd": "0",
                "output": {
                    "stck_prpr": "73000",
                    "prdy_vrss": "+1000",
                    "acml_vol": "15000000",
                },
            },
        )
        result = client.get_current_price(code="005930")
        assert result["output"]["stck_prpr"] == "73000"
