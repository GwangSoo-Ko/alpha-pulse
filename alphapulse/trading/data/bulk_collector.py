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

        today = self._find_latest_trading_date()
        start_dt = datetime.strptime(today, "%Y%m%d") - timedelta(days=years * 365)
        start = start_dt.strftime("%Y%m%d")
        results = []

        for market in markets:
            logger.info(
                "=== %s 수집 시작 (기간: %s ~ %s) ===", market, start, today
            )
            t0 = _time.time()

            # 1. 종목 목록 수집 (최근 거래일 기준)
            codes = self._collect_stock_list(market)
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

    def _collect_stock_list(self, market: str, date: str | None = None) -> list[str]:
        """종목 목록을 수집하고 코드 리스트를 반환한다.

        1차: pykrx get_market_ticker_list 시도.
        2차: 네이버 금융 시가총액 페이지 스크래핑 (KRX 로그인 필요 시 폴백).

        Args:
            market: 시장 ("KOSPI" | "KOSDAQ").
            date: 기준일 (YYYYMMDD). None이면 최근 영업일 자동 탐색.

        Returns:
            종목코드 리스트.
        """
        tickers = []

        # 1차: pykrx 시도
        try:
            if date is not None:
                tickers = stock.get_market_ticker_list(date, market=market)
            if not tickers:
                tickers = stock.get_market_ticker_list(market=market)
        except Exception:
            pass

        # 2차: 네이버 금융 스크래핑 (pykrx 실패 시)
        if not tickers:
            logger.info("%s: pykrx 실패. 네이버 금융에서 종목 목록 수집.", market)
            tickers = self._scrape_naver_stock_list(market)

        if not tickers:
            logger.warning("종목 목록 수집 실패: %s", market)
            return []

        # DB에 종목 정보 저장
        for ticker in tickers:
            try:
                name = stock.get_market_ticker_name(ticker)
                self.store.upsert_stock(ticker, name, market)
            except Exception:
                # pykrx 이름 조회 실패 시 네이버에서 이미 저장된 이름 유지
                pass

        logger.info("%s 종목 %d개 로드", market, len(tickers))
        return tickers

    def _scrape_naver_stock_list(self, market: str) -> list[str]:
        """네이버 금융 시가총액 페이지에서 종목 목록을 스크래핑한다.

        Args:
            market: "KOSPI" 또는 "KOSDAQ".

        Returns:
            종목코드 리스트.
        """
        import requests
        from bs4 import BeautifulSoup

        sosok = "0" if market == "KOSPI" else "1"
        base_url = "https://finance.naver.com/sise/sise_market_sum.naver"
        headers = {"User-Agent": "Mozilla/5.0"}
        tickers = []

        # 최대 40페이지 (페이지당 50종목, KOSPI ~950, KOSDAQ ~1700)
        max_pages = 40
        for page in range(1, max_pages + 1):
            try:
                resp = requests.get(
                    base_url,
                    params={"sosok": sosok, "page": page},
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a.tltle")
                if not links:
                    break  # 더 이상 종목 없음

                for a in links:
                    code = a["href"].split("=")[-1]
                    name = a.text.strip()
                    tickers.append(code)
                    self.store.upsert_stock(code, name, market)

            except Exception as e:
                logger.warning("네이버 금융 %s 페이지 %d 실패: %s", market, page, e)
                break

        logger.info("네이버 금융에서 %s %d종목 수집", market, len(tickers))
        return tickers

    def _find_latest_trading_date(self) -> str:
        """pykrx OHLCV가 존재하는 가장 최근 거래일을 찾는다.

        삼성전자(005930) OHLCV 조회로 최근 거래일을 탐색한다.

        Returns:
            최근 거래일 (YYYYMMDD).
        """
        base = datetime.now()
        for i in range(0, 60):
            try_date = (base - timedelta(days=i)).strftime("%Y%m%d")
            try:
                df = stock.get_market_ohlcv(try_date, try_date, "005930")
                if not df.empty:
                    return df.index[-1].strftime("%Y%m%d")
            except Exception:
                continue

        # 최종 폴백
        return (base - timedelta(days=1)).strftime("%Y%m%d")
