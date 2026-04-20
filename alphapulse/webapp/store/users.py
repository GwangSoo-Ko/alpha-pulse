"""UserRepository — data/webapp.db users 테이블 CRUD."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    role: str
    tenant_id: int | None
    is_active: bool
    created_at: float
    last_login_at: float | None


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=row["role"],
        tenant_id=row["tenant_id"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
    )


class UserRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        email: str,
        password_hash: str,
        role: str = "admin",
        tenant_id: int | None = None,
    ) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute(
                    "INSERT INTO users (email, password_hash, role, "
                    "tenant_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (email, password_hash, role, tenant_id, time.time()),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"duplicate email: {email}") from e

    def get_by_email(self, email: str) -> User | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return _row_to_user(row) if row else None

    def get_by_id(self, user_id: int) -> User | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return _row_to_user(row) if row else None

    def touch_last_login(self, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (time.time(), user_id),
            )

    def update_password_hash(self, user_id: int, new_hash: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id),
            )

    def set_active(self, user_id: int, active: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if active else 0, user_id),
            )
