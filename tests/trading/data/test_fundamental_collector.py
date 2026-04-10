"""재무제표 수집기 테스트 — 네이버 금융 크롤링 기반."""

from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.data.fundamental_collector import FundamentalCollector

SAMPLE_MAIN_HTML = """
<html><body>
<table class="per_table">
<tr>
    <th>PERlEPS(2025.12)</th>
    <td>31.73배\nl\n6,564원</td>
</tr>
<tr>
    <th>추정PERlEPS</th>
    <td>6.00배\nl\n36,119원</td>
</tr>
<tr>
    <th>PBRlBPS (2025.12)</th>
    <td>3.25배\nl\n63,997원</td>
</tr>
<tr>
    <th>배당수익률l2025.12</th>
    <td>0.80%</td>
</tr>
</table>
</body></html>
"""

SAMPLE_NO_TABLE_HTML = "<html><body><p>no data</p></body></html>"


@pytest.fixture
def collector(tmp_path):
    return FundamentalCollector(db_path=tmp_path / "test.db")


class TestFundamentalCollector:
    @patch("alphapulse.trading.data.fundamental_collector.requests.get")
    def test_collect_fundamentals(self, mock_get, collector):
        """PER/PBR/배당수익률을 네이버 금융에서 크롤링한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_MAIN_HTML
        mock_get.return_value = resp

        collector.collect("20250404", codes=["005930"])

        result = collector.store.get_fundamentals("005930")
        assert result is not None
        assert result["per"] == 31.73
        assert result["pbr"] == 3.25
        assert result["dividend_yield"] == 0.80

    @patch("alphapulse.trading.data.fundamental_collector.requests.get")
    def test_collect_no_table(self, mock_get, collector):
        """per_table이 없으면 저장하지 않는다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_NO_TABLE_HTML
        mock_get.return_value = resp

        collector.collect("20250404", codes=["005930"])
        assert collector.store.get_fundamentals("005930") is None

    @patch("alphapulse.trading.data.fundamental_collector.requests.get")
    def test_collect_api_error(self, mock_get, collector):
        """HTTP 에러 시 해당 종목을 건너뛴다."""
        resp = MagicMock()
        resp.status_code = 500
        mock_get.return_value = resp

        collector.collect("20250404", codes=["005930"])
        assert collector.store.get_fundamentals("005930") is None

    @patch("alphapulse.trading.data.fundamental_collector.requests.get")
    def test_collect_network_error(self, mock_get, collector):
        """네트워크 에러 시 해당 종목을 건너뛴다."""
        mock_get.side_effect = Exception("timeout")

        collector.collect("20250404", codes=["005930"])
        assert collector.store.get_fundamentals("005930") is None

    def test_extract_number(self):
        """_extract_number가 다양한 형식을 올바르게 변환한다."""
        assert FundamentalCollector._extract_number("31.73배") == 31.73
        assert FundamentalCollector._extract_number("3.25배\nl\n63,997원") == 3.25
        assert FundamentalCollector._extract_number("0.80%") == 0.80
        assert FundamentalCollector._extract_number("") is None
        assert FundamentalCollector._extract_number("N/A") is None
