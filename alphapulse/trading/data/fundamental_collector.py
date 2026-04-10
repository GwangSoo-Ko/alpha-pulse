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

                if per is not None or pbr is not None:
                    with store_lock:
                        self.store.save_fundamental(
                            code=code,
                            date=date,
                            per=per,
                            pbr=pbr,
                            dividend_yield=div_yield,
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

    @staticmethod
    def _extract_number(text: str) -> float | None:
        """'31.73배' 또는 '0.80%' 에서 숫자를 추출한다."""
        match = re.search(r"([\d.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
