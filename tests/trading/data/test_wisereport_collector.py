"""wisereport 수집기 테스트 — 네이버 기업정보 크롤링 기반."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.trading.data.wisereport_collector import WisereportCollector

# ── 샘플 HTML ────────────────────────────────────────────────────

SAMPLE_STATIC_HTML = """
<html><body>

<!-- 시장정보 테이블 -->
<table class="gHead01 all-width">
<tbody>
<tr>
    <th>시가총액</th>
    <td>4,217,873</td>
</tr>
<tr>
    <th>52주최고</th>
    <td>88,800</td>
</tr>
<tr>
    <th>52주최저</th>
    <td>49,900</td>
</tr>
<tr>
    <th>52주베타</th>
    <td>1.23</td>
</tr>
<tr>
    <th>외국인지분율</th>
    <td>55.21%</td>
</tr>
<tr>
    <th>수익률(1M)</th>
    <td>-3.52%</td>
</tr>
<tr>
    <th>수익률(3M)</th>
    <td>8.15%</td>
</tr>
<tr>
    <th>수익률(6M)</th>
    <td>-12.30%</td>
</tr>
<tr>
    <th>수익률(1Y)</th>
    <td>15.20%</td>
</tr>
</tbody>
</table>

<!-- 주요지표 테이블 -->
<table class="gHead01 all-width" id="cTB11">
<thead>
<tr>
    <th>주요지표</th>
    <th>2024/12(A)</th>
    <th>2025/12(E)</th>
</tr>
</thead>
<tbody>
<tr>
    <td>PER(배)</td>
    <td>12.50</td>
    <td>9.80</td>
</tr>
<tr>
    <td>PBR(배)</td>
    <td>1.30</td>
    <td></td>
</tr>
<tr>
    <td>PCR(배)</td>
    <td>5.20</td>
    <td></td>
</tr>
<tr>
    <td>EV/EBITDA(배)</td>
    <td>6.80</td>
    <td></td>
</tr>
<tr>
    <td>EPS(원)</td>
    <td>5,800</td>
    <td>7,200</td>
</tr>
<tr>
    <td>BPS(원)</td>
    <td>56,000</td>
    <td></td>
</tr>
<tr>
    <td>EBITDA(억원)</td>
    <td>85,000</td>
    <td></td>
</tr>
<tr>
    <td>현금DPS(원)</td>
    <td>1,444</td>
    <td></td>
</tr>
<tr>
    <td>배당수익률(%)</td>
    <td>2.10</td>
    <td></td>
</tr>
</tbody>
</table>

<!-- 컨센서스 테이블 -->
<table class="gHead01 all-width" id="cTB13">
<thead>
<tr>
    <th>투자의견</th>
    <th>목표주가(원)</th>
    <th>EPS(원)</th>
    <th>PER(배)</th>
    <th>추정기관수</th>
</tr>
</thead>
<tbody>
<tr>
    <td>4.00</td>
    <td>95,000</td>
    <td>7,200</td>
    <td>9.80</td>
    <td>32</td>
</tr>
</tbody>
</table>

<!-- 주요주주 -->
<table class="gHead01 all-width" id="cTB14">
<thead><tr><th>주요주주</th><th>지분율(%)</th></tr></thead>
<tbody>
<tr><td>삼성물산 외 8인</td><td>20.35</td></tr>
<tr><td>국민연금공단</td><td>11.52</td></tr>
</tbody>
</table>

</body></html>
"""

SAMPLE_FINANCIAL_HTML = """
<html><body>
<table class="gHead01 all-width" id="cTB15">
<thead>
<tr>
    <th>주요재무정보</th>
    <th>2021/12</th>
    <th>2022/12</th>
    <th>2023/12</th>
    <th>2024/12</th>
</tr>
</thead>
<tbody>
<tr>
    <td>매출액</td>
    <td>2,796,048</td>
    <td>3,022,314</td>
    <td>2,588,908</td>
    <td>3,006,720</td>
</tr>
<tr>
    <td>영업이익</td>
    <td>516,339</td>
    <td>433,766</td>
    <td>65,670</td>
    <td>328,215</td>
</tr>
<tr>
    <td>순이익</td>
    <td>399,075</td>
    <td>557,590</td>
    <td>154,870</td>
    <td>348,201</td>
</tr>
<tr>
    <td>ROE(%)</td>
    <td>12.50</td>
    <td>16.40</td>
    <td>4.20</td>
    <td>9.80</td>
</tr>
<tr>
    <td>ROA(%)</td>
    <td>8.30</td>
    <td>10.50</td>
    <td>2.70</td>
    <td>6.50</td>
</tr>
<tr>
    <td>부채비율(%)</td>
    <td>39.80</td>
    <td>42.10</td>
    <td>40.50</td>
    <td>38.20</td>
</tr>
<tr>
    <td>영업이익률(%)</td>
    <td>18.50</td>
    <td>14.30</td>
    <td>2.50</td>
    <td>10.90</td>
