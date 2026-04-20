"""SettingsService — DB → .env fallback + load_env_overrides."""
import os

import pytest
from cryptography.fernet import Fernet

from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.settings import SettingsRepository


@pytest.fixture
def fernet_key():
    return Fernet.generate_key()


@pytest.fixture
def svc(webapp_db, fernet_key):
    repo = SettingsRepository(db_path=webapp_db, fernet_key=fernet_key)
    return SettingsService(repo=repo)


class TestGetFallback:
    def test_db_has_value(self, svc):
        svc.repo.set(
            key="K", value="from_db", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get("K") == "from_db"

    def test_db_missing_env_has(self, svc, monkeypatch):
        monkeypatch.setenv("K", "from_env")
        assert svc.get("K") == "from_env"

    def test_db_takes_priority_over_env(self, svc, monkeypatch):
        monkeypatch.setenv("K", "from_env")
        svc.repo.set(
            key="K", value="from_db", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get("K") == "from_db"

    def test_both_missing(self, svc):
        assert svc.get("NOT_EXIST_AT_ALL") is None


class TestTypedGet:
    def test_int(self, svc):
        svc.repo.set(
            key="N", value="42", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get_int("N", default=0) == 42
        assert svc.get_int("MISSING", default=99) == 99

    def test_float(self, svc):
        svc.repo.set(
            key="R", value="0.25", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get_float("R", default=1.0) == 0.25

    def test_bool_truthy(self, svc):
        svc.repo.set(
            key="B", value="true", is_secret=False,
            category="notification", user_id=1,
        )
        assert svc.get_bool("B", default=False) is True

    def test_bool_falsy(self, svc):
        svc.repo.set(
            key="B", value="0", is_secret=False,
            category="notification", user_id=1,
        )
        assert svc.get_bool("B", default=True) is False


class TestMask:
    def test_masks_long_secret(self):
        assert SettingsService.mask("sk-abcdefghij1234") == "sk-a****1234"

    def test_masks_short_secret(self):
        assert SettingsService.mask("short") == "****"

    def test_none(self):
        assert SettingsService.mask(None) == ""


class TestLoadEnvOverrides:
    def test_overrides_os_environ(self, svc, monkeypatch):
        monkeypatch.delenv("KIS_APP_KEY", raising=False)
        svc.repo.set(
            key="KIS_APP_KEY", value="db_val",
            is_secret=True, category="api_key", user_id=1,
        )
        svc.load_env_overrides()
        assert os.environ.get("KIS_APP_KEY") == "db_val"
