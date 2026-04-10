"""공매도 수집기 테스트 — KRX crawl4ai 기반."""

import logging

import pytest

from alphapulse.trading.data.short_collector import ShortCollector

SAMPLE_KRX_HTML = """
<html><body>
<table>
<tr><th>일자</th><th>전체</th><th>업틱룰적용</th><th>업틱룰예외</th><th>순보유잔고수량</th>
    <th>전체</th><th>업틱룰적용</th><th>업틱룰예외</th><th>순보유잔고금액</th></tr>
<tr><td>2025/04/04</td><td>1,259,931</td><td>667,944</td><td>591,987</td><td>45,000,000</td>
    <td>257,652,409,500</td><td>136,599,242,000</td><td>121,053,167,500</td><td>9,000,000,000,000</td></tr>
<tr><td>2025/04/03</td><td>1,065,990</td><td>416,237</td><td>649,753</td><td>44,500,000</td>
    <td>224,699,967,750</td><td>87,696,161,500</td><td>137,003,806,250</td><td>8,900,000,000,000</td></tr>
<tr><td>2025/04/02</td><td>800,000</td><td>400,000</td><td>400,000</td><td>44,000,000</td>
    <td>160,000,000,000</td><td>80,000,000,000</td><td>80,000,000,000</td><td>8,800,000,000,000</td></tr>
</table>
</body></html>
"""

EMPTY_HTML = "<html><body><table><tr><th>no data</th></tr></table></body></html>"


@pytest.fixture
def collector(tmp_path):
    return ShortCollector(db_path=tmp_path / "test.db")


class TestParseShortData:
    def test_parse_normal(self, collector):
        """정상 HTML에서 공매도 데이터를 파싱한다."""
        rows = collector._parse_short_data(
            SAMPLE_KRX_HTML, "005930", "20250401", "20250410"
        )
        assert len(rows) == 3
        assert rows[0][0] == "005930"  # code
        assert rows[0][1] == "20250404"  # date
        assert rows[0][2] == 1259931  # short_volume
        assert rows[0][3] == 45000000  # short_balance

    def test_parse_date_filter(self, collector):
        """날짜 범위 필터링."""
        rows = collector._parse_short_data(
            SAMPLE_KRX_HTML, "005930", "20250403", "20250404"
        )
        assert len(rows) == 2

    def test_parse_empty_html(self, collector):
        """빈 HTML이면 빈 리스트."""
        rows = collector._parse_short_data(
            EMPTY_HTML, "005930", "20250401", "20250410"
        )
        assert rows == []

    def test_parse_and_save_to_store(self, collector):
        """파싱 결과를 DB에 저장하고 조회한다."""
        rows = collector._parse_short_data(
            SAMPLE_KRX_HTML, "005930", "20250401", "20250410"
        )
        collector.store.save_short_interest_bulk(rows)

        result = collector.store.get_short_interest("005930", days=10)
        assert len(result) == 3
        assert result[0]["short_volume"] == 1259931


class TestParseInt:
    def test_normal(self):
        assert ShortCollector._parse_int("1,259,931") == 1259931

    def test_zero(self):
        assert ShortCollector._parse_int("0") == 0

    def test_dash(self):
        assert ShortCollector._parse_int("-") == 0

    def test_empty(self):
        assert ShortCollector._parse_int("") == 0


class TestCollectSync:
    def test_sync_collect_logs_info(self, collector, caplog):
        """동기 collect()는 안내 메시지를 출력한다."""
        with caplog.at_level(logging.INFO):
            collector.collect("005930", "20250401", "20250410")
        assert "collect_async" in caplog.text or "collect-short" in caplog.text


class TestStoreCompat:
    def test_save_and_get(self, collector):
        """기존 저장소 호환 — 수동 저장 + 조회."""
        collector.store.save_short_interest_bulk([
            ("005930", "20260409", 500_000, 10_000_000, 0.5, 100e9, 5_000_000),
        ])
        result = collector.store.get_short_interest("005930", days=1)
        assert len(result) == 1
        assert result[0]["short_ratio"] == 0.5
