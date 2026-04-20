"""SettingsRepository — data/webapp.db settings 테이블 (Fernet 암호화)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet

__all__ = ["SettingsRepository", "SettingsEntry"]


@dataclass
class SettingsEntry:
    """Settings 엔트리 (평문)."""

    key: str
    value: str
    is_secret: bool
    category: str
    updated_at: float
    updated_by: int | None = None
    tenant_id: int | None = None


class SettingsRepository:
    """Settings 저장소 (Fernet 암호화 저장)."""

    def __init__(self, db_path: str | Path, fernet_key: bytes) -> None:
        """초기화.

        Args:
            db_path: webapp.db 경로
            fernet_key: Fernet 암호화 키 (bytes)
        """
        self.db_path = Path(db_path)
        self._fernet = Fernet(fernet_key)

    def set(
        self,
        key: str,
        value: str,
        is_secret: bool,
        category: str,
        user_id: int | None = None,
        tenant_id: int | None = None,
    ) -> None:
        """설정값 저장 (암호화).

        기존 키면 업데이트. 새 키면 삽입.

        Args:
            key: 설정 키
            value: 설정값 (평문)
            is_secret: 기밀 여부 (0=공개, 1=기밀)
            category: 카테고리 (api_key, risk_limit, 등)
            user_id: 수정 사용자 ID
            tenant_id: 테넌트 ID (멀티테넌트)
        """
        encrypted_value = self._fernet.encrypt(value.encode()).decode()
        updated_at = time.time()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO settings
                    (key, value_encrypted, is_secret, category, tenant_id, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_encrypted=excluded.value_encrypted,
                    is_secret=excluded.is_secret,
                    category=excluded.category,
                    tenant_id=excluded.tenant_id,
                    updated_at=excluded.updated_at,
                    updated_by=excluded.updated_by
                """,
                (key, encrypted_value, int(is_secret), category, tenant_id, updated_at, user_id),
            )
            conn.commit()

    def get(self, key: str) -> str | None:
        """설정값 조회 (복호화).

        Args:
            key: 설정 키

        Returns:
            설정값 (평문). 없으면 None.

        Raises:
            InvalidToken: 복호화 실패 (키 불일치 등)
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value_encrypted FROM settings WHERE key=?",
                (key,),
            ).fetchone()

        if not row:
            return None

        encrypted_value = row[0]
        decrypted_bytes = self._fernet.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()

    def list_by_category(self, category: str) -> list[SettingsEntry]:
        """특정 카테고리 모든 설정 조회.

        Args:
            category: 카테고리명

        Returns:
            SettingsEntry 리스트 (평문)
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value_encrypted, is_secret, category, updated_at, updated_by, tenant_id FROM settings WHERE category=?",
                (category,),
            ).fetchall()

        entries = []
        for row in rows:
            key, encrypted_value, is_secret, category, updated_at, updated_by, tenant_id = row
            value = self._fernet.decrypt(encrypted_value.encode()).decode()
            entries.append(
                SettingsEntry(
                    key=key,
                    value=value,
                    is_secret=bool(is_secret),
                    category=category,
                    updated_at=updated_at,
                    updated_by=updated_by,
                    tenant_id=tenant_id,
                )
            )
        return entries

    def list_all(self) -> list[SettingsEntry]:
        """모든 설정 조회.

        Returns:
            SettingsEntry 리스트 (평문)
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value_encrypted, is_secret, category, updated_at, updated_by, tenant_id FROM settings"
            ).fetchall()

        entries = []
        for row in rows:
            key, encrypted_value, is_secret, category, updated_at, updated_by, tenant_id = row
            value = self._fernet.decrypt(encrypted_value.encode()).decode()
            entries.append(
                SettingsEntry(
                    key=key,
                    value=value,
                    is_secret=bool(is_secret),
                    category=category,
                    updated_at=updated_at,
                    updated_by=updated_by,
                    tenant_id=tenant_id,
                )
            )
        return entries

    def delete(self, key: str) -> None:
        """설정값 삭제.

        Args:
            key: 설정 키
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM settings WHERE key=?", (key,))
            conn.commit()
