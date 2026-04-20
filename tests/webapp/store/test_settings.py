"""SettingsRepository — Fernet 암호화 저장/조회."""
import sqlite3

import pytest
from cryptography.fernet import Fernet

from alphapulse.webapp.store.settings import SettingsRepository


@pytest.fixture
def fernet_key():
    return Fernet.generate_key()


@pytest.fixture
def repo(webapp_db, fernet_key):
    return SettingsRepository(db_path=webapp_db, fernet_key=fernet_key)


class TestSettingsRepository:
    def test_set_and_get_roundtrip(self, repo):
        repo.set(
            key="KIS_APP_KEY", value="secret-value-12345",
            is_secret=True, category="api_key", user_id=1,
        )
        assert repo.get("KIS_APP_KEY") == "secret-value-12345"

    def test_get_missing_returns_none(self, repo):
        assert repo.get("NOT_EXIST") is None

    def test_encryption_at_rest(self, repo, webapp_db):
        repo.set(
            key="KIS_APP_KEY", value="plaintext",
            is_secret=True, category="api_key", user_id=1,
        )
        with sqlite3.connect(webapp_db) as conn:
            row = conn.execute(
                "SELECT value_encrypted FROM settings WHERE key=?",
                ("KIS_APP_KEY",),
            ).fetchone()
        assert row is not None
        assert "plaintext" not in row[0]

    def test_set_updates_existing(self, repo):
        repo.set(
            key="K", value="v1", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K", value="v2", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert repo.get("K") == "v2"

    def test_list_by_category(self, repo):
        repo.set(
            key="K1", value="v1", is_secret=True,
            category="api_key", user_id=1,
        )
        repo.set(
            key="K2", value="v2", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K3", value="v3", is_secret=True,
            category="api_key", user_id=1,
        )
        api_keys = repo.list_by_category("api_key")
        assert {e.key for e in api_keys} == {"K1", "K3"}

    def test_list_all(self, repo):
        repo.set(
            key="K1", value="v1", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K2", value="v2", is_secret=True,
            category="api_key", user_id=1,
        )
        assert len(repo.list_all()) == 2

    def test_delete(self, repo):
        repo.set(
            key="K", value="v", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.delete("K")
        assert repo.get("K") is None

    def test_key_mismatch_raises(self, webapp_db):
        k1 = Fernet.generate_key()
        k2 = Fernet.generate_key()
        r1 = SettingsRepository(db_path=webapp_db, fernet_key=k1)
        r1.set(
            key="K", value="v", is_secret=True,
            category="api_key", user_id=1,
        )
        r2 = SettingsRepository(db_path=webapp_db, fernet_key=k2)
        with pytest.raises(Exception):
            r2.get("K")

    def test_entry_fields(self, repo):
        repo.set(
            key="K", value="v", is_secret=True,
            category="api_key", user_id=42,
        )
        entries = repo.list_all()
        e = entries[0]
        assert e.key == "K"
        assert e.is_secret is True
        assert e.category == "api_key"
        assert e.updated_by == 42
        assert e.updated_at > 0
