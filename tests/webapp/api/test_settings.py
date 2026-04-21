"""Settings API 테스트."""
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.settings import router as settings_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.settings import SettingsRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    fkey = Fernet.generate_key()
    repo = SettingsRepository(db_path=webapp_db, fernet_key=fkey)
    svc = SettingsService(repo=repo)
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.settings_repo = repo
    app.state.settings_service = svc
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request: Request):
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(settings_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    t = c.get("/api/v1/csrf-token").json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": t},
    )
    c.headers.update({"X-CSRF-Token": t})
    return c


class TestSettings:
    def test_list_masks_secrets(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="super-secret-12345",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.get("/api/v1/settings?category=api_key")
        assert r.status_code == 200
        items = r.json()["items"]
        assert items[0]["value"] != "super-secret-12345"
        assert "****" in items[0]["value"]

    def test_update_requires_correct_password(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="old",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.put(
            "/api/v1/settings/KIS_APP_KEY",
            json={"value": "new", "current_password": "wrong"},
        )
        assert r.status_code == 401

    def test_update_success(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="old",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.put(
            "/api/v1/settings/KIS_APP_KEY",
            json={
                "value": "new-value", "current_password": "long-enough-pw!",
            },
        )
        assert r.status_code == 200
        assert app.state.settings_repo.get("KIS_APP_KEY") == "new-value"

    def test_update_unknown_key_404(self, client):
        r = client.put(
            "/api/v1/settings/UNKNOWN_KEY",
            json={"value": "x", "current_password": "long-enough-pw!"},
        )
        assert r.status_code == 404
