"""데이터 수집 스케줄러 테스트."""

from unittest.mock import patch

import pytest

from alphapulse.trading.data.scheduler import DataScheduler, ScheduleResult


@pytest.fixture
def scheduler(tmp_path):
    return DataScheduler(db_path=tmp_path / "test.db", top_n=5, delay=0)


class TestShouldCollect:
    def test_never_collected(self, scheduler):
        """미수집 시 항상 True."""
        assert scheduler._should_collect("ohlcv", "20250410", "daily") is True

    def test_already_collected_today(self, scheduler):
        """오늘 수집했으면 False."""
        scheduler.metadata.set_last_date("ALL", "ohlcv", "20250410")
        assert scheduler._should_collect("ohlcv", "20250410", "daily") is False

    def test_daily_yesterday(self, scheduler):
        """어제 수집 + daily → True."""
        scheduler.metadata.set_last_date("ALL", "ohlcv", "20250409")
        assert scheduler._should_collect("ohlcv", "20250410", "daily") is True

    def test_weekly_3days_ago(self, scheduler):
        """3일 전 수집 + weekly → False."""
        scheduler.metadata.set_last_date("ALL", "reports", "20250407")
        assert scheduler._should_collect("reports", "20250410", "weekly") is False

    def test_weekly_8days_ago(self, scheduler):
        """8일 전 수집 + weekly → True."""
        scheduler.metadata.set_last_date("ALL", "reports", "20250402")
        assert scheduler._should_collect("reports", "20250410", "weekly") is True

    def test_monthly_20days_ago(self, scheduler):
        """20일 전 수집 + monthly → False."""
        scheduler.metadata.set_last_date("ALL", "financials", "20250320")
        assert scheduler._should_collect("financials", "20250410", "monthly") is False

    def test_monthly_31days_ago(self, scheduler):
        """31일 전 수집 + monthly → True."""
        scheduler.metadata.set_last_date("ALL", "financials", "20250310")
        assert scheduler._should_collect("financials", "20250410", "monthly") is True

    def test_quarterly_60days_ago(self, scheduler):
        """60일 전 수집 + quarterly → False."""
        scheduler.metadata.set_last_date("ALL", "overview", "20250210")
        assert scheduler._should_collect("overview", "20250410", "quarterly") is False

    def test_quarterly_91days_ago(self, scheduler):
        """91일 전 수집 + quarterly → True."""
        scheduler.metadata.set_last_date("ALL", "overview", "20250110")
        assert scheduler._should_collect("overview", "20250410", "quarterly") is True


class TestFallbackByMarketCap:
    def test_returns_top_n(self, scheduler):
        """시총 상위 N종목을 반환한다."""
        for i, (code, cap) in enumerate([
            ("005930", 400e12), ("000660", 120e12), ("035720", 20e12),
            ("005380", 50e12), ("051910", 80e12), ("006400", 30e12),
        ]):
            scheduler.store.upsert_stock(code, f"종목{i}", "KOSPI", market_cap=cap)

        codes = scheduler._fallback_by_market_cap(["KOSPI"])
        assert len(codes) == 5  # top_n=5
        assert codes[0] == "005930"  # 시총 최대
        assert codes[1] == "000660"

    def test_empty_market(self, scheduler):
        """종목 없으면 빈 리스트."""
        codes = scheduler._fallback_by_market_cap(["KOSPI"])
        assert codes == []


class TestSelectCandidates:
    def test_fallback_when_no_data(self, scheduler):
        """팩터 데이터 없으면 시총 폴백."""
        scheduler.store.upsert_stock("005930", "삼성전자", "KOSPI", market_cap=400e12)
        codes = scheduler._select_candidates(["KOSPI"])
        assert "005930" in codes


class TestGetStatus:
    def test_shows_all_schedules(self, scheduler):
        """모든 스케줄 항목을 반환한다."""
        with patch.object(scheduler, "_get_latest_date", return_value="20250410"):
            status = scheduler.get_status()
        assert "ohlcv" in status
        assert "short" in status
        assert "financials" in status
        assert status["ohlcv"]["frequency"] == "daily"
        assert status["ohlcv"]["stage"] == 1
        assert status["financials"]["stage"] == 2

    def test_needs_update_when_never_collected(self, scheduler):
        """미수집 항목은 needs_update=True."""
        with patch.object(scheduler, "_get_latest_date", return_value="20250410"):
            status = scheduler.get_status()
        assert status["ohlcv"]["needs_update"] is True


class TestScheduleResult:
    def test_default(self):
        result = ScheduleResult()
        assert result.executed == []
        assert result.skipped == []
        assert result.errors == []
        assert result.stage2_codes == []
