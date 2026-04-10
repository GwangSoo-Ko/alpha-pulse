"""주가 수집기 테스트 -- 네이버 금융 스크래핑 기반."""

import pytest
from unittest.mock import patch, MagicMock

from alphapulse.trading.data.stock_collector import StockCollector

SAMPLE_SISE_HTML = """
<table class="type2">
<tr><th>날짜</th><th>종가</th><th>전일비</th><th>시가</th><th>고가</th><th>저가</th>
<th>거래량</th></tr>
<tr>
    <td><span>2025.04.04</span></td>
    <td><span>56,100</span></td>
    <td><span>하락</span></td>
    <td><span>56,200</span></td>
    <td><span>58,200</span></td>
    <td><span>55,700</span></td>
    <td><span>23,527,139</span></td>
</tr>
<tr>
    <td><span>2025.04.03</span></td>
    <td><span>57,600</span></td>
    <td><span>하락</span></td>
    <td><span>56,900</span></td>
    <td><span>57,800</span></td>
    <td><span>56,900</span></td>
    <td><span>19,508,076</span></td>
</tr>
</table>
"""

SAMPLE_STOCK_LIST_HTML = """
<table>
<tr><td><a class="tltle" href="/item/main.naver?code=005930">삼성전자</a></td></tr>
<tr><td><a class="tltle" href="/item/main.naver?code=000660">SK하이닉스</a></td></tr>
</table>
"""


@pytest.fixture
def collector(tmp_path):
    return StockCollector(db_path=tmp_path / "test.db")


class TestStockCollector:
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect_ohlcv(self, mock_get, collector):
        """OHLCV를 네이버 금융에서 수집하여 DB에 저장한다."""
        # 첫 번째 페이지: 데이터 있음
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.text = SAMPLE_SISE_HTML
        resp_ok.raise_for_status = MagicMock()

        # 두 번째 페이지: 데이터 없음 (종료)
        resp_empty = MagicMock()
        resp_empty.status_code = 200
        resp_empty.text = "<table class='type2'></table>"
        resp_empty.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_ok, resp_empty]

        collector.collect_ohlcv("005930", "20250403", "20250404")

        result = collector.store.get_ohlcv("005930", "20250403", "20250404")
        assert len(result) == 2
        # 2025.04.04 행
        row_04 = next(r for r in result if r["date"] == "20250404")
        assert row_04["close"] == 56100
        assert row_04["open"] == 56200
        assert row_04["high"] == 58200
        assert row_04["low"] == 55700
        assert row_04["volume"] == 23527139
        # 2025.04.03 행
        row_03 = next(r for r in result if r["date"] == "20250403")
        assert row_03["close"] == 57600

    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect_ohlcv_empty(self, mock_get, collector):
        """테이블이 비어있으면 저장하지 않는다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>no table</body></html>"
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        collector.collect_ohlcv("005930", "20250403", "20250404")

        assert collector.store.get_ohlcv("005930", "20250403", "20250404") == []

    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect_ohlcv_date_filter(self, mock_get, collector):
        """날짜 범위 밖 데이터는 제외한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        # start=end=20250404이면 04.03은 범위 밖
        collector.collect_ohlcv("005930", "20250404", "20250404")

        result = collector.store.get_ohlcv("005930", "20250403", "20250404")
        assert len(result) == 1
        assert result[0]["date"] == "20250404"

    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect_ohlcv_request_error(self, mock_get, collector):
        """네트워크 에러 시 수집을 중단한다."""
        mock_get.side_effect = Exception("timeout")

        collector.collect_ohlcv("005930", "20250403", "20250404")

        assert collector.store.get_ohlcv("005930", "20250403", "20250404") == []

    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect_stock_list(self, mock_get, collector):
        """종목 목록을 네이버 금융에서 수집한다."""
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.text = SAMPLE_STOCK_LIST_HTML
        resp_ok.raise_for_status = MagicMock()

        resp_empty = MagicMock()
        resp_empty.status_code = 200
        resp_empty.text = "<html></html>"
        resp_empty.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_ok, resp_empty]

        result = collector.collect_stock_list("20250404", "KOSPI")

        assert len(result) == 2
        assert result[0]["code"] == "005930"
        assert result[0]["name"] == "삼성전자"
        assert result[1]["code"] == "000660"

        # DB에 저장 확인
        stock = collector.store.get_stock("005930")
        assert stock is not None
        assert stock["name"] == "삼성전자"
