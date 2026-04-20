"""ap webapp CLI 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")
    return tmp_path


class TestCreateAdmin:
    def test_create_admin(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="correct-horse-battery\ncorrect-horse-battery\n",
        )
        assert r.exit_code == 0
        assert "a@x.com" in r.output

    def test_rejects_short_password(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="short\nshort\n",
        )
        assert r.exit_code != 0 or "12" in r.output


class TestResetPassword:
    def test_reset(self, runner, env):
        from alphapulse.cli import cli
        runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="correct-horse-battery\ncorrect-horse-battery\n",
        )
        r = runner.invoke(
            cli,
            ["webapp", "reset-password", "--email", "a@x.com"],
            input="new-password-12!\nnew-password-12!\n",
        )
        assert r.exit_code == 0
        assert "updated" in r.output.lower()


class TestUnlock:
    def test_unlock_removes_recent_fails(self, runner, env):
        from alphapulse.cli import cli
        from alphapulse.webapp.store.login_attempts import (
            LoginAttemptsRepository,
        )
        db = env / "webapp.db"
        from alphapulse.webapp.store.webapp_db import init_webapp_db
        init_webapp_db(db)
        la = LoginAttemptsRepository(db_path=db)
        for _ in range(5):
            la.record(email="a@x.com", ip="1.1.1.1", success=False)

        r = runner.invoke(
            cli, ["webapp", "unlock-account", "--email", "a@x.com"],
        )
        assert r.exit_code == 0
        assert la.recent_failures_by_email("a@x.com", 900) == 0


class TestVerifyMonitoring:
    def test_disabled_when_missing(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(cli, ["webapp", "verify-monitoring"])
        assert r.exit_code == 0
        assert "disabled" in r.output.lower() or "set" in r.output.lower()

    @patch("alphapulse.webapp.cli.MonitorNotifier")
    def test_sends_test_message(
        self, mock_notifier_cls, runner, env, monkeypatch,
    ):
        monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "-100")
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send = AsyncMock()
        mock_notifier_cls.return_value = mock_notifier

        from alphapulse.cli import cli
        r = runner.invoke(cli, ["webapp", "verify-monitoring"])
        assert r.exit_code == 0
        assert mock_notifier.send.await_count == 1
