"""재무제표 수집기.

pykrx를 사용하여 PER, PBR, 배당수익률 등을 수집한다.
ROE/매출/영업이익은 pykrx로 직접 제공되지 않으므로 추후 소스 확장 필요.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class FundamentalCollector:
    """재무제표 데이터 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, date: str, codes: list[str] | None = None,
                market: str = "KOSPI") -> None:
        """PER/PBR/배당수익률을 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (YYYYMMDD).
            codes: 종목코드 리스트 (None이면 전 시장).
            market: 시장 (codes=None일 때 사용).
        """
        try:
            df = stock.get_market_fundamental_by_ticker(date, market=market)
        except Exception:
            logger.warning("재무제표 수집 실패: %s %s", market, date)
            return

        if df.empty:
            return

        target_codes = codes if codes else df.index.tolist()

        for code in target_codes:
            if code not in df.index:
                continue
            row = df.loc[code]
            per = float(row.get("PER", 0)) or None
            pbr = float(row.get("PBR", 0)) or None
            div_yield = float(row.get("DIV", 0)) or None

            self.store.save_fundamental(
                code=code,
                date=date,
                per=per,
                pbr=pbr,
                dividend_yield=div_yield,
            )

        logger.info("재무제표 저장: %d종목 (%s)", len(target_codes), date)
