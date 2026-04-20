"""FastAPI main 통합 테스트."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    # BacktestStore(db_path) を事前に作成して空DBを用意
    from alphapulse.trading.backtest.store import BacktestStore

    BacktestStore(db_path=tmp_path / "backtest.db")
    # Config.DATA_DIR는 __init__에서 인스턴스 속성으로 설정되므로
    # class-level monkeypatch로는 오버라이드 불가. backtest_db_path를 create_app()에 직접 전달한다.
    return tmp_path


# 테스트 헬퍼: backtest_db 경로를 tmp_path로 교체하기 위한 팩토리
def _make_client(tmp_path: Path):
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=tmp_path / "backtest.db")
    return TestClient(app)


def test_app_starts_and_healthchecks(env: Path):
    client = _make_client(env)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_app_has_all_routers(env: Path):
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    paths = {r.path for r in app.routes}
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/backtest/runs" in paths
    assert "/api/v1/jobs/{job_id}" in paths


def test_startup_recovers_orphans(env: Path):
    """running 상태인 job이 있으면 시작 시 failed로 변환."""
    from alphapulse.webapp.store.jobs import JobRepository
    from alphapulse.webapp.store.webapp_db import init_webapp_db

    db = env / "webapp.db"
    init_webapp_db(db)
    jobs = JobRepository(db_path=db)
    jid = str(uuid.uuid4())
    jobs.create(job_id=jid, kind="backtest", params={}, user_id=1)
    jobs.update_status(jid, "running", started_at=time.time())

    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    client = TestClient(app)
    with client:  # lifespan 실행
        pass
    assert jobs.get(jid).status == "failed"
