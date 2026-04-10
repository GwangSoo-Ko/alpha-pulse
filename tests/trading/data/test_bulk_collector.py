"""일괄 수집기 테스트 -- 네이버 금융 기반."""

from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.data.bulk_collector import BulkCollector

SAMPLE_SISE_HTML = """
<table class="type2">
<tr>
    <td><span>2025.04.04</span></td>
    <td><span>56,100</span></td>
    <td><span>하락</span></td>
    <td><span>56,200</span></td>
    <td><span>58,200</span></td>
    <td><span>55,700</span></td>
    <td><span>23,527,139</span></td>
</tr>
</table>
"""

SAMPLE_STOCK_LIST_HTML = """
<table>
<tr><td><a class="tltle" href="/item/main.naver?code=005930">삼성전자</a></td></tr>
</table>
"""


@pytest.fixture
def collector(tmp_path):
    return BulkCollector(db_path=tmp_path / "test.db", delay=0, years=1)


class TestBulkCollector:
    def test_collect_all_calls_collectors(self, collector):
        """전종목 수집이 수집기를 호출한다."""
        with patch.object(
            collector, "_find_latest_trading_date", return_value="20250404"
        ), patch.object(
            collector, "_collect_stock_list", return_value=["005930"]
        ), patch.object(
            collector.stock_collector, "collect_ohlcv"
        ), patch.object(
            collector.fundamental_collector, "collect"
        ), patch.object(
            collector.flow_collector, "collect"
        ):
            result = collector.collect_all(markets=["KOSPI"], resume=False)
            assert len(result) == 1
            assert result[0].market == "KOSPI"
            collector.stock_collector.collect_ohlcv.assert_called_once()
            collector.fundamental_collector.collect.assert_called_once()
            collector.flow_collector.collect.assert_called_once()

    def test_update_when_never_collected(self, collector):
        """미수집 상태에서 update -> collect_all 폴백."""
        with patch.object(
            collector, "collect_all", return_value=[]
        ) as mock_collect:
            collector.update(markets=["KOSPI"])
            mock_collect.assert_called_once()

    def test_update_already_current(self, collector):
        """이미 최신이면 수집하지 않는다."""
        with patch.object(
            collector, "_find_latest_trading_date", return_value="20250404"
        ):
            collector.metadata.set_last_date("KOSPI", "ohlcv", "20250404")
            with patch.object(
                collector, "_collect_stock_list"
            ) as mock_collect:
                collector.update(markets=["KOSPI"])
                mock_collect.assert_not_called()

    def test_refresh_swallows_exceptions(self, collector):
        """refresh()는 예외를 전파하지 않는다."""
        with patch.object(collector, "update", side_effect=Exception("fail")):
            collector.refresh()  # should not raise

    def test_status(self, collector):
        """수집 현황을 반환한다."""
        collector.metadata.set_last_date("KOSPI", "ohlcv", "20250404")
        status = collector.status()
        assert "collection" in status
        assert len(status["collection"]) >= 1

    @patch("alphapulse.trading.data.bulk_collector.requests.get")
    def test_find_latest_trading_date(self, mock_get, collector):
        """네이버 금융에서 최근 거래일을 탐색한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = collector._find_latest_trading_date()
        assert result == "20250404"

    @patch("alphapulse.trading.data.bulk_collector.requests.get")
    def test_find_latest_trading_date_fallback(self, mock_get, collector):
        """네이버 금융 실패 시 어제 날짜를 반환한다."""
        mock_get.side_effect = Exception("network error")

        result = collector._find_latest_trading_date()
        # 어제 날짜 (YYYYMMDD 형식)
        assert len(result) == 8
        assert result.isdigit()
