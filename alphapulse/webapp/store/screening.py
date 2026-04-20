"""ScreeningRepository — webapp.db screening_runs CRUD."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path


@dataclass
class ScreeningRun:
    run_id: str
    name: str
    market: str
    strategy: str
    factor_weights: dict
    top_n: int
    market_context: dict
    results: list
    user_id: int
    tenant_id: int | None
    created_at: float


@dataclass
class Page:
    items: list[ScreeningRun] = dc_field(default_factory=list)
    page: int = 1
    size: int = 20
    total: int = 0


def _row_to_run(row: sqlite3.Row) -> ScreeningRun:
    return ScreeningRun(
        run_id=row["run_id"],
        name=row["name"] or "",
        market=row["market"],
        strategy=row["strategy"],
        factor_weights=json.loads(row["factor_weights"]),
        top_n=row["top_n"],
        market_context=json.loads(row["market_context"] or "{}"),
        results=json.loads(row["results"]),
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
    )


class ScreeningRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def save(
        self,
        *,
        name: str,
        market: str,
        strategy: str,
        factor_weights: dict,
        top_n: int,
        market_context: dict,
        results: list,
        user_id: int,
        tenant_id: int | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO screening_runs "
                "(run_id, name, market, strategy, factor_weights, "
                "top_n, market_context, results, user_id, tenant_id, "
                "created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, name, market, strategy,
                    json.dumps(factor_weights, ensure_ascii=False),
                    top_n,
                    json.dumps(market_context, ensure_ascii=False),
                    json.dumps(results, ensure_ascii=False),
                    user_id, tenant_id, time.time(),
                ),
            )
        return run_id

    def get(self, run_id: str) -> ScreeningRun | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM screening_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_run(row) if row else None

    def list_for_user(
        self, user_id: int, page: int = 1, size: int = 20,
    ) -> Page:
        offset = (page - 1) * size
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                "SELECT COUNT(*) FROM screening_runs WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM screening_runs WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, size, offset),
            ).fetchall()
        return Page(
            items=[_row_to_run(r) for r in rows],
            page=page, size=size, total=total,
        )

    def delete(self, run_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM screening_runs WHERE run_id = ?", (run_id,),
            )
