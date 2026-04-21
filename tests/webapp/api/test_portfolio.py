"""Portfolio API 테스트."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.trading.portfolio.store import PortfolioStore
from alphapulse.webapp.api.portfolio import router as portfolio_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    portfolio_db = tmp_path / "portfolio.db"
    PortfolioStore(db_path=str(portfolio_db))  # schema init

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
    _app.state.portfolio_reader = PortfolioReader(db_path=portfolio_db)
    _app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(portfolio_router)
    _app._portfolio_db = portfolio_db
    return _app


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


def _seed_snapshot(db_path, date: str, total_value: float, mode: str = "paper") -> None:
    """PortfolioStore.snapshots 테이블에 직접 삽입."""
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO snapshots "
            "(date, mode, run_id, cash, total_value, positions, "
            "daily_return, cumulative_return, drawdown) "
            "VALUES (?, ?, '', ?, ?, '[]', 0.5, 2.0, 0.0)",
            (date, mode, total_value * 0.1, total_value),
        )


def _seed_attribution(db_path, date: str, mode: str = "paper") -> None:
    """PortfolioStore.attribution 테이블에 직접 삽입."""
    import json
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO attribution "
            "(date, mode, run_id, strategy_returns, factor_returns, sector_returns) "
            "VALUES (?, ?, '', ?, ?, ?)",
            (
                date,
                mode,
                json.dumps({"momentum": 1.2}),
                json.dumps({"value": 0.5}),
                json.dumps({"tech": 0.8}),
            ),
        )


class TestPortfolio:
    def test_get_none_when_empty(self, client):
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200
        assert r.json() is None

    def test_get_latest(self, app, client):
        _seed_snapshot(app._portfolio_db, "20260420", 100_000_000)
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["total_value"] == 100_000_000

    def test_mode_filter(self, app, client):
        _seed_snapshot(app._portfolio_db, "20260420", 100_000_000, mode="paper")
        _seed_snapshot(app._portfolio_db, "20260420", 200_000_000, mode="live")
        r1 = client.get("/api/v1/portfolio?mode=paper")
        r2 = client.get("/api/v1/portfolio?mode=live")
        assert r1.json()["total_value"] == 100_000_000
        assert r2.json()["total_value"] == 200_000_000

    def test_history(self, app, client):
        for i, d in enumerate(["20260418", "20260419", "20260420"]):
            _seed_snapshot(app._portfolio_db, d, 100_000_000 + i * 1_000_000)
        r = client.get("/api/v1/portfolio/history?days=30")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    def test_history_items_have_fields(self, app, client):
        _seed_snapshot(app._portfolio_db, "20260420", 50_000_000)
        r = client.get("/api/v1/portfolio/history?days=30")
        assert r.status_code == 200
        item = r.json()["items"][0]
        for field in ("date", "cash", "total_value", "daily_return", "cumulative_return", "drawdown", "positions"):
            assert field in item

    def test_attribution_none_when_empty(self, client):
        r = client.get("/api/v1/portfolio/attribution?date=20260420")
        assert r.status_code == 200
        assert r.json() is None

    def test_attribution_returns_data(self, app, client):
        _seed_attribution(app._portfolio_db, "20260420")
        r = client.get("/api/v1/portfolio/attribution?date=20260420")
        assert r.status_code == 200
        body = r.json()
        assert body["date"] == "20260420"
        assert body["strategy_returns"] == {"momentum": 1.2}
        assert body["factor_returns"] == {"value": 0.5}
        assert body["sector_returns"] == {"tech": 0.8}

    def test_attribution_mode_filter(self, app, client):
        _seed_attribution(app._portfolio_db, "20260420", mode="paper")
        r = client.get("/api/v1/portfolio/attribution?date=20260420&mode=live")
        assert r.json() is None

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get("/api/v1/portfolio")
        assert r.status_code == 401

    def test_history_days_validation(self, client):
        r = client.get("/api/v1/portfolio/history?days=0")
        assert r.status_code == 422

    def test_history_days_max(self, client):
        r = client.get("/api/v1/portfolio/history?days=366")
        assert r.status_code == 422
