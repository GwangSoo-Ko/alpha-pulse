"""Notification API 통합 테스트."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.notifications import router as notif_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.notifications import NotificationStore
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
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
    app.state.notification_store = NotificationStore(db_path=webapp_db)

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
    app.include_router(notif_router)
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


@pytest.fixture
def store(app) -> NotificationStore:
    return app.state.notification_store


def test_list_notifications_returns_items(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="briefing", level="info", title="B", link="/b")
    r = client.get("/api/v1/notifications")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2


def test_list_notifications_respects_limit(client, store):
    for i in range(5):
        store.add(kind="job", level="info", title=f"n{i}", link=f"/l{i}")
    r = client.get("/api/v1/notifications?limit=3")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 3


def test_unread_count_endpoint(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="job", level="info", title="B", link="/b")
    r = client.get("/api/v1/notifications/unread-count")
    assert r.status_code == 200
    assert r.json() == {"count": 2}


def test_mark_read_endpoint(client, store):
    nid = store.add(kind="job", level="info", title="A", link="/a")
    r = client.post(f"/api/v1/notifications/{nid}/read")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert store.unread_count() == 0


def test_mark_read_404_on_missing(client):
    r = client.post("/api/v1/notifications/99999/read")
    assert r.status_code == 404


def test_mark_all_read_endpoint(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="job", level="info", title="B", link="/b")
    r = client.post("/api/v1/notifications/read-all")
    assert r.status_code == 200
    assert r.json() == {"count": 2}
    assert store.unread_count() == 0


def test_all_endpoints_require_auth(app):
    unauthed = TestClient(app, base_url="https://testserver")
    # CSRF token so POSTs bypass CSRF middleware and hit auth check
    t = unauthed.get("/api/v1/csrf-token").json()["token"]
    unauthed.headers.update({"X-CSRF-Token": t})
    assert unauthed.get("/api/v1/notifications").status_code == 401
    assert unauthed.get("/api/v1/notifications/unread-count").status_code == 401
    assert unauthed.post("/api/v1/notifications/1/read").status_code == 401
    assert unauthed.post("/api/v1/notifications/read-all").status_code == 401
