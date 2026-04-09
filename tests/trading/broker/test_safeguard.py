"""TradingSafeguard 테스트 — 실매매 안전장치.

LIVE_TRADING_ENABLED, 일일 한도, 사용자 확인을 검증한다.
"""

from unittest.mock import patch

import pytest

from alphapulse.trading.broker.safeguard import TradingSafeguard


class TestCheckLiveAllowed:
    """LIVE_TRADING_ENABLED 검사 테스트."""

    def test_live_enabled(self):
        """LIVE_TRADING_ENABLED=True이면 True를 반환한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        assert sg.check_live_allowed() is True

    def test_live_disabled_raises(self):
        """LIVE_TRADING_ENABLED=False이면 RuntimeError를 발생시킨다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": False,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        with pytest.raises(RuntimeError, match="실매매가 비활성화"):
            sg.check_live_allowed()

    def test_default_is_disabled(self):
        """기본값은 비활성화이다."""
        sg = TradingSafeguard(config={})
        with pytest.raises(RuntimeError, match="실매매가 비활성화"):
            sg.check_live_allowed()


class TestConfirmLiveStart:
    """사용자 수동 확인 테스트."""

    def test_user_confirms_yes(self):
        """사용자가 'yes'를 입력하면 True를 반환한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="yes"):
            assert sg.confirm_live_start("12345678-01") is True

    def test_user_confirms_no(self):
        """사용자가 'no'를 입력하면 False를 반환한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="no"):
            assert sg.confirm_live_start("12345678-01") is False

    def test_user_confirms_with_spaces(self):
        """입력 앞뒤 공백을 제거한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value="  yes  "):
            assert sg.confirm_live_start("12345678-01") is True

    def test_user_empty_input(self):
        """빈 입력은 거부한다."""
        sg = TradingSafeguard(config={"LIVE_TRADING_ENABLED": True})
        with patch("builtins.input", return_value=""):
            assert sg.confirm_live_start("12345678-01") is False


class TestDailyLimits:
    """일일 주문 한도 테스트."""

    @pytest.fixture
    def safeguard(self):
        return TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })

    def test_within_limits(self, safeguard):
        """한도 내이면 True를 반환한다."""
        assert safeguard.check_daily_limit(today_orders=10, today_amount=10_000_000) is True

    def test_order_count_exceeded(self, safeguard):
        """주문 횟수 한도 초과 시 RuntimeError."""
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            safeguard.check_daily_limit(today_orders=50, today_amount=10_000_000)

    def test_order_amount_exceeded(self, safeguard):
        """주문 금액 한도 초과 시 RuntimeError."""
        with pytest.raises(RuntimeError, match="일일 금액 한도 초과"):
            safeguard.check_daily_limit(today_orders=10, today_amount=50_000_000)

    def test_both_exceeded(self, safeguard):
        """횟수와 금액 모두 초과 시 — 횟수가 먼저 검사된다."""
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            safeguard.check_daily_limit(today_orders=50, today_amount=50_000_000)

    def test_just_below_limits(self, safeguard):
        """한도 직전이면 허용한다."""
        assert safeguard.check_daily_limit(today_orders=49, today_amount=49_999_999) is True


class TestTrackDailyUsage:
    """일일 사용량 추적 테스트."""

    def test_record_and_check(self):
        """주문을 기록하면 누적 횟수/금액이 증가한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 3,
            "MAX_DAILY_AMOUNT": 10_000_000,
        })
        sg.record_order(amount=3_000_000)
        sg.record_order(amount=3_000_000)
        assert sg.today_order_count == 2
        assert sg.today_order_amount == 6_000_000

        # 세 번째까지 가능
        sg.record_order(amount=3_000_000)
        # 네 번째는 한도 초과
        with pytest.raises(RuntimeError, match="일일 주문 한도 초과"):
            sg.check_daily_limit(
                today_orders=sg.today_order_count,
                today_amount=sg.today_order_amount,
            )

    def test_reset_daily(self):
        """일일 카운터를 초기화한다."""
        sg = TradingSafeguard(config={
            "LIVE_TRADING_ENABLED": True,
            "MAX_DAILY_ORDERS": 50,
            "MAX_DAILY_AMOUNT": 50_000_000,
        })
        sg.record_order(amount=5_000_000)
        sg.reset_daily()
        assert sg.today_order_count == 0
        assert sg.today_order_amount == 0
