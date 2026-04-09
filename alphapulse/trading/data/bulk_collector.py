"""전종목 일괄 데이터 수집기.

초기 수집(collect_all)과 증분 업데이트(update)를 지원한다.
TradingEngine이 매일 refresh()를 호출하여 자동 업데이트한다.
"""

import logging
import time as _time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.collection_metadata import CollectionMetadata
from alphapulse.trading.data.flow_collector import FlowCollector
from alphapulse.trading.data.fundamental_collector import FundamentalCollector
from alphapulse.trading.data.progress_tracker import ProgressTracker
from alphapulse.trading.data.rate_limiter import RateLimiter
from alphapulse.trading.data.stock_collector import StockCollector
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    """수집 결과."""

    market: str
    ohlcv_count: int = 0
    fundamentals_count: int = 0
    flow_count: int = 0
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

        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
        results = []

        for market in markets:
            logger.info(
                "=== %s 수집 시작 (기간: %s ~ %s) ===", market, start, today
            )
            t0 = _time.time()

            # 1. 종목 목록 수집
            codes = self._collect_stock_list(market, today)
            if not codes:
                logger.warning("%s 종목 목록이 비어 있습니다.", market)
                continue

            result = CollectionResult(market=market)

            # 2. OHLCV 수집
            tracker = ProgressTracker(
                total=len(codes),
                label=f"{market} OHLCV",
                checkpoint_dir=self.db_path.parent,
            )
            remaining = tracker.get_resume_point(codes) if resume else codes
            logger.info(
                "%s OHLCV: %d종목 (%d건 재개)",
                market,
                len(codes),
                len(codes) - len(remaining),
            )
            tracker.start()

            for code in remaining:
                ok = self.rate_limiter.call_safe(
                    self.stock_collector.collect_ohlcv, code, start, today
                )
                tracker.advance(skipped=(ok is None))
                tracker.checkpoint(code)
                tracker.print_progress(code)

            s = tracker.summary()
            result.ohlcv_count = s["completed"] - s["skipped"]
            result.skipped = s["skipped"]
            tracker.cleanup()

            # 3. 재무제표 수집 (시장 전체 1회 호출)
            self.rate_limiter.call_safe(
                self.fundamental_collector.collect, today, market=market
            )
            result.fundamentals_count = len(codes)

            # 4. 수급 수집
            flow_tracker = ProgressTracker(
                total=len(codes),
                label=f"{market} Flow",
                checkpoint_dir=self.db_path.parent,
            )
            flow_remaining = (
                flow_tracker.get_resume_point(codes) if resume else codes
            )
            flow_tracker.start()

            for code in flow_remaining:
                self.rate_limiter.call_safe(
                    self.flow_collector.collect, code, start, today
                )
                flow_tracker.advance()
                flow_tracker.checkpoint(code)
                flow_tracker.print_progress(code)

            result.flow_count = flow_tracker.summary()["completed"]
            flow_tracker.cleanup()

            # 메타데이터 갱신
            self.metadata.set_last_date(market, "ohlcv", today)
            self.metadata.set_last_date(market, "fundamentals", today)
            self.metadata.set_last_date(market, "flow", today)

            result.elapsed_seconds = _time.time() - t0
            results.append(result)
            logger.info(
                "=== %s 완료: OHLCV %d, 재무 %d, 수급 %d (%.0f초) ===",
                market,
                result.ohlcv_count,
                result.fundamentals_count,
                result.flow_count,
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

        today = datetime.now().strftime("%Y%m%d")
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

            codes = self._collect_stock_list(market, today)
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

            # 메타데이터 갱신
            self.metadata.set_last_date(market, "ohlcv", today)
            self.metadata.set_last_date(market, "fundamentals", today)
            self.metadata.set_last_date(market, "flow", today)

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

    def _collect_stock_list(self, market: str, date: str) -> list[str]:
        """종목 목록을 수집하고 코드 리스트를 반환한다."""
        try:
            tickers = stock.get_market_ticker_list(date, market=market)
        except Exception:
            logger.warning("종목 목록 수집 실패: %s", market)
            return []
        for ticker in tickers:
            try:
                name = stock.get_market_ticker_name(ticker)
                self.store.upsert_stock(ticker, name, market)
            except Exception:
                pass
        return tickers
