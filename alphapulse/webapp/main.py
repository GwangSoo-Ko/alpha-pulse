"""FastAPI 앱 어셈블리."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request

from alphapulse.core.config import Config
from alphapulse.core.storage import PulseHistory
from alphapulse.trading.core.audit import AuditLogger
from alphapulse.webapp.api.audit import router as audit_router
from alphapulse.webapp.api.backtest import router as backtest_router
from alphapulse.webapp.api.dashboard import router as dashboard_router
from alphapulse.webapp.api.data import router as data_router
from alphapulse.webapp.api.market import router as market_router
from alphapulse.webapp.api.portfolio import router as portfolio_router
from alphapulse.webapp.api.risk import router as risk_router
from alphapulse.webapp.api.screening import router as screening_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner, recover_orphans
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.risk_cache import RiskReportCacheRepository
from alphapulse.webapp.store.screening import ScreeningRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db

logger = logging.getLogger(__name__)


def create_app(
    backtest_db_path: Optional[Path] = None,
) -> FastAPI:
    """FastAPI 앱을 조립한다.

    Args:
        backtest_db_path: 테스트용 backtest.db 경로 오버라이드.
            None이면 Config().BACKTEST_DB_PATH를 사용한다.
    """
    cfg = WebAppConfig.from_env()
    core = Config()
    base = Path(core.DATA_DIR).resolve().parent
    db_path = cfg.db_path_resolved(base)
    init_webapp_db(db_path)

    resolved_backtest_db = (
        Path(backtest_db_path) if backtest_db_path is not None
        else core.BACKTEST_DB_PATH
    )

    alert_log = AlertLogRepository(db_path=db_path)
    monitor = MonitorNotifier(
        bot_token=cfg.monitor_bot_token,
        chat_id=cfg.monitor_channel_id,
        alert_log=alert_log,
    )
    users = UserRepository(db_path=db_path)
    sessions = SessionRepository(db_path=db_path)
    login_attempts = LoginAttemptsRepository(db_path=db_path)
    jobs = JobRepository(db_path=db_path)
    job_runner = JobRunner(job_repo=jobs)
    bt_reader = BacktestReader(db_path=resolved_backtest_db)

    # Phase 2: readers / services
    audit_db = db_path.with_suffix(".audit.db")
    trading_db = Path(core.DATA_DIR) / "trading.db"

    portfolio_reader = PortfolioReader(db_path=db_path)
    risk_cache = RiskReportCacheRepository(db_path=db_path)
    risk_reader = RiskReader(portfolio_reader=portfolio_reader, cache=risk_cache)
    screening_repo = ScreeningRepository(db_path=db_path)
    data_status_reader = DataStatusReader(trading_db_path=trading_db)
    audit_reader = AuditReader(db_path=audit_db)
    pulse_history = PulseHistory(db_path=core.HISTORY_DB)

    # Settings — conditional on WEBAPP_ENCRYPT_KEY being present
    encrypt_key = os.environ.get("WEBAPP_ENCRYPT_KEY", cfg.encrypt_key)
    settings_repo = None
    settings_service = None
    if encrypt_key:
        from alphapulse.webapp.services.settings_service import SettingsService
        from alphapulse.webapp.store.settings import SettingsRepository

        fernet_key = (
            encrypt_key.encode()
            if isinstance(encrypt_key, str)
            else encrypt_key
        )
        settings_repo = SettingsRepository(db_path=db_path, fernet_key=fernet_key)
        settings_service = SettingsService(repo=settings_repo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings_service is not None:
            settings_service.load_env_overrides()
        n = recover_orphans(job_repo=jobs)
        if n:
            logger.warning("recovered %d orphan jobs", n)
            await monitor.send(
                "WARN", f"Orphan jobs recovered: {n}",
                "Prior session had running jobs; marked as failed.",
            )
        await monitor.send(
            "INFO", "AlphaPulse webapp started",
            "FastAPI 앱이 기동되었습니다.",
        )
        yield
        await monitor.send(
            "INFO", "AlphaPulse webapp stopping", "",
        )

    app = FastAPI(
        title="AlphaPulse Web API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,   # 프로덕션 비활성
        redoc_url=None,
    )
    app.state.config = cfg
    app.state.users = users
    app.state.sessions = sessions
    app.state.login_attempts = login_attempts
    app.state.jobs = jobs
    app.state.job_runner = job_runner
    app.state.backtest_reader = bt_reader
    app.state.alert_log = alert_log
    app.state.monitor = monitor
    app.state.audit = AuditLogger(db_path=audit_db)

    # Phase 2 state
    app.state.portfolio_reader = portfolio_reader
    app.state.risk_cache = risk_cache
    app.state.risk_reader = risk_reader
    app.state.screening_repo = screening_repo
    app.state.data_status_reader = data_status_reader
    app.state.audit_reader = audit_reader
    app.state.pulse_history = pulse_history
    app.state.settings_repo = settings_repo
    app.state.settings_service = settings_service

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        """CSRF 토큰 발급 — CSRFMiddleware가 쿠키를 세팅하고 body를 반환."""
        return {"token": request.state.csrf_token}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(backtest_router)

    # Phase 2 routers
    app.include_router(portfolio_router)
    app.include_router(risk_router)
    app.include_router(screening_router)
    app.include_router(data_router)
    app.include_router(audit_router)
    app.include_router(dashboard_router)
    app.include_router(market_router)
    if settings_service is not None:
        from alphapulse.webapp.api.settings import router as settings_router

        app.include_router(settings_router)

    return app


app = create_app()
