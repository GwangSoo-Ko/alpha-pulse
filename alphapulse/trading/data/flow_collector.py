"""종목별 투자자 수급 수집기.

pykrx를 사용하여 외국인/기관/개인 순매수를 수집한다.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class FlowCollector:
    """종목별 수급 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, code: str, start: str, end: str) -> None:
        """종목별 투자자 수급을 수집하여 DB에 저장한다.

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        try:
            df = stock.get_market_trading_value_by_date(start, end, code)
        except Exception:
            logger.warning("수급 수집 실패: %s (%s~%s)", code, start, end)
            return

        if df.empty:
            return

        rows = []
        for dt in df.index:
            date_str = dt.strftime("%Y%m%d")
            row = df.loc[dt]
            rows.append((
                code, date_str,
                float(row.get("외국인합계", 0)),
                float(row.get("기관합계", 0)),
                float(row.get("개인", 0)),
                None,  # foreign_holding_pct — 별도 API 필요
            ))

        if rows:
            self.store.save_investor_flow_bulk(rows)
            logger.info("수급 저장: %s (%d건)", code, len(rows))
