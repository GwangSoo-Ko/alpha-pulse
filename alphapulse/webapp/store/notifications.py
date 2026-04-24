"""알림 저장소 — 이벤트별 push 기록, 조회, 읽음 관리."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Literal

NotificationKind = Literal["job", "briefing", "risk", "pulse"]
NotificationLevel = Literal["info", "warn", "error"]

ALLOWED_KINDS = {"job", "briefing", "risk", "pulse"}
ALLOWED_LEVELS = {"info", "warn", "error"}

DEDUP_WINDOW_SECONDS = 60
RETENTION_DAYS = 30


class NotificationStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def add(
        self,
        *,
        kind: NotificationKind | str,
        level: NotificationLevel | str,
        title: str,
        body: str | None = None,
        link: str | None = None,
    ) -> int | None:
        """알림을 추가. 1분 내 동일 (kind, link) 중복은 skip (None 반환)."""
        if kind not in ALLOWED_KINDS or level not in ALLOWED_LEVELS:
            return None
        now = time.time()
        dedup_after = now - DEDUP_WINDOW_SECONDS
        with sqlite3.connect(self.db_path) as conn:
            if link is not None:
                # Best-effort dedup: between this SELECT and INSERT there is a
                # small race window, which is acceptable for notifications.
                dup = conn.execute(
                    "SELECT id FROM notifications "
                    "WHERE kind = ? AND link = ? AND created_at >= ? "
                    "LIMIT 1",
                    (kind, link, dedup_after),
                ).fetchone()
                if dup is not None:
                    return None
            cur = conn.execute(
                "INSERT INTO notifications "
                "(kind, level, title, body, link, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, level, title, body, link, now),
            )
            return cur.lastrowid

    def list_recent(self, limit: int = 20) -> list[dict]:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM notifications "
                "WHERE created_at >= ? "
                "ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def unread_count(self) -> int:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM notifications "
                "WHERE is_read = 0 AND created_at >= ?",
                (cutoff,),
            ).fetchone()
        return row[0]

    def mark_read(self, notification_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE is_read = 0",
            )
            return cur.rowcount
