"""KRX 마켓 캘린더 테스트."""

from alphapulse.trading.core.calendar import KRXCalendar


class TestKRXCalendar:
    def setup_method(self):
        self.cal = KRXCalendar()

    def test_weekday_is_trading_day(self):
        """평일은 거래일이다 (공휴일 아닌 경우)."""
        # 2026-04-06 월요일
        assert self.cal.is_trading_day("20260406") is True

    def test_saturday_is_not_trading_day(self):
        assert self.cal.is_trading_day("20260411") is False  # 토요일

    def test_sunday_is_not_trading_day(self):
        assert self.cal.is_trading_day("20260412") is False  # 일요일

    def test_new_years_day_is_not_trading_day(self):
        """신정은 공휴일이다."""
        assert self.cal.is_trading_day("20260101") is False

    def test_chuseok_is_not_trading_day(self):
        """추석 연휴는 공휴일이다."""
        # 2026년 추석: 9/24(목), 9/25(금) 추석당일, 9/26(토)
        assert self.cal.is_trading_day("20260924") is False
        assert self.cal.is_trading_day("20260925") is False

    def test_next_trading_day_from_friday(self):
        """금요일 다음 거래일은 월요일."""
        # 2026-04-10 금요일 → 2026-04-13 월요일
        assert self.cal.next_trading_day("20260410") == "20260413"

    def test_next_trading_day_skips_holiday(self):
        """공휴일을 건너뛴다."""
        # 2025-12-31(수) → 2026-01-02(금) (1/1 신정 건너뜀)
        assert self.cal.next_trading_day("20251231") == "20260102"

    def test_prev_trading_day_from_monday(self):
        """월요일 이전 거래일은 금요일."""
        # 2026-04-13 월요일 → 2026-04-10 금요일
        assert self.cal.prev_trading_day("20260413") == "20260410"

    def test_trading_days_between(self):
        """구간 거래일 목록."""
        # 2026-04-06(월) ~ 2026-04-10(금) = 5 영업일
        days = self.cal.trading_days_between("20260406", "20260410")
        assert len(days) == 5
        assert days[0] == "20260406"
        assert days[-1] == "20260410"

    def test_trading_days_between_excludes_weekend(self):
        """주말 포함 구간에서 주말은 제외."""
        # 2026-04-09(목) ~ 2026-04-14(화) = 4일 (토일 제외)
        days = self.cal.trading_days_between("20260409", "20260414")
        assert len(days) == 4
        assert "20260411" not in days  # 토
        assert "20260412" not in days  # 일

    def test_is_half_day_returns_false(self):
        """반일장은 현재 항상 False (스텁)."""
        assert self.cal.is_half_day("20260409") is False
