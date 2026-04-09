"""HistoricalDataFeed 테스트 — look-ahead bias 방지 검증."""

import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.core.models import OHLCV


@pytest.fixture
def sample_data():
    """삼성전자 5일치 OHLCV 데이터."""
    return {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
            OHLCV(date="20260409", open=74000, high=74500, low=72500, close=73000, volume=9_000_000),
            OHLCV(date="20260410", open=73000, high=73500, low=71000, close=71500, volume=15_000_000),
        ],
        "000660": [
            OHLCV(date="20260406", open=150000, high=155000, low=149000, close=153000, volume=3_000_000),
            OHLCV(date="20260407", open=153000, high=157000, low=152000, close=156000, volume=4_000_000),
            OHLCV(date="20260408", open=156000, high=158000, low=154000, close=155000, volume=3_500_000),
            OHLCV(date="20260409", open=155000, high=156000, low=150000, close=151000, volume=5_000_000),
            OHLCV(date="20260410", open=151000, high=152000, low=148000, close=149000, volume=6_000_000),
        ],
    }


class TestHistoricalDataFeed:
    def test_advance_to_sets_current_date(self, sample_data):
        """advance_to로 현재 날짜를 전진시킨다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        assert feed.current_date == "20260407"

    def test_get_ohlcv_within_current_date(self, sample_data):
        """현재 날짜 이전 데이터는 정상 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        result = feed.get_ohlcv("005930", "20260406", "20260408")
        assert len(result) == 3
        assert result[0].date == "20260406"
        assert result[-1].date == "20260408"

    def test_look_ahead_bias_raises(self, sample_data):
        """미래 데이터 요청 시 AssertionError를 발생시킨다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        with pytest.raises(AssertionError, match="Look-ahead bias"):
            feed.get_ohlcv("005930", "20260406", "20260409")

    def test_get_ohlcv_exact_current_date(self, sample_data):
        """현재 날짜와 동일한 end는 허용한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260409")
        result = feed.get_ohlcv("005930", "20260409", "20260409")
        assert len(result) == 1
        assert result[0].close == 73000

    def test_get_ohlcv_unknown_code_returns_empty(self, sample_data):
        """존재하지 않는 종목은 빈 리스트를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260410")
        result = feed.get_ohlcv("999999", "20260406", "20260410")
        assert result == []

    def test_get_latest_price(self, sample_data):
        """현재 날짜의 종가를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        assert feed.get_latest_price("005930") == 74000

    def test_get_latest_price_no_data_returns_zero(self, sample_data):
        """데이터 없는 종목은 0을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        assert feed.get_latest_price("999999") == 0.0

    def test_get_bar_returns_current_date_ohlcv(self, sample_data):
        """현재 날짜의 OHLCV 바를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        bar = feed.get_bar("005930")
        assert bar is not None
        assert bar.date == "20260407"
        assert bar.close == 73500

    def test_get_bar_no_data_returns_none(self, sample_data):
        """현재 날짜에 데이터 없는 종목은 None을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        assert feed.get_bar("999999") is None

    def test_get_available_codes(self, sample_data):
        """등록된 종목 코드 목록을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        codes = feed.get_available_codes()
        assert set(codes) == {"005930", "000660"}

    def test_initial_state_before_advance(self, sample_data):
        """advance_to 호출 전에는 current_date가 빈 문자열이다."""
        feed = HistoricalDataFeed(sample_data)
        assert feed.current_date == ""
