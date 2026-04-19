"""인증 보안 유틸 — bcrypt + 세션 토큰."""

from __future__ import annotations

import secrets

import bcrypt

_MIN_PASSWORD_LEN = 12
_BCRYPT_COST = 12


def hash_password(password: str) -> str:
    """bcrypt로 비밀번호를 해싱한다. 최소 길이 12자 강제."""
    if len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(
            f"password must be at least {_MIN_PASSWORD_LEN} chars"
        )
    salt = bcrypt.gensalt(rounds=_BCRYPT_COST)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """평문과 해시를 비교한다. timing-safe."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed.encode("utf-8")
        )
    except ValueError:
        return False


def generate_session_token() -> str:
    """세션 ID — URL-safe 토큰 32바이트."""
    return secrets.token_urlsafe(32)
