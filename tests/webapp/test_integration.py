"""통합 테스트: 로그인 → 백테스트 실행 → 결과 조회."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")

    # data dir 세팅 — Config.DATA_DIR는 인스턴스 속성이므로
    # class-level monkeypatch 불가. backtest_db_path를 create_app()에 직접 전달.
    from alphapulse.trading.backtest.store import BacktestStore

    BacktestStore(db_path=tmp_path / "backtest.db")  # 스키마 생성
    return tmp_path


@pytest.fixture
def app(env: Path):
    from alphapulse.webapp.auth.security import hash_password
    from alphapulse.webapp.main import create_app

    _app = create_app(backtest_db_path=env / "backtest.db")
    # seed admin user
    _app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    return _app


def _csrf(client: TestClient) -> str:
    """CSRF 토큰 획득. 미들웨어가 ap_csrf 쿠키를 client에 자동 설정한다."""
    return client.get("/api/v1/csrf-token").json()["token"]


def test_full_backtest_flow(app, env: Path, monkeypatch: pytest.MonkeyPatch):
    """로그인 → 실행 → 진행률 polling → 완료 조회."""
    from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
    from alphapulse.trading.backtest.store import BacktestStore
    from alphapulse.trading.core.cost_model import CostModel

    bt_store = BacktestStore(db_path=env / "backtest.db")

    def fake_run(*, progress_callback, **kwargs):
        for i in range(3):
            progress_callback(i, 3, f"day {i}")
        result = BacktestResult(
            snapshots=[],
            trades=[],
            metrics={"total_return": 12.3},
            config=BacktestConfig(
                initial_capital=100_000_000,
                start_date="20240101",
                end_date="20241231",
                cost_model=CostModel(slippage_model="none"),
            ),
        )
        return bt_store.save_run(
            result, name="integration-test", strategies=["momentum"],
        )

    monkeypatch.setattr(
        "alphapulse.webapp.api.backtest.run_backtest_sync", fake_run,
    )

    with TestClient(app, base_url="https://testserver") as client:
        token = _csrf(client)
        hdrs = {"X-CSRF-Token": token}

        # 1. 로그인
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            headers=hdrs,
        )
        assert r.status_code == 200

        # 2. 백테스트 실행
        r = client.post(
            "/api/v1/backtest/run",
            json={
                "strategy": "momentum",
                "start": "20240101",
                "end": "20241231",
                "capital": 100_000_000,
                "market": "KOSPI",
                "top": 20,
            },
            headers=hdrs,
        )
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        # 3. 진행률 polling (background task 동기 대기)
        j = {}
        for _ in range(50):
            j = client.get(f"/api/v1/jobs/{job_id}").json()
            if j["status"] in {"done", "failed"}:
                break
            time.sleep(0.05)
        assert j["status"] == "done"
        run_id = j["result_ref"]

        # 4. 결과 조회
        r = client.get(f"/api/v1/backtest/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["metrics"]["total_return"] == 12.3

        # 5. 목록에 나타남
        r = client.get("/api/v1/backtest/runs")
        assert r.json()["total"] == 1
