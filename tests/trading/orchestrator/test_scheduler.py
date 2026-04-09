"""TradingScheduler 테스트 — KRX 시간대 기반 스케줄링.

datetime.now()를 mock하여 시간대별 동작을 검증한다.
"""

from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphapulse.trading.orchestrator.scheduler import TradingScheduler


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.run_daily = AsyncMock(return_value={"status": "ok"})
    return engine


@pytest.fixture
def mock_calendar():
    calendar = MagicMock()
    calendar.is_trading_day.return_value = True
    calendar.next_trading_day.return_value = "20260410"
    return calendar


class TestScheduleDefinition:
    """스케줄 정의 테스트."""

    def test_default_schedule(self, mock_engine, mock_calendar):
        """기본 스케줄이 정의되어 있다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert "data_update" in scheduler.SCHEDULE
        assert "analysis" in scheduler.SCHEDULE
        assert "portfolio" in scheduler.SCHEDULE
        assert "pre_market_alert" in scheduler.SCHEDULE
        assert "market_open" in scheduler.SCHEDULE
        assert "midday_check" in scheduler.SCHEDULE
        assert "market_close" in scheduler.SCHEDULE
        assert "post_market" in scheduler.SCHEDULE

    def test_schedule_times_order(self, mock_engine, mock_calendar):
        """스케줄 시간이 올바른 순서이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        times = list(scheduler.SCHEDULE.values())
        for i in range(len(times) - 1):
            assert times[i] <= times[i + 1], f"{times[i]} > {times[i + 1]}"


class TestShouldRunPhase:
    """실행 시점 판단 테스트."""

    def test_data_update_at_0800(self, mock_engine, mock_calendar):
        """08:00에 data_update 단계를 실행한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("data_update", time(8, 0)) is True

    def test_data_update_before_0800(self, mock_engine, mock_calendar):
        """08:00 이전에는 data_update를 실행하지 않는다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("data_update", time(7, 59)) is False

    def test_market_open_at_0900(self, mock_engine, mock_calendar):
        """09:00에 market_open 단계를 실행한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.should_run_phase("market_open", time(9, 0)) is True


class TestHolidayHandling:
    """공휴일 처리 테스트."""

    def test_skips_holiday(self, mock_engine, mock_calendar):
        """공휴일에는 실행하지 않는다."""
        mock_calendar.is_trading_day.return_value = False
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.is_active_day("20260409") is False

    def test_runs_on_trading_day(self, mock_engine, mock_calendar):
        """거래일에는 실행한다."""
        mock_calendar.is_trading_day.return_value = True
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        assert scheduler.is_active_day("20260409") is True


class TestRunOnce:
    """단일 실행 테스트."""

    @pytest.mark.asyncio
    async def test_run_once_calls_engine(self, mock_engine, mock_calendar):
        """run_once()는 engine.run_daily()를 호출한다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        result = await scheduler.run_once(date="20260409")
        mock_engine.run_daily.assert_called_once_with(date="20260409")
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_run_once_skips_holiday(self, mock_engine, mock_calendar):
        """공휴일이면 실행하지 않고 None을 반환한다."""
        mock_calendar.is_trading_day.return_value = False
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        result = await scheduler.run_once(date="20260409")
        mock_engine.run_daily.assert_not_called()
        assert result is None


class TestGetNextPhase:
    """다음 실행 단계 조회 테스트."""

    def test_next_phase_morning(self, mock_engine, mock_calendar):
        """07:00에는 다음 단계가 data_update이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(7, 0))
        assert phase == "data_update"
        assert phase_time == "08:00"

    def test_next_phase_after_all(self, mock_engine, mock_calendar):
        """모든 단계 이후에는 None이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(17, 0))
        assert phase is None
        assert phase_time is None

    def test_next_phase_midday(self, mock_engine, mock_calendar):
        """10:00에는 다음 단계가 midday_check이다."""
        scheduler = TradingScheduler(engine=mock_engine, calendar=mock_calendar)
        phase, phase_time = scheduler.get_next_phase(time(10, 0))
        assert phase == "midday_check"
        assert phase_time == "12:30"
