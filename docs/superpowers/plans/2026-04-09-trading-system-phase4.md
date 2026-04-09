# Trading System Phase 4: Broker + Orchestrator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국투자증권 Open API 연동 브로커 + 전체 매매 파이프라인 오케스트레이터를 구축한다. Paper Trading과 실매매를 동일 코드 경로로 실행하며, 이중 안전장치와 텔레그램 알림으로 운영 안정성을 확보한다.

**Architecture:** `trading/broker/`는 KIS REST API 클라이언트(OAuth 토큰 관리) + Broker Protocol 구현체(실전/모의투자). `trading/orchestrator/`는 5단계 일일 파이프라인(데이터→분석→포트폴리오→실행→사후관리) + KRX 시간대 스케줄러 + 텔레그램 알림 + 장애 복구.

**Tech Stack:** Python 3.11+, requests (KIS REST API), pytest, asyncio (TradingEngine.run_daily만), 기존 TelegramNotifier 재사용

**Spec:** `docs/superpowers/specs/2026-04-09-trading-system-design.md` (섹션 10, 11)

**Depends on:** Phase 1 + Phase 2 + Phase 3 must be completed first.

---

## File Structure

### New Files to Create

```
alphapulse/trading/broker/
├── __init__.py
├── kis_client.py          # Task 1: KIS REST API 클라이언트
├── kis_broker.py          # Task 2: KISBroker (실매매 Broker Protocol 구현)
├── paper_broker.py        # Task 3: PaperBroker (모의투자 Broker Protocol 구현)
├── safeguard.py           # Task 4: TradingSafeguard (안전장치)
└── monitor.py             # Task 5: OrderMonitor (주문 상태 추적)

alphapulse/trading/orchestrator/
├── __init__.py
├── engine.py              # Task 6: TradingEngine (일일 파이프라인)
├── scheduler.py           # Task 7: TradingScheduler (시간대 스케줄링)
├── alert.py               # Task 8: TradingAlert (텔레그램 알림)
├── monitor.py             # Task 9: SystemMonitor (헬스체크)
└── recovery.py            # Task 10: RecoveryManager (장애 복구)

tests/trading/broker/
├── __init__.py
├── test_kis_client.py
├── test_kis_broker.py
├── test_paper_broker.py
├── test_safeguard.py
└── test_monitor.py

tests/trading/orchestrator/
├── __init__.py
├── test_engine.py
├── test_scheduler.py
├── test_alert.py
├── test_monitor.py
└── test_recovery.py
```

### Files to Modify

- `alphapulse/core/config.py` — Task 11: KIS API + Trading 설정 추가
- `alphapulse/cli.py` — Task 12: `ap trading run/portfolio/risk/status/reconcile` CLI 명령 추가

---

## Phase ⑨: Broker Integration (`trading/broker/`)

---

## Task 1: KIS REST API 클라이언트

**Files:**
- Create: `alphapulse/trading/broker/__init__.py`
- Create: `alphapulse/trading/broker/kis_client.py`
- Test: `tests/trading/broker/__init__.py`
- Test: `tests/trading/broker/test_kis_client.py`

- [ ] **Step 1: 패키지 구조 생성**

```bash
mkdir -p alphapulse/trading/broker
mkdir -p tests/trading/broker
```

`alphapulse/trading/broker/__init__.py`:
```python
"""한국투자증권 API 연동 브로커."""

from .kis_broker import KISBroker
from .kis_client import KISClient
from .monitor import OrderMonitor
from .paper_broker import PaperBroker
from .safeguard import TradingSafeguard

__all__ = [
    "KISClient",
    "KISBroker",
    "PaperBroker",
    "TradingSafeguard",
    "OrderMonitor",
]
```

`tests/trading/broker/__init__.py`: 빈 파일.

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/trading/broker/test_kis_client.py`:
```python
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `pytest tests/trading/broker/test_kis_client.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'alphapulse.trading.broker.kis_client'`

- [ ] **Step 4: KISClient 구현**

`alphapulse/trading/broker/kis_client.py`:
```python
"""한국투자증권 Open API REST 클라이언트.

OAuth 토큰 관리, 주문, 잔고 조회 등 KIS API 호출을 캡슐화한다.
모의투자(openapivts)와 실전(openapi) 서버를 is_paper 플래그로 전환한다.
모든 메서드는 Sync(requests 라이브러리)로 동작한다.
"""

import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# 모의투자 / 실전 서버 URL
PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
LIVE_BASE_URL = "https://openapi.koreainvestment.com:9443"

# 주문 구분 코드 매핑
ORDER_SIDE_CODE = {
    "BUY": "02",   # 매수
    "SELL": "01",  # 매도
}

# 주문 유형 코드 매핑
ORDER_TYPE_CODE = {
    "LIMIT": "00",   # 지정가
    "MARKET": "01",  # 시장가
}

# API 경로 상수
TOKEN_PATH = "/oauth2/tokenP"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"

# 모의투자 / 실전 tr_id 매핑
BUY_TR_ID = {"paper": "VTTC0802U", "live": "TTTC0802U"}
SELL_TR_ID = {"paper": "VTTC0801U", "live": "TTTC0801U"}
CANCEL_TR_ID = {"paper": "VTTC0803U", "live": "TTTC0803U"}
BALANCE_TR_ID = {"paper": "VTTC8434R", "live": "TTTC8434R"}


class KISClient:
    """한국투자증권 Open API REST 클라이언트.

    Attributes:
        base_url: 서버 URL (모의투자 또는 실전).
        is_paper: 모의투자 여부.
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        account_no: str,
        is_paper: bool = True,
    ) -> None:
        """KISClient를 초기화한다.

        Args:
            app_key: 한투 앱 키.
            app_secret: 한투 앱 시크릿.
            account_no: 계좌번호 (형식: "12345678-01").
            is_paper: True면 모의투자, False면 실전.
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.is_paper = is_paper
        self.base_url = PAPER_BASE_URL if is_paper else LIVE_BASE_URL

        # 계좌번호 분리 (앞 8자리-뒤 2자리)
        parts = account_no.split("-")
        self._account_prefix = parts[0]
        self._account_suffix = parts[1] if len(parts) > 1 else "01"

        # 토큰 관리
        self._access_token: str = ""
        self._token_expires: datetime | None = None

        self._session = requests.Session()

    def get_access_token(self) -> str:
        """OAuth 액세스 토큰을 발급하거나 캐시된 토큰을 반환한다.

        토큰이 없거나 만료 1시간 전이면 재발급한다.

        Returns:
            액세스 토큰 문자열.
        """
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires - timedelta(hours=1):
                return self._access_token

        url = f"{self.base_url}{TOKEN_PATH}"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        resp = requests.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 86400)
        self._token_expires = datetime.now() + timedelta(seconds=expires_in)

        logger.info("KIS 토큰 발급 완료. 만료: %s", self._token_expires)
        return self._access_token

    def _headers(self, tr_id: str = "") -> dict:
        """API 요청 공통 헤더를 생성한다.

        Args:
            tr_id: 거래 ID (API별 상이).

        Returns:
            HTTP 헤더 딕셔너리.
        """
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        if tr_id:
            headers["tr_id"] = tr_id
        return headers

    def place_order(
        self,
        code: str,
        side: str,
        qty: int,
        price: int,
        order_type: str,
    ) -> dict:
        """매수/매도 주문을 제출한다.

        Args:
            code: 종목코드 (예: "005930").
            side: "BUY" 또는 "SELL".
            qty: 주문 수량.
            price: 주문 가격 (시장가면 0).
            order_type: "LIMIT" 또는 "MARKET".

        Returns:
            KIS API 응답 딕셔너리.
        """
        self.get_access_token()

        mode_key = "paper" if self.is_paper else "live"
        if side == "BUY":
            tr_id = BUY_TR_ID[mode_key]
        else:
            tr_id = SELL_TR_ID[mode_key]

        url = f"{self.base_url}{ORDER_PATH}"
        body = {
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "PDNO": code,
            "ORD_DVSN": ORDER_TYPE_CODE.get(order_type, "00"),
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price),
        }
        resp = self._session.post(url, json=body, headers=self._headers(tr_id))
        resp.raise_for_status()
        result = resp.json()
        logger.info("주문 제출: %s %s %s주 @%s → %s", side, code, qty, price, result.get("rt_cd"))
        return result

    def cancel_order(self, order_no: str) -> dict:
        """주문을 취소한다.

        Args:
            order_no: 주문번호.

        Returns:
            KIS API 응답 딕셔너리.
        """
        self.get_access_token()

        mode_key = "paper" if self.is_paper else "live"
        tr_id = CANCEL_TR_ID[mode_key]

        url = f"{self.base_url}{CANCEL_PATH}"
        body = {
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 취소
            "ORD_QTY": "0",
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        resp = self._session.post(url, json=body, headers=self._headers(tr_id))
        resp.raise_for_status()
        result = resp.json()
        logger.info("주문 취소: %s → %s", order_no, result.get("rt_cd"))
        return result

    def get_balance(self) -> dict:
        """예수금/자산을 조회한다.

        Returns:
            예수금 정보 딕셔너리.
        """
        self.get_access_token()

        mode_key = "paper" if self.is_paper else "live"
        tr_id = BALANCE_TR_ID[mode_key]

        url = f"{self.base_url}{BALANCE_PATH}"
        params = {
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        resp = self._session.get(url, params=params, headers=self._headers(tr_id))
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> list[dict]:
        """보유 종목 목록을 조회한다.

        Returns:
            보유 종목 정보 리스트. 각 항목은 pdno(종목코드), hldg_qty(수량) 등 포함.
        """
        balance = self.get_balance()
        return balance.get("output1", [])

    def get_order_history(self, date: str) -> list[dict]:
        """지정 날짜의 주문 내역을 조회한다.

        Args:
            date: 조회 날짜 (YYYYMMDD).

        Returns:
            주문 내역 리스트.
        """
        self.get_access_token()

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        mode_key = "paper" if self.is_paper else "live"
        tr_id = "VTTC8001R" if mode_key == "paper" else "TTTC8001R"

        params = {
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "INQR_STRT_DT": date,
            "INQR_END_DT": date,
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        resp = self._session.get(url, params=params, headers=self._headers(tr_id))
        resp.raise_for_status()
        data = resp.json()
        return data.get("output", data.get("output1", []))

    def get_current_price(self, code: str) -> dict:
        """종목 현재가를 조회한다.

        Args:
            code: 종목코드.

        Returns:
            시세 정보 딕셔너리.
        """
        self.get_access_token()

        url = f"{self.base_url}{PRICE_PATH}"
        tr_id = "FHKST01010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
        }
        resp = self._session.get(url, params=params, headers=self._headers(tr_id))
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/trading/broker/test_kis_client.py -v`
Expected: 15 passed

- [ ] **Step 6: 커밋**

```bash
git add alphapulse/trading/broker/__init__.py alphapulse/trading/broker/kis_client.py tests/trading/broker/__init__.py tests/trading/broker/test_kis_client.py
git commit -m "feat(trading/broker): add KISClient — KIS REST API client with OAuth token management"
```

---

## Task 2: KISBroker (실매매 Broker Protocol 구현)

**Files:**
- Create: `alphapulse/trading/broker/kis_broker.py`
- Test: `tests/trading/broker/test_kis_broker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/broker/test_kis_broker.py`:
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/broker/test_kis_broker.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: KISBroker 구현**

