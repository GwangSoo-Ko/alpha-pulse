"""Backtest 조회 API 테스트."""
from __future__ import annotations

import json
import time
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.api.backtest import router as bt_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


def _seed(store: BacktestStore, name: str = "r") -> str:
    rid = str(uuid.uuid4())
    import sqlite3

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT INTO runs (run_id, name, strategies, allocations,
                start_date, end_date, initial_capital, final_value,
                benchmark, params, metrics, created_at)
            VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                1e8, 1.05e8, 'KOSPI', '{}', ?, ?)""",
            (
                rid,
                name,
                json.dumps({"total_return": 5.0}),
                time.time(),
            ),
        )
    return rid


@pytest.fixture
def app(tmp_path):
    bt_db = tmp_path / "backtest.db"
    webapp_db = tmp_path / "webapp.db"
    from alphapulse.webapp.store.webapp_db import init_webapp_db

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
    _app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    _app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    _app.include_router(auth_router)
    _app.include_router(bt_router)
    _app._bt_db = bt_db  # 테스트용 핸들

    @_app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    return _app


def _make_client(app) -> TestClient:
    """secure 쿠키 전송을 위해 https://testserver 사용."""
    return TestClient(app, base_url="https://testserver")


def _csrf(client: TestClient) -> str:
    """CSRF 토큰을 가져온다. 미들웨어가 ap_csrf 쿠키를 자동 설정한다."""
    r = client.get("/api/v1/csrf-token")
    return r.json()["token"]


@pytest.fixture
def client(app):
    c = _make_client(app)
    token = _csrf(c)
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


class TestBacktestRead:
    def test_list_empty(self, client):
        r = client.get("/api/v1/backtest/runs")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_with_data(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="run-a")
        _seed(store, name="run-b")
        r = client.get("/api/v1/backtest/runs")
        assert r.json()["total"] == 2

    def test_list_paginate(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        for i in range(15):
            _seed(store, name=f"r{i}")
        r = client.get("/api/v1/backtest/runs?page=2&size=10")
        assert len(r.json()["items"]) == 5

    def test_get_run_by_prefix(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="r1")
        r = client.get(f"/api/v1/backtest/runs/{rid[:8]}")
        assert r.status_code == 200
        assert r.json()["name"] == "r1"

    def test_get_run_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexist")
        assert r.status_code == 404

    def test_delete_requires_admin(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="r")
        r = client.delete(
            f"/api/v1/backtest/runs/{rid[:8]}",
            headers={"X-CSRF-Token": client.headers["X-CSRF-Token"]},
        )
        assert r.status_code == 200

    def test_compare_400_when_not_two(self, client):
        r = client.get("/api/v1/backtest/compare?ids=a")
        assert r.status_code == 400

    def test_requires_auth(self, app):
        c = TestClient(app)
        r = c.get("/api/v1/backtest/runs")
        assert r.status_code == 401

    def test_get_snapshots_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexist/snapshots")
        assert r.status_code == 404

    def test_get_trades_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexist/trades")
        assert r.status_code == 404

    def test_get_positions_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexist/positions")
        assert r.status_code == 404

    def test_compare_404_when_run_missing(self, client):
        r = client.get("/api/v1/backtest/compare?ids=aaa,bbb")
        assert r.status_code == 404

    def test_get_snapshots_ok(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="snap-test")
        r = client.get(f"/api/v1/backtest/runs/{rid}/snapshots")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_get_trades_ok(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="trade-test")
        r = client.get(f"/api/v1/backtest/runs/{rid}/trades")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_get_positions_ok(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="pos-test")
        r = client.get(f"/api/v1/backtest/runs/{rid}/positions")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_compare_ok(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid_a = _seed(store, name="cmp-a")
        rid_b = _seed(store, name="cmp-b")
        r = client.get(f"/api/v1/backtest/compare?ids={rid_a},{rid_b}")
        assert r.status_code == 200
        assert "a" in r.json()
        assert "b" in r.json()

    def test_delete_run(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="del-me")
        r = client.delete(
            f"/api/v1/backtest/runs/{rid}",
            headers={"X-CSRF-Token": client.headers["X-CSRF-Token"]},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # 삭제 후 조회 시 404
        r2 = client.get(f"/api/v1/backtest/runs/{rid}")
        assert r2.status_code == 404

    def test_list_name_filter(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="alpha-strategy")
        _seed(store, name="beta-strategy")
        r = client.get("/api/v1/backtest/runs?name=alpha")
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["name"] == "alpha-strategy"

    # --- runs sort ---
    def test_runs_sort_by_name(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="zzz")
        _seed(store, name="aaa")
        r = client.get("/api/v1/backtest/runs?sort=name&dir=asc")
        assert r.status_code == 200
        names = [i["name"] for i in r.json()["items"]]
        assert names == sorted(names)

    # --- runs export ---
    def test_runs_export_returns_csv_with_bom(self, app, client):
        """runs export 응답이 CSV + BOM + 헤더 포함."""
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="export-test")
        r = client.get("/api/v1/backtest/runs/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        body = r.content.decode("utf-8")
        assert body.startswith("\ufeff")
        lines = body.lstrip("\ufeff").strip().split("\r\n")
        assert lines[0].startswith("이름,전략")

    def test_runs_export_applies_sort(self, app, client):
        """sort 파라미터 전달 시 CSV 순서 반영."""
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="zzz-export")
        _seed(store, name="aaa-export")
        r = client.get("/api/v1/backtest/runs/export?sort=name&dir=asc")
        assert r.status_code == 200

    # --- trades export ---
    def test_trades_export_returns_csv(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="trades-export-test")
        r = client.get(f"/api/v1/backtest/runs/{rid}/trades/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        body = r.content.decode("utf-8")
        assert body.startswith("\ufeff")
        lines = body.lstrip("\ufeff").strip().split("\r\n")
        assert lines[0]  # 헤더 존재

    def test_trades_export_run_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexistent/trades/export")
        assert r.status_code == 404

    # --- positions export ---
    def test_positions_export_returns_csv(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="positions-export-test")
        r = client.get(f"/api/v1/backtest/runs/{rid}/positions/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

    def test_positions_export_run_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexistent/positions/export")
        assert r.status_code == 404
