"""LoginAttemptsRepository 테스트 — 브루트포스 방어 카운팅."""
import time

import pytest

from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository


@pytest.fixture
def attempts(webapp_db):
    return LoginAttemptsRepository(db_path=webapp_db)


class TestLoginAttempts:
    def test_record_and_count_failures(self, attempts):
        for _ in range(3):
            attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_email(
            "a@b.com", window_seconds=900,
        )
        assert n == 3

    def test_success_does_not_count(self, attempts):
        attempts.record(email="a@b.com", ip="1.1.1.1", success=True)
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_email("a@b.com", 900)
        assert n == 1

    def test_old_failures_ignored(self, attempts):
        # 윈도우 밖으로 밀어내기 위해 직접 삽입
        import sqlite3
        with sqlite3.connect(attempts.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                ("a@b.com", "1.1.1.1", 0, time.time() - 10_000),
            )
        n = attempts.recent_failures_by_email("a@b.com", 900)
        assert n == 0

    def test_count_by_ip(self, attempts):
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        attempts.record(email="c@d.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_ip("1.1.1.1", window_seconds=60)
        assert n == 2

    def test_cleanup(self, attempts):
        import sqlite3
        with sqlite3.connect(attempts.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                ("a@b.com", "1.1.1.1", 0, time.time() - 86400 * 30),
            )
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        deleted = attempts.cleanup_older_than(86400 * 7)
        assert deleted == 1