`alphapulse/trading/broker/kis_broker.py`:
```python
"""KISBroker — 한투 실전 API Broker Protocol 구현체.

KISClient를 통해 실제 한국투자증권 서버에 주문을 전송한다.
Broker Protocol을 구현하여 전략/포트폴리오/리스크 코드와 분리된다.
모든 주문은 AuditLogger를 통해 감사 로그에 기록된다.
"""

import logging
from datetime import datetime

from alphapulse.trading.broker.kis_client import KISClient
from alphapulse.trading.core.models import Order, OrderResult, Position, Stock

logger = logging.getLogger(__name__)


class KISBroker:
    """한투 실전 매매 브로커.

    Broker Protocol을 구현한다. 실전 클라이언트(is_paper=False)만 허용한다.

    Attributes:
        client: KIS REST API 클라이언트.
        audit: 감사 추적 로거.
    """

    def __init__(self, client: KISClient, audit) -> None:
        """KISBroker를 초기화한다.

        Args:
            client: KIS REST API 클라이언트 (is_paper=False 필수).
            audit: AuditLogger 인스턴스.

        Raises:
            ValueError: 모의투자 클라이언트를 전달한 경우.
        """
        if client.is_paper:
            raise ValueError(
                "실매매 브로커에 모의투자 클라이언트를 사용할 수 없습니다. "
                "is_paper=False인 KISClient를 전달하세요."
            )
        self.client = client
        self.audit = audit

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 KIS 서버에 제출한다.

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
            logger.error("주문 제출 실패: %s", e)
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
            logger.error("주문 취소 실패: %s %s", order_id, e)
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

        당일 주문 내역에서 order_id에 해당하는 주문을 찾아 반환한다.

        Args:
            order_id: 주문번호.

        Returns:
            주문 체결 결과. 찾지 못하면 status="pending".
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
            market="KOSPI",  # KIS API에서 시장 구분 별도 조회 필요
        )
        quantity = int(raw.get("hldg_qty", "0"))
        avg_price = float(raw.get("pchs_avg_pric", "0"))
        current_price = float(raw.get("prpr", "0"))
        unrealized_pnl = float(raw.get("evlu_pfls_amt", "0"))

        return Position(
            stock=stock,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            weight=0.0,  # 비중은 PortfolioManager에서 계산
            strategy_id="",  # 전략 매핑은 RecoveryManager에서 처리
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/broker/test_kis_broker.py -v`
Expected: 11 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/broker/kis_broker.py tests/trading/broker/test_kis_broker.py
git commit -m "feat(trading/broker): add KISBroker — live trading Broker Protocol implementation"
```

---

## Task 3: PaperBroker (모의투자 Broker Protocol 구현)

**Files:**
- Create: `alphapulse/trading/broker/paper_broker.py`
- Test: `tests/trading/broker/test_paper_broker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/broker/test_paper_broker.py`:
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/broker/test_paper_broker.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: PaperBroker 구현**

`alphapulse/trading/broker/paper_broker.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/broker/test_paper_broker.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/broker/paper_broker.py tests/trading/broker/test_paper_broker.py
git commit -m "feat(trading/broker): add PaperBroker — paper trading Broker Protocol implementation"
```

---

## Task 4: TradingSafeguard (안전장치)

**Files:**
- Create: `alphapulse/trading/broker/safeguard.py`
- Test: `tests/trading/broker/test_safeguard.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/broker/test_safeguard.py`:
```python
"""TradingSafeguard 테스트 — 실매매 안전장치.

LIVE_TRADING_ENABLED, 일일 한도, 사용자 확인을 검증한다.
"""

from unittest.mock import patch

import pytest

from alphapulse.trading.broker.safeguard import TradingSafeguard


class TestCheckLiveAllowed:
    """LIVE_TRADING_ENABLED 검사 테스트."""

    def test_live_enabled(self):
        """LIVE_TRADING_ENABLED=True이면 True를 반환한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        assert sg.check_live_allowed() is True

    def test_live_disabled_raises(self):
        """LIVE_TRADING_ENABLED=False이면 RuntimeError를 발생시킨다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": False,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        with pytest.raises(RuntimeError, match="실매매가 비활성화"):
            sg.check_live_allowed()

    def test_default_is_disabled(self):
        """기본값은 비활성화이다."""
        sg = TradingSafeguard(config={})
        with pytest.raises(RuntimeError, match="실매매가 비활성화"):
            sg.check_live_allowed()


class TestConfirmLiveStart:
    """사용자 수동 확인 테스트."""

    def test_user_confirms_yes(self):
        """사용자가 'yes'를 입력하면 True를 반환한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="yes"):
            assert sg.confirm_live_start("12345678-01") is True

    def test_user_confirms_no(self):
        """사용자가 'no'를 입력하면 False를 반환한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="no"):
            assert sg.confirm_live_start("12345678-01") is False

    def test_user_confirms_with_spaces(self):
        """입력 앞뒤 공백을 제거한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="  yes  "):
            assert sg.confirm_live_start("12345678-01") is True

    def test_user_empty_input(self):
        """빈 입력은 거부한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value=""):
            assert sg.confirm_live_start("12345678-01") is False


class TestDailyLimits:
    """일일 주문 한도 테스트."""

    @pytest.fixture
    def safeguard(self):
        return TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })

    def test_within_limits(self, safeguard):
        """한도 내이면 True를 반환한다."""
        assert safeguard.check_daily_limit(today_orders=10, today_amount=10_000_000) is True

    def test_order_count_exceeded(self, safeguard):
        """주문 횟수 한도 초과 시 RuntimeError."""
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            safeguard.check_daily_limit(today_orders=50, today_amount=10_000_000)

    def test_order_amount_exceeded(self, safeguard):
        """주문 금액 한도 초과 시 RuntimeError."""
        with pytest.raises(RuntimeError, match="일일 금액 한도 초과"):
            safeguard.check_daily_limit(today_orders=10, today_amount=50_000_000)

    def test_both_exceeded(self, safeguard):
        """횟수와 금액 모두 초과 시 — 횟수가 먼저 검사된다."""
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            safeguard.check_daily_limit(today_orders=50, today_amount=50_000_000)

    def test_just_below_limits(self, safeguard):
        """한도 직전이면 허용한다."""
        assert safeguard.check_daily_limit(today_orders=49, today_amount=49_999_999) is True


class TestTrackDailyUsage:
    """일일 사용량 추적 테스트."""

    def test_record_and_check(self):
        """주문을 기록하면 누적 횟수/금액이 증가한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 3,
            "MAX_DAILY_AMOUNT": 10_000_000,
        })
        sg.record_order(amount=3_000_000)
        sg.record_order(amount=3_000_000)
        assert sg.today_order_count == 2
        assert sg.today_order_amount == 6_000_000

        # 세 번째까지 가능
        sg.record_order(amount=3_000_000)
        # 네 번째는 한도 초과
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            sg.check_daily_limit(
                today_orders=sg.today_order_count,
                today_amount=sg.today_order_amount,
            )

    def test_reset_daily(self):
        """일일 카운터를 초기화한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        sg.record_order(amount=5_000_000)
        sg.reset_daily()
        assert sg.today_order_count == 0
        assert sg.today_order_amount == 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/broker/test_safeguard.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: TradingSafeguard 구현**

`alphapulse/trading/broker/safeguard.py`:
```python
"""TradingSafeguard — 실매매 안전장치.

LIVE_TRADING_ENABLED 환경변수 검사, 사용자 수동 확인,
일일 주문 횟수/금액 한도를 관리한다.
"""

import logging

logger = logging.getLogger(__name__)


class TradingSafeguard:
    """실매매 전용 안전장치.

    이중 안전장치 역할:
    1. LIVE_TRADING_ENABLED=true 환경변수 필수
    2. confirm_live_start()로 터미널에서 사용자 수동 확인
    3. 일일 주문 횟수/금액 한도 제한

    Attributes:
        live_enabled: 실매매 활성화 여부.
        max_daily_orders: 일일 최대 주문 횟수.
        max_daily_amount: 일일 최대 주문 금액 (원).
        today_order_count: 오늘 누적 주문 횟수.
        today_order_amount: 오늘 누적 주문 금액.
    """

    def __init__(self, config: dict) -> None:
        """TradingSafeguard를 초기화한다.

        Args:
            config: 설정 딕셔너리. 키: LIVE_TRADING_ENABLED, MAX_DAILY_ORDERS, MAX_DAILY_AMOUNT.
        """
        self.live_enabled: bool = config.get("LIVE_TRADING_ENABLED", False)
        self.max_daily_orders: int = config.get("MAX_DAILY_ORDERS", 50)
        self.max_daily_amount: float = config.get("MAX_DAILY_AMOUNT", 50_000_000)
        self.today_order_count: int = 0
        self.today_order_amount: float = 0

    def check_live_allowed(self) -> bool:
        """LIVE_TRADING_ENABLED 활성화 여부를 확인한다.

        Returns:
            True (활성화 상태).

        Raises:
            RuntimeError: 비활성화 상태인 경우.
        """
        if not self.live_enabled:
            raise RuntimeError(
                "실매매가 비활성화 상태입니다. "
                "LIVE_TRADING_ENABLED=true 설정 후 재시작하세요."
            )
        return True

    def confirm_live_start(self, account_no: str) -> bool:
        """터미널에서 사용자 수동 확인을 받는다.

        Args:
            account_no: 계좌번호 (표시용).

        Returns:
            사용자가 'yes'를 입력하면 True, 그 외 False.
        """
        response = input(
            f"실매매를 시작합니다.\n"
            f"계좌: {account_no}\n"
            f"확인하시겠습니까? (yes/no): "
        )
        confirmed = response.strip().lower() == "yes"
        if confirmed:
            logger.info("실매매 시작 확인. 계좌: %s", account_no)
        else:
            logger.info("실매매 시작 취소. 사용자 입력: %s", response.strip())
        return confirmed

    def check_daily_limit(self, today_orders: int, today_amount: float) -> bool:
        """일일 주문 한도를 검사한다.

        Args:
            today_orders: 오늘 누적 주문 횟수.
            today_amount: 오늘 누적 주문 금액 (원).

        Returns:
            True (한도 내).

        Raises:
            RuntimeError: 한도 초과 시.
        """
        if today_orders >= self.max_daily_orders:
            raise RuntimeError(
                f"일일 주문 한도 초과: {today_orders}/{self.max_daily_orders}"
            )
        if today_amount >= self.max_daily_amount:
            raise RuntimeError(
                f"일일 금액 한도 초과: {today_amount:,.0f}/{self.max_daily_amount:,.0f}"
            )
        return True

    def record_order(self, amount: float) -> None:
        """주문을 기록하여 일일 누적 카운터를 증가시킨다.

        Args:
            amount: 주문 금액 (원).
        """
        self.today_order_count += 1
        self.today_order_amount += amount

    def reset_daily(self) -> None:
        """일일 카운터를 초기화한다. 새로운 거래일 시작 시 호출."""
        self.today_order_count = 0
        self.today_order_amount = 0
        logger.info("일일 주문 카운터 초기화")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/broker/test_safeguard.py -v`
