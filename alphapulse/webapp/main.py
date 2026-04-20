"""FastAPI 앱 어셈블리."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI

from alphapulse.core.config import Config
from alphapulse.trading.core.audit import AuditLogger
from alphapulse.webapp.api.backtest import router as backtest_router
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
from alphapulse.webapp.store.readers.backtest import BacktestReader
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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
    app.state.audit = AuditLogger(db_path=db_path.with_suffix(".audit.db"))

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(backtest_router)

    return app


app = create_app()
