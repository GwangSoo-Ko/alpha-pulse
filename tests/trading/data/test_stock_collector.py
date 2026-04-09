"""주가 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from alphapulse.trading.data.stock_collector import StockCollector


@pytest.fixture
def collector(tmp_path):
    return StockCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_ohlcv_df():
    """pykrx가 반환하는 OHLCV DataFrame 형식."""
    return pd.DataFrame({
        "시가": [72000, 72500],
        "고가": [73000, 74000],
        "저가": [71500, 72000],
        "종가": [72500, 73500],
        "거래량": [10_000_000, 12_000_000],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


@pytest.fixture
def sample_cap_df():
    """pykrx가 반환하는 시가총액 DataFrame."""
    return pd.DataFrame({
        "시가총액": [430_000_000_000_000, 435_000_000_000_000],
        "상장주식수": [5_969_782_550, 5_969_782_550],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


class TestStockCollector:
    @patch("alphapulse.trading.data.stock_collector.stock")
    def test_collect_ohlcv(self, mock_stock, collector,
                            sample_ohlcv_df, sample_cap_df):
        """OHLCV + 시가총액을 수집하여 DB에 저장한다."""
        mock_stock.get_market_ohlcv.return_value = sample_ohlcv_df
        mock_stock.get_market_cap.return_value = sample_cap_df

        collector.collect_ohlcv("005930", "20260409", "20260410")

        result = collector.store.get_ohlcv("005930", "20260409", "20260410")
        assert len(result) == 2
        assert result[0]["close"] == 72500
        assert result[0]["market_cap"] == 430_000_000_000_000

    @patch("alphapulse.trading.data.stock_collector.stock")
    def test_collect_ohlcv_empty(self, mock_stock, collector):
        """데이터가 없으면 저장하지 않는다."""
        mock_stock.get_market_ohlcv.return_value = pd.DataFrame()
        mock_stock.get_market_cap.return_value = pd.DataFrame()

        collector.collect_ohlcv("005930", "20260409", "20260410")

        result = collector.store.get_ohlcv("005930", "20260409", "20260410")
        assert result == []