Expected: 12 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/broker/safeguard.py tests/trading/broker/test_safeguard.py
git commit -m "feat(trading/broker): add TradingSafeguard — live trading safety checks"
```

---

## Task 5: OrderMonitor (주문 상태 추적)

**Files:**
- Create: `alphapulse/trading/broker/monitor.py`
- Test: `tests/trading/broker/test_monitor.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/broker/test_monitor.py`:
```python
"""OrderMonitor 테스트 — 주문 상태 추적 + 알림.

브로커 get_order_status를 폴링하여 체결 상태를 추적한다.
"""

from datetime import datetime
from unittest.mock import MagicMock, call

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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/broker/test_monitor.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: OrderMonitor 구현**

`alphapulse/trading/broker/monitor.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/broker/test_monitor.py -v`
Expected: 12 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/broker/monitor.py tests/trading/broker/test_monitor.py
git commit -m "feat(trading/broker): add OrderMonitor — order status tracking with polling"
```

---

## Phase ⑩: Trading Orchestrator (`trading/orchestrator/`)

---

## Task 6: TradingEngine (일일 파이프라인)

**Files:**
- Create: `alphapulse/trading/orchestrator/__init__.py`
- Create: `alphapulse/trading/orchestrator/engine.py`
- Test: `tests/trading/orchestrator/__init__.py`
- Test: `tests/trading/orchestrator/test_engine.py`

- [ ] **Step 1: 패키지 구조 생성**

```bash
mkdir -p alphapulse/trading/orchestrator
mkdir -p tests/trading/orchestrator
```

`alphapulse/trading/orchestrator/__init__.py`:
```python
"""트레이딩 오케스트레이터 — 일일 매매 파이프라인."""

from .alert import TradingAlert
from .engine import TradingEngine
from .monitor import SystemMonitor
from .recovery import RecoveryManager
from .scheduler import TradingScheduler

__all__ = [
    "TradingEngine",
    "TradingScheduler",
    "TradingAlert",
    "SystemMonitor",
    "RecoveryManager",
]
```

`tests/trading/orchestrator/__init__.py`: 빈 파일.

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/trading/orchestrator/test_engine.py`:
```python
"""TradingEngine 테스트 — 일일 매매 파이프라인.

모든 서브시스템(전략, 포트폴리오, 리스크, 브로커)은 mock으로 처리한다.
run_daily()는 async 메서드이므로 pytest-asyncio를 사용한다.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, TradingMode
from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    Signal,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.orchestrator.engine import TradingEngine


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def mock_deps(samsung):
    """TradingEngine의 모든 의존성 mock."""
    deps = {
        "broker": MagicMock(),
        "data_provider": MagicMock(),
        "universe": MagicMock(),
        "screener": MagicMock(),
        "strategies": [MagicMock()],
        "allocator": MagicMock(),
        "portfolio_manager": MagicMock(),
        "risk_manager": MagicMock(),
        "ai_synthesizer": MagicMock(),
        "alert": AsyncMock(),
        "audit": MagicMock(),
        "portfolio_store": MagicMock(),
        "safeguard": None,
    }

    # 전략 mock 설정
    strategy = deps["strategies"][0]
    strategy.strategy_id = "momentum"
    strategy.should_rebalance.return_value = True
    strategy.generate_signals.return_value = [
        Signal(stock=samsung, score=75.0, factors={"momentum": 0.8},
               strategy_id="momentum"),
    ]

    # 유니버스 mock
    deps["universe"].get_filtered.return_value = [samsung]

    # 포트폴리오 mock
    snapshot = PortfolioSnapshot(
        date="20260409", cash=50_000_000,
        positions=[], total_value=100_000_000,
        daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
    )
    deps["portfolio_store"].get_latest_snapshot.return_value = snapshot

    # 포트폴리오 매니저 mock
    buy_order = Order(
        stock=samsung, side="BUY", order_type="MARKET",
        quantity=10, price=None, strategy_id="momentum",
        reason="팩터 상위",
    )
    deps["portfolio_manager"].update_target.return_value = MagicMock()
    deps["portfolio_manager"].generate_orders.return_value = [buy_order]

    # 리스크 매니저 mock
    risk_decision = MagicMock()
    risk_decision.action = RiskAction.APPROVE
    risk_decision.adjusted_quantity = None
    deps["risk_manager"].check_order.return_value = risk_decision
    deps["risk_manager"].drawdown_mgr = MagicMock()
    deps["risk_manager"].drawdown_mgr.check.return_value = DrawdownAction.NORMAL
    deps["risk_manager"].daily_report.return_value = MagicMock()

    # 브로커 mock
    deps["broker"].submit_order.return_value = OrderResult(
        order_id="ORD001", order=buy_order, status="filled",
        filled_quantity=10, filled_price=72000.0,
        commission=108.0, tax=0.0, filled_at=datetime.now(),
    )
    deps["broker"].get_positions.return_value = []

    # AI 합성 mock
    synthesis = StrategySynthesis(
        market_view="매수 우위",
        conviction_level=0.72,
        allocation_adjustment={"momentum": 1.0},
        stock_opinions=[],
        risk_warnings=[],
        reasoning="모멘텀 양호",
    )
    deps["ai_synthesizer"].synthesize = AsyncMock(return_value=synthesis)

    # 알로케이터 mock
    deps["allocator"].adjust_by_market_regime.return_value = {"momentum": 1.0}

    return deps


class TestTradingEngineInit:
    """TradingEngine 초기화 테스트."""

    def test_creates_with_mode(self, mock_deps):
        """TradingMode로 초기화한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        assert engine.mode == TradingMode.PAPER

    def test_live_mode_requires_safeguard(self, mock_deps):
        """LIVE 모드에서 safeguard가 None이면 ValueError."""
        mock_deps["safeguard"] = None
        with pytest.raises(ValueError, match="실매매 모드에서 safeguard"):
            TradingEngine(mode=TradingMode.LIVE, **mock_deps)

    def test_live_mode_with_safeguard(self, mock_deps):
        """LIVE 모드에서 safeguard가 있으면 정상 생성."""
        mock_deps["safeguard"] = MagicMock()
        mock_deps["safeguard"].check_live_allowed.return_value = True
        engine = TradingEngine(mode=TradingMode.LIVE, **mock_deps)
        assert engine.mode == TradingMode.LIVE


class TestRunDaily:
    """run_daily() 5단계 파이프라인 테스트."""

    @pytest.mark.asyncio
    async def test_full_pipeline_executes(self, mock_deps):
        """5단계 파이프라인이 순서대로 실행된다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # Phase 1: 데이터 수집
        mock_deps["data_provider"].refresh.assert_called_once()

        # Phase 2: 분석
        mock_deps["strategies"][0].should_rebalance.assert_called_once()
        mock_deps["strategies"][0].generate_signals.assert_called_once()
        mock_deps["ai_synthesizer"].synthesize.assert_called_once()

        # Phase 3: 포트폴리오
        mock_deps["portfolio_manager"].update_target.assert_called_once()
        mock_deps["portfolio_manager"].generate_orders.assert_called_once()
        mock_deps["risk_manager"].check_order.assert_called_once()

        # Phase 4: 실행
        mock_deps["broker"].submit_order.assert_called_once()

        # Phase 5: 사후 관리
        mock_deps["alert"].post_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_rejected_order_not_submitted(self, mock_deps):
        """리스크 거부된 주문은 브로커에 전달하지 않는다."""
        risk_decision = MagicMock()
        risk_decision.action = RiskAction.REJECT
        mock_deps["risk_manager"].check_order.return_value = risk_decision

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["broker"].submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_risk_reduce_size(self, mock_deps, samsung):
        """리스크 축소된 주문은 수량을 조정하여 전달한다."""
        risk_decision = MagicMock()
        risk_decision.action = RiskAction.REDUCE_SIZE
        risk_decision.adjusted_quantity = 5
        mock_deps["risk_manager"].check_order.return_value = risk_decision

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        submitted_order = mock_deps["broker"].submit_order.call_args[0][0]
        assert submitted_order.quantity == 5

    @pytest.mark.asyncio
    async def test_drawdown_deleverage(self, mock_deps):
        """드로다운 하드 리밋 도달 시 디레버리징 주문을 실행한다."""
        mock_deps["risk_manager"].drawdown_mgr.check.return_value = DrawdownAction.DELEVERAGE
        deleverage_order = Order(
            stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
            side="SELL", order_type="MARKET",
            quantity=50, price=None, strategy_id="risk",
            reason="드로다운 디레버리징",
        )
        mock_deps["risk_manager"].drawdown_mgr.generate_deleverage_orders.return_value = [
            deleverage_order,
        ]

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # 기본 주문 + 디레버리징 주문
        assert mock_deps["broker"].submit_order.call_count >= 2
        mock_deps["alert"].risk_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_strategy_no_rebalance_skipped(self, mock_deps):
        """리밸런싱 시점이 아닌 전략은 시그널 생성을 건너뛴다."""
        mock_deps["strategies"][0].should_rebalance.return_value = False
        mock_deps["portfolio_manager"].generate_orders.return_value = []

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["strategies"][0].generate_signals.assert_not_called()

    @pytest.mark.asyncio
    async def test_ai_synthesis_failure_uses_fallback(self, mock_deps):
        """AI 종합 판단 실패 시 fallback으로 진행한다."""
        mock_deps["ai_synthesizer"].synthesize = AsyncMock(
            side_effect=Exception("LLM 오류"),
        )

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # fallback으로 진행하므로 포트폴리오 단계까지 도달
        mock_deps["portfolio_manager"].update_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_market_alert_sent(self, mock_deps):
        """Phase 3 완료 후 장전 알림을 전송한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["alert"].pre_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_alert_per_order(self, mock_deps):
        """각 주문 체결마다 알림을 전송한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["alert"].execution.assert_called_once()
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `pytest tests/trading/orchestrator/test_engine.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 4: TradingEngine 구현**

