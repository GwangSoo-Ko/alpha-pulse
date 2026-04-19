"""SessionRepository — data/webapp.db sessions 테이블.

슬라이딩 갱신과 절대 만료를 모두 관리한다.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Session:
    id: str            # 토큰
    user_id: int
    created_at: float
    expires_at: float
    ip: str | None
    user_agent: str | None
    revoked_at: float | None

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        ip=row["ip"],
        user_agent=row["user_agent"],
        revoked_at=row["revoked_at"],
    )


class SessionRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        token: str,
        user_id: int,
        ttl_seconds: int,
        absolute_ttl_seconds: int,
        ip: str,
        ua: str,
    ) -> None:
        now = time.time()
        expires = now + min(ttl_seconds, absolute_ttl_seconds)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, user_id, created_at, "
                "expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
                (token, user_id, now, expires, ip, ua),
            )

    def get(self, token: str) -> Session | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (token,)
            ).fetchone()
        return _row_to_session(row) if row else None

    def touch(
        self,
        token: str,
        ttl_seconds: int,
        absolute_ttl_seconds: int,
    ) -> None:
        """슬라이딩 갱신 — 요청된 TTL이 절대 만료를 넘지 않도록 cap."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT created_at FROM sessions WHERE id = ?", (token,)
            ).fetchone()
            if row is None:
                return
            abs_deadline = row["created_at"] + absolute_ttl_seconds
            new_expires = min(now + ttl_seconds, abs_deadline)
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                (new_expires, token),
            )

    def revoke(self, token: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE id = ?",
                (time.time(), token),
            )

    def cleanup_expired(self) -> int:
        """만료된 세션 삭제. 삭제된 행 수 반환."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (time.time(),),
            )
            return cur.rowcount
