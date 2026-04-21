"""Dashboard home API — aggregation."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.dashboard import router as dash_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import SnapshotDTO
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):  # noqa: PLR0915
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

    # Readers mocks
    portfolio = MagicMock()
    portfolio.get_latest.return_value = SnapshotDTO(
        date="20260420", cash=10_000_000, total_value=100_000_000,
        daily_return=0.5, cumulative_return=2.0, drawdown=-1.0,
        positions=[],
    )
    portfolio.get_history.return_value = []
    app.state.portfolio_reader = portfolio

    risk = MagicMock()
    risk.get_report.return_value = {
        "report": {"var_95": -2.5}, "stress": {}, "cached": False,
    }
    app.state.risk_reader = risk

    data = MagicMock()
    data.get_status.return_value = []
    data.detect_gaps.return_value = []
    app.state.data_status_reader = data

    audit = MagicMock()
    audit.query.return_value = {
        "items": [], "page": 1, "size": 10, "total": 0,
    }
    app.state.audit_reader = audit

    bt = MagicMock()
    listing = MagicMock()
    listing.items = []
    bt.list_runs.return_value = listing
    app.state.backtest_reader = bt

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
    app.include_router(dash_router)
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


class TestHome:
    def test_aggregates(self, client):
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["portfolio"]["total_value"] == 100_000_000
        assert body["risk"]["report"]["var_95"] == -2.5
        assert "tables" in body["data_status"]

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/dashboard/home",
        )
        assert r.status_code == 401
