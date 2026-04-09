"""주가 수집기.

pykrx를 사용하여 종목별 OHLCV 및 시가총액을 수집한다.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class StockCollector:
    """종목별 주가 데이터 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect_ohlcv(self, code: str, start: str, end: str) -> None:
        """OHLCV + 시가총액을 수집하여 DB에 저장한다.

        Args:
            code: 종목코드 (예: "005930").
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        try:
            ohlcv_df = stock.get_market_ohlcv(start, end, code)
            cap_df = stock.get_market_cap(start, end, code)
        except Exception:
            logger.warning("OHLCV 수집 실패: %s (%s~%s)", code, start, end)
            return

        if ohlcv_df.empty:
            return

        rows = []
        for dt in ohlcv_df.index:
            date_str = dt.strftime("%Y%m%d")
            o = ohlcv_df.loc[dt]
            mcap = 0
            if not cap_df.empty and dt in cap_df.index:
                mcap = cap_df.loc[dt].get("시가총액", 0)
            rows.append((
                code, date_str,
                float(o["시가"]), float(o["고가"]),
                float(o["저가"]), float(o["종가"]),
                int(o["거래량"]), float(mcap),
            ))

        if rows:
            self.store.save_ohlcv_bulk(rows)
            logger.info("OHLCV 저장: %s (%d건)", code, len(rows))

    def collect_stock_list(self, date: str, market: str = "KOSPI") -> list[dict]:
        """특정 시장의 전 종목 목록을 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (YYYYMMDD).
            market: 시장 ("KOSPI" | "KOSDAQ").

        Returns:
            종목 정보 딕셔너리 리스트.
        """
        try:
            tickers = stock.get_market_ticker_list(date, market=market)
        except Exception:
            logger.warning("종목 목록 수집 실패: %s %s", market, date)
            return []

        results = []
        for ticker in tickers:
            name = stock.get_market_ticker_name(ticker)
            self.store.upsert_stock(ticker, name, market)
            results.append({"code": ticker, "name": name, "market": market})

        logger.info("%s 종목 %d개 저장", market, len(results))
        return results
