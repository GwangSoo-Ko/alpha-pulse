"""Risk API 테스트 — mock 기반."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.risk import router as risk_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import SnapshotDTO
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.risk_cache import RiskReportCacheRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


def _make_app(webapp_db, risk_reader):
    """테스트용 FastAPI 앱을 생성한다."""
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    _app = FastAPI()
    _app.state.config = cfg
    _app.state.users = UserRepository(db_path=webapp_db)
    _app.state.sessions = SessionRepository(db_path=webapp_db)
    _app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    _app.state.risk_reader = risk_reader
    _app.state.audit = MagicMock()

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(risk_router)
    return _app


def _make_client(app, email: str, password: str = "long-enough-pw!"):
    """로그인된 TestClient를 반환한다."""
    c = TestClient(app, base_url="https://testserver")
    t = c.get("/api/v1/csrf-token").json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": t},
    )
    c.headers.update({"X-CSRF-Token": t})
    return c


@pytest.fixture
def risk_reader(webapp_db):
    mock_portfolio = MagicMock()
    mock_portfolio.get_latest.return_value = SnapshotDTO(
        date="20260420", cash=10_000_000, total_value=100_000_000,
        daily_return=0.5, cumulative_return=2.0, drawdown=-1.0,
        positions=[],
    )
    cache = RiskReportCacheRepository(db_path=webapp_db)
    return RiskReader(portfolio_reader=mock_portfolio, cache=cache)


@pytest.fixture
def app(webapp_db, risk_reader):
    _app = _make_app(webapp_db, risk_reader)
    _app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    return _app


@pytest.fixture
def client(app):
    return _make_client(app, email="a@x.com")


class TestRiskAPI:
    def test_report(self, client):
        r = client.get("/api/v1/risk/report?mode=paper")
        assert r.status_code == 200
        body = r.json()
        assert "report" in body
        assert "stress" in body

    def test_stress(self, client):
        r = client.get("/api/v1/risk/stress?mode=paper")
        assert r.status_code == 200
        body = r.json()
        assert "report" in body
        assert "stress" in body

    def test_limits(self, client):
        r = client.get("/api/v1/risk/limits")
        assert r.status_code == 200
        body = r.json()
        assert body["max_position_weight"] > 0

    def test_custom_stress(self, client):
        r = client.post(
            "/api/v1/risk/stress/custom",
            json={"mode": "paper", "shocks": {"KOSPI": -0.1}},
        )
        assert r.status_code == 200
        assert "results" in r.json()

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/risk/report"
        )
        assert r.status_code == 401

    def test_report_cached_second_call(self, client):
        # 첫 번째 호출 — 계산 후 캐시 저장
        r1 = client.get("/api/v1/risk/report?mode=paper")
        assert r1.status_code == 200
        assert r1.json()["cached"] is False
        # 두 번째 호출 — 캐시 히트
        r2 = client.get("/api/v1/risk/report?mode=paper")
        assert r2.status_code == 200
        assert r2.json()["cached"] is True

    def test_report_none_when_no_snapshot(self, webapp_db):
        """포트폴리오 스냅샷이 없으면 None 반환."""
        mock_portfolio = MagicMock()
        mock_portfolio.get_latest.return_value = None
        cache = RiskReportCacheRepository(db_path=webapp_db)
        reader = RiskReader(portfolio_reader=mock_portfolio, cache=cache)

        inner_app = _make_app(webapp_db, reader)
        inner_app.state.users.create(
            email="b@x.com",
            password_hash=hash_password("long-enough-pw!"),
            role="admin",
        )
        c = _make_client(inner_app, email="b@x.com")
        r = c.get("/api/v1/risk/report?mode=paper")
        assert r.status_code == 200
        assert r.json() is None

    def test_custom_stress_no_snapshot(self, webapp_db):
        """포트폴리오 없으면 custom stress 결과는 빈 dict."""
        mock_portfolio = MagicMock()
        mock_portfolio.get_latest.return_value = None
        cache = RiskReportCacheRepository(db_path=webapp_db)
        reader = RiskReader(portfolio_reader=mock_portfolio, cache=cache)

        inner_app = _make_app(webapp_db, reader)
        inner_app.state.users.create(
            email="c@x.com",
            password_hash=hash_password("long-enough-pw!"),
            role="admin",
        )
        c = _make_client(inner_app, email="c@x.com")
        r = c.post(
            "/api/v1/risk/stress/custom",
            json={"mode": "paper", "shocks": {"KOSPI": -0.1}},
        )
        assert r.status_code == 200
        assert r.json()["results"] == {}
