"""투자 유니버스 관리 테스트."""

import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.universe import Universe


@pytest.fixture
def store(tmp_path):
    s = TradingStore(tmp_path / "test.db")
    # 테스트 종목 등록
    s.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
    s.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)
    s.upsert_stock("035720", "카카오", "KOSPI", "IT", 20e12)
    s.upsert_stock("069500", "KODEX 200", "ETF", "", 50e12)
    s.upsert_stock("999999", "소형주", "KOSDAQ", "기타", 5e9)  # 시총 50억
    # OHLCV (거래대금 계산용)
    s.save_ohlcv_bulk([
        ("005930", "20260409", 72000, 73000, 71500, 72500, 10_000_000, 430e12),
        ("000660", "20260409", 180000, 185000, 178000, 183000, 3_000_000, 120e12),
        ("035720", "20260409", 50000, 51000, 49500, 50500, 500_000, 20e12),
        ("069500", "20260409", 35000, 35500, 34800, 35200, 200_000, 50e12),
        ("999999", "20260409", 1000, 1050, 980, 1020, 1000, 5e9),
    ])
    return s


@pytest.fixture
def universe(store):
    return Universe(store)


class TestUniverse:
    def test_get_all(self, universe):
        """전체 종목을 Stock 리스트로 반환한다."""
        stocks = universe.get_all()
        assert len(stocks) == 5
        assert all(isinstance(s, Stock) for s in stocks)

    def test_get_by_market(self, universe):
        """시장별 종목 조회."""
        kospi = universe.get_by_market("KOSPI")
        assert len(kospi) == 3  # 삼성전자, SK하이닉스, 카카오

        etfs = universe.get_by_market("ETF")
        assert len(etfs) == 1

    def test_filter_by_market_cap(self, universe):
        """시가총액 필터링."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_market_cap=10e12,  # 10조 이상
        )
        codes = [s.code for s in filtered]
        assert "005930" in codes
        assert "000660" in codes
        assert "999999" not in codes  # 50억 → 제외

    def test_filter_by_avg_volume(self, universe):
        """일평균 거래대금 필터링."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_avg_volume=1e9,  # 10억 이상
        )
        codes = [s.code for s in filtered]
        assert "005930" in codes  # 7250억
        assert "999999" not in codes  # 100만원

    def test_filter_combined(self, universe):
        """복합 필터링 (시총 + 거래대금)."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_market_cap=10e12,
            min_avg_volume=1e9,
        )
        # 삼성전자, SK하이닉스, 카카오(시총20조, 거래대금 252.5억)
        assert len(filtered) >= 2
