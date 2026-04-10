"""주가 수집기 테스트 — pykrx 우선 + 네이버 폴백."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

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
def sample_ohlcv_df():
    """pykrx가 반환하는 OHLCV DataFrame."""
    return pd.DataFrame(
        {
            "시가": [56200, 56900],
            "고가": [58200, 57800],
            "저가": [55700, 56900],
            "종가": [56100, 57600],
            "거래량": [23527139, 19508076],
        },
        index=pd.to_datetime(["2025-04-04", "2025-04-03"]),
    )


@pytest.fixture
def collector(tmp_path):
    return StockCollector(db_path=tmp_path / "test.db")


class TestCollectOhlcvPykrx:
    """pykrx 기반 OHLCV 수집 테스트."""

    @patch("alphapulse.trading.data.stock_collector.StockCollector._collect_ohlcv_pykrx")
    def test_pykrx_success(self, mock_pykrx, collector):
        """pykrx 성공 시 네이버를 호출하지 않는다."""
        mock_pykrx.return_value = True

        with patch.object(collector, "_collect_ohlcv_naver") as mock_naver:
            collector.collect_ohlcv("005930", "20250403", "20250404")
            mock_naver.assert_not_called()

    @patch("alphapulse.trading.data.stock_collector.StockCollector._collect_ohlcv_pykrx")
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_pykrx_fail_naver_fallback(self, mock_get, mock_pykrx, collector):
        """pykrx 실패 시 네이버 폴백."""
        mock_pykrx.return_value = False

        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()

        resp_empty = MagicMock()
        resp_empty.status_code = 200
        resp_empty.text = "<table class='type2'></table>"
        resp_empty.raise_for_status = MagicMock()

        mock_get.side_effect = [resp, resp_empty]

        collector.collect_ohlcv("005930", "20250403", "20250404")

        result = collector.store.get_ohlcv("005930", "20250403", "20250404")
        assert len(result) == 2


class TestCollectOhlcvNaver:
    """네이버 금융 폴백 테스트."""

    @patch("alphapulse.trading.data.stock_collector.StockCollector._collect_ohlcv_pykrx", return_value=False)
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_naver_collect(self, mock_get, mock_pykrx, collector):
        """네이버에서 OHLCV를 수집한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()

        resp_empty = MagicMock()
        resp_empty.status_code = 200
        resp_empty.text = "<table class='type2'></table>"
        resp_empty.raise_for_status = MagicMock()

        mock_get.side_effect = [resp, resp_empty]

        collector.collect_ohlcv("005930", "20250403", "20250404")

        result = collector.store.get_ohlcv("005930", "20250403", "20250404")
        assert len(result) == 2
        row_04 = next(r for r in result if r["date"] == "20250404")
        assert row_04["close"] == 56100
        assert row_04["open"] == 56200

    @patch("alphapulse.trading.data.stock_collector.StockCollector._collect_ohlcv_pykrx", return_value=False)
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_naver_date_filter(self, mock_get, mock_pykrx, collector):
        """날짜 범위 밖 데이터는 제외한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_SISE_HTML
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        collector.collect_ohlcv("005930", "20250404", "20250404")

        result = collector.store.get_ohlcv("005930", "20250403", "20250404")
        assert len(result) == 1

    @patch("alphapulse.trading.data.stock_collector.StockCollector._collect_ohlcv_pykrx", return_value=False)
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_both_fail(self, mock_get, mock_pykrx, collector):
        """pykrx + 네이버 모두 실패 시 빈 결과."""
        mock_get.side_effect = Exception("timeout")

        collector.collect_ohlcv("005930", "20250403", "20250404")

        assert collector.store.get_ohlcv("005930", "20250403", "20250404") == []


class TestCollectStockList:
    @patch("alphapulse.trading.data.stock_collector.requests.get")
    def test_collect(self, mock_get, collector):
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

        stock = collector.store.get_stock("005930")
        assert stock is not None
        assert stock["name"] == "삼성전자"
