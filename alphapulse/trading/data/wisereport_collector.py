"""네이버 기업정보(wisereport) 수집기.

wisereport 기업현황 페이지에서 종목별 재무 데이터를 수집한다.
- 정적 데이터 (requests): 시장정보, 주요지표, 컨센서스
- 동적 데이터 (crawl4ai): Financial Summary (재무 시계열)
"""

import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

WISEREPORT_URL = (
    "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx"
)
HEADERS = {"User-Agent": "Mozilla/5.0"}


class WisereportCollector:
    """네이버 기업정보(wisereport) 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    # ── 정적 수집 (requests + BS4) ─────────────────────────────────

    def collect_static(self, code: str, date: str) -> dict:
        """requests+BS4로 정적 데이터를 수집한다.

        시가총액, 베타, 외국인지분율, 수익률, PER/PBR/EPS,
        컨센서스, 주요주주 지분율을 추출한다.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            파싱된 데이터 dict. 실패 시 빈 dict.
        """
        try:
            resp = requests.get(
                WISEREPORT_URL,
                params={"cmp_cd": code},
                headers=HEADERS,
                timeout=10,
            )
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            data: dict = {}

            self._parse_market_info(soup, data)
            self._parse_key_indicators(soup, data)
            self._parse_consensus(soup, data)

            if not data:
                return {}

            self.store.save_wisereport(code, date, **data)
            return data

        except Exception as e:
            logger.debug("wisereport 정적 수집 실패: %s: %s", code, e)
            return {}

    def collect_static_batch(
        self,
        codes: list[str],
        date: str,
        delay: float = 0.3,
    ) -> dict[str, dict]:
        """여러 종목의 정적 데이터를 순차 수집한다.

        Args:
            codes: 종목코드 리스트.
            date: 기준일 (YYYYMMDD).
            delay: 요청 간 딜레이 (초).

        Returns:
            {code: data} 딕셔너리. 수집 실패 종목은 제외.
        """
        results: dict[str, dict] = {}
        for code in codes:
            data = self.collect_static(code, date)
            if data:
                results[code] = data
            time.sleep(delay)

        if results:
            logger.info(
                "wisereport 정적 수집: %d/%d종목 (%s)",
                len(results), len(codes), date,
            )
        return results

    # ── 재무 시계열 (crawl4ai) ─────────────────────────────────────

    async def collect_financials(self, code: str, date: str) -> dict:
        """crawl4ai로 JS 렌더링 후 재무 시계열을 수집한다.

        연간 매출액, 영업이익, 순이익, ROE, ROA, 부채비율 등을 추출한다.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            파싱된 재무 데이터 dict. 실패 시 빈 dict.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            url = f"{WISEREPORT_URL}?cmp_cd={code}"
            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(
                wait_until="networkidle",
                delay_before_return_html=3.0,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if not result.success:
                    logger.debug("wisereport 크롤링 실패: %s", code)
                    return {}

                soup = BeautifulSoup(result.html, "html.parser")
                data = self._parse_financial_summary(soup)

                if data:
                    self.store.save_wisereport(code, date, **data)
                return data

        except Exception as e:
            logger.debug("wisereport 재무 수집 실패: %s: %s", code, e)
            return {}

    async def collect_financials_batch(
        self,
        codes: list[str],
        date: str,
    ) -> dict[str, dict]:
        """여러 종목의 재무 시계열을 순차 수집한다.

        Args:
            codes: 종목코드 리스트.
            date: 기준일 (YYYYMMDD).

        Returns:
            {code: data} 딕셔너리. 수집 실패 종목은 제외.
        """
        results: dict[str, dict] = {}
        for code in codes:
            data = await self.collect_financials(code, date)
            if data:
                results[code] = data

        if results:
            logger.info(
                "wisereport 재무 수집: %d/%d종목 (%s)",
                len(results), len(codes), date,
            )
        return results

    # ── 파싱 헬퍼 ──────────────────────────────────────────────────

    def _parse_market_info(self, soup: BeautifulSoup, data: dict) -> None:
        """시장정보 테이블에서 시가총액, 베타, 외국인지분율 등을 추출한다."""
        field_map = {
            "시가총액": "market_cap",
            "52주최고": "high_52w",
            "52주최저": "low_52w",
            "52주베타": "beta",
            "외국인지분율": "foreign_pct",
            "수익률(1M)": "return_1m",
            "수익률(3M)": "return_3m",
            "수익률(6M)": "return_6m",
            "수익률(1Y)": "return_1y",
        }

        for tr in soup.select("table tr"):
            cells = tr.select("th, td")
            if len(cells) < 2:
                continue
            key = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)

            for label, field in field_map.items():
                if key == label:
                    parsed = self._parse_number(val)
                    if parsed is not None:
                        data[field] = parsed
                    break

    def _parse_key_indicators(self, soup: BeautifulSoup, data: dict) -> None:
        """주요지표 테이블에서 PER, PBR, EPS 등을 추출한다."""
        table = soup.select_one("table#cTB11")
        if not table:
            return

        # 헤더 확인: 실적(A) vs 추정(E) 컬럼 인덱스 파악
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        actual_idx = None
        est_idx = None
        for i, h in enumerate(headers):
            if "(A)" in h:
                actual_idx = i
            elif "(E)" in h:
                est_idx = i

        indicator_map = {
            "PER": "per",
            "PBR": "pbr",
            "PCR": "pcr",
            "EV/EBITDA": "ev_ebitda",
            "EPS": "eps",
            "BPS": "bps",
            "배당수익률": "dividend_yield",
        }

        for tr in table.select("tbody tr"):
            cells = tr.select("td")
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True)

            for key, field in indicator_map.items():
                if label.startswith(key):
                    # 실적 값
                    if actual_idx is not None and actual_idx < len(cells):
                        val = self._parse_number(
                            cells[actual_idx].get_text(strip=True)
                        )
                        if val is not None:
                            data[field] = val

                    # 추정 값 (PER, EPS만)
                    if (
                        key in ("PER", "EPS")
                        and est_idx is not None
                        and est_idx < len(cells)
                    ):
                        est_val = self._parse_number(
                            cells[est_idx].get_text(strip=True)
                        )
                        if est_val is not None:
                            est_field = f"est_{field}"
                            data[est_field] = est_val
                    break

    def _parse_consensus(self, soup: BeautifulSoup, data: dict) -> None:
        """컨센서스 테이블에서 목표가, 투자의견, 추정기관수를 추출한다."""
        table = soup.select_one("table#cTB13")
        if not table:
            return

        headers = [
            th.get_text(strip=True) for th in table.select("thead th")
        ]
        rows = table.select("tbody tr")
        if not rows:
            return

        cells = rows[0].select("td")
        if len(cells) < len(headers):
            return

        for i, header in enumerate(headers):
            val = self._parse_number(cells[i].get_text(strip=True))
            if val is None:
                continue

            if "투자의견" in header:
                data["consensus_opinion"] = val
            elif "목표주가" in header:
                data["target_price"] = val
            elif "추정기관수" in header:
                data["analyst_count"] = int(val)

    def _parse_financial_summary(self, soup: BeautifulSoup) -> dict:
        """Financial Summary 테이블에서 최근 연간 재무 데이터를 추출한다."""
        table = soup.select_one("table#cTB15")
        if not table:
            return {}

        # 긴 키를 먼저 매칭하여 "영업이익률"이 "영업이익"보다 우선되도록 정렬
        field_map = [
            ("영업이익률", "operating_margin"),
            ("순이익률", "net_margin"),
            ("영업이익", "operating_profit"),
            ("순이익", "net_income"),
            ("매출액", "revenue"),
            ("ROE", "roe"),
            ("ROA", "roa"),
            ("부채비율", "debt_ratio"),
        ]

        data: dict = {}
        for tr in table.select("tbody tr"):
            cells = tr.select("td")
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True)

            for key, field in field_map:
                if label.startswith(key):
                    # 마지막 컬럼 = 최근 연간 데이터
                    last_val = cells[-1].get_text(strip=True)
                    parsed = self._parse_number(last_val)
                    if parsed is not None:
                        data[field] = parsed
                    break

        return data

    @staticmethod
    def _parse_number(text: str) -> float | None:
        """문자열에서 숫자를 추출한다.

        콤마, 퍼센트 기호, 단위(배/원/억원) 등을 처리한다.

        Args:
            text: 파싱할 문자열.

        Returns:
            추출된 숫자. 파싱 실패 시 None.
        """
        if not text or text.strip() in ("", "N/A", "-"):
            return None

        cleaned = text.replace(",", "").replace("%", "")
        match = re.search(r"-?[\d.]+", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        return None
