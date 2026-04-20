"""Audit API 테스트."""
import sqlite3
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.audit import router as audit_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    audit_db = tmp_path / "audit.db"
    with sqlite3.connect(audit_db) as conn:
        conn.execute(
            "CREATE TABLE audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "timestamp REAL NOT NULL,"
            "event_type TEXT NOT NULL,"
            "component TEXT,"
            "data TEXT,"
            "mode TEXT)"
        )
        for i, ev in enumerate([
            "webapp.login_success", "webapp.backtest_run",
            "webapp.settings.update",
        ]):
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, component, "
                "data, mode) VALUES (?, ?, ?, ?, ?)",
                (time.time() - i, ev, "webapp", "{}", "live"),
            )

    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.audit_reader = AuditReader(db_path=audit_db)
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
    app.include_router(audit_router)
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


class TestAudit:
    def test_list(self, client):
        r = client.get("/api/v1/audit/events")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_filter_by_action_prefix(self, client):
        r = client.get("/api/v1/audit/events?action_prefix=webapp.settings")
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(
            ev["event_type"].startswith("webapp.settings") for ev in items
        )

    def test_requires_admin(self, app):
        app.state.users.create(
            email="u@x.com",
            password_hash=hash_password("long-enough-pw!"),
            role="user",
        )
        c = TestClient(app, base_url="https://testserver")
        t = c.get("/api/v1/csrf-token").json()["token"]
        c.post(
            "/api/v1/auth/login",
            json={"email": "u@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        r = c.get("/api/v1/audit/events")
        assert r.status_code == 403
