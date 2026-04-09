"""재무제표 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch

from alphapulse.trading.data.fundamental_collector import FundamentalCollector


@pytest.fixture
def collector(tmp_path):
    return FundamentalCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_fundamental_df():
    """pykrx가 반환하는 펀더멘털 DataFrame."""
    return pd.DataFrame({
        "BPS": [65000],
        "PER": [12.5],
        "PBR": [1.3],
        "EPS": [5800],
        "DIV": [2.1],
        "DPS": [1500],
    }, index=["005930"])


class TestFundamentalCollector:
    @patch("alphapulse.trading.data.fundamental_collector.stock")
    def test_collect_fundamentals(self, mock_stock, collector,
                                    sample_fundamental_df):
        """PER/PBR/배당수익률을 수집하여 DB에 저장한다."""
        mock_stock.get_market_fundamental_by_ticker.return_value = sample_fundamental_df

        collector.collect("20260409", codes=["005930"])

        result = collector.store.get_fundamentals("005930")
        assert result is not None
        assert result["per"] == 12.5
        assert result["pbr"] == 1.3
        assert result["dividend_yield"] == 2.1

    @patch("alphapulse.trading.data.fundamental_collector.stock")
    def test_collect_empty(self, mock_stock, collector):
        """데이터가 없으면 저장하지 않는다."""
        mock_stock.get_market_fundamental_by_ticker.return_value = pd.DataFrame()

        collector.collect("20260409", codes=["005930"])

        assert collector.store.get_fundamentals("005930") is None
