"""요청 제한기.

pykrx API 호출 간 딜레이 + 지수 백오프 재시도를 관리한다.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """요청 제한기.

    Attributes:
        delay: 요청 간 기본 딜레이 (초).
        max_retries: 최대 재시도 횟수.
        backoff_base: 백오프 지수 기저.
    """

    def __init__(
        self,
        delay: float = 0.5,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        self.delay = delay
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def call(self, fn, *args, **kwargs):
        """함수를 호출한다. 실패 시 재시도 후 예외를 전파한다."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.delay)
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                wait = self.delay * (self.backoff_base**attempt) + random.uniform(
                    0, 0.2
                )
                logger.warning("재시도 %d/%d: %s", attempt + 1, self.max_retries, e)
                time.sleep(wait)
        raise last_error

    def call_safe(self, fn, *args, **kwargs):
        """함수를 호출한다. 실패 시 None을 반환한다 (예외 전파 안 함)."""
        try:
            return self.call(fn, *args, **kwargs)
        except Exception as e:
            logger.error("최종 실패 (무시): %s", e)
            return None
