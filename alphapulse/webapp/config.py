"""웹앱 전용 설정 — alphapulse.core.Config와 별도.

환경 변수:
  WEBAPP_SESSION_SECRET     (필수, 최소 32자)
  WEBAPP_ENCRYPT_KEY        (선택, Phase 3 대비 — Fernet 키)
  TELEGRAM_MONITOR_BOT_TOKEN (선택, 운영 채널)
  TELEGRAM_MONITOR_CHANNEL_ID (선택)
  WEBAPP_DB_PATH            (기본 data/webapp.db)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WebAppConfig:
    session_secret: str
    monitor_bot_token: str
    monitor_channel_id: str
    encrypt_key: str = ""
    db_path: str = "data/webapp.db"
    session_cookie_name: str = "ap_session"
    session_ttl_seconds: int = 86400           # 24h
    session_absolute_ttl_seconds: int = 30 * 86400
    session_sliding_seconds: int = 900          # 15분
    bcrypt_cost: int = 12

    def __post_init__(self) -> None:
        if len(self.session_secret) < 32:
            raise ValueError(
                "WEBAPP_SESSION_SECRET must be at least 32 chars"
            )

    @property
    def monitor_enabled(self) -> bool:
        return bool(self.monitor_bot_token and self.monitor_channel_id)

    @classmethod
    def from_env(cls) -> "WebAppConfig":
        return cls(
            session_secret=os.environ["WEBAPP_SESSION_SECRET"],
            monitor_bot_token=os.environ.get(
                "TELEGRAM_MONITOR_BOT_TOKEN", ""
            ),
            monitor_channel_id=os.environ.get(
                "TELEGRAM_MONITOR_CHANNEL_ID", ""
            ),
            encrypt_key=os.environ.get("WEBAPP_ENCRYPT_KEY", ""),
            db_path=os.environ.get("WEBAPP_DB_PATH", "data/webapp.db"),
        )

    def db_path_resolved(self, base_dir: Path) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else base_dir / p
