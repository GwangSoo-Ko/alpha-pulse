"""종목별 수급 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch

from alphapulse.trading.data.flow_collector import FlowCollector


@pytest.fixture
def collector(tmp_path):
    return FlowCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_trading_df():
    """pykrx 종목별 거래실적 DataFrame."""
    return pd.DataFrame({
        "기관합계": [50e9, -30e9],
        "기타법인": [5e9, -2e9],
        "개인": [-80e9, 50e9],
        "외국인합계": [25e9, -18e9],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


class TestFlowCollector:
    @patch("alphapulse.trading.data.flow_collector.stock")
    def test_collect(self, mock_stock, collector, sample_trading_df):
        """종목별 수급을 수집하여 DB에 저장한다."""
        mock_stock.get_market_trading_value_by_date.return_value = sample_trading_df

        collector.collect("005930", "20260409", "20260410")

        result = collector.store.get_investor_flow("005930", days=2)
        assert len(result) == 2
        assert result[0]["foreign_net"] == -18e9  # DESC 정렬 (최근순)

    @patch("alphapulse.trading.data.flow_collector.stock")
    def test_collect_empty(self, mock_stock, collector):
        mock_stock.get_market_trading_value_by_date.return_value = pd.DataFrame()
        collector.collect("005930", "20260409", "20260410")
        assert collector.store.get_investor_flow("005930") == []
