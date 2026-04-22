"""Dashboard home API — aggregation."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.dashboard import _build_briefing_hero, _select_top3_indicators
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


class TestSelectTop3Indicators:
    def test_returns_empty_when_no_keys(self):
        assert _select_top3_indicators({}) == []

    def test_returns_empty_when_indicators_and_descriptions_missing(self):
        assert _select_top3_indicators({"score": 50, "signal": "positive"}) == []

    def test_picks_top3_by_abs_score_from_indicators(self):
        pulse = {
            "indicators": {
                "RSI": {"score": 80},
                "MA": {"score": -30},
                "VIX": {"score": 60},
                "VOL": {"score": 10},
                "FX": {"score": -70},
            }
        }
        result = _select_top3_indicators(pulse)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["RSI", "FX", "VIX"]

    def test_direction_and_sentiment_signs(self):
        pulse = {"indicators": {"A": {"score": 80}, "B": {"score": -40}, "C": {"score": 0}}}
        result = _select_top3_indicators(pulse)
        by_name = {r["name"]: r for r in result}
        assert by_name["A"]["direction"] == "up"
        assert by_name["A"]["sentiment"] == "positive"
        assert by_name["B"]["direction"] == "down"
        assert by_name["B"]["sentiment"] == "negative"
        assert by_name["C"]["direction"] == "neutral"
        assert by_name["C"]["sentiment"] == "neutral"

    def test_indicator_descriptions_preferred_over_indicators(self):
        pulse = {
            "indicator_descriptions": {"DESC_A": {"score": 90}},
            "indicators": {"IND_A": {"score": 50}, "IND_B": {"score": 60}},
        }
        result = _select_top3_indicators(pulse)
        assert [r["name"] for r in result] == ["DESC_A"]

    def test_accepts_scalar_score_value(self):
        pulse = {"indicators": {"X": 70, "Y": -20, "Z": 55}}
        result = _select_top3_indicators(pulse)
        assert [r["name"] for r in result] == ["X", "Z", "Y"]

    def test_returns_empty_when_source_is_not_dict(self):
        # "indicators" 키가 있지만 dict 가 아닐 때 안전하게 빈 리스트
        assert _select_top3_indicators({"indicators": "not-a-dict"}) == []

    def test_stable_order_on_ties_insertion_order(self):
        # 절대값 동률 시 dict 삽입 순서로 결정됨 (명시적 계약)
        pulse = {"indicators": {"A": 50, "B": -50, "C": 50}}
        result = _select_top3_indicators(pulse)
        assert [r["name"] for r in result] == ["A", "B", "C"]


class TestBuildBriefingHero:
    def test_returns_none_when_store_empty(self):
        store = MagicMock()
        store.get_recent.return_value = []
        assert _build_briefing_hero(store) is None

    @patch("alphapulse.webapp.api.dashboard.Config.get_today_str", return_value="20260422")
    def test_is_today_true_when_date_matches(self, _today):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1766839200,
            "payload": {
                "pulse_result": {"score": 62.5, "signal": "positive", "indicators": {"RSI": 80}},
                "daily_result_msg": "코스피 강세 흐름.\n외국인 순매수 유입.",
                "commentary": "상세 해설",
            },
        }]
        result = _build_briefing_hero(store)
        assert result is not None
        assert result.is_today is True
        assert result.date == "20260422"
        assert result.score == 62.5
        assert result.signal == "positive"
        assert result.summary_line == "코스피 강세 흐름."
        assert result.created_at == 1766839200
        assert len(result.highlight_badges) == 1
        assert result.highlight_badges[0].name == "RSI"

    @patch("alphapulse.webapp.api.dashboard.Config.get_today_str", return_value="20260422")
    def test_is_today_false_when_yesterday(self, _today):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260421",
            "created_at": 1766752800,
            "payload": {
                "pulse_result": {"score": 40.0, "signal": "neutral"},
                "daily_result_msg": "전일 혼조.",
                "commentary": None,
            },
        }]
        result = _build_briefing_hero(store)
        assert result is not None
        assert result.is_today is False
        assert result.summary_line == "전일 혼조."

    def test_summary_line_falls_back_to_commentary(self):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1,
            "payload": {
                "pulse_result": {"score": 0, "signal": "neutral"},
                "daily_result_msg": "",
                "commentary": "첫 문장. 두 번째 문장.",
            },
        }]
        result = _build_briefing_hero(store)
        assert result.summary_line == "첫 문장."

    def test_summary_line_empty_when_both_missing(self):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1,
            "payload": {"pulse_result": {"score": 0, "signal": "neutral"}},
        }]
        result = _build_briefing_hero(store)
        assert result.summary_line == ""
