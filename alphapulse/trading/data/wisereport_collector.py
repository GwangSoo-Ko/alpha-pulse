"""네이버 기업정보(wisereport) 수집기.

wisereport 기업현황 페이지에서 종목별 재무 데이터를 수집한다.
- 정적 데이터 (requests): 시장정보, 주요지표, 컨센서스
- 동적 데이터 (crawl4ai): Financial Summary (재무 시계열)
"""

import logging
import random
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.rate_bucket import RateBucket
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

WISEREPORT_BASE = "https://navercomp.wisereport.co.kr/v2/company"
WISEREPORT_URL = f"{WISEREPORT_BASE}/c1010001.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com",
}

# 전역 rate limiter: 초당 8회, 모든 wisereport 호출에 공유
_WISEREPORT_BUCKET = RateBucket(rate=8.0, capacity=8)


def _safe_get(url: str, params: dict, timeout: int = 10) -> requests.Response | None:
    """rate limiting + 429 지수 백오프 재시도가 적용된 HTTP GET.

    Returns:
        성공 시 Response. 실패 시 None.
    """
    for attempt in range(3):
        _WISEREPORT_BUCKET.acquire()
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if resp.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("wisereport 429 수신. %.1f초 대기", wait)
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
            resp = _safe_get(WISEREPORT_URL, {"cmp_cd": code})
            if resp is None:
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
        max_workers: int = 5,
        progress_callback=None,
    ) -> dict[str, dict]:
        """여러 종목의 정적 데이터를 병렬 수집한다.

        ThreadPoolExecutor로 동시 HTTP 요청하여 10배 빠르게 수집한다.
        SQLite 쓰기는 내부 lock으로 직렬화된다.

        Args:
            codes: 종목코드 리스트.
            date: 기준일 (YYYYMMDD).
            delay: 사용되지 않음 (호환성 유지).
            max_workers: 동시 요청 수. 기본 10.
            progress_callback: 진행률 콜백 (완료 시 code 전달).

        Returns:
            {code: data} 딕셔너리. 수집 실패 종목은 제외.
        """
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, dict] = {}
        results_lock = threading.Lock()

        def _collect_one(code: str) -> tuple[str, dict]:
            try:
                data = self.collect_static(code, date)
                return code, data
            except Exception as e:
                logger.debug("wisereport 정적 실패: %s: %s", code, e)
                return code, {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_collect_one, code): code for code in codes
            }
            for future in as_completed(futures):
                try:
                    code, data = future.result()
                    if data:
                        with results_lock:
                            results[code] = data
                    if progress_callback:
                        progress_callback(code)
                except Exception:
                    pass

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

    # ── 기업개요 (c1020001) — 정적 ─────────────────────────────────

    def collect_overview(self, code: str, date: str) -> dict:
        """기업개요 — 매출구성, R&D 비율, 종업원수, 관계사.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            파싱된 기업개요 dict. 실패 시 빈 dict.
        """
        import json

        try:
            resp = _safe_get(
                f"{WISEREPORT_BASE}/c1020001.aspx",
                {"cmp_cd": code},
            )
            if resp is None:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            data: dict = {}

            for table in soup.select("table"):
                ths = [th.get_text(strip=True) for th in table.select("tr:first-child th")]
                if "제품명" in ths and "구성비" in ths:
                    products = []
                    for tr in table.select("tr")[1:]:
                        tds = tr.select("td")
                        if len(tds) >= 2:
                            name = tds[0].get_text(strip=True)
                            ratio = self._parse_number(tds[1].get_text(strip=True))
                            if name and ratio is not None:
                                products.append({"name": name, "ratio": ratio})
                    if products:
                        data["products"] = json.dumps(products, ensure_ascii=False)
                    break

            for table in soup.select("table"):
                if "연구개발비" in table.get_text():
                    for tr in table.select("tr")[1:2]:
                        tds = tr.select("td")
                        if len(tds) >= 3:
                            data["rd_expense"] = self._parse_number(tds[1].get_text(strip=True))
                            data["rd_ratio"] = self._parse_number(tds[2].get_text(strip=True))
                    break

            for table in soup.select("table"):
                if "기말인원" in table.get_text():
                    for tr in table.select("tr"):
                        if "(계)" in tr.get_text():
                            for td in tr.select("td"):
                                val = self._parse_number(td.get_text(strip=True))
                                if val and val > 100:
                                    data["employees"] = int(val)
                                    break
                            break
                    break

            for table in soup.select("table"):
                ths = [th.get_text(strip=True) for th in table.select("tr:first-child th, tr:first-child td")]
                if "관계사명" in ths:
                    data["subsidiary_count"] = len([tr for tr in table.select("tr")[1:] if tr.select("td")])
                    break

            if data:
                self.store.save_company_overview(code, date, **data)
            return data

        except Exception as e:
            logger.debug("기업개요 수집 실패: %s: %s", code, e)
            return {}

    # ── 섹터분석/지분현황 (c1070001) — 정적 ──────────────────────

    def collect_shareholders(self, code: str, date: str) -> dict:
        """주주 구성 및 지분 변동.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            주주 데이터 dict. 실패 시 빈 dict.
        """
        import json

        try:
            resp = _safe_get(
                f"{WISEREPORT_BASE}/c1070001.aspx",
                {"cmp_cd": code},
            )
            if resp is None:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            data: dict = {}

            for table in soup.select("table"):
                if "최대주주" in table.get_text() and "유동주식" in table.get_text():
                    for td in table.select("td"):
                        pct = re.search(r"([\d.]+)%", td.get_text())
                        if pct and "유동" in td.parent.get_text():
                            data["float_pct"] = float(pct.group(1))
                    break

            for table in soup.select("table"):
                ths = [th.get_text(strip=True) for th in table.select("tr:first-child th")]
                if "대표주주" in ths and any("보유지분" in h for h in ths):
                    rows = table.select("tr")
                    if len(rows) >= 2:
                        tds = rows[1].select("td")
                        if len(tds) >= 4:
                            data["largest_holder"] = tds[0].get_text(strip=True)[:50]
                            pct = self._parse_number(tds[3].get_text(strip=True))
                            if pct is not None:
                                data["largest_pct"] = pct
                    changes = []
                    for tr in rows[1:6]:
                        tds = tr.select("td")
                        if len(tds) >= 6:
                            changes.append({
                                "holder": tds[1].get_text(strip=True)[:20],
                                "pct": tds[3].get_text(strip=True),
                            })
                    if changes:
                        data["changes"] = json.dumps(changes, ensure_ascii=False)
                    break

            if data:
                self.store.save_shareholder_data(code, date, **data)
            return data

        except Exception as e:
            logger.debug("주주현황 수집 실패: %s: %s", code, e)
            return {}

    # ── 증권사 리포트 (c1080001) — 정적 ──────────────────────────

    def collect_analyst_reports(self, code: str, date: str) -> list[dict]:
        """증권사 리포트 목록.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            리포트 리스트. 실패 시 빈 리스트.
        """
        try:
            resp = _safe_get(
                f"{WISEREPORT_BASE}/c1080001.aspx",
                {"cmp_cd": code},
            )
            if resp is None:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            reports: list[dict] = []

            for table in soup.select("table"):
                ths = [th.get_text(strip=True) for th in table.select("tr:first-child th")]
                if "제목" in ths and "투자의견" in ths:
                    for tr in table.select("tr")[1:]:
                        tds = tr.select("td")
                        if len(tds) < 6:
                            continue
                        title = tds[1].get_text(strip=True)[:100]
                        if not title:
                            continue
                        report = {
                            "report_date": tds[0].get_text(strip=True),
                            "title": title,
                            "analyst": tds[2].get_text(strip=True)[:30],
                            "provider": tds[3].get_text(strip=True)[:20],
                            "opinion": tds[4].get_text(strip=True)[:10],
                            "target_price": self._parse_number(tds[5].get_text(strip=True)),
                        }
                        reports.append(report)
                        self.store.save_analyst_report(code=code, **report)
                    break

            return reports

        except Exception as e:
            logger.debug("증권사 리포트 수집 실패: %s: %s", code, e)
            return []

    # ── 투자지표 (c1040001) — crawl4ai ───────────────────────────

    async def collect_investment_indicators(self, code: str, date: str) -> list[dict]:
        """53개 투자지표 시계열 (수익성/성장성/안정성/활동성).

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            지표 리스트. 실패 시 빈 리스트.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            url = f"{WISEREPORT_BASE}/c1040001.aspx?cmp_cd={code}"
            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(wait_until="networkidle", delay_before_return_html=3.0)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                if not result.success:
                    return []

                soup = BeautifulSoup(result.html, "html.parser")
                indicators: list[dict] = []

                for table in soup.select("table"):
                    rows = table.select("tr")
                    if len(rows) < 5:
                        continue
                    headers = [th.get_text(strip=True) for th in rows[0].select("th")]
                    if len(headers) < 3:
                        continue
                    periods = headers[1:]

                    for tr in rows[1:]:
                        tds = tr.select("th, td")
                        if len(tds) < 2:
                            continue
                        name = tds[0].get_text(strip=True)
                        if not name:
                            continue
                        for i, td in enumerate(tds[1:]):
                            if i >= len(periods):
                                break
                            val = self._parse_number(td.get_text(strip=True))
                            if val is not None:
                                indicators.append({"period": periods[i], "indicator": name, "value": val})
                                self.store.save_investment_indicator(code, date, periods[i], name, val)

                return indicators

        except Exception as e:
            logger.debug("투자지표 수집 실패: %s: %s", code, e)
            return []

    # ── 컨센서스 (c1050001) — crawl4ai ───────────────────────────

    async def collect_consensus(self, code: str, date: str) -> list[dict]:
        """추정실적 시계열 (컨센서스).

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            추정실적 리스트. 실패 시 빈 리스트.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            url = f"{WISEREPORT_BASE}/c1050001.aspx?cmp_cd={code}"
            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(wait_until="networkidle", delay_before_return_html=3.0)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                if not result.success:
                    return []

                soup = BeautifulSoup(result.html, "html.parser")
                estimates: list[dict] = []
                field_map = {"매출액": "revenue", "영업이익": "operating_profit", "순이익": "net_income", "EPS": "eps", "PER": "per"}

                for table in soup.select("table"):
                    text = table.get_text()
                    if "매출액" not in text or "영업이익" not in text:
                        continue
                    rows = table.select("tr")
                    headers = [th.get_text(strip=True) for th in rows[0].select("th")]
                    if len(headers) < 2:
                        continue
                    periods = headers[1:]
                    row_data: dict[str, dict] = {p: {} for p in periods}

                    for tr in rows[1:]:
                        tds = tr.select("th, td")
                        if len(tds) < 2:
                            continue
                        label = tds[0].get_text(strip=True)
                        for key, field in field_map.items():
                            if label.startswith(key):
                                for i, td in enumerate(tds[1:]):
                                    if i < len(periods):
                                        val = self._parse_number(td.get_text(strip=True))
                                        if val is not None:
                                            row_data[periods[i]][field] = val
                                break

                    for period, vals in row_data.items():
                        if vals:
                            self.store.save_consensus_estimate(code, date, period, **vals)
                            estimates.append({"period": period, **vals})
                    break

                return estimates

        except Exception as e:
            logger.debug("컨센서스 수집 실패: %s: %s", code, e)
            return []

    # ── 업종분석 (c1060001) — crawl4ai ───────────────────────────

    async def collect_sector_analysis(self, code: str, date: str) -> dict:
        """업종 내 순위 및 동종 비교.

        Args:
            code: 종목코드.
            date: 기준일 (YYYYMMDD).

        Returns:
            섹터 분석 dict. 실패 시 빈 dict.
        """
        import json

        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            url = f"{WISEREPORT_BASE}/c1060001.aspx?cmp_cd={code}"
            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(wait_until="networkidle", delay_before_return_html=3.0)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                if not result.success:
                    return {}

                soup = BeautifulSoup(result.html, "html.parser")
                data: dict = {}

                for table in soup.select("table"):
                    for tr in table.select("tr"):
                        cells = tr.select("th, td")
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            val = self._parse_number(cells[1].get_text(strip=True))
                            if "업종PER" in label and val:
                                data["sector_per"] = val
                            elif "업종PBR" in label and val:
                                data["sector_pbr"] = val

                if data:
                    self.store.save_sector_comparison(
                        code, date,
                        sector_per=data.get("sector_per"),
                        sector_pbr=data.get("sector_pbr"),
                        comparison_data=json.dumps(data, ensure_ascii=False),
                    )
                return data

        except Exception as e:
            logger.debug("업종분석 수집 실패: %s: %s", code, e)
            return {}

    # ── 전체 수집 통합 ────────────────────────────────────────────

    def collect_all_static(self, code: str, date: str) -> dict:
        """모든 정적 데이터를 수집한다 (기업현황+기업개요+주주+리포트).

        Args:
            code: 종목코드.
            date: 기준일.

        Returns:
            탭별 수집 결과 dict.
        """
        return {
            "static": self.collect_static(code, date),
            "overview": self.collect_overview(code, date),
            "shareholders": self.collect_shareholders(code, date),
            "reports": self.collect_analyst_reports(code, date),
        }

    async def collect_all_dynamic(self, code: str, date: str) -> dict:
        """모든 JS 렌더링 데이터를 수집한다 (재무+투자지표+컨센서스+업종).

        Args:
            code: 종목코드.
            date: 기준일.

        Returns:
            탭별 수집 결과 dict.
        """
        return {
            "financials": await self.collect_financials(code, date),
            "indicators": await self.collect_investment_indicators(code, date),
            "consensus": await self.collect_consensus(code, date),
            "sector": await self.collect_sector_analysis(code, date),
        }

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
