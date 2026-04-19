"""webapp 설정 테스트."""
import pytest

from alphapulse.webapp.config import WebAppConfig


class TestWebAppConfig:
    def test_session_defaults(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="", monitor_channel_id="",
        )
        assert cfg.session_cookie_name == "ap_session"
        assert cfg.session_ttl_seconds == 86400
        assert cfg.session_absolute_ttl_seconds == 30 * 86400

    def test_monitor_disabled_when_missing(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="", monitor_channel_id="",
        )
        assert cfg.monitor_enabled is False

    def test_monitor_enabled_when_set(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="abc", monitor_channel_id="-100",
        )
        assert cfg.monitor_enabled is True

    def test_session_secret_required_min_length(self):
        with pytest.raises(ValueError, match="32"):
            WebAppConfig(
                session_secret="short",
                monitor_bot_token="", monitor_channel_id="",
            )

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("WEBAPP_SESSION_SECRET", "y" * 32)
        monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "-1")
        cfg = WebAppConfig.from_env()
        assert cfg.session_secret == "y" * 32
        assert cfg.monitor_enabled is True
