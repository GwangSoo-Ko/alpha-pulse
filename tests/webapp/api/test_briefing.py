"""Briefing API — GET endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.webapp.api.briefing import router as briefing_router
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
def briefing_store(tmp_path):
    return BriefingStore(db_path=tmp_path / "briefings.db")


@pytest.fixture
def app(webapp_db, briefing_store):
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
    app.state.briefing_store = briefing_store
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
    app.include_router(briefing_router)
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


def _minimal_payload(date: str, score: float = 10.0, signal: str = "neutral",
                     synthesis: str | None = "syn", commentary: str | None = "comm") -> dict:
    return {
        "pulse_result": {"date": date, "score": score, "signal": signal,
                         "indicator_scores": {}, "details": {}},
        "content_summaries": [],
        "commentary": commentary,
        "synthesis": synthesis,
        "quant_msg": "q",
        "synth_msg": "s",
        "feedback_context": None,
        "daily_result_msg": "",
        "news": {"articles": []},
        "post_analysis": None,
        "generated_at": "2026-04-21T10:00:00",
    }


def test_list_empty(client):
    r = client.get("/api/v1/briefings")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["size"] == 20


def test_list_returns_items(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", score=42.0))
    briefing_store.save("20260420", _minimal_payload("20260420", score=10.0))
    r = client.get("/api/v1/briefings")
    body = r.json()
    assert body["total"] == 2
    assert [i["date"] for i in body["items"]] == ["20260421", "20260420"]
    assert body["items"][0]["score"] == 42.0
    assert body["items"][0]["has_synthesis"] is True


def test_list_has_synthesis_false_when_null(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", synthesis=None))
    r = client.get("/api/v1/briefings")
    assert r.json()["items"][0]["has_synthesis"] is False


def test_latest_returns_null_when_empty(client):
    r = client.get("/api/v1/briefings/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_latest_returns_most_recent(client, briefing_store):
    briefing_store.save("20260419", _minimal_payload("20260419"))
    briefing_store.save("20260421", _minimal_payload("20260421", score=50.0))
    r = client.get("/api/v1/briefings/latest")
    body = r.json()
    assert body["date"] == "20260421"
    assert body["pulse_result"]["score"] == 50.0


def test_detail_returns_full_payload(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", score=42.0,
                                                     synthesis="종합", commentary="해설"))
    r = client.get("/api/v1/briefings/20260421")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260421"
    assert body["synthesis"] == "종합"
    assert body["commentary"] == "해설"
    assert body["pulse_result"]["score"] == 42.0


def test_detail_404_when_missing(client):
    r = client.get("/api/v1/briefings/19000101")
    assert r.status_code == 404


def test_detail_rejects_invalid_date_format(client):
    r = client.get("/api/v1/briefings/not-a-date")
    assert r.status_code == 422


def test_list_size_out_of_range(client):
    r = client.get("/api/v1/briefings?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/briefings?size=500")
    assert r.status_code == 422


def test_list_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/briefings")
    assert r.status_code == 401


def test_detail_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/briefings/20260421")
    assert r.status_code == 401