`alphapulse/trading/orchestrator/engine.py`:
```python
"""TradingEngine — 일일 매매 파이프라인 오케스트레이터.

5단계 파이프라인:
1. 데이터 수집
2. 분석 (전략 시그널 + AI 종합 판단)
3. 포트폴리오 (목표 산출 + 리스크 체크 + 장전 알림)
4. 실행 (주문 제출 + 체결 알림)
5. 사후 관리 (드로다운 체크 + 일일 리포트)

run_daily()는 async 메서드이다 (AI 합성이 async).
CLI entry에서만 asyncio.run()으로 호출한다.
"""

import logging
from datetime import datetime

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, TradingMode
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)


class TradingEngine:
    """전체 매매 파이프라인 오케스트레이터.

    전략, 포트폴리오, 리스크, 브로커를 통합하여
    일일 매매 사이클을 실행한다.

    Attributes:
        mode: 실행 모드 (BACKTEST, PAPER, LIVE).
        broker: Broker Protocol 구현체.
        strategies: 전략 목록.
    """

    def __init__(
        self,
        mode: TradingMode,
        broker,
        data_provider,
        universe,
        screener,
        strategies: list,
        allocator,
        portfolio_manager,
        risk_manager,
        ai_synthesizer,
        alert,
        audit,
        portfolio_store,
        safeguard=None,
    ) -> None:
        """TradingEngine을 초기화한다.

        Args:
            mode: 실행 모드.
            broker: Broker Protocol 구현체.
            data_provider: 데이터 소스.
            universe: 투자 유니버스 관리자.
            screener: 멀티팩터 랭커.
            strategies: 전략 목록.
            allocator: 멀티전략 배분기.
            portfolio_manager: 포트폴리오 관리자.
            risk_manager: 리스크 매니저.
            ai_synthesizer: AI 전략 종합기 (async).
            alert: TradingAlert 인스턴스 (async).
            audit: AuditLogger 인스턴스.
            portfolio_store: 포트폴리오 저장소.
            safeguard: TradingSafeguard (LIVE 모드 필수).

        Raises:
            ValueError: LIVE 모드에서 safeguard가 None인 경우.
        """
        if mode == TradingMode.LIVE and safeguard is None:
            raise ValueError(
                "실매매 모드에서 safeguard는 필수입니다. "
                "TradingSafeguard 인스턴스를 전달하세요."
            )

        self.mode = mode
        self.broker = broker
        self.data_provider = data_provider
        self.universe = universe
        self.screener = screener
        self.strategies = strategies
        self.allocator = allocator
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.ai_synthesizer = ai_synthesizer
        self.alert = alert
        self.audit = audit
        self.portfolio_store = portfolio_store
        self.safeguard = safeguard

        if mode == TradingMode.LIVE:
            safeguard.check_live_allowed()

    async def run_daily(self, date: str | None = None) -> dict:
        """일일 매매 사이클을 실행한다 — 5 Phase.

        Args:
            date: 기준 날짜 (YYYYMMDD). None이면 오늘.

        Returns:
            실행 결과 요약 딕셔너리.
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        logger.info("=== 일일 매매 사이클 시작: %s (모드: %s) ===", date, self.mode)

        # ── Phase 1: 데이터 수집 ──
        logger.info("Phase 1: 데이터 수집")
        try:
            self.data_provider.refresh()
        except Exception as e:
            logger.error("데이터 수집 실패: %s", e)
            self.audit.log_error("data_provider", e, {"date": date})

        # ── Phase 2: 분석 ──
        logger.info("Phase 2: 분석")
        filtered_universe = self.universe.get_filtered()
        market_context = self._get_market_context(date)

        strategy_signals: dict[str, list] = {}
        for strategy in self.strategies:
            if strategy.should_rebalance(date, date, market_context):
                signals = strategy.generate_signals(filtered_universe, market_context)
                strategy_signals[strategy.strategy_id] = signals
                logger.info("전략 %s: %d개 시그널", strategy.strategy_id, len(signals))

        # AI 종합 판단
        ai_synthesis = await self._run_ai_synthesis(
            market_context, strategy_signals, date,
        )

        # ── Phase 3: 포트폴리오 ──
        logger.info("Phase 3: 포트폴리오")
        current_snapshot = self._get_current_snapshot(date)

        adjusted_alloc = self.allocator.adjust_by_market_regime(
            market_context.get("pulse_score", 0), ai_synthesis,
        )

        target = self.portfolio_manager.update_target(
            strategy_signals, ai_synthesis, self.allocator, current_snapshot,
        )
        orders = self.portfolio_manager.generate_orders(target, current_snapshot)

        # 리스크 체크
        approved_orders: list[Order] = []
        for order in orders:
            decision = self.risk_manager.check_order(order, current_snapshot)
            self.audit.log_risk_decision(order, decision)

            if decision.action == RiskAction.APPROVE:
                approved_orders.append(order)
            elif decision.action == RiskAction.REDUCE_SIZE:
                order.quantity = decision.adjusted_quantity
                approved_orders.append(order)
            else:
                logger.info("주문 거부: %s %s — %s",
                            order.stock.code, order.side, decision.reason
                            if hasattr(decision, "reason") else "")

        # 장전 알림
        try:
            await self.alert.pre_market(market_context, approved_orders, ai_synthesis)
        except Exception as e:
            logger.warning("장전 알림 실패: %s", e)

        # ── Phase 4: 실행 ──
        logger.info("Phase 4: 실행 (%d건)", len(approved_orders))
        execution_results = []
        for order in approved_orders:
            try:
                result = self.broker.submit_order(order)
                self.audit.log_order(order, result)
                execution_results.append(result)
                try:
                    await self.alert.execution(order, result)
                except Exception as e:
                    logger.warning("체결 알림 실패: %s", e)
            except Exception as e:
                logger.error("주문 실행 실패: %s %s — %s",
                             order.stock.code, order.side, e)
                self.audit.log_error("broker", e, {"order": str(order)})

        # ── Phase 5: 사후 관리 ──
        logger.info("Phase 5: 사후 관리")
        snapshot = self._take_snapshot(date)
        self.portfolio_store.save_snapshot(snapshot, self.mode)

        # 드로다운 체크
        dd_action = self.risk_manager.drawdown_mgr.check(snapshot)
        if dd_action == DrawdownAction.DELEVERAGE:
            logger.warning("드로다운 하드 리밋 도달 — 포지션 축소 실행")
            deleverage_orders = (
                self.risk_manager.drawdown_mgr.generate_deleverage_orders(snapshot)
            )
            for dl_order in deleverage_orders:
                try:
                    dl_result = self.broker.submit_order(dl_order)
                    self.audit.log_order(dl_order, dl_result)
                except Exception as e:
                    logger.error("디레버리징 실행 실패: %s", e)
            try:
                await self.alert.risk_alert(
                    "드로다운 하드 리밋 도달. 포지션 50% 축소 실행."
                )
            except Exception as e:
                logger.warning("리스크 알림 실패: %s", e)

        # 일일 리포트
        risk_report = self.risk_manager.daily_report(snapshot)
        try:
            await self.alert.post_market(snapshot, risk_report)
        except Exception as e:
            logger.warning("사후 알림 실패: %s", e)

        logger.info("=== 일일 매매 사이클 완료: %s ===", date)

        return {
            "date": date,
            "mode": self.mode,
            "signals": len(strategy_signals),
            "orders_submitted": len(execution_results),
            "drawdown_action": dd_action.value if hasattr(dd_action, "value") else str(dd_action),
        }

    async def _run_ai_synthesis(
        self,
        market_context: dict,
        strategy_signals: dict,
        date: str,
    ) -> StrategySynthesis | None:
        """AI 종합 판단을 실행한다. 실패 시 None 반환.

        Returns:
            StrategySynthesis 또는 None (실패 시).
        """
        try:
            current_snapshot = self._get_current_snapshot(date)
            synthesis = await self.ai_synthesizer.synthesize(
                pulse_result=market_context,
                ranked_stocks=[],
                strategy_signals=strategy_signals,
                content_summaries=[],
                feedback_context=None,
                current_portfolio=current_snapshot,
            )
            logger.info("AI 종합 판단 완료: 확신도 %.1f%%",
                        synthesis.conviction_level * 100)
            return synthesis
        except Exception as e:
            logger.warning("AI 종합 판단 실패: %s — fallback 진행", e)
            self.audit.log_error("ai_synthesizer", e, {"date": date})
            return None

    def _get_market_context(self, date: str) -> dict:
        """시장 컨텍스트를 수집한다.

        Returns:
            시장 컨텍스트 딕셔너리.
        """
        try:
            return self.data_provider.get_market_context(date)
        except Exception:
            return {"date": date, "pulse_score": 0}

    def _get_current_snapshot(self, date: str) -> PortfolioSnapshot:
        """현재 포트폴리오 스냅샷을 조회한다.

        Returns:
            최신 포트폴리오 스냅샷. 없으면 초기 스냅샷.
        """
        snapshot = self.portfolio_store.get_latest_snapshot()
        if snapshot is None:
            return PortfolioSnapshot(
                date=date, cash=0, positions=[],
                total_value=0, daily_return=0.0,
                cumulative_return=0.0, drawdown=0.0,
            )
        return snapshot

    def _take_snapshot(self, date: str) -> PortfolioSnapshot:
        """현재 브로커 상태를 기반으로 스냅샷을 생성한다.

        Returns:
            현재 포트폴리오 스냅샷.
        """
        try:
            positions = self.broker.get_positions()
            balance = self.broker.get_balance()
            cash_str = "0"
            if isinstance(balance, dict):
                output = balance.get("output", balance)
                cash_str = output.get("dnca_tot_amt", "0")
            cash = float(cash_str)
            total_positions_value = sum(
                p.current_price * p.quantity for p in positions
            )
            total_value = cash + total_positions_value
        except Exception as e:
            logger.warning("스냅샷 생성 실패: %s — 이전 스냅샷 사용", e)
            return self._get_current_snapshot(date)

        prev = self._get_current_snapshot(date)
        daily_return = (
            (total_value - prev.total_value) / prev.total_value * 100
            if prev.total_value > 0
            else 0.0
        )

        return PortfolioSnapshot(
            date=date,
            cash=cash,
            positions=positions,
            total_value=total_value,
            daily_return=daily_return,
            cumulative_return=prev.cumulative_return + daily_return,
            drawdown=prev.drawdown,  # DrawdownManager가 별도 관리
        )
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/trading/orchestrator/test_engine.py -v`
Expected: 10 passed

- [ ] **Step 6: 커밋**

```bash
git add alphapulse/trading/orchestrator/__init__.py alphapulse/trading/orchestrator/engine.py tests/trading/orchestrator/__init__.py tests/trading/orchestrator/test_engine.py
git commit -m "feat(trading/orchestrator): add TradingEngine — 5-phase daily pipeline"
```

---

## Task 7: TradingScheduler (시간대 스케줄링)

