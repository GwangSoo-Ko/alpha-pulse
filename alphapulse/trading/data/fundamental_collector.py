"""재무제표 수집기 — 네이버 금융 웹 크롤링 기반.

네이버 금융 종목 메인 페이지(finance.naver.com/item/main.naver)에서
PER, PBR, 배당수익률을 병렬 크롤링한다.

기본 PER/PBR은 빠른 수집에 적합하다. 심층 재무 데이터가 필요하면
WisereportCollector를 사용한다 (시가총액, 베타, 컨센서스, 재무 시계열).
"""

import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.rate_bucket import RateBucket
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

NAVER_MAIN_URL = "https://finance.naver.com/item/main.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 전역 rate limiter: 네이버 차단 방지
_RATE_BUCKET = RateBucket(rate=8.0, capacity=8)


class FundamentalCollector:
    """재무제표 수집기 (네이버 금융 크롤링 기반).

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(
        self,
        date: str,
        codes: list[str] | None = None,
        market: str = "KOSPI",
        max_workers: int = 5,
        progress_callback=None,
    ) -> None:
        """PER/PBR/배당수익률을 병렬 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (YYYYMMDD).
            codes: 종목코드 리스트 (None이면 DB의 전 종목).
            market: 시장 (codes가 None일 때 사용).
            max_workers: 동시 요청 수. 기본 5.
            progress_callback: 종목 완료 시 code 전달.
        """
        if codes is None:
            stocks = self.store.get_all_stocks(market=market)
            codes = [s["code"] for s in stocks]

        store_lock = threading.Lock()
        collected = 0
        collected_lock = threading.Lock()

        def _collect_one(code: str) -> tuple[str, bool]:
            nonlocal collected
            try:
                resp = self._safe_get(NAVER_MAIN_URL, {"code": code})
                if resp is None:
                    return code, False

                soup = BeautifulSoup(resp.text, "html.parser")
                per, pbr, div_yield = self._parse_fundamentals(soup)
                financial = self._parse_financial_summary(soup)

                if per is not None or pbr is not None or financial:
                    with store_lock:
                        self.store.save_fundamental(
                            code=code,
                            date=date,
                            per=per,
                            pbr=pbr,
                            dividend_yield=div_yield,
                            **financial,
                        )
                    with collected_lock:
                        collected += 1
                    return code, True
            except Exception as e:
                logger.debug("재무 수집 실패: %s: %s", code, e)
            return code, False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_collect_one, code): code for code in codes}
            for future in as_completed(futures):
                try:
                    code, _ok = future.result()
                except Exception:
                    code = futures[future]
                if progress_callback:
                    progress_callback(code)

        if collected:
            logger.info("재무제표 저장: %d종목 (%s)", collected, date)

    @staticmethod
    def _safe_get(url: str, params: dict) -> requests.Response | None:
        """rate bucket + 429 지수 백오프 재시도."""
        for attempt in range(3):
            _RATE_BUCKET.acquire()
            try:
                resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
                if resp.status_code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("fundamental 429 수신. %.1f초 대기", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    return None
                return resp
            except Exception:
                if attempt == 2:
                    return None
                time.sleep(1 + random.uniform(0, 0.5))
        return None

    def _parse_fundamentals(self, soup: BeautifulSoup) -> tuple:
        """네이버 금융 메인 페이지에서 PER, PBR, 배당수익률을 추출한다.

        Args:
            soup: BeautifulSoup 파싱 결과.

        Returns:
            (per, pbr, dividend_yield) 튜플. 값이 없으면 None.
        """
        per = None
        pbr = None
        div_yield = None

        table = soup.select_one("table.per_table")
        if not table:
            return per, pbr, div_yield

        for tr in table.select("tr"):
            tds = tr.select("td, th")
            if len(tds) < 2:
                continue
            header = tds[0].text.strip()
            value = tds[1].text.strip()

            if header.startswith("PER") and "추정" not in header:
                per = self._extract_number(value)
            elif header.startswith("PBR"):
                pbr = self._extract_number(value)
            elif "배당수익률" in header:
                div_yield = self._extract_number(value)

        return per, pbr, div_yield

    def _parse_financial_summary(self, soup: BeautifulSoup) -> dict:
        """기업실적분석 테이블에서 ROE/매출/영업이익/부채비율 등을 추출한다.

        네이버 금융 item/main.naver 페이지의 `table.tb_type1.tb_type1_ifrs`는
        '최근 연간 실적' (보통 3개 연간 + 1개 추정) + '최근 분기 실적' 구조.
        가장 최근 연간 실적 (E가 아닌 마지막 연간 컬럼) 값을 추출한다.

        Args:
            soup: BeautifulSoup 파싱 결과.

        Returns:
            {roe, revenue, operating_profit, net_income, debt_ratio,
             operating_margin, net_margin} 딕셔너리. 값이 없으면 포함하지 않음.
        """
        data: dict = {}

        # 기업실적분석 테이블 찾기
        table = None
        for t in soup.select("table.tb_type1"):
            classes = t.get("class") or []
            if "tb_type1_ifrs" in classes:
                tbl_text = t.get_text()
                if "ROE" in tbl_text and "매출액" in tbl_text:
                    table = t
                    break

        if table is None:
            return data

        # 연간 실적 컬럼 개수 파악
        # thead 첫 tr에 '주요재무정보', '최근 연간 실적' (colspan=N), '최근 분기 실적' 구조
        annual_count = 0
        thead = table.select_one("thead")
        if thead:
            first_tr = thead.select_one("tr")
            if first_tr:
                for th in first_tr.select("th"):
                    text = th.get_text(strip=True)
                    if "연간" in text:
                        colspan = th.get("colspan")
                        if colspan:
                            try:
                                annual_count = int(colspan)
                            except ValueError:
                                pass
                        break

        if annual_count == 0:
            return data

        # 두 번째 tr = 실제 기간 헤더
        period_row = None
        if thead:
            trs = thead.select("tr")
            if len(trs) >= 2:
                period_row = trs[1]
        if period_row is None:
            return data

        # 연간 실적 구간 내에서 E가 아닌 마지막 컬럼 찾기
        period_ths = period_row.select("th")
        target_col_idx = None  # 0부터 시작 (데이터 컬럼 기준)
        for i in range(min(annual_count, len(period_ths))):
            text = period_ths[i].get_text(strip=True)
            if "(E)" not in text and re.match(r"\d{4}\.\d{2}", text):
                target_col_idx = i

        if target_col_idx is None:
            return data

        # 행별 데이터 추출 (tbody tr)
        field_map = [
            ("ROE", "roe"),
            ("부채비율", "debt_ratio"),
            ("영업이익률", "operating_margin"),
            ("순이익률", "net_margin"),
            ("영업이익", "operating_profit"),
            ("당기순이익", "net_income"),
            ("매출액", "revenue"),
        ]

        tbody = table.select_one("tbody")
        if tbody is None:
            return data

        for tr in tbody.select("tr"):
            # tr 구조: <th>label</th><td>...</td><td>...</td>...
            label_th = tr.select_one("th")
            if label_th is None:
                continue
            label = label_th.get_text(strip=True)

            tds = tr.select("td")
            if target_col_idx >= len(tds):
                continue

            for key, field in field_map:
                if label.startswith(key):
                    value = tds[target_col_idx].get_text(strip=True)
                    parsed = self._extract_number(value)
                    if parsed is not None:
                        data[field] = parsed
                    break

        return data

    @staticmethod
    def _extract_number(text: str) -> float | None:
        """'31.73배' 또는 '0.80%' 에서 숫자를 추출한다."""
        # 음수 처리 + 콤마 제거
        cleaned = text.strip().replace(",", "")
        match = re.search(r"-?[\d.]+", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        return None
