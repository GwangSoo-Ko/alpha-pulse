"""종목별 수급 수집기 테스트 -- 네이버 금융 기반."""

import pytest
from unittest.mock import patch, MagicMock

from alphapulse.trading.data.flow_collector import FlowCollector

# frgn.naver 페이지에는 table.type2가 2개 있음. 두 번째가 수급 데이터.
SAMPLE_FRGN_HTML = """
<table class="type2">
<tr><th>첫 번째 테이블 (무시)</th></tr>
</table>
<table class="type2">
<tr><th>날짜</th><th>종가</th><th>전일비</th><th>등락률</th><th>거래량</th>
<th>기관순매매</th><th>외국인순매매</th><th>보유주수</th><th>보유율</th></tr>
<tr>
    <td>2025.04.04</td>
    <td>56,100</td>
    <td>하락 1,500</td>
    <td>-2.60%</td>
    <td>23,527,139</td>
    <td>+1,500</td>
    <td>-2,300</td>
    <td>3,200,000</td>
    <td>55.30%</td>
</tr>
<tr>
    <td>2025.04.03</td>
    <td>57,600</td>
    <td>상승 700</td>
    <td>+1.23%</td>
    <td>19,508,076</td>
    <td>-800</td>
    <td>+1,200</td>
    <td>3,202,300</td>
    <td>55.34%</td>
</tr>
</table>
"""


@pytest.fixture
def collector(tmp_path):
    return FlowCollector(db_path=tmp_path / "test.db")


class TestFlowCollector:
    @patch("alphapulse.trading.data.flow_collector.requests.get")
    def test_collect(self, mock_get, collector):
        """종목별 수급을 네이버 금융에서 수집하여 DB에 저장한다."""
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.text = SAMPLE_FRGN_HTML
        resp_ok.raise_for_status = MagicMock()

        resp_empty = MagicMock()
        resp_empty.status_code = 200
        resp_empty.text = "<table class='type2'></table>"
        resp_empty.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_ok, resp_empty]

        collector.collect("005930", "20250403", "20250404")

        result = collector.store.get_investor_flow("005930", days=10)
        assert len(result) == 2
        # DESC 정렬 -> 최근(04.04)이 먼저
        assert result[0]["date"] == "20250404"
        assert result[0]["institutional_net"] == 1500
        assert result[0]["foreign_net"] == -2300
        assert result[0]["individual_net"] == -(1500 + (-2300))  # 800
        assert result[0]["foreign_holding_pct"] == 55.30

    @patch("alphapulse.trading.data.flow_collector.requests.get")
    def test_collect_empty(self, mock_get, collector):
        """테이블이 부족하면 저장하지 않는다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>no data</body></html>"
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        collector.collect("005930", "20250403", "20250404")

        assert collector.store.get_investor_flow("005930") == []

    @patch("alphapulse.trading.data.flow_collector.requests.get")
    def test_collect_date_filter(self, mock_get, collector):
        """날짜 범위 밖 데이터는 제외한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_FRGN_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        collector.collect("005930", "20250404", "20250404")

        result = collector.store.get_investor_flow("005930", days=10)
        assert len(result) == 1
        assert result[0]["date"] == "20250404"

    @patch("alphapulse.trading.data.flow_collector.requests.get")
    def test_collect_request_error(self, mock_get, collector):
        """네트워크 에러 시 수집을 중단한다."""
        mock_get.side_effect = Exception("connection error")

        collector.collect("005930", "20250403", "20250404")

        assert collector.store.get_investor_flow("005930") == []

    def test_parse_number(self):
        """_parse_number가 다양한 형식을 올바르게 파싱한다."""
        assert FlowCollector._parse_number("+1,234") == 1234
        assert FlowCollector._parse_number("-1,234") == -1234
        assert FlowCollector._parse_number("0") == 0
        assert FlowCollector._parse_number("  ") == 0
        assert FlowCollector._parse_number("500") == 500
