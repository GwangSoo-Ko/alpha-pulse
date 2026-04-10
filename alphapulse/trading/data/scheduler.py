"""데이터 수집 스케줄러.

주기별로 데이터 수집을 자동 관리한다.
2단계 수집 전략:
  Stage 1: 전종목 기본 데이터 (스크리닝용, sync, 빠름)
  Stage 2: 스크리닝 후 투자 후보 N종목 상세 데이터 (crawl4ai, 느림)
"""

import logging
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from alphapulse.trading.data.bulk_collector import BulkCollector
from alphapulse.trading.data.collection_metadata import CollectionMetadata
from alphapulse.trading.data.short_collector import ShortCollector
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.wisereport_collector import WisereportCollector

logger = logging.getLogger(__name__)


@dataclass
class ScheduleResult:
    """스케줄 실행 결과."""

    executed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0
    stage2_codes: list[str] = field(default_factory=list)


class DataScheduler:
    """주기별 데이터 수집 스케줄러.

    2단계 수집 전략:
      Stage 1 (전종목, sync): OHLCV, 수급, 기본 재무, wisereport 정적
      Stage 2 (후보 종목, crawl4ai): 공매도, 재무 시계열, 투자지표, 컨센서스, 업종

    collection_metadata에서 각 데이터 유형의 마지막 수집일을 확인하고,
    주기에 따라 필요한 수집만 실행한다.

    Attributes:
        db_path: 데이터베이스 경로.
        top_n: Stage 2 대상 종목 수 (스크리닝 상위 N).
    """

    # (주기, 단계, 설명)
    SCHEDULES: dict[str, tuple[str, int, str]] = {
        # Stage 1: 전종목 기본 (sync)
        "ohlcv":          ("daily",     1, "일봉 + 수급 + 기본 재무"),
        "wisereport":     ("daily",     1, "시가총액, 베타, 컨센서스"),
        "reports":        ("weekly",    1, "증권사 리포트"),
        "shareholders":   ("weekly",    1, "주주 지분 변동"),
        "overview":       ("quarterly", 1, "기업개요 (매출구성, R&D)"),
        # Stage 2: 후보 종목 상세 (crawl4ai)
        "short":          ("daily",     2, "공매도 수량/잔고"),
        "financials":     ("monthly",   2, "재무 시계열 (매출, ROE)"),
        "indicators":     ("monthly",   2, "53개 투자지표"),
        "consensus_est":  ("monthly",   2, "추정실적 컨센서스"),
        "sector":         ("monthly",   2, "업종분석 (동종비교)"),
    }

    def __init__(
        self,
        db_path: str | Path,
        top_n: int = 100,
        delay: float = 0.3,
    ) -> None:
        self.db_path = Path(db_path)
        self.top_n = top_n
        self.delay = delay
        self.metadata = CollectionMetadata(db_path)
        self.store = TradingStore(db_path)
        self.bulk_collector = BulkCollector(db_path, delay=delay)
        self.wisereport_collector = WisereportCollector(db_path)
        self.short_collector = ShortCollector(db_path)

    async def run(
        self,
        markets: list[str] | None = None,
        force: bool = False,
    ) -> ScheduleResult:
        """오늘 수집해야 할 데이터를 자동 판단하여 실행한다.

        Args:
            markets: 대상 시장. 기본 ["KOSPI", "KOSDAQ"].
            force: True이면 주기 무시하고 전체 실행.

        Returns:
            실행 결과.
        """
        if markets is None:
            markets = ["KOSPI", "KOSDAQ"]

        today = self._get_latest_date()
        result = ScheduleResult()
        t0 = _time.time()

        # ── Stage 1: 전종목 기본 데이터 ──────────────────────────
        logger.info("=== Stage 1: 전종목 기본 데이터 수집 ===")

        # OHLCV + 수급 + 기본재무 (BulkCollector가 통합 처리)
        if force or self._should_collect("ohlcv", today, "daily"):
            try:
                self.bulk_collector.update(markets=markets)
                self.metadata.set_last_date("ALL", "ohlcv", today)
                result.executed.append("ohlcv (전종목)")
            except Exception as e:
                logger.error("OHLCV 수집 실패: %s", e)
                result.errors.append(f"ohlcv: {e}")
        else:
            result.skipped.append("ohlcv (이미 최신)")

        # wisereport 정적 (전종목)
        if force or self._should_collect("wisereport", today, "daily"):
            try:
                all_codes = self._get_all_codes(markets)
                self.wisereport_collector.collect_static_batch(all_codes, today, delay=self.delay)
                self.metadata.set_last_date("ALL", "wisereport", today)
                result.executed.append(f"wisereport 정적 ({len(all_codes)}종목)")
            except Exception as e:
                logger.error("wisereport 수집 실패: %s", e)
                result.errors.append(f"wisereport: {e}")
        else:
            result.skipped.append("wisereport (이미 최신)")

        # 증권사 리포트 + 주주 (주간)
        if force or self._should_collect("reports", today, "weekly"):
            try:
                all_codes = self._get_all_codes(markets)
                for code in all_codes:
                    self.wisereport_collector.collect_analyst_reports(code, today)
                    self.wisereport_collector.collect_shareholders(code, today)
                    _time.sleep(self.delay)
                self.metadata.set_last_date("ALL", "reports", today)
                self.metadata.set_last_date("ALL", "shareholders", today)
                result.executed.append(f"리포트+주주 ({len(all_codes)}종목)")
            except Exception as e:
                logger.error("리포트/주주 수집 실패: %s", e)
                result.errors.append(f"reports: {e}")
        else:
            result.skipped.append("리포트+주주 (주간 미도래)")

        # 기업개요 (분기)
        if force or self._should_collect("overview", today, "quarterly"):
            try:
                all_codes = self._get_all_codes(markets)
                for code in all_codes:
                    self.wisereport_collector.collect_overview(code, today)
                    _time.sleep(self.delay)
                self.metadata.set_last_date("ALL", "overview", today)
                result.executed.append(f"기업개요 ({len(all_codes)}종목)")
            except Exception as e:
                logger.error("기업개요 수집 실패: %s", e)
                result.errors.append(f"overview: {e}")
        else:
            result.skipped.append("기업개요 (분기 미도래)")

        # ── 스크리닝 → 후보 종목 선정 ────────────────────────────
        stage2_codes = self._select_candidates(markets)
        result.stage2_codes = stage2_codes
        logger.info(
            "=== Stage 2: 투자 후보 %d종목 상세 데이터 ===",
            len(stage2_codes),
        )

        # ── Stage 2: 후보 종목 상세 (crawl4ai) ───────────────────

        # 공매도 (매일)
        if stage2_codes and (force or self._should_collect("short", today, "daily")):
            try:
                start_30d = (datetime.strptime(today, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
                for code in stage2_codes:
                    await self.short_collector.collect_async(code, start_30d, today)
                self.metadata.set_last_date("TOP", "short", today)
                result.executed.append(f"공매도 ({len(stage2_codes)}종목)")
            except Exception as e:
                logger.error("공매도 수집 실패: %s", e)
                result.errors.append(f"short: {e}")
        else:
            result.skipped.append("공매도 (스킵)")

        # 재무 시계열 + 투자지표 + 컨센서스 + 업종 (월간)
        if stage2_codes and (force or self._should_collect("financials", today, "monthly")):
            try:
                for code in stage2_codes:
                    await self.wisereport_collector.collect_financials(code, today)
                    await self.wisereport_collector.collect_investment_indicators(code, today)
                    await self.wisereport_collector.collect_consensus(code, today)
                    await self.wisereport_collector.collect_sector_analysis(code, today)
                self.metadata.set_last_date("TOP", "financials", today)
                self.metadata.set_last_date("TOP", "indicators", today)
                self.metadata.set_last_date("TOP", "consensus_est", today)
                self.metadata.set_last_date("TOP", "sector", today)
                result.executed.append(f"재무+지표+컨센서스+업종 ({len(stage2_codes)}종목)")
            except Exception as e:
                logger.error("상세 재무 수집 실패: %s", e)
                result.errors.append(f"financials: {e}")
        else:
            result.skipped.append("재무 시계열 (월간 미도래)")

        result.elapsed_seconds = _time.time() - t0
        self._log_result(result)
        return result

    def _select_candidates(self, markets: list[str]) -> list[str]:
        """스크리닝 엔진으로 투자 후보 종목을 선정한다.

        팩터 데이터가 충분하면 스크리닝 결과 상위 N종목을 반환한다.
        데이터 부족 시 시가총액 상위 N종목으로 폴백한다.

        Args:
            markets: 대상 시장.

        Returns:
            후보 종목코드 리스트 (최대 top_n개).
        """
        try:
            from alphapulse.trading.data.universe import Universe
            from alphapulse.trading.screening.factors import FactorCalculator
            from alphapulse.trading.screening.ranker import MultiFactorRanker

            universe = Universe(self.store)
            all_stocks = []
            for market in markets:
                all_stocks.extend(universe.get_by_market(market))

            if not all_stocks:
                return self._fallback_by_market_cap(markets)

            calc = FactorCalculator(self.store)
            factor_data = {}
            for s in all_stocks:
                momentum = calc.momentum(s.code, lookback=20)
                value = calc.value(s.code)
                if momentum is not None or value is not None:
                    factor_data[s.code] = {
                        "momentum": momentum,
                        "value": value,
                        "quality": calc.quality(s.code),
                        "flow": calc.flow(s.code),
                        "volatility": calc.volatility(s.code),
                    }

            if len(factor_data) < 10:
                return self._fallback_by_market_cap(markets)

            ranker = MultiFactorRanker(
                weights={"momentum": 0.25, "value": 0.25, "quality": 0.2,
                         "flow": 0.15, "volatility": 0.15}
            )
            signals = ranker.rank(
                [s for s in all_stocks if s.code in factor_data],
                factor_data,
                strategy_id="scheduler",
            )

            codes = [sig.stock.code for sig in signals[:self.top_n]]
            logger.info("스크리닝 기반 후보 선정: %d종목", len(codes))
            return codes

        except Exception as e:
            logger.warning("스크리닝 실패, 시총 기반 폴백: %s", e)
            return self._fallback_by_market_cap(markets)

    def _fallback_by_market_cap(self, markets: list[str]) -> list[str]:
        """시가총액 상위 N종목을 반환한다 (스크리닝 폴백)."""
        stocks = []
        for market in markets:
            stocks.extend(self.store.get_all_stocks(market=market))
        stocks.sort(key=lambda s: s.get("market_cap", 0), reverse=True)
        codes = [s["code"] for s in stocks[:self.top_n]]
        logger.info("시총 기반 후보 선정 (폴백): %d종목", len(codes))
        return codes

    def _should_collect(self, data_type: str, today: str, frequency: str) -> bool:
        """해당 데이터 유형을 오늘 수집해야 하는지 판단한다."""
        # ALL 스코프와 TOP 스코프 모두 확인
        for scope in ["ALL", "TOP"]:
            last = self.metadata.get_last_date(scope, data_type)
            if last is not None and last >= today:
                return False

        last_all = self.metadata.get_last_date("ALL", data_type)
        last_top = self.metadata.get_last_date("TOP", data_type)
        last = last_all or last_top

        if last is None:
            return True

        last_dt = datetime.strptime(last, "%Y%m%d")
        today_dt = datetime.strptime(today, "%Y%m%d")
        days_since = (today_dt - last_dt).days

        if frequency == "daily":
            return days_since >= 1
        elif frequency == "weekly":
            return days_since >= 7
        elif frequency == "monthly":
            return days_since >= 30
        elif frequency == "quarterly":
            return days_since >= 90
        return True

    def _get_all_codes(self, markets: list[str]) -> list[str]:
        """전종목 코드 리스트를 반환한다."""
        codes = []
        for market in markets:
            stocks = self.store.get_all_stocks(market=market)
            codes.extend(s["code"] for s in stocks)
        return codes

    def _get_latest_date(self) -> str:
        """최근 거래일을 반환한다."""
        return self.bulk_collector._find_latest_trading_date()

    def _log_result(self, result: ScheduleResult) -> None:
        """실행 결과를 로깅한다."""
        logger.info(
            "=== 데이터 수집 완료 (%.0f초) ===", result.elapsed_seconds,
        )
        if result.executed:
            logger.info("  실행: %s", ", ".join(result.executed))
        if result.skipped:
            logger.info("  스킵: %s", ", ".join(result.skipped))
        if result.errors:
            logger.warning("  에러: %s", ", ".join(result.errors))
        if result.stage2_codes:
            logger.info("  Stage 2 대상: %d종목", len(result.stage2_codes))

    def get_status(self) -> dict:
        """수집 스케줄 현황을 반환한다."""
        today = self._get_latest_date()
        status = {}
        for data_type, (freq, stage, desc) in self.SCHEDULES.items():
            last_all = self.metadata.get_last_date("ALL", data_type)
            last_top = self.metadata.get_last_date("TOP", data_type)
            last = last_all or last_top
            needs = self._should_collect(data_type, today, freq)
            status[data_type] = {
                "description": desc,
                "frequency": freq,
                "stage": stage,
                "last_collected": last or "미수집",
                "needs_update": needs,
            }
        return status
