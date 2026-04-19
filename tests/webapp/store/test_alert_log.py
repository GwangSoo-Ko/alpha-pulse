"""AlertLogRepository — 동일 알림 중복 방지."""
import time

import pytest

from alphapulse.webapp.store.alert_log import AlertLogRepository


@pytest.fixture
def log(webapp_db):
    return AlertLogRepository(db_path=webapp_db)


class TestAlertLog:
    def test_first_send_allowed(self, log):
        allowed = log.should_send(
            title="FastAPI 5xx burst", level="ERROR", window_seconds=300,
        )
        assert allowed is True

    def test_duplicate_within_window_denied(self, log):
        log.should_send(
            title="same", level="ERROR", window_seconds=300,
        )
        allowed = log.should_send(
            title="same", level="ERROR", window_seconds=300,
        )
        assert allowed is False

    def test_after_window_allowed(self, log):
        log.should_send(title="x", level="ERROR", window_seconds=1)
        time.sleep(1.1)
        allowed = log.should_send(
            title="x", level="ERROR", window_seconds=1,
        )
        assert allowed is True

    def test_counts_duplicates(self, log):
        log.should_send(title="y", level="ERROR", window_seconds=300)
        log.should_send(title="y", level="ERROR", window_seconds=300)
        log.should_send(title="y", level="ERROR", window_seconds=300)
        n = log.suppressed_count(title="y")
        assert n == 2   # 첫 번째는 send, 이후 2번 억제됨
