"""CSRF 미들웨어 — Double Submit Cookie 패턴.

- GET /api/v1/csrf-token → 쿠키 `ap_csrf` 설정 + body에 토큰
- 변경 요청(POST/PUT/DELETE)은 `X-CSRF-Token` 헤더와 `ap_csrf` 쿠키가 일치해야 통과
- GET/HEAD/OPTIONS는 통과
"""

from __future__ import annotations

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_CSRF_COOKIE = "ap_csrf"
_CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret: str) -> None:
        super().__init__(app)
        self.secret = secret

    async def dispatch(self, request: Request, call_next) -> Response:
        cookie = request.cookies.get(_CSRF_COOKIE, "")
        # 토큰 발급 엔드포인트 전용 처리
        if request.url.path == "/api/v1/csrf-token":
            token = cookie or secrets.token_urlsafe(32)
            request.state.csrf_token = token
            response = await call_next(request)
            response.set_cookie(
                _CSRF_COOKIE, token,
                httponly=False,       # JS가 읽어 헤더에 복사해야 함
                secure=True,
                samesite="strict",
                path="/",
            )
            return response

        # 안전 메서드는 검증 생략
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        header = request.headers.get(_CSRF_HEADER, "")
        if not cookie or not header or not hmac.compare_digest(
            cookie, header,
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "type": "https://alphapulse/errors/csrf",
                    "title": "CSRF validation failed",
                    "status": 403,
                    "detail": "missing or mismatched CSRF token",
                },
            )
        return await call_next(request)
