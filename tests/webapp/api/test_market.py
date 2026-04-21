"""Market Pulse API 테스트 — GET endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.core.storage import PulseHistory
from alphapulse.webapp.api.market import router as market_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def pulse_history(tmp_path):
    return PulseHistory(db_path=tmp_path / "history.db")


@pytest.fixture
def app(webapp_db, pulse_history):
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
    app.state.pulse_history = pulse_history
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(market_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/csrf-token")
    token = r.json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"x-csrf-token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


def test_latest_returns_null_when_empty(client):
    r = client.get("/api/v1/market/pulse/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_latest_returns_most_recent(client, pulse_history):
    pulse_history.save(
        "20260419", 10.0, "neutral",
        {"indicator_scores": {"investor_flow": 5}, "period": "daily",
         "indicator_descriptions": {"investor_flow": "외국인 +100억"}},
    )
    pulse_history.save(
        "20260420", 42.0, "moderately_bullish",
        {"indicator_scores": {"investor_flow": 60}, "period": "daily",
         "indicator_descriptions": {"investor_flow": "외국인 +580억"}},
    )
    r = client.get("/api/v1/market/pulse/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260420"
    assert body["score"] == 42.0
    assert body["signal"] == "moderately_bullish"
    assert body["indicator_scores"]["investor_flow"] == 60
    assert body["indicator_descriptions"]["investor_flow"] == "외국인 +580억"
    assert body["period"] == "daily"


def test_history_returns_empty_when_no_data(client):
    r = client.get("/api/v1/market/pulse/history?days=30")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_history_returns_ascending_order(client, pulse_history):
    pulse_history.save("20260420", 42.0, "moderately_bullish",
                       {"indicator_scores": {}, "period": "daily"})
    pulse_history.save("20260418", 10.0, "neutral",
                       {"indicator_scores": {}, "period": "daily"})
    pulse_history.save("20260419", 20.0, "moderately_bullish",
                       {"indicator_scores": {}, "period": "daily"})
    r = client.get("/api/v1/market/pulse/history?days=10")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [x["date"] for x in items] == ["20260418", "20260419", "20260420"]


def test_pulse_detail_returns_404_when_missing(client):
    r = client.get("/api/v1/market/pulse/19000101")
    assert r.status_code == 404


def test_pulse_detail_returns_all_fields(client, pulse_history):
    pulse_history.save(
        "20260420", 42.0, "moderately_bullish",
        {
            "indicator_scores": {"investor_flow": 60, "vkospi": None},
            "indicator_descriptions": {"investor_flow": "외국인 +580억", "vkospi": None},
            "period": "daily",
        },
    )
    r = client.get("/api/v1/market/pulse/20260420")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260420"
    assert body["indicator_scores"]["vkospi"] is None
    assert body["indicator_descriptions"]["vkospi"] is None


def test_pulse_detail_handles_legacy_row_without_descriptions(client, pulse_history):
    """과거 저장분 (indicator_descriptions 키 없음) → null 로 응답."""
    pulse_history.save(
        "20260315", 15.0, "neutral",
        {"indicator_scores": {"investor_flow": 15}, "period": "daily"},
    )
    r = client.get("/api/v1/market/pulse/20260315")
    assert r.status_code == 200
    body = r.json()
    assert body["indicator_descriptions"] == {"investor_flow": None}


def test_latest_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/market/pulse/latest")
    assert r.status_code == 401


def test_history_rejects_days_out_of_range(client):
    r = client.get("/api/v1/market/pulse/history?days=0")
    assert r.status_code == 422
    r = client.get("/api/v1/market/pulse/history?days=500")
    assert r.status_code == 422


def test_pulse_detail_rejects_invalid_date_format(client):
    r = client.get("/api/v1/market/pulse/not-a-date")
    assert r.status_code == 422  # FastAPI path validation


def test_history_and_detail_require_auth(app):
    # base_url=https://testserver for secure cookies (consistency)
    from fastapi.testclient import TestClient
    c = TestClient(app, base_url="https://testserver")
    r1 = c.get("/api/v1/market/pulse/history")
    assert r1.status_code == 401
    r2 = c.get("/api/v1/market/pulse/20260420")
    assert r2.status_code == 401


def test_run_creates_job_and_returns_id(client, monkeypatch):
    """POST /run → BackgroundTasks 로 스케줄, reused=false."""
    called: dict = {}

    async def fake_runner_run(self, job_id, func, **kwargs):
        called["job_id"] = job_id
        called["kwargs"] = kwargs

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is False
    assert "job_id" in body


def test_run_reuses_existing_job(client, app, monkeypatch):
    """같은 date 의 running Job 있으면 그 id 반환, reused=true."""
    # 기존 Job 수동 생성
    app.state.jobs.create(
        job_id="existing-job", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    app.state.jobs.update_status("existing-job", "running")

    async def fake_runner_run(self, job_id, func, **kwargs):
        raise AssertionError("should not be called for reused job")

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "existing-job"
    assert body["reused"] is True


def test_run_with_null_date_resolves_via_helper(client, app, monkeypatch):
    """date=None → _resolve_target_date 호출, 결과가 Job params.date 에 저장."""
    monkeypatch.setattr(
        "alphapulse.webapp.api.market._resolve_target_date",
        lambda d: "20260420",
    )

    async def noop(self, *a, **kw):
        pass

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )

    r = client.post("/api/v1/market/pulse/run", json={})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # DB 에서 직접 params 확인
    saved = app.state.jobs.get(job_id)
    assert saved is not None
    assert saved.params.get("date") == "20260420"


def test_run_audit_log(client, app, monkeypatch):
    """POST /run 시 audit.log 호출."""
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    assert app.state.audit.log.called
    call_args = app.state.audit.log.call_args
    assert call_args.args[0] == "webapp.market.pulse.run"