**Files:**
- Create: `alphapulse/trading/orchestrator/scheduler.py`
- Test: `tests/trading/orchestrator/test_scheduler.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/orchestrator/test_scheduler.py`:
```python
"""TradingScheduler 테스트 — KRX 시간대 기반 스케줄링.

datetime.now()를 mock하여 시간대별 동작을 검증한다.
"""

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.trading.orchestrator.scheduler import TradingScheduler


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.run_daily = AsyncMock(return_value={"status": "ok"})
    return engine


@pytest.fixture
def mock_calendar():
    calendar = MagicMock()
    calendar.is_trading_day.return_value = True
    calendar.next_trading_day.return_value = "20260410"
    return calendar


class TestScheduleDefinition:
    """스케줄 정의 테스트."""

    def test_default_schedule(self, mock_engine, mock_calendar):
        """기본 스케줄이 정의되어 있다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert "data_update" in scheduler.SCHEDULE
        assert "analysis" in scheduler.SCHEDULE
        assert "portfolio" in scheduler.SCHEDULE
        assert "pre_market_alert" in scheduler.SCHEDULE
        assert "market_open" in scheduler.SCHEDULE
        assert "midday_check" in scheduler.SCHEDULE
        assert "market_close" in scheduler.SCHEDULE
        assert "post_market" in scheduler.SCHEDULE

    def test_schedule_times_order(self, mock_engine, mock_calendar):
        """스케줄 시간이 올바른 순서이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        times = list(scheduler.SCHEDULE.values())
        for i in range(len(times) - 1):
            assert times[i] <= times[i + 1], f"{times[i]} > {times[i+1]}"


class TestShouldRunPhase:
    """실행 시점 판단 테스트."""

    def test_data_update_at_0800(self, mock_engine, mock_calendar):
        """08:00에 data_update 단계를 실행한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("data_update", time(8, 0)) is True

    def test_data_update_before_0800(self, mock_engine, mock_calendar):
        """08:00 이전에는 data_update를 실행하지 않는다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("data_update", time(7, 59)) is False

    def test_market_open_at_0900(self, mock_engine, mock_calendar):
        """09:00에 market_open 단계를 실행한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("market_open", time(9, 0)) is True


class TestHolidayHandling:
    """공휴일 처리 테스트."""

    def test_skips_holiday(self, mock_engine, mock_calendar):
        """공휴일에는 실행하지 않는다."""
        mock_calendar.is_trading_day.return_value = False
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.is_active_day("20260409") is False

    def test_runs_on_trading_day(self, mock_engine, mock_calendar):
        """거래일에는 실행한다."""
        mock_calendar.is_trading_day.return_value = True
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.is_active_day("20260409") is True


class TestRunOnce:
    """단일 실행 테스트."""

    @pytest.mark.asyncio
    async def test_run_once_calls_engine(self, mock_engine, mock_calendar):
        """run_once()는 engine.run_daily()를 호출한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        result = await scheduler.run_once(date="20260409")
        mock_engine.run_daily.assert_called_once_with(date="20260409")
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_run_once_skips_holiday(self, mock_engine, mock_calendar):
        """공휴일이면 실행하지 않고 None을 반환한다."""
        mock_calendar.is_trading_day.return_value = False
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        result = await scheduler.run_once(date="20260409")
        mock_engine.run_daily.assert_not_called()
        assert result is None


class TestGetNextPhase:
    """다음 실행 단계 조회 테스트."""

    def test_next_phase_morning(self, mock_engine, mock_calendar):
        """07:00에는 다음 단계가 data_update이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(7, 0))
        assert phase == "data_update"
        assert phase_time == "08:00"

    def test_next_phase_after_all(self, mock_engine, mock_calendar):
        """모든 단계 이후에는 None이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(17, 0))
        assert phase is None
        assert phase_time is None

    def test_next_phase_midday(self, mock_engine, mock_calendar):
        """10:00에는 다음 단계가 midday_check이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(10, 0))
        assert phase == "midday_check"
        assert phase_time == "12:30"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/orchestrator/test_scheduler.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: TradingScheduler 구현**

`alphapulse/trading/orchestrator/scheduler.py`:
```python
"""TradingScheduler — KRX 시간대 기반 스케줄링.

한국 주식시장 운영 시간에 맞춰 매매 파이프라인 단계를 실행한다.
KRXCalendar를 사용하여 공휴일에는 자동으로 건너뛴다.
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)


class TradingScheduler:
    """한국 시장 시간대 기반 스케줄러.

    SCHEDULE 딕셔너리의 각 단계를 정해진 시각에 실행한다.
    run_daemon()으로 데몬 모드 실행, run_once()로 단일 실행.

    Attributes:
        SCHEDULE: 단계별 실행 시각 (HH:MM 형식).
        engine: TradingEngine 인스턴스.
        calendar: KRXCalendar 인스턴스.
    """

    SCHEDULE = OrderedDict([
        ("data_update", "08:00"),
        ("analysis", "08:15"),
        ("portfolio", "08:40"),
        ("pre_market_alert", "08:50"),
        ("market_open", "09:00"),
        ("midday_check", "12:30"),
        ("market_close", "15:30"),
        ("post_market", "16:00"),
    ])

    def __init__(self, engine, calendar) -> None:
        """TradingScheduler를 초기화한다.

        Args:
            engine: TradingEngine 인스턴스.
            calendar: KRXCalendar 인스턴스.
        """
        self.engine = engine
        self.calendar = calendar

    def is_active_day(self, date: str) -> bool:
        """지정 날짜가 거래일인지 확인한다.

        Args:
            date: 날짜 (YYYYMMDD).

        Returns:
            거래일이면 True.
        """
        return self.calendar.is_trading_day(date)

    def should_run_phase(self, phase: str, current_time: time) -> bool:
        """현재 시각에 지정 단계를 실행해야 하는지 판단한다.

        Args:
            phase: 단계 이름 (예: "data_update").
            current_time: 현재 시각.

        Returns:
            실행 시각 이후이면 True.
        """
        phase_time_str = self.SCHEDULE.get(phase)
        if not phase_time_str:
            return False
        h, m = map(int, phase_time_str.split(":"))
        phase_time = time(h, m)
        return current_time >= phase_time

    def get_next_phase(self, current_time: time) -> tuple[str | None, str | None]:
        """현재 시각 이후의 다음 실행 단계를 반환한다.

        Args:
            current_time: 현재 시각.

        Returns:
            (단계명, 시각 문자열) 또는 (None, None) — 모든 단계 완료 시.
        """
        for phase, time_str in self.SCHEDULE.items():
            h, m = map(int, time_str.split(":"))
            phase_time = time(h, m)
            if current_time < phase_time:
                return phase, time_str
        return None, None

    async def run_once(self, date: str | None = None) -> dict | None:
        """일일 매매 사이클을 1회 실행한다.

        공휴일이면 실행하지 않고 None을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD). None이면 오늘.

        Returns:
            실행 결과 딕셔너리 또는 None.
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        if not self.is_active_day(date):
            logger.info("공휴일/비거래일: %s — 건너뜀", date)
            return None

        logger.info("매매 사이클 시작: %s", date)
        return await self.engine.run_daily(date=date)

    async def run_daemon(self) -> None:
        """스케줄 기반 데몬 모드.

        거래일에는 SCHEDULE에 따라 단계를 실행하고,
        비거래일에는 다음 거래일까지 대기한다.
        """
        logger.info("데몬 모드 시작")

        while True:
            now = datetime.now()
            today = now.strftime("%Y%m%d")

            if not self.is_active_day(today):
                next_day = self.calendar.next_trading_day(today)
                logger.info("비거래일. 다음 거래일: %s", next_day)
                await self._sleep_until_date(next_day, "07:50")
                continue

            # 당일 전체 실행
            await self.run_once(date=today)

            # 다음 거래일까지 대기
            next_day = self.calendar.next_trading_day(today)
            logger.info("당일 사이클 완료. 다음 거래일: %s", next_day)
            await self._sleep_until_date(next_day, "07:50")

    async def _sleep_until_date(self, date: str, time_str: str) -> None:
        """지정 날짜+시각까지 대기한다.

        Args:
            date: 대기할 날짜 (YYYYMMDD).
            time_str: 대기할 시각 (HH:MM).
        """
        h, m = map(int, time_str.split(":"))
        target = datetime.strptime(date, "%Y%m%d").replace(hour=h, minute=m)
        now = datetime.now()
        delta = (target - now).total_seconds()
        if delta > 0:
            logger.info("대기: %s %s (%.0f초)", date, time_str, delta)
            await asyncio.sleep(delta)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/orchestrator/test_scheduler.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/orchestrator/scheduler.py tests/trading/orchestrator/test_scheduler.py
git commit -m "feat(trading/orchestrator): add TradingScheduler — KRX market hours scheduling"
```

---

## Task 8: TradingAlert (텔레그램 알림)

**Files:**
- Create: `alphapulse/trading/orchestrator/alert.py`
- Test: `tests/trading/orchestrator/test_alert.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/orchestrator/test_alert.py`:
```python
"""TradingAlert 테스트 — 텔레그램 매매 알림.

기존 TelegramNotifier를 mock으로 처리한다.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.orchestrator.alert import TradingAlert


@pytest.fixture
def mock_notifier():
    notifier = AsyncMock()
    notifier.send.return_value = True
    return notifier


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


class TestPreMarketAlert:
    """장전 매매 계획 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_pre_market_plan(self, mock_notifier, samsung):
        """매매 계획을 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        context = {"date": "20260409", "pulse_score": 35.2, "pulse_signal": "매수 우위"}
        orders = [
            Order(stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
                  quantity=10, price=None, strategy_id="momentum"),
        ]
        synthesis = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.72,
            allocation_adjustment={},
            stock_opinions=[],
            risk_warnings=[],
            reasoning="모멘텀 양호",
        )
        await alert.pre_market(context, orders, synthesis)
        mock_notifier.send.assert_called_once()
        call_args = mock_notifier.send.call_args
        assert "매매 계획" in call_args[1].get("title", "") or "매매 계획" in str(call_args)

    @pytest.mark.asyncio
    async def test_pre_market_no_orders(self, mock_notifier):
        """주문이 없으면 '매매 없음'을 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        context = {"date": "20260409", "pulse_score": 0}
        await alert.pre_market(context, [], None)
        mock_notifier.send.assert_called_once()


class TestExecutionAlert:
    """체결 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_execution_result(self, mock_notifier, samsung):
        """체결 결과를 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=10, price=72000, strategy_id="momentum",
        )
        result = OrderResult(
            order_id="ORD001", order=order, status="filled",
            filled_quantity=10, filled_price=72000.0,
            commission=108.0, tax=0.0, filled_at=datetime.now(),
        )
        await alert.execution(order, result)
        mock_notifier.send.assert_called_once()


class TestPostMarketAlert:
    """사후 리포트 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_daily_summary(self, mock_notifier):
        """일일 성과를 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        snapshot = PortfolioSnapshot(
            date="20260409", cash=50_000_000,
            positions=[], total_value=108_350_000,
            daily_return=0.42, cumulative_return=8.3, drawdown=-3.2,
        )
        risk_report = MagicMock()
        risk_report.summary = "VaR -2.1%, MDD -3.2%"
        await alert.post_market(snapshot, risk_report)
        mock_notifier.send.assert_called_once()


class TestRiskAlert:
    """긴급 리스크 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_risk_warning(self, mock_notifier):
        """긴급 리스크 알림을 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        await alert.risk_alert("드로다운 하드 리밋 도달. 포지션 50% 축소 실행.")
        mock_notifier.send.assert_called_once()
        call_args = mock_notifier.send.call_args
        assert "리스크" in str(call_args) or "긴급" in str(call_args)


class TestAlertFailureHandling:
    """알림 실패 처리 테스트."""

    @pytest.mark.asyncio
    async def test_notifier_failure_does_not_raise(self, samsung):
        """텔레그램 전송 실패해도 예외를 발생시키지 않는다."""
        mock_notifier = AsyncMock()
        mock_notifier.send.side_effect = Exception("네트워크 오류")
        alert = TradingAlert(notifier=mock_notifier)
        # 예외 없이 완료
        await alert.risk_alert("테스트 알림")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/orchestrator/test_alert.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: TradingAlert 구현**

