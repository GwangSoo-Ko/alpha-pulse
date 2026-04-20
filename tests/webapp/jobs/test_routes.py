"""Jobs 라우트 테스트."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
    from fastapi import Request

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
    _app.state.jobs = JobRepository(db_path=webapp_db)
    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(jobs_router)

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    return _app


def _make_client(app) -> TestClient:
    """secure 쿠키 전송을 위해 https://testserver 사용."""
    return TestClient(app, base_url="https://testserver")


def _csrf(client: TestClient) -> str:
    """CSRF 토큰을 가져온다. 미들웨어가 ap_csrf 쿠키를 자동 설정한다."""
    r = client.get("/api/v1/csrf-token")
    return r.json()["token"]


@pytest.fixture
def authed_client(app):
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    client = _make_client(app)
    token = _csrf(client)
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": token},
    )
    return client


class TestJobsRoute:
    def test_get_404(self, authed_client):
        r = authed_client.get("/api/v1/jobs/none")
        assert r.status_code == 404

    def test_get_ok(self, app, authed_client):
        jid = str(uuid.uuid4())
        app.state.jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        r = authed_client.get(f"/api/v1/jobs/{jid}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_requires_auth(self, app):
        jid = str(uuid.uuid4())
        app.state.jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        r = TestClient(app).get(f"/api/v1/jobs/{jid}")
        assert r.status_code == 401
