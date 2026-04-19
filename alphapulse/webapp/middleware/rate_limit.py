"""Rate Limit — slowapi 래퍼.

FastAPI 앱에 limiter.state 주입을 편하게 하기 위한 팩토리.
라우트에서는 `@limiter.limit("10/minute")` 데코레이터로 사용.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def make_limiter() -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        default_limits=["300/minute"],   # 사용자당 기본값
    )
