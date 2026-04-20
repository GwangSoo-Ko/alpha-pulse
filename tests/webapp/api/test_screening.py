"""Screening API 테스트."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.screening import router as screening_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.screening import ScreeningRepository
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
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.state.job_runner = JobRunner(job_repo=app.state.jobs)
    app.state.screening_repo = ScreeningRepository(db_path=webapp_db)
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
    app.include_router(jobs_router)
    app.include_router(screening_router)
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


class TestScreeningAPI:
    def test_list_empty(self, client):
        r = client.get("/api/v1/screening/runs")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_run_creates_job(self, app, client, monkeypatch):
        captured = {}

        def fake_run(*, progress_callback, **kwargs):
            captured.update(kwargs)
            progress_callback(1, 1, "done")
            return app.state.screening_repo.save(
                name=kwargs.get("name") or "t",
                market=kwargs["market"],
                strategy=kwargs["strategy"],
                factor_weights=kwargs["factor_weights"],
                top_n=kwargs["top_n"],
                market_context={}, results=[],
                user_id=kwargs["user_id"],
            )

        monkeypatch.setattr(
            "alphapulse.webapp.api.screening.run_screening_sync", fake_run,
        )
        r = client.post(
            "/api/v1/screening/run",
            json={
                "market": "KOSPI", "strategy": "momentum",
                "factor_weights": {"momentum": 1.0},
                "top_n": 10, "name": "test",
            },
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_invalid_market(self, client):
        r = client.post(
            "/api/v1/screening/run",
            json={"market": "INVALID", "strategy": "momentum"},
        )
        assert r.status_code == 422

    def test_delete_requires_admin(self, app, client):
        rid = app.state.screening_repo.save(
            name="t", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        r = client.delete(f"/api/v1/screening/runs/{rid}")
        assert r.status_code == 200

    def test_get_run(self, app, client):
        rid = app.state.screening_repo.save(
            name="t", market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 1.0}, top_n=10,
            market_context={}, results=[{"code": "005930"}], user_id=1,
        )
        r = client.get(f"/api/v1/screening/runs/{rid}")
        assert r.status_code == 200
        assert r.json()["market"] == "KOSPI"

    def test_get_run_not_found(self, client):
        r = client.get("/api/v1/screening/runs/nonexistent-id")
        assert r.status_code == 404

    def test_delete_run_not_found(self, client):
        r = client.delete("/api/v1/screening/runs/nonexistent-id")
        assert r.status_code == 404

    def test_list_pagination(self, app, client):
        for i in range(5):
            app.state.screening_repo.save(
                name=f"run{i}", market="KOSPI", strategy="momentum",
                factor_weights={}, top_n=10, market_context={},
                results=[], user_id=1,
            )
        r = client.get("/api/v1/screening/runs?page=1&size=3")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 3
        assert body["page"] == 1
        assert body["size"] == 3

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/screening/runs"
        )
        assert r.status_code == 401

    def test_get_run_detail_fields(self, app, client):
        rid = app.state.screening_repo.save(
            name="detail-test", market="KOSDAQ", strategy="value",
            factor_weights={"value": 0.8, "momentum": 0.2}, top_n=15,
            market_context={"score": 5}, results=[{"code": "035720"}],
            user_id=1,
        )
        r = client.get(f"/api/v1/screening/runs/{rid}")
        assert r.status_code == 200
        body = r.json()
        assert body["run_id"] == rid
        assert body["name"] == "detail-test"
        assert body["market"] == "KOSDAQ"
        assert body["strategy"] == "value"
        assert body["top_n"] == 15
        assert body["factor_weights"] == {"value": 0.8, "momentum": 0.2}
        assert body["results"] == [{"code": "035720"}]
        assert body["market_context"] == {"score": 5}
        assert "created_at" in body
