"""SessionRepository 테스트."""
import time

import pytest

from alphapulse.webapp.store.sessions import SessionRepository


@pytest.fixture
def sessions(webapp_db):
    return SessionRepository(db_path=webapp_db)


class TestSessions:
    def test_create_and_get(self, sessions):
        sessions.create(
            token="tok1", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="1.2.3.4", ua="agent",
        )
        sess = sessions.get("tok1")
        assert sess is not None
        assert sess.user_id == 1
        assert sess.ip == "1.2.3.4"
        assert sess.is_expired is False
        assert sess.revoked_at is None

    def test_expired(self, sessions):
        sessions.create(
            token="old", user_id=1, ttl_seconds=-1,
            absolute_ttl_seconds=-1, ip="", ua="",
        )
        sess = sessions.get("old")
        assert sess.is_expired is True

    def test_touch_extends(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=60,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        first = sessions.get("t").expires_at
        time.sleep(0.01)
        sessions.touch("t", ttl_seconds=120, absolute_ttl_seconds=86400)
        second = sessions.get("t").expires_at
        assert second > first

    def test_touch_respects_absolute_cap(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=60,
            absolute_ttl_seconds=120,   # 120초 후 절대 만료
            ip="", ua="",
        )
        # touch할 때 원하는 TTL이 절대 만료보다 크면 절대로 cap
        sessions.touch(
            "t", ttl_seconds=86400, absolute_ttl_seconds=120,
        )
        sess = sessions.get("t")
        assert sess.expires_at - sess.created_at <= 120

    def test_revoke(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        sessions.revoke("t")
        sess = sessions.get("t")
        assert sess.revoked_at is not None

    def test_cleanup_expired(self, sessions):
        sessions.create(
            token="old", user_id=1, ttl_seconds=-1,
            absolute_ttl_seconds=-1, ip="", ua="",
        )
        sessions.create(
            token="new", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        deleted = sessions.cleanup_expired()
        assert deleted == 1
        assert sessions.get("old") is None
        assert sessions.get("new") is not None

    def test_get_not_found(self, sessions):
        assert sessions.get("missing") is None
