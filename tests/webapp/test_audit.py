"""감사 로그 wiring 테스트."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.core.audit import AuditLogger
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
def app_with_audit(tmp_path):
    """AuditLogger 가 state 에 연결된 앱 fixture."""
    bt_db = tmp_path / "backtest.db"
    webapp_db = tmp_path / "webapp.db"
    audit_db = tmp_path / "audit.db"
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
    _app.state.audit = AuditLogger(db_path=audit_db)
    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(bt_router)

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    return _app


@pytest.fixture
def seed_admin(app_with_audit):
    app_with_audit.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    return app_with_audit


def _make_client(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _csrf(client: TestClient) -> str:
    r = client.get("/api/v1/csrf-token")
    return r.json()["token"]


def _audit_actions(app) -> list[str]:
    """audit.db 에서 webapp.% 이벤트 유형을 조회한다."""
    audit_db = app.state.audit.db_path
    with sqlite3.connect(audit_db) as conn:
        rows = conn.execute(
            "SELECT event_type FROM audit_log WHERE event_type LIKE 'webapp.%'"
        ).fetchall()
    return [r[0] for r in rows]


class TestLoginAudit:
    def test_login_success_audited(self, app_with_audit, seed_admin):
        """로그인 성공 시 audit.db에 webapp.login_success 이벤트가 기록된다."""
        client = _make_client(app_with_audit)
        t = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        assert r.status_code == 200
        actions = _audit_actions(app_with_audit)
        assert "webapp.login_success" in actions

    def test_login_failed_audited(self, app_with_audit, seed_admin):
        """로그인 실패 시 audit.db에 webapp.login_failed 이벤트가 기록된다."""
        client = _make_client(app_with_audit)
        t = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "wrong-password!"},
            headers={"X-CSRF-Token": t},
        )
        assert r.status_code == 401
        actions = _audit_actions(app_with_audit)
        assert "webapp.login_failed" in actions

    def test_logout_audited(self, app_with_audit, seed_admin):
        """로그아웃 시 audit.db에 webapp.logout 이벤트가 기록된다."""
        client = _make_client(app_with_audit)
        t = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": t})
        actions = _audit_actions(app_with_audit)
        assert "webapp.logout" in actions


class TestBacktestAudit:
    def test_backtest_run_audited(self, app_with_audit, seed_admin, monkeypatch):
        """백테스트 실행 시 audit.db에 webapp.backtest_run 이벤트가 기록된다."""
        monkeypatch.setattr(
            "alphapulse.webapp.api.backtest.run_backtest_sync",
            lambda *, progress_callback, **kw: "run_audited",
        )
        client = _make_client(app_with_audit)
        t = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "momentum"},
            headers={"X-CSRF-Token": t},
        )
        assert r.status_code == 200
        actions = _audit_actions(app_with_audit)
        assert "webapp.backtest_run" in actions

    def test_backtest_delete_audited(self, app_with_audit, seed_admin):
        """백테스트 삭제 시 audit.db에 webapp.backtest_delete 이벤트가 기록된다."""
        import json
        import sqlite3
        import time

        bt_db = app_with_audit.state.backtest_reader.db_path
        with sqlite3.connect(bt_db) as conn:
            conn.execute(
                """INSERT INTO runs (run_id, name, strategies, allocations,
                    start_date, end_date, initial_capital, final_value,
                    benchmark, params, metrics, created_at)
                VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                    1e8, 1.05e8, 'KOSPI', '{}', ?, ?)""",
                ("run-del-001", "delete-test", json.dumps({}), time.time()),
            )

        client = _make_client(app_with_audit)
        t = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        r = client.delete(
            "/api/v1/backtest/runs/run-del-001",
            headers={"X-CSRF-Token": t},
        )
        assert r.status_code == 200
        actions = _audit_actions(app_with_audit)
        assert "webapp.backtest_delete" in actions
