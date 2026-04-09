"""일괄 수집기 테스트."""
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.data.bulk_collector import BulkCollector


@pytest.fixture
def collector(tmp_path):
    return BulkCollector(db_path=tmp_path / "test.db", delay=0, years=1)


class TestBulkCollector:
    @patch("alphapulse.trading.data.bulk_collector.stock")
    def test_collect_all_calls_collectors(self, mock_stock, collector):
        """전종목 수집이 수집기를 호출한다."""
        mock_stock.get_market_ticker_list.return_value = ["005930"]
        mock_stock.get_market_ticker_name.return_value = "삼성전자"
        mock_stock.get_market_ohlcv.return_value = MagicMock(empty=True)
        mock_stock.get_market_cap.return_value = MagicMock(empty=True)
        mock_stock.get_market_fundamental_by_ticker.return_value = MagicMock(
            empty=True
        )
        mock_stock.get_market_trading_value_by_date.return_value = MagicMock(
            empty=True
        )

        result = collector.collect_all(markets=["KOSPI"], resume=False)
        assert len(result) == 1
        assert result[0].market == "KOSPI"
        mock_stock.get_market_ticker_list.assert_called()

    def test_update_when_never_collected(self, collector):
        """미수집 상태에서 update -> collect_all 폴백."""
        with patch.object(
            collector, "collect_all", return_value=[]
        ) as mock_collect:
            collector.update(markets=["KOSPI"])
            mock_collect.assert_called_once()

    def test_update_already_current(self, collector):
        """이미 최신이면 수집하지 않는다."""
        # _find_latest_trading_date가 반환하는 날짜를 last_date와 동일하게 설정
        with patch.object(
            collector, "_find_latest_trading_date", return_value="20250404"
        ):
            collector.metadata.set_last_date("KOSPI", "ohlcv", "20250404")
            with patch.object(collector, "_collect_stock_list") as mock_collect:
                collector.update(markets=["KOSPI"])
                mock_collect.assert_not_called()

    def test_refresh_swallows_exceptions(self, collector):
        """refresh()는 예외를 전파하지 않는다."""
        with patch.object(collector, "update", side_effect=Exception("fail")):
            collector.refresh()  # should not raise

    def test_status(self, collector):
        """수집 현황을 반환한다."""
        collector.metadata.set_last_date("KOSPI", "ohlcv", "20260409")
        status = collector.status()
        assert "collection" in status
        assert len(status["collection"]) >= 1
