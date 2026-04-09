"""데이터 수집 메타데이터 관리.

시장/데이터 유형별 마지막 수집일을 추적한다.
"""

import sqlite3
import time
from pathlib import Path


class CollectionMetadata:
    """수집 메타데이터 저장소."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_metadata (
                    market TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    last_date TEXT NOT NULL,
                    updated_at REAL,
                    PRIMARY KEY (market, data_type)
                )
            """)

    def get_last_date(self, market: str, data_type: str) -> str | None:
        """시장/데이터 유형의 마지막 수집일을 반환한다."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT last_date FROM collection_metadata WHERE market = ? AND data_type = ?",
                (market, data_type),
            ).fetchone()
        return row[0] if row else None

    def set_last_date(self, market: str, data_type: str, date: str) -> None:
        """시장/데이터 유형의 마지막 수집일을 설정한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO collection_metadata (market, data_type, last_date, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(market, data_type) DO UPDATE SET
                    last_date=excluded.last_date, updated_at=excluded.updated_at""",
                (market, data_type, date, time.time()),
            )

    def get_all_status(self) -> list[dict]:
        """전체 수집 상태를 반환한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM collection_metadata ORDER BY market, data_type"
            ).fetchall()
        return [dict(r) for r in rows]
