"""RiskReportCacheRepository — 스냅샷 해시 기반 리스크 리포트 캐시."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CachedRiskReport:
    snapshot_key: str
    report: dict
    stress: dict
    computed_at: float


class RiskReportCacheRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @staticmethod
    def snapshot_key(date: str, mode: str, total_value: float) -> str:
        return f"{date}|{mode}|{int(total_value)}"

    def get(self, key: str) -> CachedRiskReport | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM risk_report_cache WHERE snapshot_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CachedRiskReport(
            snapshot_key=row["snapshot_key"],
            report=json.loads(row["report_json"]),
            stress=json.loads(row["stress_json"] or "{}"),
            computed_at=row["computed_at"],
        )

    def put(self, key: str, report: dict, stress: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO risk_report_cache "
                "(snapshot_key, report_json, stress_json, computed_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(snapshot_key) DO UPDATE SET "
                "report_json = excluded.report_json, "
                "stress_json = excluded.stress_json, "
                "computed_at = excluded.computed_at",
                (
                    key,
                    json.dumps(report, ensure_ascii=False),
                    json.dumps(stress, ensure_ascii=False),
                    time.time(),
                ),
            )
