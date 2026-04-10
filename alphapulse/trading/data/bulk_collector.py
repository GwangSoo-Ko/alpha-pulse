"""전종목 일괄 데이터 수집기.

초기 수집(collect_all)과 증분 업데이트(update)를 지원한다.
TradingEngine이 매일 refresh()를 호출하여 자동 업데이트한다.
"""

import logging
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.collection_metadata import CollectionMetadata
from alphapulse.trading.data.flow_collector import FlowCollector
from alphapulse.trading.data.fundamental_collector import FundamentalCollector
from alphapulse.trading.data.progress_tracker import ProgressTracker
from alphapulse.trading.data.rate_limiter import RateLimiter
from alphapulse.trading.data.stock_collector import StockCollector
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.wisereport_collector import WisereportCollector

logger = logging.getLogger(__name__)

NAVER_SISE_URL = "https://finance.naver.com/item/sise_day.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass
class CollectionResult:
    """수집 결과."""

    market: str
    ohlcv_count: int = 0
    fundamentals_count: int = 0
    flow_count: int = 0
    wisereport_count: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0


class BulkCollector:
    """전종목 일괄 수집기.

    Attributes:
        db_path: 데이터베이스 경로.
        delay: 요청 간 딜레이 (초).
        years: 기본 수집 기간 (년).
    """

    def __init__(
        self,
        db_path: str | Path,
        delay: float = 0.5,
        years: int = 3,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.years = years
        self.store = TradingStore(db_path)
        self.metadata = CollectionMetadata(db_path)
        self.stock_collector = StockCollector(db_path)
        self.fundamental_collector = FundamentalCollector(db_path)
        self.flow_collector = FlowCollector(db_path)
        self.wisereport_collector = WisereportCollector(db_path)
        self.rate_limiter = RateLimiter(delay=delay)

    def collect_all(
        self,
        markets: list[str] | None = None,
        years: int | None = None,
        resume: bool = True,
    ) -> list[CollectionResult]:
        """전종목 데이터를 일괄 수집한다.

        Args:
            markets: 대상 시장 목록. 기본 ["KOSPI", "KOSDAQ"].
            years: 수집 기간 (년). 기본 self.years.
            resume: 체크포인트에서 재개 여부.

        Returns:
            시장별 수집 결과 리스트.
        """
        if markets is None:
            markets = ["KOSPI", "KOSDAQ"]
        if years is None:
            years = self.years

        today = self._find_latest_trading_date()
        start_dt = datetime.strptime(today, "%Y%m%d") - timedelta(days=years * 365)
        start = start_dt.strftime("%Y%m%d")
        results = []

        import sys

        for market in markets:
            sys.stderr.write(
                f"\n{'='*60}\n"
                f"  {market} 수집 ({start} ~ {today}) | {years}년치\n"
                f"{'='*60}\n"
            )
            t0 = _time.time()

            # 1. 종목 목록 수집
            sys.stderr.write("\n  [1/5] 종목 목록 수집 중...\n")
            codes = self._collect_stock_list(market)
            if not codes:
                sys.stderr.write(f"  -> {market} 종목 목록이 비어 있습니다.\n")
                continue
            sys.stderr.write(f"  -> {len(codes)}종목 로드 완료\n")

            result = CollectionResult(market=market)

            # 2. OHLCV 수집 (pykrx 우선)
            tracker = ProgressTracker(
                total=len(codes),
                label=f"[2/5] {market} OHLCV",
                checkpoint_dir=self.db_path.parent,
            )
            remaining = tracker.get_resume_point(codes) if resume else codes
            tracker.start()
            tracker._completed = len(codes) - len(remaining)

            for code in remaining:
                ok = self.rate_limiter.call_safe(
                    self.stock_collector.collect_ohlcv, code, start, today
                )
                tracker.advance(skipped=(ok is None))
                tracker.checkpoint(code)
                tracker.print_progress(code)

            tracker.print_summary()
            s = tracker.summary()
            result.ohlcv_count = s["completed"] - s["skipped"]
            result.skipped = s["skipped"]
            tracker.cleanup()

            # 3. 재무제표 수집
            sys.stderr.write(f"\n  [3/5] {market} 재무제표 수집 중...\n")
            self.rate_limiter.call_safe(
                self.fundamental_collector.collect, today, market=market
            )
            result.fundamentals_count = len(codes)
            sys.stderr.write("  -> 재무제표 완료\n")

            # 4. 수급 수집 (병렬)
            flow_tracker = ProgressTracker(
                total=len(codes),
                label=f"[4/5] {market} 수급",
                checkpoint_dir=self.db_path.parent,
            )
            flow_remaining = (
                flow_tracker.get_resume_point(codes) if resume else codes
            )
            flow_tracker.start()
            flow_tracker._completed = len(codes) - len(flow_remaining)

            self._collect_flow_parallel(
                flow_remaining, start, today, flow_tracker, max_workers=5,
            )

            flow_tracker.print_summary()
            result.flow_count = flow_tracker.summary()["completed"]
            flow_tracker.cleanup()

            # 5. wisereport 정적 데이터 수집 (병렬)
            ws_tracker = ProgressTracker(
                total=len(codes),
                label=f"[5/5] {market} wisereport",
                checkpoint_dir=self.db_path.parent,
            )
            ws_tracker.start()

            def _ws_progress(code: str) -> None:
                ws_tracker.advance()
                ws_tracker.print_progress(code)

            try:
                ws_results = self.wisereport_collector.collect_static_batch(
                    codes, today, max_workers=5, progress_callback=_ws_progress,
                )
                result.wisereport_count = len(ws_results)
                ws_tracker.print_summary()
            except Exception as e:
                logger.warning("wisereport 수집 실패 (무시): %s", e)

            # 메타데이터 갱신
            self.metadata.set_last_date(market, "ohlcv", today)
            self.metadata.set_last_date(market, "fundamentals", today)
            self.metadata.set_last_date(market, "flow", today)
            if result.wisereport_count > 0:
                self.metadata.set_last_date(market, "wisereport", today)

            result.elapsed_seconds = _time.time() - t0
            results.append(result)
            logger.info(
                "=== %s 완료: OHLCV %d, 재무 %d, 수급 %d, "
                "wisereport %d (%.0f초) ===",
                market,
                result.ohlcv_count,
                result.fundamentals_count,
                result.flow_count,
                result.wisereport_count,
                result.elapsed_seconds,
            )

        return results

    def update(
        self, markets: list[str] | None = None
    ) -> list[CollectionResult]:
        """마지막 수집일 이후 신규 데이터만 수집한다.

        Args:
            markets: 대상 시장 목록.

        Returns:
            시장별 수집 결과 리스트.
        """
        if markets is None:
            markets = ["KOSPI", "KOSDAQ"]

        today = self._find_latest_trading_date()
        results = []

        for market in markets:
            last = self.metadata.get_last_date(market, "ohlcv")
            if last is None:
                logger.info("%s: 미수집 상태. collect_all 실행.", market)
                results.extend(self.collect_all(markets=[market]))
                continue

            # 다음 거래일 계산 (간단히 +1일)
            last_dt = datetime.strptime(last, "%Y%m%d")
            start = (last_dt + timedelta(days=1)).strftime("%Y%m%d")

            if start > today:
                logger.info("%s: 이미 최신 (%s).", market, last)
                continue

            logger.info("%s 증분 업데이트: %s ~ %s", market, start, today)
            t0 = _time.time()

            codes = self._collect_stock_list(market)
            if not codes:
                continue

            result = CollectionResult(market=market)

            # OHLCV 증분
            for code in codes:
                self.rate_limiter.call_safe(
                    self.stock_collector.collect_ohlcv, code, start, today
                )
            result.ohlcv_count = len(codes)

            # 재무제표
            self.rate_limiter.call_safe(
                self.fundamental_collector.collect, today, market=market
            )
            result.fundamentals_count = len(codes)

            # 수급 증분
            for code in codes:
                self.rate_limiter.call_safe(
                    self.flow_collector.collect, code, start, today
                )
            result.flow_count = len(codes)

            # wisereport 정적 데이터
            try:
                ws_results = self.wisereport_collector.collect_static_batch(
                    codes, today
                )
                result.wisereport_count = len(ws_results)
            except Exception as e:
                logger.warning("wisereport 증분 수집 실패 (무시): %s", e)

            # 메타데이터 갱신
            self.metadata.set_last_date(market, "ohlcv", today)
            self.metadata.set_last_date(market, "fundamentals", today)
            self.metadata.set_last_date(market, "flow", today)
            if result.wisereport_count > 0:
                self.metadata.set_last_date(market, "wisereport", today)

            result.elapsed_seconds = _time.time() - t0
            results.append(result)

        return results

    def refresh(self) -> None:
        """TradingEngine용 자동 업데이트. 예외를 전파하지 않는다."""
        try:
            self.update()
        except Exception as e:
            logger.error("데이터 자동 업데이트 실패 (무시): %s", e)

    def status(self) -> dict:
        """수집 현황을 반환한다."""
        collection = self.metadata.get_all_status()
        stocks = self.store.get_all_stocks()
        return {
            "collection": collection,
            "total_stocks": len(stocks),
            "kospi": len([s for s in stocks if s["market"] == "KOSPI"]),
            "kosdaq": len([s for s in stocks if s["market"] == "KOSDAQ"]),
            "etf": len([s for s in stocks if s["market"] == "ETF"]),
        }

    def _collect_flow_parallel(
        self,
        codes: list[str],
        start: str,
        end: str,
        tracker: "ProgressTracker",
        max_workers: int = 5,
    ) -> None:
        """수급 데이터를 안전하게 병렬 수집한다.

        다음 방어 메커니즘 적용:
        - max_workers=5 (초당 동시 요청 수 축소)
        - 전역 rate bucket (초당 8회 제한)
        - 429 응답 감지 시 지수 백오프 재시도
        - 요청 간 랜덤 jitter

        Args:
            codes: 종목코드 리스트.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
            tracker: 진행률 추적기.
            max_workers: 동시 요청 수. 기본 5 (안전).
        """
        import random
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from alphapulse.trading.data.rate_bucket import RateBucket

        store_lock = threading.Lock()
        rate_bucket = RateBucket(rate=8.0, capacity=8)

        def _fetch_with_retry(url: str, params: dict, headers: dict) -> object | None:
            """429 지수 백오프 재시도가 적용된 HTTP GET."""
            import requests

            for attempt in range(3):
                rate_bucket.acquire()
                try:
                    resp = requests.get(url, params=params, headers=headers, timeout=10)
                    if resp.status_code == 429:
                        wait = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning("429 수신. %.1f초 대기 후 재시도", wait)
                        _time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp
                except Exception:
                    if attempt == 2:
                        return None
                    _time.sleep(1 + random.uniform(0, 0.5))
            return None

        def _collect_one(code: str) -> tuple[str, bool]:
            """단일 종목 수집."""
            from bs4 import BeautifulSoup

            url = "https://finance.naver.com/item/frgn.naver"
            headers = {"User-Agent": "Mozilla/5.0"}
            rows = []
            page = 1
            max_pages = 100

            while page <= max_pages:
                resp = _fetch_with_retry(
                    url, {"code": code, "page": page}, headers
                )
                if resp is None:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                tables = soup.select("table.type2")
                if len(tables) < 2:
                    break
                table = tables[1]

                found_data = False
                reached_start = False

                for tr in table.select("tr"):
                    tds = tr.select("td")
                    if len(tds) < 9:
                        continue
                    found_data = True
                    date_text = tds[0].text.strip().replace(".", "")
                    if date_text > end:
                        continue
                    if date_text < start:
                        reached_start = True
                        break
                    try:
                        institutional = self._parse_flow_number(tds[5].text)
                        foreign = self._parse_flow_number(tds[6].text)
                        individual = -(institutional + foreign)
                        holding_pct_text = tds[8].text.strip().replace("%", "")
                        holding_pct = (
                            float(holding_pct_text) if holding_pct_text else None
                        )
                        rows.append((
                            code, date_text, foreign, institutional,
                            individual, holding_pct,
                        ))
                    except (ValueError, IndexError):
                        continue

                if reached_start or not found_data:
                    break
                page += 1
                # 페이지 간 랜덤 jitter
                _time.sleep(random.uniform(0.1, 0.3))

            if rows:
                with store_lock:
                    self.store.save_investor_flow_bulk(rows)
                return code, True
            return code, False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_collect_one, code): code for code in codes}
            for future in as_completed(futures):
                try:
                    code, _ok = future.result()
                except Exception as e:
                    code = futures[future]
                    logger.debug("수급 수집 실패: %s: %s", code, e)

                tracker.advance()
                tracker.checkpoint(code)
                tracker.print_progress(code)

    @staticmethod
    def _parse_flow_number(text: str) -> int:
        """'+1,234' 또는 '-1,234' 형태를 int로 변환한다."""
        cleaned = text.strip().replace(",", "").replace("+", "")
        if not cleaned or cleaned == "0":
            return 0
        try:
            return int(cleaned)
        except ValueError:
            return 0

    def _collect_stock_list(self, market: str) -> list[str]:
        """네이버 금융에서 종목 목록을 수집하고 코드 리스트를 반환한다.

        Args:
            market: 시장 ("KOSPI" | "KOSDAQ").

        Returns:
            종목코드 리스트.
        """
        stock_list = self.stock_collector.collect_stock_list(
            date="", market=market
        )
        codes = [s["code"] for s in stock_list]
        if not codes:
            logger.warning("종목 목록 수집 실패: %s", market)
        else:
            logger.info("%s 종목 %d개 로드", market, len(codes))
        return codes

    def _find_latest_trading_date(self) -> str:
        """네이버 금융에서 가장 최근 거래일을 찾는다.

        삼성전자(005930) 일별 시세 페이지에서 최근 거래일을 추출한다.

        Returns:
            최근 거래일 (YYYYMMDD).
        """
        try:
            resp = requests.get(
                NAVER_SISE_URL,
                params={"code": "005930", "page": 1},
                headers=HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one("table.type2")
            if table:
                for tr in table.select("tr"):
                    tds = tr.select("td span")
                    if len(tds) >= 7:
                        date_str = tds[0].text.strip().replace(".", "")
                        if len(date_str) == 8 and date_str.isdigit():
                            return date_str
        except Exception as e:
            logger.warning("최근 거래일 탐색 실패: %s", e)

        # 폴백: 어제 날짜
        base = datetime.now()
        return (base - timedelta(days=1)).strftime("%Y%m%d")
