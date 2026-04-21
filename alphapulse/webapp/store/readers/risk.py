"""Risk 어댑터 — 캐싱 포함. RiskManager/StressTest 호출."""

from __future__ import annotations

from dataclasses import asdict

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


class RiskReader:
    def __init__(
        self,
        portfolio_reader: PortfolioReader,
        cache: RiskReportCacheRepository,
    ) -> None:
        self.portfolio_reader = portfolio_reader
        self.cache = cache

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
        report_dict = {
            "drawdown_status": report.drawdown_status,
            "var_95": report.var_95,
            "cvar_95": report.cvar_95,
            "alerts": [
                {"level": a.level, "message": a.message}
                for a in (report.alerts or [])
            ],
        }
        self.cache.put(key=key, report=report_dict, stress=stress)
        return {
            "report": report_dict, "stress": stress,
            "cached": False,
        }

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
