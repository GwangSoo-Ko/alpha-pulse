"""전역 토큰 버킷 rate limiter.

여러 스레드가 네이버 금융을 동시 호출할 때 전체 초당 요청 수를 제한하여
429 차단을 방지한다.
"""

import threading
import time


class RateBucket:
    """토큰 버킷 알고리즘 기반 전역 rate limiter.

    스레드 안전하게 초당 요청 수를 제한한다.

    Attributes:
        rate: 초당 최대 요청 수.
        capacity: 버킷 최대 용량 (버스트 허용량).
    """

    def __init__(self, rate: float = 8.0, capacity: int | None = None) -> None:
        """RateBucket을 초기화한다.

        Args:
            rate: 초당 토큰 보충 속도 (= 초당 최대 요청 수).
            capacity: 버킷 용량. None이면 rate와 동일.
        """
        self.rate = rate
        self.capacity = capacity if capacity is not None else int(rate)
        self._tokens = float(self.capacity)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        """토큰을 획득한다. 부족하면 대기한다.

        Args:
            tokens: 필요한 토큰 수. 기본 1.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(
                    self.capacity, self._tokens + elapsed * self.rate
                )
                self._last_update = now

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                wait = (tokens - self._tokens) / self.rate

            time.sleep(wait)
