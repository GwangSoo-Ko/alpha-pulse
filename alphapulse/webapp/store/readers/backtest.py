"""BacktestReader — 기존 BacktestStore 래핑 + 페이지네이션 DTO."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from alphapulse.trading.backtest.store import BacktestStore


@dataclass
class RunSummary:
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    metrics: dict = field(default_factory=dict)
    created_at: float = 0.0


@dataclass
class RunFull:
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    params: dict
    metrics: dict
    created_at: float


@dataclass
class Page:
    items: list[RunSummary]
    page: int
    size: int
    total: int


class BacktestReader:
    """읽기 전용 어댑터 — 페이지네이션/필터 + 접두사 검색."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        BacktestStore(db_path=self.db_path)  # ensure schema exists
        self._store = BacktestStore(db_path=self.db_path)

    def list_runs(
        self,
        page: int = 1,
        size: int = 20,
        name_contains: str | None = None,
    ) -> Page:
        offset = (page - 1) * size
        where = ""
        params: list = []
        if name_contains:
            where = "WHERE name LIKE ?"
            params.append(f"%{name_contains}%")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM runs {where}", params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM runs {where} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, size, offset],
            ).fetchall()
        items = [self._row_to_summary(r) for r in rows]
        return Page(items=items, page=page, size=size, total=total)

    def resolve_run(self, run_id_or_prefix: str) -> RunSummary | None:
        exact = self._store.get_run(run_id_or_prefix)
        if exact:
            return self._dict_to_summary(exact)
        for row in self._store.list_runs():
            if row["run_id"].startswith(run_id_or_prefix):
                return self._dict_to_summary(row)
        return None

    def get_run_full(self, run_id_or_prefix: str) -> RunFull | None:
        s = self.resolve_run(run_id_or_prefix)
        if s is None:
            return None
        raw = self._store.get_run(s.run_id)
        return RunFull(
            run_id=s.run_id, name=s.name, strategies=s.strategies,
            start_date=s.start_date, end_date=s.end_date,
            initial_capital=s.initial_capital,
            final_value=s.final_value,
            benchmark=s.benchmark,
            params=json.loads(raw.get("params") or "{}"),
            metrics=s.metrics,
            created_at=s.created_at,
        )

    def get_snapshots(self, run_id: str) -> list[dict]:
        return self._store.get_snapshots(run_id)

    def get_trades(
        self,
        run_id: str,
        code: str | None = None,
        winner: bool | None = None,
    ) -> list[dict]:
        rts = self._store.get_round_trips(run_id)
        out = rts
        if code:
            out = [r for r in out if r["code"] == code]
        if winner is True:
            out = [r for r in out if r["pnl"] > 0]
        elif winner is False:
            out = [r for r in out if r["pnl"] <= 0]
        return out

    def get_positions(
        self,
        run_id: str,
        date: str | None = None,
        code: str | None = None,
    ) -> list[dict]:
        return self._store.get_positions(
            run_id, date=date or "", code=code or "",
        )

    def delete_run(self, run_id: str) -> None:
        self._store.delete_run(run_id)

    @staticmethod
    def _row_to_summary(row) -> RunSummary:
        return RunSummary(
            run_id=row["run_id"],
            name=row["name"] or "",
            strategies=json.loads(row["strategies"] or "[]"),
            start_date=row["start_date"],
            end_date=row["end_date"],
            initial_capital=row["initial_capital"],
            final_value=row["final_value"],
            benchmark=row["benchmark"] or "KOSPI",
            metrics=json.loads(row["metrics"] or "{}"),
            created_at=row["created_at"],
        )

    @staticmethod
    def _dict_to_summary(d: dict) -> RunSummary:
        return RunSummary(
            run_id=d["run_id"],
            name=d.get("name", "") or "",
            strategies=json.loads(d.get("strategies") or "[]"),
            start_date=d["start_date"],
            end_date=d["end_date"],
            initial_capital=d["initial_capital"],
            final_value=d["final_value"],
            benchmark=d.get("benchmark") or "KOSPI",
            metrics=json.loads(d.get("metrics") or "{}"),
            created_at=d["created_at"],
        )
