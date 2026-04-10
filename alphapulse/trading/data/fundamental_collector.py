"""재무제표 수집기 — 네이버 금융 웹 크롤링 기반.

네이버 금융 종목 메인 페이지(finance.naver.com/item/main.naver)에서
PER, PBR, 배당수익률을 크롤링한다.
"""

import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

NAVER_MAIN_URL = "https://finance.naver.com/item/main.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}


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
    ) -> None:
        """PER/PBR/배당수익률을 수집하여 DB에 저장한다.

        네이버 금융 종목 메인 페이지의 per_table에서 데이터를 추출한다.

        Args:
            date: 기준일 (YYYYMMDD).
            codes: 종목코드 리스트 (None이면 DB의 전 종목).
            market: 시장 (codes가 None일 때 사용).
        """
        if codes is None:
            stocks = self.store.get_all_stocks(market=market)
            codes = [s["code"] for s in stocks]

        collected = 0
        for code in codes:
            try:
                resp = requests.get(
                    NAVER_MAIN_URL,
                    params={"code": code},
                    headers=HEADERS,
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                per, pbr, div_yield = self._parse_fundamentals(soup)

                if per is not None or pbr is not None:
                    self.store.save_fundamental(
                        code=code,
                        date=date,
                        per=per,
                        pbr=pbr,
                        dividend_yield=div_yield,
                    )
                    collected += 1

            except Exception as e:
                logger.debug("재무 수집 실패: %s: %s", code, e)
                continue

            time.sleep(0.2)

        if collected:
            logger.info("재무제표 저장: %d종목 (%s)", collected, date)

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
