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
