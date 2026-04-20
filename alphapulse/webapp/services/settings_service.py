"""SettingsService — 런타임 설정 중앙 접근.

우선순위: DB (Fernet 복호화) → os.environ → default.
"""

from __future__ import annotations

import os

from alphapulse.webapp.store.settings import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository) -> None:
        self.repo = repo

    def get(self, key: str) -> str | None:
        val = self.repo.get(key)
        if val is not None:
            return val
        return os.environ.get(key)

    def get_int(self, key: str, default: int) -> int:
        v = self.get(key)
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float) -> float:
        v = self.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool) -> bool:
        v = self.get(key)
        if v is None:
            return default
        return v.strip().lower() in {"1", "true", "yes", "on"}

    def load_env_overrides(self) -> None:
        """DB의 모든 설정을 os.environ에 덮어쓰기.
        FastAPI startup 훅에서 1회 호출. Phase 2 한정 방식.
        """
        for entry in self.repo.list_all():
            val = self.repo.get(entry.key)
            if val is not None:
                os.environ[entry.key] = val

    @staticmethod
    def mask(value: str | None) -> str:
        """Secret 값 마스킹."""
        if value is None:
            return ""
        if len(value) < 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
