"""TradingStore 기반 백테스트 DataFeed.

HistoricalDataFeed를 확장하여 TradingStore에서 OHLCV, 재무, 수급 데이터를
자동으로 로드한다. look-ahead bias 방지는 get_ohlcv 시 end <= current_date
체크로 강제된다.
"""

import logging
from pathlib import Path

from alphapulse.trading.core.models import OHLCV, Stock
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class TradingStoreDataFeed:
    """TradingStore를 읽기 전용 데이터 소스로 사용하는 DataFeed.

    HistoricalDataFeed와 호환되며, advance_to/get_ohlcv/get_financials 등을 제공한다.

    Attributes:
        store: TradingStore 인스턴스.
        current_date: 현재 시뮬레이션 날짜.
        codes: 유니버스 종목코드 리스트.
    """

    def __init__(
        self,
        db_path: str | Path,
        codes: list[str] | None = None,
        market: str | None = None,
    ) -> None:
        """초기화.

        Args:
            db_path: TradingStore DB 경로.
            codes: 유니버스 종목코드 목록. None이면 market 기반 조회.
            market: None + codes=None이면 전종목.
        """
        self.store = TradingStore(db_path)
        self.current_date: str = ""

        if codes is not None:
            self.codes = list(codes)
        elif market is not None:
            self.codes = [
                s["code"] for s in self.store.get_all_stocks(market=market)
            ]
        else:
            self.codes = [s["code"] for s in self.store.get_all_stocks()]

        # code → Stock 캐시 (백테스트 중 반복 호출)
        self._stock_cache: dict[str, Stock] = {}
        for row in self.store.get_all_stocks():
            if row["code"] in self.codes:
                self._stock_cache[row["code"]] = Stock(
                    code=row["code"],
                    name=row["name"],
                    market=row["market"],
                    sector=row.get("sector", ""),
                )

    # ── 시뮬레이션 제어 ──────────────────────────────────────────

    def advance_to(self, date: str) -> None:
        """현재 날짜를 전진시킨다."""
        self.current_date = date

    def get_universe(self) -> list[Stock]:
        """현재 유니버스를 반환한다."""
        return [self._stock_cache[c] for c in self.codes if c in self._stock_cache]

    def get_available_codes(self) -> list[str]:
        """현재 날짜 기준 유효 종목코드 리스트."""
        return list(self.codes)

    # ── DataProvider 인터페이스 ──────────────────────────────────

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """OHLCV를 조회한다. end > current_date면 look-ahead 방지."""
        if self.current_date and end > self.current_date:
            raise AssertionError(
                f"Look-ahead bias: requested end={end} > current={self.current_date}"
            )
        rows = self.store.get_ohlcv(code, start, end)
        return [
            OHLCV(
                date=r["date"],
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
                market_cap=r.get("market_cap", 0),
            )
            for r in rows
        ]

    def get_financials(self, code: str) -> dict:
        """재무제표 (최신 스냅샷)."""
        result = self.store.get_fundamentals(code)
        return result or {}

    def get_investor_flow(self, code: str, days: int) -> dict:
        """종목별 수급 (최근 N일 합계)."""
        rows = self.store.get_investor_flow(code, days=days)
        if not rows:
            return {}
        # current_date 이후 데이터는 제외
        if self.current_date:
            rows = [r for r in rows if r.get("date", "") <= self.current_date]
        if not rows:
            return {}
        foreign = sum(r.get("foreign_net", 0) or 0 for r in rows)
        institutional = sum(r.get("institutional_net", 0) or 0 for r in rows)
        individual = sum(r.get("individual_net", 0) or 0 for r in rows)
        return {
            "foreign_net": foreign,
            "institutional_net": institutional,
            "individual_net": individual,
            "days": len(rows),
        }

    def get_short_interest(self, code: str, days: int) -> dict:
        """공매도."""
        rows = self.store.get_short_interest(code, days=days)
        if not rows:
            return {}
        return {
            "short_volume": rows[0].get("short_volume", 0),
            "short_balance": rows[0].get("short_balance", 0),
        }

    def get_latest_price(self, code: str) -> float | None:
        """현재 날짜의 종가를 반환한다 (없으면 None)."""
        if not self.current_date:
            return None
        rows = self.store.get_ohlcv(code, "00000000", self.current_date)
        if not rows:
            return None
        return rows[-1]["close"]

    def get_bar(self, code: str) -> OHLCV | None:
        """현재 날짜의 OHLCV bar를 반환한다 (BacktestEngine 벤치마크용)."""
        if not self.current_date:
            return None
        rows = self.store.get_ohlcv(code, "00000000", self.current_date)
        if not rows:
            return None
        r = rows[-1]
        return OHLCV(
            date=r["date"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            volume=r["volume"],
            market_cap=r.get("market_cap", 0),
        )

    def get_market_context(self, date: str) -> dict:
        """시장 컨텍스트 (백테스트에서는 중립 반환).

        실제 SignalEngine은 과거 데이터 재구축이 복잡하므로
        백테스트에서는 일단 중립값 반환. 필요 시 확장.
        """
        return {
            "date": date,
            "pulse_score": 0.0,
            "pulse_signal": "중립 (Neutral)",
            "indicator_scores": {},
            "details": {},
        }
