"""TradingDataProvider — TradingEngine용 데이터 프로바이더.

TradingStore를 랩핑하여 refresh(), get_market_context() 인터페이스 제공.
DataProvider Protocol을 구현한다.
"""

import logging
from datetime import datetime
from pathlib import Path

from alphapulse.trading.core.models import OHLCV
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class TradingDataProvider:
    """TradingEngine용 데이터 프로바이더.

    TradingStore 위에 얇은 계층을 두어 인터페이스를 제공한다.

    Attributes:
        store: TradingStore 인스턴스.
        scheduler: (선택) DataScheduler. 있으면 refresh()에서 사용.
    """

    def __init__(
        self,
        db_path: str | Path,
        scheduler=None,
    ) -> None:
        self.store = TradingStore(db_path)
        self.scheduler = scheduler

    # ── DataProvider Protocol ──────────────────────────────────────

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """종목별 OHLCV를 OHLCV 객체 리스트로 반환."""
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
        """최신 재무제표."""
        result = self.store.get_fundamentals(code)
        return result or {}

    def get_investor_flow(self, code: str, days: int) -> dict:
        """종목별 수급 (최근 N일 합계)."""
        rows = self.store.get_investor_flow(code, days=days)
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
        """공매도 잔고 (최근 N일)."""
        rows = self.store.get_short_interest(code, days=days)
        if not rows:
            return {}
        return {
            "short_volume": rows[0].get("short_volume", 0),
            "short_balance": rows[0].get("short_balance", 0),
            "days": len(rows),
        }

    # ── TradingEngine 전용 ─────────────────────────────────────────

    async def refresh(self) -> None:
        """데이터를 최신으로 업데이트한다 (async).

        scheduler가 주입되어 있으면 DataScheduler.run()을 await한다.
        없으면 no-op (수동 수집 사용).

        호출 예: `await data_provider.refresh()` (async 컨텍스트).
        CLI entry에서 진입 시에는 상위 async 컨텍스트 안에서 호출됨.
        """
        if self.scheduler is None:
            logger.debug("DataProvider.refresh: scheduler 없음, skip")
            return
        try:
            await self.scheduler.run()
        except Exception as e:
            logger.warning("DataProvider.refresh 실패: %s", e)

    def get_market_context(self, date: str | None = None) -> dict:
        """시장 컨텍스트 (Market Pulse Score 기반)를 반환한다.

        기존 AlphaPulse market/engine SignalEngine을 호출한다.
        실패 시 중립 값 반환.

        Args:
            date: 기준일 (YYYYMMDD). None이면 최근 거래일.

        Returns:
            {
                "date": str,
                "pulse_score": float (-100~+100),
                "pulse_signal": str,
                "indicator_scores": dict,
                "details": dict,
            }
        """
        try:
            from alphapulse.market.engine.signal_engine import SignalEngine
            from alphapulse.trading.core.adapters import PulseResultAdapter

            engine = SignalEngine()
            result = engine.run(date=date)
            return PulseResultAdapter.to_market_context(result)
        except Exception as e:
            logger.debug("Market context 조회 실패: %s. 중립값 반환.", e)
            return {
                "date": date or datetime.now().strftime("%Y%m%d"),
                "pulse_score": 0.0,
                "pulse_signal": "중립 (Neutral)",
                "indicator_scores": {},
                "details": {},
            }
