"""요청 제한 테스트."""
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.data.rate_limiter import RateLimiter


class TestRateLimiter:
    @patch("time.sleep")
    def test_call_safe_success(self, mock_sleep):
        rl = RateLimiter(delay=0.1)
        result = rl.call_safe(lambda: 42)
        assert result == 42

    @patch("time.sleep")
    def test_call_safe_failure_returns_none(self, mock_sleep):
        rl = RateLimiter(delay=0.1, max_retries=2)
        fn = MagicMock(side_effect=Exception("fail"))
        result = rl.call_safe(fn)
        assert result is None
        assert fn.call_count == 2

    @patch("time.sleep")
    def test_call_retries(self, mock_sleep):
        rl = RateLimiter(delay=0.1, max_retries=3)
        fn = MagicMock(side_effect=[Exception("1"), Exception("2"), 99])
        result = rl.call_safe(fn)
        assert result == 99
        assert fn.call_count == 3

    @patch("time.sleep")
    def test_delay_between_calls(self, mock_sleep):
        rl = RateLimiter(delay=0.5)
        rl.call_safe(lambda: 1)
        mock_sleep.assert_called()

    @patch("time.sleep")
    def test_call_raises_on_failure(self, mock_sleep):
        rl = RateLimiter(delay=0.1, max_retries=1)
        with pytest.raises(Exception, match="boom"):
            rl.call(lambda: (_ for _ in ()).throw(Exception("boom")))
