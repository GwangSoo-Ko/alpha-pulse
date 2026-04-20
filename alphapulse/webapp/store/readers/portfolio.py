"""PortfolioStore 래핑 어댑터 — 웹 응답용 DTO."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from alphapulse.trading.portfolio.store import PortfolioStore


@dataclass
class SnapshotDTO:
    date: str
    cash: float
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions: list


@dataclass
class AttributionDTO:
    date: str
    strategy_returns: dict
    factor_returns: dict
    sector_returns: dict


class PortfolioReader:
    def __init__(self, db_path: str | Path) -> None:
        self.store = PortfolioStore(db_path=str(db_path))

    def get_latest(self, mode: str) -> SnapshotDTO | None:
        raw = self.store.get_latest_snapshot(mode=mode)
        if raw is None:
            return None
        return self._to_dto(raw)

    def get_history(
        self,
        mode: str,
        days: int,
    ) -> list[SnapshotDTO]:
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        rows = self.store.get_snapshots(start=start, end=end, mode=mode)
        return [self._to_dto(r) for r in rows]

    def get_attribution(self, mode: str, date: str) -> AttributionDTO | None:
        raw = self.store.get_attribution(date=date, mode=mode)
        if not raw:
            return None
        return AttributionDTO(
            date=raw["date"],
            strategy_returns=self._parse_json(raw.get("strategy_returns")),
            factor_returns=self._parse_json(raw.get("factor_returns")),
            sector_returns=self._parse_json(raw.get("sector_returns")),
        )

    @staticmethod
    def _parse_json(val) -> dict:  # noqa: ANN001
        if val is None:
            return {}
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return val

    @staticmethod
    def _to_dto(raw: dict) -> SnapshotDTO:
        positions = raw.get("positions", "[]")
        if isinstance(positions, str):
            try:
                positions = json.loads(positions)
            except json.JSONDecodeError:
                positions = []
        return SnapshotDTO(
            date=raw["date"],
            cash=raw["cash"],
            total_value=raw["total_value"],
            daily_return=raw["daily_return"],
            cumulative_return=raw["cumulative_return"],
            drawdown=raw["drawdown"],
            positions=positions or [],
        )