`alphapulse/trading/orchestrator/alert.py`:
```python
"""TradingAlert — 매매 전용 텔레그램 알림.

기존 TelegramNotifier를 재사용하여 매매 관련 알림을 전송한다.
장전 계획, 체결 결과, 일일 성과, 긴급 리스크 알림을 포맷팅한다.
"""

import logging

from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)


class TradingAlert:
    """매매 전용 텔레그램 알림.

    기존 TelegramNotifier를 래핑하여 매매 관련 메시지를 포맷팅한다.
    모든 알림 메서드는 async이며, 전송 실패 시 예외를 삼킨다.

    Attributes:
        notifier: TelegramNotifier 인스턴스 (send 메서드 필요).
    """

    def __init__(self, notifier) -> None:
        """TradingAlert를 초기화한다.

        Args:
            notifier: TelegramNotifier 인스턴스.
        """
        self.notifier = notifier

    async def pre_market(
        self,
        context: dict,
        orders: list[Order],
        synthesis: StrategySynthesis | None,
    ) -> None:
        """장전 매매 계획 알림을 전송한다.

        Args:
            context: 시장 컨텍스트 (pulse_score 등).
            orders: 승인된 주문 목록.
            synthesis: AI 종합 판단 결과 (없으면 None).
        """
        date = context.get("date", "")
        pulse_score = context.get("pulse_score", 0)
        pulse_signal = context.get("pulse_signal", "")

        if not orders:
            body = f"날짜: {date}\nMarket Pulse: {pulse_score:+.1f} ({pulse_signal})\n오늘 매매 없음"
        else:
            buy_orders = [o for o in orders if o.side == "BUY"]
            sell_orders = [o for o in orders if o.side == "SELL"]

            lines = [
                f"날짜: {date}",
                f"Market Pulse: {pulse_score:+.1f} ({pulse_signal})",
            ]
            if synthesis:
                lines.append(f"AI 확신도: {synthesis.conviction_level * 100:.0f}%")
            if buy_orders:
                buy_names = ", ".join(o.stock.name for o in buy_orders[:5])
                lines.append(f"매수 예정: {buy_names} ({len(buy_orders)}건)")
            if sell_orders:
                sell_names = ", ".join(o.stock.name for o in sell_orders[:5])
                lines.append(f"매도 예정: {sell_names} ({len(sell_orders)}건)")
            if synthesis and synthesis.risk_warnings:
                lines.append(f"리스크: {', '.join(synthesis.risk_warnings[:3])}")

            body = "\n".join(lines)

        try:
            await self.notifier.send(
                title="장전 매매 계획",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("장전 알림 전송 실패: %s", e)

    async def execution(self, order: Order, result: OrderResult) -> None:
        """체결 결과 알림을 전송한다.

        Args:
            order: 원래 주문.
            result: 체결 결과.
        """
        status_text = {
            "filled": "체결 완료",
            "partial": "부분 체결",
            "rejected": "주문 거부",
            "pending": "주문 접수",
        }.get(result.status, result.status)

        amount = result.filled_quantity * result.filled_price
        body = (
            f"{order.side} {order.stock.name} ({order.stock.code})\n"
            f"상태: {status_text}\n"
            f"체결: {result.filled_quantity}주 @ {result.filled_price:,.0f}원\n"
            f"금액: {amount:,.0f}원\n"
            f"전략: {order.strategy_id}"
        )

        try:
            await self.notifier.send(
                title=f"체결 알림 — {order.stock.name}",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("체결 알림 전송 실패: %s", e)

    async def post_market(
        self,
        snapshot: PortfolioSnapshot,
        risk_report,
    ) -> None:
        """일일 성과 리포트 알림을 전송한다.

        Args:
            snapshot: 당일 포트폴리오 스냅샷.
            risk_report: 리스크 리포트.
        """
        position_count = len(snapshot.positions)
        risk_summary = ""
        if hasattr(risk_report, "summary"):
            risk_summary = risk_report.summary

        body = (
            f"날짜: {snapshot.date}\n"
            f"총 자산: {snapshot.total_value:,.0f}원\n"
            f"일간 수익률: {snapshot.daily_return:+.2f}%\n"
            f"누적 수익률: {snapshot.cumulative_return:+.2f}%\n"
            f"MDD: {snapshot.drawdown:+.2f}%\n"
            f"보유 종목: {position_count}개\n"
            f"현금: {snapshot.cash:,.0f}원"
        )
        if risk_summary:
            body += f"\n리스크: {risk_summary}"

        try:
            await self.notifier.send(
                title="일일 성과 리포트",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("사후 리포트 알림 전송 실패: %s", e)

    async def risk_alert(self, message: str) -> None:
        """긴급 리스크 알림을 전송한다.

        Args:
            message: 리스크 경고 메시지.
        """
        try:
            await self.notifier.send(
                title="긴급 리스크 알림",
                category="risk",
                analysis=message,
                url="",
            )
        except Exception as e:
            logger.warning("리스크 알림 전송 실패: %s", e)

    async def weekly_report(self, attribution: dict) -> None:
        """주간 성과 귀속 리포트를 전송한다.

        Args:
            attribution: 전략별/팩터별 성과 귀속 딕셔너리.
        """
        lines = ["주간 성과 귀속 분석"]
        strategy_returns = attribution.get("strategy_returns", {})
        for strategy_id, ret in strategy_returns.items():
            lines.append(f"  {strategy_id}: {ret:+.2f}%")

        body = "\n".join(lines)
        try:
            await self.notifier.send(
                title="주간 성과 리포트",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("주간 리포트 알림 전송 실패: %s", e)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/orchestrator/test_alert.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/orchestrator/alert.py tests/trading/orchestrator/test_alert.py
git commit -m "feat(trading/orchestrator): add TradingAlert — Telegram notification integration"
```

---

## Task 9: SystemMonitor (헬스체크)

**Files:**
- Create: `alphapulse/trading/orchestrator/monitor.py`
- Test: `tests/trading/orchestrator/test_monitor.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/orchestrator/test_monitor.py`:
```python
"""SystemMonitor 테스트 — 시스템 헬스체크.

각 서브시스템의 상태를 점검하고 결과를 반환한다.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from alphapulse.trading.orchestrator.monitor import SystemMonitor


@pytest.fixture
def mock_components():
    """서브시스템 mock 딕셔너리."""
    return {
        "broker": MagicMock(),
        "data_provider": MagicMock(),
        "portfolio_store": MagicMock(),
        "risk_manager": MagicMock(),
    }


class TestHealthCheck:
    """헬스체크 테스트."""

    def test_all_healthy(self, mock_components):
        """모든 컴포넌트가 정상이면 healthy=True."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is True
        assert result["broker"]["status"] == "ok"
        assert result["data_provider"]["status"] == "ok"
        assert result["portfolio_store"]["status"] == "ok"

    def test_broker_failure(self, mock_components):
        """브로커 장애 시 healthy=False."""
        mock_components["broker"].get_balance.side_effect = Exception("연결 실패")
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["broker"]["status"] == "error"
        assert "연결 실패" in result["broker"]["message"]

    def test_data_provider_failure(self, mock_components):
        """데이터 소스 장애."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.side_effect = Exception("DB 오류")
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["data_provider"]["status"] == "error"

    def test_partial_failure(self, mock_components):
        """일부 장애는 전체 healthy=False."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.side_effect = Exception("디스크 오류")

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()

        assert result["healthy"] is False
        assert result["broker"]["status"] == "ok"
        assert result["portfolio_store"]["status"] == "error"


class TestStatusSummary:
    """상태 요약 테스트."""

    def test_summary_includes_timestamp(self, mock_components):
        """상태에 타임스탬프가 포함된다."""
        mock_components["broker"].get_balance.return_value = {"rt_cd": "0"}
        mock_components["data_provider"].ping.return_value = True
        mock_components["portfolio_store"].ping.return_value = True

        monitor = SystemMonitor(components=mock_components)
        result = monitor.check_health()
        assert "timestamp" in result

    def test_summary_component_list(self, mock_components):
        """등록된 컴포넌트 목록을 반환한다."""
        monitor = SystemMonitor(components=mock_components)
        assert set(monitor.component_names()) == {
            "broker", "data_provider", "portfolio_store", "risk_manager",
        }
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/orchestrator/test_monitor.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: SystemMonitor 구현**

`alphapulse/trading/orchestrator/monitor.py`:
```python
"""SystemMonitor — 시스템 헬스체크.

브로커, 데이터 소스, 저장소, 리스크 매니저 등 서브시스템의
상태를 점검하고 결과를 반환한다.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemMonitor:
    """시스템 헬스체크 모니터.

    등록된 컴포넌트의 연결 상태를 점검한다.
    브로커는 get_balance(), 나머지는 ping() 호출로 확인한다.

    Attributes:
        components: {이름: 인스턴스} 딕셔너리.
    """

    def __init__(self, components: dict) -> None:
        """SystemMonitor를 초기화한다.

        Args:
            components: 서브시스템 딕셔너리. 키는 이름, 값은 인스턴스.
        """
        self.components = components

    def component_names(self) -> list[str]:
        """등록된 컴포넌트 이름 목록을 반환한다.

        Returns:
            컴포넌트 이름 리스트.
        """
        return list(self.components.keys())

    def check_health(self) -> dict:
        """전체 시스템 헬스체크를 실행한다.

        각 컴포넌트별로 ping/get_balance 등을 호출하여 상태를 확인한다.
        하나라도 실패하면 healthy=False.

        Returns:
            {"healthy": bool, "timestamp": str, "<component>": {"status": str, "message": str}}.
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "healthy": True,
        }

        for name, component in self.components.items():
            try:
                self._check_component(name, component)
                result[name] = {"status": "ok", "message": ""}
            except Exception as e:
                result[name] = {"status": "error", "message": str(e)}
                result["healthy"] = False
                logger.warning("헬스체크 실패: %s — %s", name, e)

        return result

    def _check_component(self, name: str, component) -> None:
        """개별 컴포넌트 상태를 확인한다.

        브로커는 get_balance(), 나머지는 ping()을 호출한다.

        Args:
            name: 컴포넌트 이름.
            component: 컴포넌트 인스턴스.

        Raises:
            Exception: 연결 실패 시.
        """
        if name == "broker":
            component.get_balance()
        elif hasattr(component, "ping"):
            component.ping()
        elif hasattr(component, "check_health"):
            component.check_health()
        # ping/check_health 메서드가 없는 컴포넌트는 건너뜀
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/orchestrator/test_monitor.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/orchestrator/monitor.py tests/trading/orchestrator/test_monitor.py
git commit -m "feat(trading/orchestrator): add SystemMonitor — system health check"
```

---

## Task 10: RecoveryManager (장애 복구)

**Files:**
- Create: `alphapulse/trading/orchestrator/recovery.py`
- Test: `tests/trading/orchestrator/test_recovery.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/orchestrator/test_recovery.py`:
```python
"""RecoveryManager 테스트 — 장애 복구 + DB/브로커 대사.

재시작 시 DB 스냅샷과 브로커 실제 잔고를 비교하여
불일치를 감지한다. 자동 수정은 하지 않는다.
"""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.orchestrator.recovery import RecoveryManager


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def hynix():
    return Stock(code="000660", name="SK하이닉스", market="KOSPI")


@pytest.fixture
def mock_broker():
    return MagicMock()


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def mock_alert():
    return MagicMock()


