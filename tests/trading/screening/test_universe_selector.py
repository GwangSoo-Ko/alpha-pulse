"""전략별 유니버스 선택 테스트."""
import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.screening.universe_selector import UniverseSelector


@pytest.fixture
def all_stocks():
    return [
        Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체"),
        Stock(code="000660", name="SK하이닉스", market="KOSPI", sector="반도체"),
        Stock(code="035720", name="카카오", market="KOSPI", sector="IT"),
        Stock(code="069500", name="KODEX 200", market="ETF"),
        Stock(code="122630", name="KODEX 레버리지", market="ETF"),
    ]


@pytest.fixture
def stock_data():
    return {
        "005930": {"market_cap": 430e12, "avg_volume": 500e9},
        "000660": {"market_cap": 120e12, "avg_volume": 200e9},
        "035720": {"market_cap": 20e12, "avg_volume": 25e9},
        "069500": {"market_cap": 50e12, "avg_volume": 7e9},
        "122630": {"market_cap": 10e12, "avg_volume": 5e9},
    }


class TestUniverseSelector:
    def test_default_all(self, all_stocks, stock_data):
        selector = UniverseSelector()
        result = selector.select("balanced", all_stocks, stock_data)
        assert len(result) == 5

    def test_momentum_excludes_etf(self, all_stocks, stock_data):
        selector = UniverseSelector(strategy_configs={
            "momentum": {"include_markets": ["KOSPI", "KOSDAQ"]}
        })
        result = selector.select("momentum", all_stocks, stock_data)
        assert all(s.market != "ETF" for s in result)

    def test_topdown_etf_only(self, all_stocks, stock_data):
        selector = UniverseSelector(strategy_configs={
            "topdown_etf": {"include_markets": ["ETF"]}
        })
        result = selector.select("topdown_etf", all_stocks, stock_data)
        assert all(s.market == "ETF" for s in result)

    def test_with_volume_filter(self, all_stocks, stock_data):
        selector = UniverseSelector(strategy_configs={
            "value": {"min_avg_volume": 10e9}
        })
        result = selector.select("value", all_stocks, stock_data)
        codes = [s.code for s in result]
        assert "069500" not in codes
        assert "122630" not in codes
