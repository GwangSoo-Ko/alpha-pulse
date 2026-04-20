"""Backtest 실행 API 테스트 — 백그라운드 태스크는 mock."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.api.backtest import router as bt_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def app(tmp_path):
    bt_db = tmp_path / "backtest.db"
    webapp_db = tmp_path / "webapp.db"
    init_webapp_db(webapp_db)
    BacktestStore(db_path=bt_db)  # 스키마 생성

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
    _app.state.backtest_reader = BacktestReader(db_path=bt_db)
    _app.state.jobs = JobRepository(db_path=webapp_db)
    _app.state.job_runner = JobRunner(job_repo=_app.state.jobs)
    _app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(bt_router)
    _app._bt_db = bt_db

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    return _app


def _make_client(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _csrf(client: TestClient) -> str:
    r = client.get("/api/v1/csrf-token")
    return r.json()["token"]


@pytest.fixture
def client(app):
    c = _make_client(app)
    token = _csrf(c)
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


class TestBacktestRun:
    def test_requires_auth(self, app):
        c = TestClient(app)
        r = c.post("/api/v1/backtest/run", json={"strategy": "momentum"})
        assert r.status_code in (401, 403)

    def test_creates_job(self, app, client, monkeypatch):
        called = {}

        def fake_run(*, progress_callback, **kwargs):
            called["kwargs"] = kwargs
            progress_callback(1, 1, "done")
            return "run_xyz"

        monkeypatch.setattr(
            "alphapulse.webapp.api.backtest.run_backtest_sync", fake_run,
        )

        r = client.post(
            "/api/v1/backtest/run",
            json={
                "strategy": "momentum",
                "start": "20240101", "end": "20241231",
                "capital": 100_000_000, "market": "KOSPI", "top": 20,
            },
        )
        assert r.status_code == 200
        jid = r.json()["job_id"]
        assert len(jid) > 0

    def test_invalid_strategy(self, client):
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "invalid"},
        )
        assert r.status_code == 422  # Pydantic enum 검증

    def test_capital_out_of_range(self, client):
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "momentum", "capital": 500_000},
        )
        assert r.status_code == 422

    def test_top_out_of_range(self, client):
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "momentum", "top": 0},
        )
        assert r.status_code == 422

    def test_default_values_accepted(self, app, client, monkeypatch):
        """strategy 만 지정해도 기본값으로 요청 성공."""
        monkeypatch.setattr(
            "alphapulse.webapp.api.backtest.run_backtest_sync",
            lambda *, progress_callback, **kw: "run_default",
        )
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "value"},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_job_stored_in_db(self, app, client, monkeypatch):
        """POST /run 후 jobs DB에 레코드가 생성됐는지 확인."""
        monkeypatch.setattr(
            "alphapulse.webapp.api.backtest.run_backtest_sync",
            lambda *, progress_callback, **kw: "run_stored",
        )
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "quality_momentum"},
        )
        assert r.status_code == 200
        jid = r.json()["job_id"]
        job = app.state.jobs.get(jid)
        assert job is not None
        assert job.kind == "backtest"
