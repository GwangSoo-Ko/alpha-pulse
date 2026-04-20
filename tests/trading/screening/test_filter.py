"""투자 제외 필터 테스트."""
import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.screening.filter import StockFilter


@pytest.fixture
def stocks():
    return [
        Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체"),
        Stock(code="000660", name="SK하이닉스", market="KOSPI", sector="반도체"),
        Stock(code="035720", name="카카오", market="KOSPI", sector="IT"),
        Stock(code="069500", name="KODEX 200", market="ETF"),
    ]


@pytest.fixture
def stock_data():
    return {
        "005930": {"market_cap": 430e12, "avg_volume": 500e9},
        "000660": {"market_cap": 120e12, "avg_volume": 200e9},
        "035720": {"market_cap": 20e12, "avg_volume": 25e9},
        "069500": {"market_cap": 50e12, "avg_volume": 7e9},
    }


class TestStockFilter:
    def test_no_filter(self, stocks, stock_data):
        f = StockFilter({})
        result = f.apply(stocks, stock_data)
        assert len(result) == 4

    def test_min_market_cap(self, stocks, stock_data):
        f = StockFilter({"min_market_cap": 50e12})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "005930" in codes
        assert "035720" not in codes

    def test_min_avg_volume(self, stocks, stock_data):
        f = StockFilter({"min_avg_volume": 10e9})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "005930" in codes
        assert "069500" not in codes

    def test_exclude_sectors(self, stocks, stock_data):
        f = StockFilter({"exclude_sectors": ["IT"]})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "035720" not in codes

    def test_combined(self, stocks, stock_data):
        f = StockFilter({"min_market_cap": 100e12, "exclude_sectors": ["IT"]})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert codes == ["005930", "000660"]
