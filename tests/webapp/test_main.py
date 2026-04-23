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
    # 외부 shell 또는 .env 의 WEBAPP_ENCRYPT_KEY 가 누수되지 않도록 빈 문자열로 고정.
    # load_dotenv(override=False) 는 이미 설정된 env 를 덮어쓰지 않으므로, 빈 문자열이
    # 최종값이 되어 test_settings_router_absent_without_encrypt_key 가 정상 통과.
    # 필요 시 개별 테스트가 setenv 로 유효한 키를 덮어씀.
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", "")
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
    # Phase 1 routers
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/backtest/runs" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    # Phase 2 routers
    assert "/api/v1/portfolio" in paths
    assert "/api/v1/risk/report" in paths
    assert "/api/v1/screening/runs" in paths
    assert "/api/v1/data/status" in paths
    assert "/api/v1/audit/events" in paths
    assert "/api/v1/dashboard/home" in paths


def test_app_state_has_phase2_readers(env: Path):
    """Phase 2 app.state에 readers가 주입되어 있는지 확인."""
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    assert hasattr(app.state, "portfolio_reader")
    assert hasattr(app.state, "risk_cache")
    assert hasattr(app.state, "risk_reader")
    assert hasattr(app.state, "screening_repo")
    assert hasattr(app.state, "data_status_reader")
    assert hasattr(app.state, "audit_reader")
    # settings은 WEBAPP_ENCRYPT_KEY 없으면 None
    assert hasattr(app.state, "settings_repo")
    assert hasattr(app.state, "settings_service")


def test_settings_router_absent_without_encrypt_key(env: Path):
    """WEBAPP_ENCRYPT_KEY 없으면 settings 라우터가 포함되지 않아야 한다."""
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    paths = {r.path for r in app.routes}
    assert "/api/v1/settings" not in paths


def test_settings_router_present_with_encrypt_key(
    env: Path, monkeypatch: pytest.MonkeyPatch
):
    """WEBAPP_ENCRYPT_KEY 있으면 settings 라우터가 포함되어야 한다."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", Fernet.generate_key().decode())

    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    paths = {r.path for r in app.routes}
    assert "/api/v1/settings" in paths
    assert app.state.settings_repo is not None
    assert app.state.settings_service is not None


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


def test_market_router_registered(env: Path):
    """create_app 부팅 후 market 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    routes = {r.path for r in app.routes}
    assert "/api/v1/market/pulse/latest" in routes
    assert "/api/v1/market/pulse/history" in routes
    assert "/api/v1/market/pulse/{date}" in routes
    assert "/api/v1/market/pulse/run" in routes


def test_pulse_history_on_state(env: Path):
    """app.state.pulse_history 가 PulseHistory 인스턴스로 세팅된다."""
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    assert hasattr(app.state, "pulse_history")
    assert app.state.pulse_history is not None


def test_content_router_registered(env: Path):
    """create_app 부팅 후 content 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    routes = {r.path for r in app.routes}
    assert "/api/v1/content/reports" in routes
    assert "/api/v1/content/reports/{filename:path}" in routes
    assert "/api/v1/content/monitor/run" in routes


def test_content_reader_on_state(env: Path):
    from alphapulse.webapp.main import create_app

    app = create_app(backtest_db_path=env / "backtest.db")
    assert hasattr(app.state, "content_reader")
    assert app.state.content_reader is not None


def test_briefing_router_registered():
    """create_app 후 briefing 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/briefings" in routes
    assert "/api/v1/briefings/{date}" in routes
    assert "/api/v1/briefings/latest" in routes
    assert "/api/v1/briefings/run" in routes


def test_briefing_store_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "briefing_store")
    assert app.state.briefing_store is not None


def test_feedback_router_registered():
    """create_app 후 feedback 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/feedback/summary" in routes
    assert "/api/v1/feedback/history" in routes
    assert "/api/v1/feedback/{date}" in routes


def test_feedback_store_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "feedback_store")
    assert app.state.feedback_store is not None


def test_feedback_evaluator_not_on_state():
    """FeedbackEvaluator 는 request-scoped 의존성으로 주입되므로 app.state 에 없어야 한다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert not hasattr(app.state, "feedback_evaluator")
