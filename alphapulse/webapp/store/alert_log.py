"""AlertLogRepository — 알림 rate limit (동일 title 5분 내 1회)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class AlertLogRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def should_send(
        self, title: str, level: str, window_seconds: int,
    ) -> bool:
        now = time.time()
        threshold = now - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, last_sent_at, count FROM alert_log "
                "WHERE title = ? ORDER BY last_sent_at DESC LIMIT 1",
                (title,),
            ).fetchone()
            if row is None or row["last_sent_at"] < threshold:
                conn.execute(
                    "INSERT INTO alert_log (title, level, "
                    "first_sent_at, last_sent_at, count) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (title, level, now, now),
                )
                return True
            # 억제 — 카운터만 증가
            conn.execute(
                "UPDATE alert_log SET count = count + 1, "
                "last_sent_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return False

    def suppressed_count(self, title: str) -> int:
        """마지막 엔트리의 (count - 1) 반환 — 실제 억제 횟수."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT count FROM alert_log WHERE title = ? "
                "ORDER BY last_sent_at DESC LIMIT 1",
                (title,),
            ).fetchone()
        return max(0, (row[0] - 1) if row else 0)
