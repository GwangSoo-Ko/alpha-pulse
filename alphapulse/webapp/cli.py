"""ap webapp 서브커맨드 — 관리자 계정·운영 명령."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from alphapulse.core.config import Config
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db


def _db_path() -> Path:
    cfg = WebAppConfig.from_env()
    core = Config()
    base = Path(core.DATA_DIR).resolve().parent
    path = cfg.db_path_resolved(base)
    init_webapp_db(path)
    return path


@click.group()
def webapp() -> None:
    """웹앱 관리 명령."""


@webapp.command("create-admin")
@click.option("--email", required=True)
def create_admin(email: str) -> None:
    """관리자 계정을 생성한다."""
    pw1 = click.prompt("Password", hide_input=True)
    pw2 = click.prompt("Confirm password", hide_input=True)
    if pw1 != pw2:
        click.echo("Passwords do not match.", err=True)
        sys.exit(1)
    try:
        h = hash_password(pw1)
    except ValueError as e:
        click.echo(f"Password rejected: {e}", err=True)
        sys.exit(1)
    users = UserRepository(db_path=_db_path())
    try:
        uid = users.create(email=email, password_hash=h, role="admin")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(f"Created admin: {email} (id={uid})")


@webapp.command("reset-password")
@click.option("--email", required=True)
def reset_password(email: str) -> None:
    """사용자 비밀번호를 재설정한다."""
    users = UserRepository(db_path=_db_path())
    user = users.get_by_email(email)
    if user is None:
        click.echo("User not found.", err=True)
        sys.exit(1)
    pw1 = click.prompt("New password", hide_input=True)
    pw2 = click.prompt("Confirm password", hide_input=True)
    if pw1 != pw2:
        click.echo("Passwords do not match.", err=True)
        sys.exit(1)
    try:
        h = hash_password(pw1)
    except ValueError as e:
        click.echo(f"Password rejected: {e}", err=True)
        sys.exit(1)
    users.update_password_hash(user.id, h)
    click.echo(f"Password updated for {email}")


@webapp.command("unlock-account")
@click.option("--email", required=True)
def unlock_account(email: str) -> None:
    """최근 로그인 실패 기록을 삭제하여 계정 잠금을 해제한다."""
    import sqlite3
    import time

    db = _db_path()
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "DELETE FROM login_attempts WHERE email = ? "
            "AND success = 0 AND attempted_at >= ?",
            (email, time.time() - 86400),
        )
        n = cur.rowcount
    click.echo(f"Cleared {n} recent failure records for {email}")


@webapp.command("verify-monitoring")
def verify_monitoring() -> None:
    """모니터링 채널로 테스트 메시지를 발송한다."""
    cfg = WebAppConfig.from_env()
    if not cfg.monitor_enabled:
        click.echo(
            "Monitoring disabled. Set TELEGRAM_MONITOR_BOT_TOKEN and "
            "TELEGRAM_MONITOR_CHANNEL_ID in .env."
        )
        return
    alert_log = AlertLogRepository(db_path=_db_path())
    notifier = MonitorNotifier(
        bot_token=cfg.monitor_bot_token,
        chat_id=cfg.monitor_channel_id,
        alert_log=alert_log,
        window_seconds=1,  # 테스트 시 즉시 보내기
    )
    asyncio.run(notifier.send(
        "INFO", "verify-monitoring",
        "This is a test message from ap webapp verify-monitoring.",
    ))
    click.echo("Test message sent. Check your monitoring channel.")
