"""ap webapp 서브커맨드 — 관리자 계정·운영 명령."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click

from alphapulse.core.config import Config
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.alert_log import AlertLogRepository
from alphapulse.webapp.store.settings import SettingsRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db


def _db_path() -> Path:
    cfg = WebAppConfig.from_env()
    core = Config()
    base = Path(core.DATA_DIR).resolve().parent
    path = cfg.db_path_resolved(base)
    init_webapp_db(path)
    return path


def _get_fernet_key() -> bytes:
    key = os.environ.get("WEBAPP_ENCRYPT_KEY", "").strip()
    if not key:
        click.echo(
            "WEBAPP_ENCRYPT_KEY not set. "
            "Run `ap webapp init-encrypt-key` first.",
            err=True,
        )
        sys.exit(1)
    return key.encode("utf-8")


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


# === Task 16: import-env 화이트리스트 ===

_IMPORT_WHITELIST: dict[str, tuple[str, bool]] = {
    # (category, is_secret)
    "KIS_APP_KEY": ("api_key", True),
    "KIS_APP_SECRET": ("api_key", True),
    "KIS_ACCOUNT_NO": ("api_key", True),
    "GEMINI_API_KEY": ("api_key", True),
    "TELEGRAM_BOT_TOKEN": ("notification", True),
    "TELEGRAM_CHANNEL_ID": ("notification", True),
    "TELEGRAM_MONITOR_BOT_TOKEN": ("notification", True),
    "TELEGRAM_MONITOR_CHANNEL_ID": ("notification", True),
    "MAX_POSITION_WEIGHT": ("risk_limit", False),
    "MAX_DRAWDOWN_SOFT": ("risk_limit", False),
    "MAX_DRAWDOWN_HARD": ("risk_limit", False),
    "MAX_DAILY_ORDERS": ("risk_limit", False),
    "MAX_DAILY_AMOUNT": ("risk_limit", False),
    "BACKTEST_COMMISSION": ("backtest", False),
    "BACKTEST_TAX": ("backtest", False),
    "BACKTEST_INITIAL_CAPITAL": ("backtest", False),
    "STRATEGY_ALLOCATIONS": ("backtest", False),
}


# === Task 15: settings 관련 명령 ===


@webapp.command("init-encrypt-key")
def init_encrypt_key() -> None:
    """새 Fernet 키 생성 — .env에 수동 추가."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    click.echo("Generated WEBAPP_ENCRYPT_KEY:")
    click.echo("")
    click.echo(f"  {key}")
    click.echo("")
    click.echo("다음 줄을 .env에 수동 추가하세요:")
    click.echo(f"WEBAPP_ENCRYPT_KEY={key}")
    click.echo("")
    click.echo("주의: 키 분실 시 DB의 암호화 값 복구 불가.")


@webapp.command("rotate-encrypt-key")
@click.option("--new-key", required=True, help="새 키 (base64)")
def rotate_encrypt_key(new_key: str) -> None:
    """기존 키로 복호화 → 새 키로 재암호화."""
    old_key = _get_fernet_key()
    db = _db_path()
    old_repo = SettingsRepository(db_path=db, fernet_key=old_key)
    new_repo = SettingsRepository(db_path=db, fernet_key=new_key.encode("utf-8"))
    entries = old_repo.list_all()
    for e in entries:
        plain = old_repo.get(e.key)
        if plain is not None:
            new_repo.set(
                key=e.key,
                value=plain,
                is_secret=e.is_secret,
                category=e.category,
                user_id=e.updated_by or 0,
                tenant_id=e.tenant_id,
            )
    click.echo(f"Rotated {len(entries)} settings.")
    click.echo("이제 .env의 WEBAPP_ENCRYPT_KEY를 새 키로 교체하세요.")


@webapp.command("set")
@click.option("--key", required=True)
@click.option("--value", required=True)
@click.option(
    "--category",
    required=True,
    type=click.Choice(["api_key", "risk_limit", "notification", "backtest"]),
)
@click.option("--secret/--plain", default=False)
def set_setting(key: str, value: str, category: str, secret: bool) -> None:
    """설정 값을 DB에 저장."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    repo.set(key=key, value=value, is_secret=secret, category=category, user_id=0)
    click.echo(f"Set: {key}")


@webapp.command("list")
@click.option(
    "--category",
    default=None,
    type=click.Choice(["api_key", "risk_limit", "notification", "backtest"]),
)
def list_settings(category: str | None) -> None:
    """DB에 저장된 설정 목록 (secret은 마스킹)."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    entries = repo.list_by_category(category) if category else repo.list_all()
    if not entries:
        click.echo("설정 없음.")
        return
    click.echo(f"{'category':<15} {'key':<30} {'value':<30}")
    click.echo(f"{'-'*15} {'-'*30} {'-'*30}")
    for e in entries:
        val = repo.get(e.key) or ""
        display = SettingsService.mask(val) if e.is_secret else val
        click.echo(f"{e.category:<15} {e.key:<30} {display:<30}")


@webapp.command("import-env")
@click.option("--dry-run", is_flag=True, help="실제 쓰기 없이 변경 목록만 출력")
def import_env(dry_run: bool) -> None:
    """화이트리스트 키를 .env → DB로 이관. 이미 DB에 있으면 skip."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    existing_keys = {e.key for e in repo.list_all()}

    to_import: list[tuple[str, str, str, bool]] = []
    for env_key, (category, is_secret) in _IMPORT_WHITELIST.items():
        val = os.environ.get(env_key)
        if val is None or not val.strip():
            continue
        if env_key in existing_keys:
            continue
        to_import.append((env_key, val, category, is_secret))

    if dry_run:
        click.echo(f"[dry-run] {len(to_import)} 키 이관 예정:")
        for k, _, cat, _ in to_import:
            click.echo(f"  {cat:<15} {k}")
        return

    for k, v, cat, secret in to_import:
        repo.set(
            key=k, value=v,
            is_secret=secret, category=cat, user_id=0,
        )

    click.echo(f"Imported {len(to_import)} settings from .env.")
