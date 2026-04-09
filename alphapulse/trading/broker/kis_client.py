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
# 포트 번호는 KIS API 공식 문서 기준 (모의투자 :29443, 실전 :9443).
# KIS가 포트를 변경할 수 있으므로 최신 문서를 확인할 것.
# NOTE: 설계 문서(spec)에는 포트 번호가 누락되어 있으므로 spec도 업데이트 필요.
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

        self._timeout = 10

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
        resp = requests.post(url, json=body, headers=self._headers(tr_id))
        resp.raise_for_status()
        result = resp.json()
        logger.info(
            "주문 제출: %s %s %s주 @%s → %s",
            side, code, qty, price, result.get("rt_cd"),
        )
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
        resp = requests.post(url, json=body, headers=self._headers(tr_id))
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
        resp = requests.get(url, params=params, headers=self._headers(tr_id))
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
        resp = requests.get(url, params=params, headers=self._headers(tr_id))
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
        resp = requests.get(url, params=params, headers=self._headers(tr_id))
        resp.raise_for_status()
        return resp.json()
