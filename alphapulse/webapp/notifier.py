"""MonitorNotifier — 운영/장애 전용 Telegram 알림.

기존 콘텐츠 채널(alphapulse.core.notifier)과 분리된 봇/채널 사용.
AlertLog로 동일 title 반복을 rate limit.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from alphapulse.webapp.store.alert_log import AlertLogRepository

logger = logging.getLogger(__name__)

Level = Literal["INFO", "WARN", "ERROR", "CRITICAL"]

_EMOJI = {
    "INFO": "ℹ️",
    "WARN": "⚠️",
    "ERROR": "🚨",
    "CRITICAL": "🔥",
}


class MonitorNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        alert_log: AlertLogRepository,
        window_seconds: int = 300,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.alert_log = alert_log
        self.window_seconds = window_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(
        self, level: Level, title: str, detail: str = "",
    ) -> None:
        if not self.enabled:
            return
        if not self.alert_log.should_send(
            title=title, level=level,
            window_seconds=self.window_seconds,
        ):
            logger.debug("alert suppressed: %s", title)
            return

        emoji = _EMOJI.get(level, "")
        text = f"{emoji} [{level}] {title}"
        if detail:
            text += f"\n\n{detail[:3500]}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.exception("monitor telegram send failed")
