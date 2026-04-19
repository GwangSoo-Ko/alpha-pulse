"""Auth 라우트 통합 테스트."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="",
        monitor_channel_id="",
        db_path=str(webapp_db),
    )
    _app = FastAPI()
    _app.state.config = cfg
    _app.state.users = UserRepository(db_path=webapp_db)
    _app.state.sessions = SessionRepository(db_path=webapp_db)
    _app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    return _app


@pytest.fixture
def seed_admin(app):
    uid = app.state.users.create(
        email="admin@x.com",
        password_hash=hash_password("correct-horse-battery"),
        role="admin",
    )
    return uid


def _make_client(app) -> TestClient:
    """secure 쿠키 전송을 위해 https://testserver 사용."""
    return TestClient(app, base_url="https://testserver")


def _csrf(client: TestClient) -> str:
    """CSRF 토큰을 가져온다. 미들웨어가 ap_csrf 쿠키를 자동 설정한다."""
    r = client.get("/api/v1/csrf-token")
    return r.json()["token"]


class TestLogin:
    def test_success(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            headers={"X-CSRF-Token": token},
        )
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "admin@x.com"
        assert "ap_session" in r.cookies

    def test_wrong_password(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@x.com", "password": "wrong-wrong!"},
            headers={"X-CSRF-Token": token},
        )
        assert r.status_code == 401

    def test_unknown_email(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "none@x.com", "password": "whatever-long"},
            headers={"X-CSRF-Token": token},
        )
        assert r.status_code == 401

    def test_locked_after_5_fails(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                json={"email": "admin@x.com", "password": "wrong-wrong!"},
                headers={"X-CSRF-Token": token},
            )
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            headers={"X-CSRF-Token": token},
        )
        assert r.status_code == 429

    def test_csrf_missing_rejected(self, app, seed_admin):
        client = _make_client(app)
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
        )
        assert r.status_code == 403


class TestMe:
    def test_requires_session(self, app):
        client = _make_client(app)
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_returns_user_when_authed(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            headers={"X-CSRF-Token": token},
        )
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "admin@x.com"


class TestLogout:
    def test_logout_revokes(self, app, seed_admin):
        client = _make_client(app)
        token = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            headers={"X-CSRF-Token": token},
        )
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401
