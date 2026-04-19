"""LoginAttemptsRepository — 브루트포스 방어."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class LoginAttemptsRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def record(self, email: str, ip: str, success: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                (email, ip, 1 if success else 0, time.time()),
            )

    def recent_failures_by_email(
        self, email: str, window_seconds: int,
    ) -> int:
        threshold = time.time() - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE email = ? AND success = 0 AND attempted_at >= ?",
                (email, threshold),
            ).fetchone()
        return int(row[0])

    def recent_failures_by_ip(
        self, ip: str, window_seconds: int,
    ) -> int:
        threshold = time.time() - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE ip = ? AND success = 0 AND attempted_at >= ?",
                (ip, threshold),
            ).fetchone()
        return int(row[0])

    def cleanup_older_than(self, seconds: int) -> int:
        threshold = time.time() - seconds
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM login_attempts WHERE attempted_at < ?",
                (threshold,),
            )
            return cur.rowcount
