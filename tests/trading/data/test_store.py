"""종목 데이터 저장소 테스트."""

import pytest

from alphapulse.trading.data.store import TradingStore


@pytest.fixture
def store(tmp_path):
    return TradingStore(tmp_path / "test_trading.db")


class TestStocks:
    def test_upsert_and_get_stock(self, store):
        store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
        stock = store.get_stock("005930")
        assert stock is not None
        assert stock["name"] == "삼성전자"
        assert stock["market"] == "KOSPI"

    def test_get_missing_stock(self, store):
        assert store.get_stock("999999") is None

    def test_get_all_stocks(self, store):
        store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
        store.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)
        stocks = store.get_all_stocks(market="KOSPI")
        assert len(stocks) == 2


class TestOHLCV:
    def test_save_and_get_ohlcv(self, store):
        rows = [
            ("005930", "20260409", 72000, 73000, 71500, 72500, 10_000_000, 430e12),
            ("005930", "20260410", 72500, 74000, 72000, 73500, 12_000_000, 435e12),
        ]
        store.save_ohlcv_bulk(rows)

        result = store.get_ohlcv("005930", "20260409", "20260410")
        assert len(result) == 2
        assert result[0]["close"] == 72500
        assert result[1]["close"] == 73500

    def test_get_ohlcv_empty(self, store):
        result = store.get_ohlcv("005930", "20260409", "20260410")
        assert result == []


class TestFundamentals:
    def test_save_and_get(self, store):
        store.save_fundamental("005930", "20260331", per=12.5, pbr=1.3,
                                roe=15.2, revenue=300e12, operating_profit=50e12,
                                net_income=40e12, debt_ratio=35.0,
                                dividend_yield=2.1)
        result = store.get_fundamentals("005930")
        assert result is not None
        assert result["per"] == 12.5
        assert result["roe"] == 15.2


class TestInvestorFlow:
    def test_save_and_get(self, store):
        rows = [
            ("005930", "20260409", 50e9, 30e9, -80e9, 55.2),
            ("005930", "20260410", -20e9, 10e9, 10e9, 55.0),
        ]
        store.save_investor_flow_bulk(rows)

        result = store.get_investor_flow("005930", days=2)
        assert len(result) == 2
