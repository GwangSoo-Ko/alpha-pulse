"""MonitorNotifier — 운영 채널 Telegram 발송 (mock)."""
from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository


@pytest.fixture
def alert_log(webapp_db):
    return AlertLogRepository(db_path=webapp_db)


@pytest.fixture
def notifier(alert_log):
    return MonitorNotifier(
        bot_token="t", chat_id="-100",
        alert_log=alert_log, window_seconds=300,
    )


class TestMonitorNotifier:
    async def test_disabled_when_missing_token(self, alert_log):
        n = MonitorNotifier(
            bot_token="", chat_id="", alert_log=alert_log,
        )
        assert n.enabled is False
        await n.send("INFO", "t", "detail")  # no-op, no exception

    @patch("alphapulse.webapp.notifier.httpx.AsyncClient")
    async def test_send_calls_api(self, mock_client, notifier):
        mock_post = AsyncMock(
            return_value=AsyncMock(raise_for_status=lambda: None),
        )
        mock_client.return_value.__aenter__.return_value.post = mock_post
        await notifier.send("ERROR", "title", "detail")
        assert mock_post.await_count == 1
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        assert "title" in kwargs["json"]["text"]

    @patch("alphapulse.webapp.notifier.httpx.AsyncClient")
    async def test_rate_limit_skips_second(self, mock_client, notifier):
        mock_post = AsyncMock(
            return_value=AsyncMock(raise_for_status=lambda: None),
        )
        mock_client.return_value.__aenter__.return_value.post = mock_post
        await notifier.send("ERROR", "dup", "x")
        await notifier.send("ERROR", "dup", "x")
        assert mock_post.await_count == 1