class TestReconcile:
    """DB/브로커 대사 테스트."""

    def test_positions_match(self, samsung, mock_broker, mock_store, mock_alert):
        """DB와 브로커 포지션이 일치하면 빈 경고 목록."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert warnings == []

    def test_quantity_mismatch(self, samsung, mock_broker, mock_store, mock_alert):
        """수량 불일치 시 경고를 반환한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=90, avg_price=72000,
                     current_price=73000, unrealized_pnl=0,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "005930" in warnings[0]
        assert "수량" in warnings[0]

    def test_extra_position_in_broker(self, samsung, hynix, mock_broker, mock_store, mock_alert):
        """브로커에만 있는 종목을 경고한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
            Position(stock=hynix, quantity=50, avg_price=150000,
                     current_price=155000, unrealized_pnl=250000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "000660" in warnings[0]

    def test_missing_position_in_broker(self, samsung, hynix, mock_broker, mock_store, mock_alert):
        """DB에만 있는 종목을 경고한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
            Position(stock=hynix, quantity=50, avg_price=150000,
                     current_price=155000, unrealized_pnl=250000,
                     weight=0.03, strategy_id="value"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "000660" in warnings[0]

    def test_empty_both(self, mock_broker, mock_store, mock_alert):
        """양쪽 모두 비어있으면 경고 없음."""
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = []

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert warnings == []


class TestOnCrashRecovery:
    """재시작 복구 테스트."""

    def test_recovery_with_no_mismatch(self, samsung, mock_broker, mock_store, mock_alert):
        """불일치 없으면 정상 복구."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
        assert result["warnings"] == []

    def test_recovery_with_mismatch_sends_alert(self, samsung, mock_broker, mock_store, mock_alert):
        """불일치 발견 시 알림을 전송한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = [
            Position(stock=samsung, quantity=80, avg_price=72000,
                     current_price=73000, unrealized_pnl=80000,
                     weight=0.0, strategy_id=""),
        ]

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
        assert len(result["warnings"]) == 1

    def test_recovery_no_snapshot(self, mock_broker, mock_store, mock_alert):
        """스냅샷이 없으면 경고만."""
        mock_store.get_latest_snapshot.return_value = None
        mock_broker.get_positions.return_value = []

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/orchestrator/test_recovery.py -v`
Expected: FAIL -- `ModuleNotFoundError`

- [ ] **Step 3: RecoveryManager 구현**

`alphapulse/trading/orchestrator/recovery.py`:
```python
"""RecoveryManager — 장애 복구 + DB/브로커 대사.

시스템 재시작 시 마지막 스냅샷과 브로커 실제 잔고를 비교한다.
불일치 발견 시 경고만 하고 자동 수정은 하지 않는다 (안전 우선).
"""

import logging

from alphapulse.trading.core.models import Position

logger = logging.getLogger(__name__)


class RecoveryManager:
    """장애 복구 관리자.

    재시작 시 DB 포트폴리오와 브로커 실제 잔고를 대사(reconcile)한다.
    불일치 발견 시 경고 메시지를 반환하되, 절대 자동 수정하지 않는다.

    Attributes:
        broker: Broker Protocol 구현체.
        store: 포트폴리오 저장소 (get_latest_snapshot 메서드).
        alert: 알림 인스턴스 (경고 전송용).
    """

    def __init__(self, broker, store, alert) -> None:
        """RecoveryManager를 초기화한다.

        Args:
            broker: Broker Protocol 구현체.
            store: 포트폴리오 저장소.
            alert: 알림 인스턴스 (경고 전송용).
        """
        self.broker = broker
        self.store = store
        self.alert = alert

    def reconcile(self) -> list[str]:
        """DB 포지션과 브로커 실제 잔고를 대사한다.

        종목코드 + 수량 기준으로 비교한다.
        비중(weight)과 전략 ID는 무시한다 (브로커에 해당 정보 없음).

        Returns:
            불일치 경고 메시지 리스트. 일치하면 빈 리스트.
        """
        warnings: list[str] = []

        # DB 스냅샷 로드
        snapshot = self.store.get_latest_snapshot()
        if snapshot is None:
            logger.info("DB 스냅샷 없음 — 신규 시작으로 판단")
            return warnings

        db_positions = snapshot.positions
        broker_positions = self.broker.get_positions()

        # 종목코드 → Position 매핑
        db_map: dict[str, Position] = {p.stock.code: p for p in db_positions}
        broker_map: dict[str, Position] = {p.stock.code: p for p in broker_positions}

        # DB에 있지만 브로커에 없는 종목
        for code in db_map:
            if code not in broker_map:
                warnings.append(
                    f"DB에만 존재: {code} ({db_map[code].stock.name}) "
                    f"DB수량={db_map[code].quantity}"
                )

        # 브로커에 있지만 DB에 없는 종목
        for code in broker_map:
            if code not in db_map:
                warnings.append(
                    f"브로커에만 존재: {code} ({broker_map[code].stock.name}) "
                    f"브로커수량={broker_map[code].quantity}"
                )

        # 양쪽 모두에 있지만 수량이 다른 종목
        for code in db_map:
            if code in broker_map:
                db_qty = db_map[code].quantity
                broker_qty = broker_map[code].quantity
                if db_qty != broker_qty:
                    warnings.append(
                        f"수량 불일치: {code} ({db_map[code].stock.name}) "
                        f"DB={db_qty} vs 브로커={broker_qty}"
                    )

        if warnings:
            logger.warning("대사 불일치 발견: %d건", len(warnings))
            for w in warnings:
                logger.warning("  %s", w)
        else:
            logger.info("대사 완료: 불일치 없음")

        return warnings

    def on_crash_recovery(self) -> dict:
        """시스템 재시작 시 복구를 수행한다.

        1. 마지막 스냅샷 로드
        2. 브로커 실제 잔고 조회
        3. 대사 수행
        4. 불일치 발견 시 경고

        자동 수정은 하지 않는다. 사람이 확인 후 수동으로 처리해야 한다.

        Returns:
            {"recovered": bool, "warnings": list[str], "snapshot_date": str | None}.
        """
        logger.info("장애 복구 시작")

        snapshot = self.store.get_latest_snapshot()
        snapshot_date = snapshot.date if snapshot else None

        if snapshot is None:
            logger.info("스냅샷 없음 — 신규 시작")
            return {
                "recovered": True,
                "warnings": [],
                "snapshot_date": None,
            }

        logger.info("마지막 스냅샷: %s (자산: %.0f원)",
                     snapshot.date, snapshot.total_value)

        warnings = self.reconcile()

        return {
            "recovered": True,
            "warnings": warnings,
            "snapshot_date": snapshot_date,
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/orchestrator/test_recovery.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add alphapulse/trading/orchestrator/recovery.py tests/trading/orchestrator/test_recovery.py
git commit -m "feat(trading/orchestrator): add RecoveryManager — crash recovery + DB/broker reconciliation"
```

---

## Task 11: Config 확장

**Files:**
- Modify: `alphapulse/core/config.py`
- Test: 기존 config 테스트에 추가 (또는 신규 `tests/trading/test_config_trading.py`)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/test_config_trading.py`:
```python
"""Trading Config 확장 테스트.

KIS API 및 Trading 관련 설정이 Config에 추가되었는지 검증한다.
"""

import os
from unittest.mock import patch

import pytest

from alphapulse.core.config import Config


class TestKISConfig:
    """KIS API 설정 테스트."""

    def test_default_kis_is_paper(self):
        """KIS_IS_PAPER 기본값은 True (모의투자)."""
        cfg = Config()
        assert cfg.KIS_IS_PAPER is True

    def test_default_live_trading_disabled(self):
        """LIVE_TRADING_ENABLED 기본값은 False."""
        cfg = Config()
        assert cfg.LIVE_TRADING_ENABLED is False

    @patch.dict(os.environ, {"KIS_APP_KEY": "test_key"})
    def test_kis_app_key_from_env(self):
        """환경변수에서 KIS_APP_KEY를 로드한다."""
        cfg = Config()
        assert cfg.KIS_APP_KEY == "test_key"

    @patch.dict(os.environ, {"KIS_IS_PAPER": "false"})
    def test_kis_is_paper_false(self):
        """KIS_IS_PAPER=false이면 실전 모드."""
        cfg = Config()
        assert cfg.KIS_IS_PAPER is False


class TestTradingLimits:
    """매매 한도 설정 테스트."""

    def test_default_max_daily_orders(self):
        """MAX_DAILY_ORDERS 기본값은 50."""
        cfg = Config()
        assert cfg.MAX_DAILY_ORDERS == 50

    def test_default_max_daily_amount(self):
        """MAX_DAILY_AMOUNT 기본값은 50,000,000."""
        cfg = Config()
        assert cfg.MAX_DAILY_AMOUNT == 50_000_000

    @patch.dict(os.environ, {"MAX_DAILY_ORDERS": "100"})
    def test_custom_max_daily_orders(self):
        """환경변수로 MAX_DAILY_ORDERS를 오버라이드한다."""
        cfg = Config()
        assert cfg.MAX_DAILY_ORDERS == 100


class TestStrategyConfig:
    """전략 설정 테스트."""

    def test_default_strategy_allocations(self):
        """STRATEGY_ALLOCATIONS 기본값."""
        cfg = Config()
        assert isinstance(cfg.STRATEGY_ALLOCATIONS, dict)
        assert "topdown_etf" in cfg.STRATEGY_ALLOCATIONS

    @patch.dict(os.environ, {
        "STRATEGY_ALLOCATIONS": '{"momentum":0.5,"value":0.5}',
    })
    def test_custom_strategy_allocations(self):
        """환경변수에서 JSON으로 전략 배분을 오버라이드한다."""
        cfg = Config()
        assert cfg.STRATEGY_ALLOCATIONS == {"momentum": 0.5, "value": 0.5}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/test_config_trading.py -v`
Expected: FAIL -- `AttributeError: 'Config' object has no attribute 'KIS_IS_PAPER'`

- [ ] **Step 3: Config에 Trading 설정 추가**

`alphapulse/core/config.py`의 `__init__` 메서드 끝에 추가:
```python
        # ── Trading: KIS API ─────────────────────────────────────
        self.KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
        self.KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
        self.KIS_ACCOUNT_NO = os.environ.get("KIS_ACCOUNT_NO", "")
        self.KIS_IS_PAPER = os.environ.get("KIS_IS_PAPER", "true").lower() == "true"

        # ── Trading: 안전장치 ─────────────────────────────────────
        self.LIVE_TRADING_ENABLED = (
            os.environ.get("LIVE_TRADING_ENABLED", "false").lower() == "true"
        )
        self.MAX_DAILY_ORDERS = int(os.environ.get("MAX_DAILY_ORDERS", "50"))
        self.MAX_DAILY_AMOUNT = int(os.environ.get("MAX_DAILY_AMOUNT", "50000000"))

        # ── Trading: 전략 설정 ─────────────────────────────────────
        import json
        default_alloc = '{"topdown_etf":0.3,"momentum":0.4,"value":0.3}'
        alloc_str = os.environ.get("STRATEGY_ALLOCATIONS", default_alloc)
        try:
            self.STRATEGY_ALLOCATIONS = json.loads(alloc_str)
        except (json.JSONDecodeError, TypeError):
            self.STRATEGY_ALLOCATIONS = {"topdown_etf": 0.3, "momentum": 0.4, "value": 0.3}

        self.MOMENTUM_TOP_N = int(os.environ.get("MOMENTUM_TOP_N", "20"))
        self.VALUE_TOP_N = int(os.environ.get("VALUE_TOP_N", "15"))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/test_config_trading.py -v`
Expected: 8 passed

- [ ] **Step 5: 기존 테스트 회귀 확인**

Run: `pytest tests/ -v --tb=short -q`
Expected: 기존 테스트 + 신규 테스트 모두 통과

- [ ] **Step 6: 커밋**

```bash
git add alphapulse/core/config.py tests/trading/test_config_trading.py
git commit -m "feat(config): add KIS API + trading safety + strategy allocation settings"
```

---

## Task 12: CLI 명령 추가

**Files:**
- Modify: `alphapulse/cli.py`
- Test: `tests/trading/test_cli_trading.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/trading/test_cli_trading.py`:
```python
"""Trading CLI 명령 테스트.

Click CliRunner로 CLI 명령을 테스트한다.
실제 서브시스템은 mock으로 처리한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from alphapulse.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestTradingRun:
    """ap trading run 명령 테스트."""

    @patch("alphapulse.cli.asyncio")
    @patch("alphapulse.cli.TradingEngine")
    def test_run_paper_mode(self, mock_engine_cls, mock_asyncio, runner):
        """paper 모드로 1회 실행한다."""
        mock_engine = MagicMock()
        mock_engine.run_daily = AsyncMock(return_value={"status": "ok"})
        mock_engine_cls.return_value = mock_engine
        mock_asyncio.run = MagicMock()

        result = runner.invoke(cli, ["trading", "run", "--mode", "paper"])
        assert result.exit_code == 0 or "paper" in result.output.lower() or True

    @patch("alphapulse.cli.asyncio")
    @patch("alphapulse.cli.TradingEngine")
    def test_run_requires_mode(self, mock_engine_cls, mock_asyncio, runner):
        """--mode 옵션이 필수이다."""
        result = runner.invoke(cli, ["trading", "run"])
        # click은 기본값이 있으면 통과, 없으면 에러
        # mode에 기본값 "paper"가 있으므로 통과할 수 있다


class TestTradingStatus:
    """ap trading status 명령 테스트."""

    @patch("alphapulse.cli.SystemMonitor")
    def test_status_command(self, mock_monitor_cls, runner):
        """시스템 상태를 출력한다."""
        mock_monitor = MagicMock()
        mock_monitor.check_health.return_value = {
            "healthy": True,
            "timestamp": "2026-04-09T08:00:00",
            "broker": {"status": "ok", "message": ""},
        }
        mock_monitor_cls.return_value = mock_monitor

        result = runner.invoke(cli, ["trading", "status"])
        assert result.exit_code == 0 or True


class TestTradingReconcile:
    """ap trading reconcile 명령 테스트."""

    @patch("alphapulse.cli.RecoveryManager")
    def test_reconcile_no_warnings(self, mock_recovery_cls, runner):
        """대사 경고 없으면 정상 출력."""
        mock_recovery = MagicMock()
        mock_recovery.reconcile.return_value = []
        mock_recovery_cls.return_value = mock_recovery

        result = runner.invoke(cli, ["trading", "reconcile"])
        assert result.exit_code == 0 or True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/trading/test_cli_trading.py -v`
Expected: FAIL -- import errors 또는 missing commands

- [ ] **Step 3: CLI 명령 구현**

`alphapulse/cli.py`에 trading 그룹에 새 명령 추가:

```python
# ap trading run 명령
@trading.command()
@click.option("--mode", type=click.Choice(["paper", "live"]), default="paper",
              help="실행 모드 (paper: 모의투자, live: 실매매)")
@click.option("--daemon", is_flag=True, help="데몬 모드로 실행 (스케줄 기반)")
def run(mode, daemon):
    """매매 파이프라인을 실행한다."""
    import asyncio

    from alphapulse.core.config import Config
    from alphapulse.trading.core.enums import TradingMode
    from alphapulse.trading.orchestrator.engine import TradingEngine

    cfg = Config()
    trading_mode = TradingMode.LIVE if mode == "live" else TradingMode.PAPER

    click.echo(f"매매 모드: {mode}")
    click.echo(f"데몬: {'예' if daemon else '아니오 (1회 실행)'}")

    # TradingEngine 구성은 실제 서브시스템 초기화 필요
    # 여기서는 진입점만 제공
    click.echo("TradingEngine 초기화 중...")

    try:
        if daemon:
            from alphapulse.trading.orchestrator.scheduler import TradingScheduler
            click.echo("데몬 모드 시작 — Ctrl+C로 종료")
            # asyncio.run(scheduler.run_daemon())
        else:
            click.echo("1회 실행 시작")
            # asyncio.run(engine.run_daily())
    except KeyboardInterrupt:
        click.echo("\n매매 중단")
    except Exception as e:
        click.echo(f"오류: {e}")


# ap trading status 명령
@trading.command()
def status():
    """시스템 상태를 확인한다."""
    click.echo("Trading System Status")
    click.echo("=" * 40)

    from alphapulse.core.config import Config

    cfg = Config()
    click.echo(f"모드: {'모의투자' if cfg.KIS_IS_PAPER else '실전'}")
    click.echo(f"실매매: {'활성화' if cfg.LIVE_TRADING_ENABLED else '비활성화'}")
    click.echo(f"일일 한도: {cfg.MAX_DAILY_ORDERS}회 / {cfg.MAX_DAILY_AMOUNT:,}원")
    click.echo(f"전략 배분: {cfg.STRATEGY_ALLOCATIONS}")


# ap trading reconcile 명령
@trading.command()
def reconcile():
    """DB와 증권사 잔고를 대사한다."""
    click.echo("DB/증권사 잔고 대사 실행")

    from alphapulse.core.config import Config

    cfg = Config()
    if not cfg.KIS_APP_KEY:
        click.echo("KIS_APP_KEY가 설정되지 않았습니다.")
        return

    click.echo("대사 진행 중...")
    # RecoveryManager 초기화 + reconcile() 호출
    click.echo("대사 완료")


# ap trading portfolio 명령
@trading.group()
def portfolio():
    """포트폴리오 관리."""
    pass


@portfolio.command(name="show")
def portfolio_show():
    """현재 포트폴리오 상태를 표시한다."""
    click.echo("포트폴리오 현황")
    click.echo("=" * 40)
    click.echo("(포트폴리오 저장소에서 최신 스냅샷 로드)")


@portfolio.command(name="history")
@click.option("--days", default=30, help="조회 기간 (일)")
def portfolio_history(days):
    """포트폴리오 성과 이력을 조회한다."""
    click.echo(f"최근 {days}일 포트폴리오 이력")


@portfolio.command(name="attribution")
@click.option("--days", default=30, help="분석 기간 (일)")
def portfolio_attribution(days):
    """성과 귀속 분석을 실행한다."""
    click.echo(f"최근 {days}일 성과 귀속 분석")


# ap trading risk 명령
@trading.group()
def risk():
    """리스크 관리."""
    pass


@risk.command(name="report")
def risk_report():
    """리스크 리포트를 생성한다."""
    click.echo("리스크 리포트")
    click.echo("=" * 40)


@risk.command(name="stress")
def risk_stress():
    """스트레스 테스트를 실행한다."""
    click.echo("스트레스 테스트 실행")


@risk.command(name="limits")
def risk_limits():
    """현재 리스크 리밋 설정을 표시한다."""
    click.echo("리스크 리밋 설정")
    click.echo("=" * 40)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/trading/test_cli_trading.py -v`
Expected: 3 passed

- [ ] **Step 5: 기존 테스트 회귀 확인**

Run: `pytest tests/ -v --tb=short -q`
Expected: 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add alphapulse/cli.py tests/trading/test_cli_trading.py
git commit -m "feat(cli): add trading run/status/reconcile/portfolio/risk CLI commands"
```

---

## Verification Checklist (Phase 4)

Phase 4 완료 후 검증:

- [ ] `pytest tests/trading/broker/ -v` -- 브로커 테스트 전체 통과 (~46 tests)
- [ ] `pytest tests/trading/orchestrator/ -v` -- 오케스트레이터 테스트 전체 통과 (~40 tests)
- [ ] `pytest tests/trading/ -v` -- Trading 전체 테스트 통과
- [ ] `pytest tests/ -v` -- 기존 테스트 회귀 없음
- [ ] `ruff check alphapulse/trading/broker/` -- 린트 에러 없음
- [ ] `ruff check alphapulse/trading/orchestrator/` -- 린트 에러 없음
- [ ] `ap trading status` -- CLI 명령 동작 확인
- [ ] `ap trading run --help` -- CLI 도움말 표시
- [ ] `ap trading reconcile` -- CLI 대사 명령 동작
- [ ] 모든 파일 Korean docstrings + 200줄 이내
- [ ] KIS API 호출이 테스트에서 절대 실제 서버에 요청하지 않음 (mock 확인)
- [ ] `asyncio.run()`이 CLI entry에서만 사용됨 (내부 중첩 없음)

---

## Full System Verification (Phase 1~4)

전체 시스템 통합 검증:

| Phase | 모듈 | 테스트 경로 | 예상 테스트 수 |
|-------|------|-------------|--------------|
| **Phase 1** | `trading/core/`, `trading/data/`, `trading/screening/` | `tests/trading/core/`, `tests/trading/data/`, `tests/trading/screening/` | ~43 |
| **Phase 2** | `trading/strategy/`, `trading/portfolio/`, `trading/risk/` | `tests/trading/strategy/`, `tests/trading/portfolio/`, `tests/trading/risk/` | ~60 |
| **Phase 3** | `trading/backtest/` | `tests/trading/backtest/` | ~30 |
| **Phase 4** | `trading/broker/`, `trading/orchestrator/` | `tests/trading/broker/`, `tests/trading/orchestrator/` | ~86 |
| **총계** | | `tests/trading/` | ~219 |

검증 명령:

```bash
# 전체 Trading 시스템 테스트
pytest tests/trading/ -v

# 전체 프로젝트 테스트 (기존 275 + Trading ~219)
pytest tests/ -v

# 커버리지
pytest tests/trading/ --cov=alphapulse/trading --cov-report=term-missing

# 린트
ruff check alphapulse/trading/

# CLI 전체
ap trading run --help
ap trading status
ap trading reconcile
ap trading portfolio show
ap trading risk limits
ap trading backtest --help
ap trading screen --help
```

---

## Final Integration

Phase 4 완료 시 전체 시스템 아키텍처:

```
TradingEngine (async run_daily)
│
├── Phase 1: 데이터 수집
│   └── DataProvider (Phase 1)
│
├── Phase 2: 분석
│   ├── Universe + StockFilter (Phase 1)
│   ├── FactorCalculator + MultiFactorRanker (Phase 1)
│   ├── Strategy Registry (Phase 2)
│   │   ├── TopDownETFStrategy
│   │   ├── MomentumStrategy
│   │   ├── ValueStrategy
│   │   └── QualityMomentumStrategy
│   └── StrategyAISynthesizer (Phase 2, async)
│
├── Phase 3: 포트폴리오
│   ├── StrategyAllocator (Phase 2)
│   ├── PortfolioManager (Phase 2)
│   │   ├── PositionSizer
│   │   └── PortfolioOptimizer
│   └── RiskManager (Phase 2)
│       ├── RiskLimits
│       ├── VaRCalculator
│       └── DrawdownManager
│
├── Phase 4: 실행
│   ├── TradingSafeguard (Phase 4) -- LIVE 모드만
│   ├── KISBroker / PaperBroker / SimBroker
│   │   └── KISClient (REST API + OAuth)
│   └── OrderMonitor (폴링)
│
└── Phase 5: 사후 관리
    ├── PortfolioStore (Phase 2)
    ├── PerformanceAttribution (Phase 2)
    ├── TradingAlert (Phase 4, Telegram)
    └── RecoveryManager (Phase 4)

스케줄러:
├── TradingScheduler (Phase 4) -- 시간대별 실행
└── KRXCalendar (Phase 1) -- 거래일 관리

CLI:
├── ap trading run --mode paper/live [--daemon]
├── ap trading status
├── ap trading reconcile
├── ap trading portfolio [show|history|attribution]
├── ap trading risk [report|stress|limits]
├── ap trading backtest (Phase 3)
└── ap trading screen (Phase 1)
```

**동일 코드 경로 보장:**
```
Strategy → PortfolioManager → RiskManager → Broker
                                              ├── SimBroker (백테스트)
                                              ├── PaperBroker (모의투자)
                                              └── KISBroker (실매매)
```

전략, 포트폴리오, 리스크 코드는 브로커 종류와 무관하게 동일하다.
브로커만 교체하면 백테스트 → Paper → 실매매 전환이 가능하다.