</tr>
<tr>
    <td>순이익률(%)</td>
    <td>14.30</td>
    <td>18.40</td>
    <td>5.98</td>
    <td>11.60</td>
</tr>
</tbody>
</table>
</body></html>
"""

SAMPLE_EMPTY_HTML = "<html><body><p>no data</p></body></html>"


@pytest.fixture
def collector(tmp_path):
    """테스트용 WisereportCollector."""
    return WisereportCollector(db_path=tmp_path / "test.db")


# ── 정적 수집 테스트 ──────────────────────────────────────────────


class TestCollectStatic:
    """collect_static 정적 데이터 수집 테스트."""

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_market_info(self, mock_get, collector):
        """시가총액, 베타, 외국인지분율, 수익률을 파싱한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_STATIC_HTML
        mock_get.return_value = resp

        data = collector.collect_static("005930", "20260409")

        assert data["market_cap"] == 4_217_873
        assert data["beta"] == 1.23
        assert data["foreign_pct"] == 55.21
        assert data["high_52w"] == 88_800
        assert data["low_52w"] == 49_900
        assert data["return_1m"] == -3.52
        assert data["return_3m"] == 8.15
        assert data["return_6m"] == -12.30
        assert data["return_1y"] == 15.20

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_key_indicators(self, mock_get, collector):
        """주요지표 (PER, PBR, EPS 등) 실적/추정을 파싱한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_STATIC_HTML
        mock_get.return_value = resp

        data = collector.collect_static("005930", "20260409")

        assert data["per"] == 12.50
        assert data["pbr"] == 1.30
        assert data["pcr"] == 5.20
        assert data["ev_ebitda"] == 6.80
        assert data["eps"] == 5_800
        assert data["bps"] == 56_000
        assert data["dividend_yield"] == 2.10
        assert data["est_per"] == 9.80
        assert data["est_eps"] == 7_200

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_consensus(self, mock_get, collector):
        """컨센서스 (목표가, 투자의견, 추정기관수)를 파싱한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_STATIC_HTML
        mock_get.return_value = resp

        data = collector.collect_static("005930", "20260409")

        assert data["target_price"] == 95_000
        assert data["consensus_opinion"] == 4.00
        assert data["analyst_count"] == 32

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_saves_to_store(self, mock_get, collector):
        """수집된 데이터가 DB에 저장된다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_STATIC_HTML
        mock_get.return_value = resp

        collector.collect_static("005930", "20260409")

        stored = collector.store.get_wisereport("005930")
        assert stored is not None
        assert stored["market_cap"] == 4_217_873
        assert stored["per"] == 12.50

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_empty_html(self, mock_get, collector):
        """데이터가 없으면 빈 dict를 반환한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_EMPTY_HTML
        mock_get.return_value = resp

        data = collector.collect_static("005930", "20260409")
        assert data == {}

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_http_error(self, mock_get, collector):
        """HTTP 에러 시 빈 dict를 반환한다."""
        resp = MagicMock()
        resp.status_code = 500
        mock_get.return_value = resp

        data = collector.collect_static("005930", "20260409")
        assert data == {}

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_network_error(self, mock_get, collector):
        """네트워크 에러 시 빈 dict를 반환한다."""
        mock_get.side_effect = Exception("timeout")

        data = collector.collect_static("005930", "20260409")
        assert data == {}


# ── 배치 수집 테스트 ──────────────────────────────────────────────


class TestCollectStaticBatch:
    """collect_static_batch 배치 수집 테스트."""

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_batch_multiple_codes(self, mock_get, collector):
        """여러 종목을 순차 수집한다."""
        resp = MagicMock()
        resp.status_code = 200
        resp.text = SAMPLE_STATIC_HTML
        mock_get.return_value = resp

        results = collector.collect_static_batch(
            ["005930", "000660"], "20260409"
        )

        assert len(results) == 2
        assert "005930" in results
        assert "000660" in results
        assert results["005930"]["market_cap"] == 4_217_873

    @patch("alphapulse.trading.data.wisereport_collector.requests.get")
    def test_batch_partial_failure(self, mock_get, collector):
        """일부 종목 실패 시 나머지는 정상 수집한다."""
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = SAMPLE_STATIC_HTML

        fail_resp = MagicMock()
        fail_resp.status_code = 500

        mock_get.side_effect = [ok_resp, fail_resp]

        results = collector.collect_static_batch(
            ["005930", "000660"], "20260409"
        )

        assert len(results) == 1
        assert "005930" in results


# ── 재무 시계열 (crawl4ai) 테스트 ─────────────────────────────────


