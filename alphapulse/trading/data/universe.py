"""투자 유니버스 관리.

종목 목록 조회, 필터링, Stock 변환을 담당한다.
"""

import logging

from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class Universe:
    """투자 유니버스 관리자.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, store: TradingStore) -> None:
        self.store = store

    def get_all(self) -> list[Stock]:
        """전체 종목을 Stock 리스트로 반환한다."""
        rows = self.store.get_all_stocks()
        return [self._to_stock(r) for r in rows]

    def get_by_market(self, market: str) -> list[Stock]:
        """특정 시장 종목만 조회한다.

        Args:
            market: "KOSPI" | "KOSDAQ" | "ETF".
        """
        rows = self.store.get_all_stocks(market=market)
        return [self._to_stock(r) for r in rows]

    def filter_stocks(
        self,
        stocks: list[Stock],
        min_market_cap: float | None = None,
        min_avg_volume: float | None = None,
    ) -> list[Stock]:
        """종목을 조건에 따라 필터링한다.

        Args:
            stocks: 필터링할 종목 리스트.
            min_market_cap: 최소 시가총액 (원).
            min_avg_volume: 최소 일평균 거래대금 (원).

        Returns:
            필터 통과한 종목 리스트.
        """
        result = []
        for s in stocks:
            if min_market_cap is not None:
                info = self.store.get_stock(s.code)
                if info and info.get("market_cap", 0) < min_market_cap:
                    continue

            if min_avg_volume is not None:
                avg_vol = self._get_avg_trading_value(s.code)
                if avg_vol < min_avg_volume:
                    continue

            result.append(s)
        return result

    def _get_avg_trading_value(self, code: str, days: int = 20) -> float:
        """최근 N일 평균 거래대금을 계산한다."""
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if not rows:
            return 0
        recent = rows[-days:]  # 날짜 오름차순
        total = sum(r["close"] * r["volume"] for r in recent)
        return total / len(recent) if recent else 0

    @staticmethod
    def _to_stock(row: dict) -> Stock:
        """DB 딕셔너리를 Stock으로 변환한다."""
        return Stock(
            code=row["code"],
            name=row["name"],
            market=row["market"],
            sector=row.get("sector", ""),
        )
