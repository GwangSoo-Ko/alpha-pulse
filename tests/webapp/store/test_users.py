"""UserRepository 테스트."""
import time

import pytest

from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def users(webapp_db):
    return UserRepository(db_path=webapp_db)


class TestUsers:
    def test_create_and_get(self, users):
        uid = users.create(
            email="admin@example.com",
            password_hash="$2b$12$fakehash",
            role="admin",
        )
        user = users.get_by_email("admin@example.com")
        assert user is not None
        assert user.id == uid
        assert user.email == "admin@example.com"
        assert user.role == "admin"
        assert user.is_active is True

    def test_get_by_id(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h", role="admin",
        )
        user = users.get_by_id(uid)
        assert user is not None
        assert user.email == "a@b.com"

    def test_duplicate_email_raises(self, users):
        users.create(
            email="x@y.com", password_hash="h", role="admin",
        )
        with pytest.raises(ValueError):
            users.create(
                email="x@y.com", password_hash="h2", role="admin",
            )

    def test_update_last_login(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h", role="admin",
        )
        users.touch_last_login(uid)
        user = users.get_by_id(uid)
        assert user.last_login_at is not None
        assert time.time() - user.last_login_at < 5

    def test_update_password_hash(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h1", role="admin",
        )
        users.update_password_hash(uid, "h2")
        user = users.get_by_id(uid)
        assert user.password_hash == "h2"

    def test_get_not_found(self, users):
        assert users.get_by_email("none@x.com") is None
        assert users.get_by_id(9999) is None
