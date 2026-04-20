"""Data API 테스트."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.data import router as data_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    import sqlite3

    trading_db = tmp_path / "trading.db"
    with sqlite3.connect(trading_db) as conn:
        conn.execute(
            "CREATE TABLE ohlcv (code TEXT, date TEXT, close REAL)"
        )
        conn.execute(
            "INSERT INTO ohlcv VALUES ('005930', '20260420', 70000)"
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
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.state.job_runner = JobRunner(job_repo=app.state.jobs)
    app.state.data_status_reader = DataStatusReader(trading_db_path=trading_db)
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
    app.include_router(data_router)
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


class TestDataAPI:
    def test_status(self, client):
        r = client.get("/api/v1/data/status")
        assert r.status_code == 200
        assert "tables" in r.json()
        assert "gaps" in r.json()

    def test_status_tables_contain_ohlcv(self, client):
        r = client.get("/api/v1/data/status")
        tables = r.json()["tables"]
        names = [t["name"] for t in tables]
        assert "ohlcv" in names

    def test_status_ohlcv_row_count(self, client):
        r = client.get("/api/v1/data/status")
        tables = {t["name"]: t for t in r.json()["tables"]}
        assert tables["ohlcv"]["row_count"] == 1
        assert tables["ohlcv"]["distinct_codes"] == 1

    def test_status_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/data/status"
        )
        assert r.status_code == 401

    def test_update_creates_job(self, client, monkeypatch):
        def fake(*, progress_callback, **kwargs):
            progress_callback(1, 1, "done")
            return "{}"

        monkeypatch.setattr(
            "alphapulse.webapp.api.data.run_data_update", fake,
        )
        r = client.post(
            "/api/v1/data/update",
            json={"markets": ["KOSPI"]},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_status_gap_days_param(self, client):
        r = client.get("/api/v1/data/status?gap_days=10")
        assert r.status_code == 200
        assert "gaps" in r.json()

    def test_collect_financials_creates_job(self, client, monkeypatch):
        def fake(*, progress_callback, **kwargs):
            progress_callback(1, 1, "done")
            return '{"market": "KOSPI", "status": "ok"}'

        monkeypatch.setattr(
            "alphapulse.webapp.api.data.run_data_collect_financials", fake,
        )
        r = client.post(
            "/api/v1/data/collect-financials",
            json={"market": "KOSPI", "top": 10},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_collect_wisereport_creates_job(self, client, monkeypatch):
        def fake(*, progress_callback, **kwargs):
            progress_callback(1, 1, "done")
            return '{"market": "KOSPI", "collected": 5}'

        monkeypatch.setattr(
            "alphapulse.webapp.api.data.run_data_collect_wisereport", fake,
        )
        r = client.post(
            "/api/v1/data/collect-wisereport",
            json={"market": "KOSPI", "top": 5},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_collect_short_creates_job(self, client, monkeypatch):
        def fake(*, progress_callback, **kwargs):
            progress_callback(1, 1, "done")
            return '{"market": "KOSPI", "queued": 3}'

        monkeypatch.setattr(
            "alphapulse.webapp.api.data.run_data_collect_short", fake,
        )
        r = client.post(
            "/api/v1/data/collect-short",
            json={"market": "KOSPI", "top": 3},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_no_collect_all_endpoint(self, client):
        r = client.post("/api/v1/data/collect_all", json={})
        assert r.status_code == 404

    def test_no_collect_all_endpoint_hyphen(self, client):
        r = client.post("/api/v1/data/collect-all", json={})
        assert r.status_code == 404
