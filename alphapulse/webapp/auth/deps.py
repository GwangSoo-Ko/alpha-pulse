"""Auth FastAPI 의존성.

get_current_user, require_role, 그리고 테스트 편의용 provider 패턴.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request

from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.store.sessions import Session, SessionRepository
from alphapulse.webapp.store.users import User, UserRepository


def get_config(request: Request) -> WebAppConfig:
    return request.app.state.config


def get_users(request: Request) -> UserRepository:
    return request.app.state.users


def get_sessions(request: Request) -> SessionRepository:
    return request.app.state.sessions


async def get_current_user(
    request: Request,
    cfg: WebAppConfig = Depends(get_config),
    users: UserRepository = Depends(get_users),
    sessions: SessionRepository = Depends(get_sessions),
) -> User:
    token = request.cookies.get(cfg.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess: Session | None = sessions.get(token)
    if sess is None or sess.is_expired or sess.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Session invalid")
    # 슬라이딩 갱신
    sessions.touch(
        token,
        ttl_seconds=cfg.session_ttl_seconds,
        absolute_ttl_seconds=cfg.session_absolute_ttl_seconds,
    )
    user = users.get_by_id(sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User disabled")
    return user


def require_role(*allowed: str) -> Callable:
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _check
