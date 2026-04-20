"""Data 상태 조회 어댑터."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TableStatus:
    name: str
    row_count: int
    latest_date: str | None
    distinct_codes: int


class DataStatusReader:
    def __init__(self, trading_db_path: str | Path) -> None:
        self.db_path = Path(trading_db_path)

    def get_status(self) -> list[TableStatus]:
        targets = [
            ("ohlcv", "date", "code"),
            ("fundamentals_timeseries", "period", "code"),
            ("stock_investor_flow", "date", "code"),
            ("short_interest", "date", "code"),
            ("wisereport_data", "date", "code"),
        ]
        out: list[TableStatus] = []
        with sqlite3.connect(self.db_path) as conn:
            for table, date_col, code_col in targets:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*), MAX({date_col}), "
                        f"COUNT(DISTINCT {code_col}) FROM {table}"
                    ).fetchone()
                except sqlite3.OperationalError:
                    continue
                out.append(TableStatus(
                    name=table, row_count=row[0] or 0,
                    latest_date=row[1], distinct_codes=row[2] or 0,
                ))
        return out

    def detect_gaps(self, days: int = 5) -> list[dict]:
        """최근 N일 내 OHLCV 결측 종목 리스트."""
        from datetime import datetime, timedelta
        threshold = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        with sqlite3.connect(self.db_path) as conn:
            try:
                rows = conn.execute(
                    "SELECT code, MAX(date) as max_date FROM ohlcv "
                    "GROUP BY code HAVING max_date < ?",
                    (threshold,),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [{"code": r[0], "last_date": r[1]} for r in rows]