class TestCollectFinancials:
    """collect_financials (crawl4ai 기반) 테스트."""

    async def test_financials_parsing(self, collector):
        """JS 렌더링 후 재무 시계열을 파싱한다."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.html = SAMPLE_FINANCIAL_HTML

        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.return_value = mock_result
        mock_crawler_instance.__aenter__ = AsyncMock(
            return_value=mock_crawler_instance
        )
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler_instance,
        ):
            data = await collector.collect_financials("005930", "20260409")

        assert data["revenue"] == 3_006_720
        assert data["operating_profit"] == 328_215
        assert data["net_income"] == 348_201
        assert data["roe"] == 9.80
        assert data["roa"] == 6.50
        assert data["debt_ratio"] == 38.20
        assert data["operating_margin"] == 10.90
        assert data["net_margin"] == 11.60

    async def test_financials_saves_to_store(self, collector):
        """수집된 재무 데이터가 DB에 저장된다."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.html = SAMPLE_FINANCIAL_HTML

        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.return_value = mock_result
        mock_crawler_instance.__aenter__ = AsyncMock(
            return_value=mock_crawler_instance
        )
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler_instance,
        ):
            await collector.collect_financials("005930", "20260409")

        stored = collector.store.get_wisereport("005930")
        assert stored is not None
        assert stored["revenue"] == 3_006_720

    async def test_financials_crawl_failure(self, collector):
        """크롤링 실패 시 빈 dict를 반환한다."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.html = ""

        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.return_value = mock_result
        mock_crawler_instance.__aenter__ = AsyncMock(
            return_value=mock_crawler_instance
        )
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler_instance,
        ):
            data = await collector.collect_financials("005930", "20260409")

        assert data == {}

    async def test_financials_exception(self, collector):
        """예외 발생 시 빈 dict를 반환한다."""
        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.side_effect = Exception("browser crash")
        mock_crawler_instance.__aenter__ = AsyncMock(
            return_value=mock_crawler_instance
        )
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler_instance,
        ):
            data = await collector.collect_financials("005930", "20260409")

        assert data == {}


# ── 재무 배치 (crawl4ai) 테스트 ───────────────────────────────────


class TestCollectFinancialsBatch:
    """collect_financials_batch 배치 테스트."""

    async def test_batch_multiple_codes(self, collector):
        """여러 종목 재무 데이터를 순차 수집한다."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.html = SAMPLE_FINANCIAL_HTML

        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.return_value = mock_result
        mock_crawler_instance.__aenter__ = AsyncMock(
            return_value=mock_crawler_instance
        )
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler_instance,
        ):
            results = await collector.collect_financials_batch(
                ["005930", "000660"], "20260409"
            )

        assert len(results) == 2
        assert "005930" in results
        assert results["005930"]["revenue"] == 3_006_720


# ── Store 테스트 ──────────────────────────────────────────────────


class TestWisereportStore:
    """wisereport_data 테이블 CRUD 테스트."""

    def test_save_and_get(self, collector):
        """저장 후 조회가 정상 동작한다."""
        collector.store.save_wisereport(
            "005930", "20260409",
            market_cap=4_217_873, beta=1.23, per=12.5,
            revenue=3_006_720, roe=9.80,
        )
        result = collector.store.get_wisereport("005930")
        assert result is not None
        assert result["market_cap"] == 4_217_873
        assert result["beta"] == 1.23
        assert result["per"] == 12.5
        assert result["revenue"] == 3_006_720

    def test_get_missing(self, collector):
        """미존재 종목은 None을 반환한다."""
        assert collector.store.get_wisereport("999999") is None

    def test_upsert(self, collector):
        """같은 (code, date)에 재저장하면 업데이트된다."""
        collector.store.save_wisereport(
            "005930", "20260409", per=10.0
        )
        collector.store.save_wisereport(
            "005930", "20260409", per=12.5
        )
        result = collector.store.get_wisereport("005930")
        assert result["per"] == 12.5

    def test_latest_date(self, collector):
        """가장 최근 날짜의 데이터를 반환한다."""
        collector.store.save_wisereport(
            "005930", "20260408", per=10.0
        )
        collector.store.save_wisereport(
            "005930", "20260409", per=12.5
        )
        result = collector.store.get_wisereport("005930")
        assert result["date"] == "20260409"
        assert result["per"] == 12.5


# ── 파서 유틸리티 테스트 ──────────────────────────────────────────


class TestParseHelpers:
    """파서 헬퍼 함수 테스트."""

    def test_parse_number_basic(self, collector):
        """기본 숫자 파싱."""
        assert collector._parse_number("12.50") == 12.50

    def test_parse_number_comma(self, collector):
        """콤마 포함 숫자 파싱."""
        assert collector._parse_number("4,217,873") == 4_217_873

    def test_parse_number_percent(self, collector):
        """퍼센트 기호 제거."""
        assert collector._parse_number("55.21%") == 55.21

    def test_parse_number_negative(self, collector):
        """음수 파싱."""
        assert collector._parse_number("-3.52%") == -3.52

    def test_parse_number_empty(self, collector):
        """빈 문자열은 None."""
        assert collector._parse_number("") is None

    def test_parse_number_na(self, collector):
        """N/A는 None."""
        assert collector._parse_number("N/A") is None

    def test_parse_number_unit(self, collector):
        """단위 포함 문자열에서 숫자 추출."""
        assert collector._parse_number("1.23배") == 1.23
