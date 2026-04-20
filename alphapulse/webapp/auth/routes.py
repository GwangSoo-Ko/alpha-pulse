"""Auth 라우트 — /login, /logout, /me, /csrf-token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from alphapulse.webapp.auth.deps import (
    get_config,
    get_current_user,
    get_sessions,
    get_users,
)
from alphapulse.webapp.auth.models import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from alphapulse.webapp.auth.security import (
    generate_session_token,
    verify_password,
)
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import User, UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_attempts(request: Request) -> LoginAttemptsRepository:
    return request.app.state.login_attempts


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    cfg: WebAppConfig = Depends(get_config),
    users: UserRepository = Depends(get_users),
    sessions: SessionRepository = Depends(get_sessions),
    attempts: LoginAttemptsRepository = Depends(get_attempts),
):
    client_ip = request.client.host if request.client else ""

    # 계정 잠금 체크
    fails = attempts.recent_failures_by_email(
        body.email, window_seconds=900,
    )
    if fails >= 5:
        raise HTTPException(
            status_code=429, detail="Account temporarily locked",
        )
    ip_fails = attempts.recent_failures_by_ip(
        client_ip, window_seconds=60,
    )
    if ip_fails >= 10:
        raise HTTPException(
            status_code=429, detail="Too many attempts from this IP",
        )

    user = users.get_by_email(body.email)
    ok = (
        user is not None
        and user.is_active
        and verify_password(body.password, user.password_hash)
    )
    attempts.record(email=body.email, ip=client_ip, success=ok)
    if not ok:
        try:
            request.app.state.audit.log(
                "webapp.login_failed", "webapp",
                {"email": body.email, "ip": client_ip}, "live",
            )
        except AttributeError:
            pass
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_session_token()
    sessions.create(
        token=token,
        user_id=user.id,
        ttl_seconds=cfg.session_ttl_seconds,
        absolute_ttl_seconds=cfg.session_absolute_ttl_seconds,
        ip=client_ip,
        ua=request.headers.get("user-agent", ""),
    )
    users.touch_last_login(user.id)
    try:
        request.app.state.audit.log(
            "webapp.login_success", "webapp",
            {"user_id": user.id, "email": user.email, "ip": client_ip}, "live",
        )
    except AttributeError:
        pass

    response.set_cookie(
        cfg.session_cookie_name,
        token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=cfg.session_ttl_seconds,
    )
    return LoginResponse(
        user=UserResponse(id=user.id, email=user.email, role=user.role),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    cfg: WebAppConfig = Depends(get_config),
    sessions: SessionRepository = Depends(get_sessions),
):
    token = request.cookies.get(cfg.session_cookie_name)
    if token:
        sessions.revoke(token)
    try:
        request.app.state.audit.log(
            "webapp.logout", "webapp",
            {"ip": request.client.host if request.client else ""}, "live",
        )
    except AttributeError:
        pass
    response.delete_cookie(
        cfg.session_cookie_name,
        path="/",
        samesite="strict",
    )
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, role=user.role)
