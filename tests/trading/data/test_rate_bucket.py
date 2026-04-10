"""토큰 버킷 rate limiter 테스트."""

import time

from alphapulse.trading.data.rate_bucket import RateBucket


class TestRateBucket:
    def test_initial_burst_allowed(self):
        """초기 용량만큼은 즉시 acquire 가능."""
        bucket = RateBucket(rate=10.0, capacity=5)
        start = time.monotonic()
        for _ in range(5):
            bucket.acquire()
        elapsed = time.monotonic() - start
        # 5개 즉시 소진 → 거의 0초
        assert elapsed < 0.1

    def test_rate_limiting(self):
        """용량 초과 시 대기한다."""
        bucket = RateBucket(rate=10.0, capacity=2)
        start = time.monotonic()
        for _ in range(4):
            bucket.acquire()
        elapsed = time.monotonic() - start
        # 2개는 즉시, 나머지 2개는 rate=10/s → 0.2초 이상
        assert elapsed >= 0.15

    def test_refill(self):
        """시간이 지나면 토큰이 다시 채워진다."""
        bucket = RateBucket(rate=20.0, capacity=2)
        bucket.acquire()
        bucket.acquire()
        time.sleep(0.15)  # 0.15 * 20 = 3 토큰 충전
        start = time.monotonic()
        bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    def test_default_rate(self):
        """기본값은 rate=8, capacity=8."""
        bucket = RateBucket()
        assert bucket.rate == 8.0
        assert bucket.capacity == 8
