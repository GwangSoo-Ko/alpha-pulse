"""Risk 어댑터 — 캐싱 포함. RiskManager/StressTest 호출."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from alphapulse.core.config import Config
from alphapulse.trading.core.models import PortfolioSnapshot
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.stress_test import StressTest
from alphapulse.trading.risk.var import VaRCalculator
from alphapulse.webapp.store.readers.portfolio import (
    PortfolioReader,
    SnapshotDTO,
)
from alphapulse.webapp.store.risk_cache import (
    RiskReportCacheRepository,
)

if TYPE_CHECKING:
    from alphapulse.webapp.store.notifications import NotificationStore

logger = logging.getLogger(__name__)


class RiskReader:
    def __init__(
        self,
        portfolio_reader: PortfolioReader,
        cache: RiskReportCacheRepository,
        notification_store: "NotificationStore | None" = None,
    ) -> None:
        self.portfolio_reader = portfolio_reader
        self.cache = cache
        self.notification_store = notification_store

    def get_report(self, mode: str) -> dict | None:
        snap = self.portfolio_reader.get_latest(mode=mode)
        if snap is None:
            return None
        key = self.cache.snapshot_key(
            date=snap.date, mode=mode, total_value=snap.total_value,
        )
        cached = self.cache.get(key)
        if cached:
            return {
                "report": cached.report, "stress": cached.stress,
                "computed_at": cached.computed_at, "cached": True,
            }
        cfg = Config()
        limits = RiskLimits(
            max_position_weight=cfg.MAX_POSITION_WEIGHT,
            max_drawdown_soft=cfg.MAX_DRAWDOWN_SOFT,
            max_drawdown_hard=cfg.MAX_DRAWDOWN_HARD,
        )
        mgr = RiskManager(
            limits=limits,
            var_calc=VaRCalculator(),
            drawdown_mgr=DrawdownManager(limits=limits),
        )
        snap_obj = self._to_snapshot(snap)
        report = mgr.daily_report(snap_obj)
        stress_raw = StressTest().run_all(snap_obj)
        # StressResult dataclass → serializable dict
        stress = {
            name: asdict(result) for name, result in stress_raw.items()
        }
        alerts_list = [
            {"level": a.level, "message": a.message}
            for a in (report.alerts or [])
        ]
        # 드로다운 기반 alert — daily_report 는 섹터 집중도만 포함하므로
        # portfolio.drawdown 필드를 limits 에 대해 직접 검사해 보강한다.
        dd_abs = abs(snap.drawdown) / 100.0
        if dd_abs >= limits.max_drawdown_hard:
            alerts_list.append({
                "level": "CRITICAL",
                "message": (
                    f"드로다운 한도 초과: {abs(snap.drawdown):.1f}% "
                    f"(하드 한도: {limits.max_drawdown_hard * 100:.1f}%)"
                ),
            })
        elif dd_abs >= limits.max_drawdown_soft:
            alerts_list.append({
                "level": "WARNING",
                "message": (
                    f"드로다운 경고: {abs(snap.drawdown):.1f}% "
                    f"(소프트 한도: {limits.max_drawdown_soft * 100:.1f}%)"
                ),
            })
        report_dict = {
            "drawdown_status": report.drawdown_status,
            "var_95": report.var_95,
            "cvar_95": report.cvar_95,
            "alerts": alerts_list,
        }
        self.cache.put(key=key, report=report_dict, stress=stress)
        self._emit_alert_notifications(report_dict.get("alerts", []))
        return {
            "report": report_dict, "stress": stress,
            "cached": False,
        }

    def _emit_alert_notifications(self, alerts: list[dict]) -> None:
        """각 alert 에 대해 notification 발행.

        저장소 dedup(1분/link) 으로 중복 완화 — 동일 report 내 여러 alert 는
        첫 번째만 persist 되고 나머지는 silently None 반환됨.
        """
        if self.notification_store is None or not alerts:
            return
        for alert in alerts:
            try:
                message = alert.get("message", "")
                self.notification_store.add(
                    kind="risk",
                    level="warn",
                    title="Risk 경고",
                    body=message[:200] if message else None,
                    link="/risk",
                )
            except Exception as e:
                logger.warning("notification add failed for risk: %s", e)

    def get_limits(self) -> dict:
        cfg = Config()
        return {
            "max_position_weight": cfg.MAX_POSITION_WEIGHT,
            "max_drawdown_soft": cfg.MAX_DRAWDOWN_SOFT,
            "max_drawdown_hard": cfg.MAX_DRAWDOWN_HARD,
            "max_daily_orders": cfg.MAX_DAILY_ORDERS,
            "max_daily_amount": cfg.MAX_DAILY_AMOUNT,
        }

    def run_custom_stress(self, mode: str, shocks: dict[str, float]) -> dict:
        snap = self.portfolio_reader.get_latest(mode=mode)
        if snap is None:
            return {}
        snap_obj = self._to_snapshot(snap)
        tester = StressTest()
        tester.add_custom_scenario(name="custom_user", shocks=shocks)
        result = tester.run(portfolio=snap_obj, scenario="custom_user")
        return {"custom_user": asdict(result)}

    @staticmethod
    def _to_snapshot(dto: SnapshotDTO) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            date=dto.date, cash=dto.cash, positions=[],
            total_value=dto.total_value,
            daily_return=dto.daily_return,
            cumulative_return=dto.cumulative_return,
            drawdown=dto.drawdown,
        )
