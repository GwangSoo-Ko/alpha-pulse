"""데이터 수집기 단위 테스트

외부 API 호출을 모킹하여 각 수집기의 로직을 검증한다.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from alphapulse.market.collectors.base import BaseCollector, retry
from alphapulse.market.collectors.fdr_collector import FdrCollector, _to_dash_date
from alphapulse.market.collectors.fred_collector import FredCollector
from alphapulse.market.collectors.krx_scraper import KrxScraper
from alphapulse.market.collectors.pykrx_collector import PykrxCollector

# ---------------------------------------------------------------------------
# retry 데코레이터 테스트
# ---------------------------------------------------------------------------

class TestRetryDecorator:
    """retry 데코레이터 테스트."""

    def test_success_on_first_attempt(self):
        """첫 번째 시도에서 성공하면 바로 반환한다."""
        call_count = 0

        @retry(max_retries=3, delay=0)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_success_after_retries(self):
        """재시도 후 성공하면 결과를 반환한다."""
        call_count = 0

        @retry(max_retries=3, delay=0)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3

    def test_raises_after_all_retries_exhausted(self):
        """모든 재시도 실패 시 마지막 예외를 발생시킨다."""

        @retry(max_retries=2, delay=0)
        def always_fail():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            always_fail()


# ---------------------------------------------------------------------------
# BaseCollector 테스트
# ---------------------------------------------------------------------------

class TestBaseCollector:
    """BaseCollector 캐시 메서드 테스트."""

    def test_get_cached_with_no_cache(self):
        """cache=None이면 None을 반환한다."""

        class DummyCollector(BaseCollector):
            pass

        collector = DummyCollector(cache=None)
        assert collector._get_cached("key") is None

    def test_get_cached_with_cache(self):
        """cache가 있으면 cache.get을 호출한다."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = pd.DataFrame({"a": [1]})

        class DummyCollector(BaseCollector):
            pass

        collector = DummyCollector(cache=mock_cache)
        result = collector._get_cached("key", ttl_minutes=30)

        mock_cache.get.assert_called_once_with("key", 30)
        assert isinstance(result, pd.DataFrame)

    def test_set_cached_with_no_cache(self):
        """cache=None이면 set 호출이 무시된다."""

        class DummyCollector(BaseCollector):
            pass

        collector = DummyCollector(cache=None)
        # 예외 없이 정상 동작
        collector._set_cached("key", pd.DataFrame())

    def test_set_cached_with_cache(self):
        """cache가 있으면 cache.set을 호출한다."""
        mock_cache = MagicMock()

        class DummyCollector(BaseCollector):
            pass

        collector = DummyCollector(cache=mock_cache)
        df = pd.DataFrame({"a": [1]})
        collector._set_cached("key", df)

        mock_cache.set.assert_called_once_with("key", df)


# ---------------------------------------------------------------------------
# PykrxCollector 테스트
# ---------------------------------------------------------------------------

class TestPykrxCollector:
    """PykrxCollector 테스트. pykrx.stock 모듈을 모킹한다."""

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_investor_trading(
        self,
        mock_stock,
        sample_investor_trading_df,
        sample_start_date,
        sample_end_date,
    ):
        """투자자별 매매동향을 정상적으로 반환한다 (네이버 API 우선)."""
        collector = PykrxCollector()
        # 네이버 API mock
        collector._naver_get = MagicMock(return_value={
            "bizdate": "20260313",
            "personalValue": "+8,000",
            "foreignValue": "-5,000",
            "institutionalValue": "-3,000",
        })

        result = collector.get_investor_trading(
            sample_start_date, sample_end_date, "KOSPI"
        )

        assert not result.empty
        assert "기관합계" in result.columns
        assert "외국인합계" in result.columns

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_investor_trading_empty(
        self,
        mock_stock,
        sample_start_date,
        sample_end_date,
    ):
        """네이버 API와 pykrx 모두 실패하면 빈 DataFrame을 반환한다."""
        mock_stock.get_market_trading_value_by_date.return_value = pd.DataFrame()

        collector = PykrxCollector()
        collector._naver_get = MagicMock(return_value=None)
        result = collector.get_investor_trading(
            sample_start_date, sample_end_date
        )

        assert result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_investor_trading_futures(
        self,
        mock_stock,
        sample_investor_trading_df,
        sample_start_date,
        sample_end_date,
    ):
        """선물 투자자별 매매동향을 정상적으로 반환한다."""
        mock_stock.get_market_trading_value_by_date.return_value = (
            sample_investor_trading_df
        )

        collector = PykrxCollector()
        result = collector.get_investor_trading_futures(
            sample_start_date, sample_end_date
        )

        mock_stock.get_market_trading_value_by_date.assert_called_once_with(
            sample_start_date, sample_end_date, "선물"
        )
        assert not result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_market_cap_top(
        self,
        mock_stock,
        sample_market_cap_df,
        sample_date,
    ):
        """시가총액 상위 종목을 정상적으로 반환한다."""
        mock_stock.get_market_cap_by_ticker.return_value = sample_market_cap_df

        collector = PykrxCollector()
        result = collector.get_market_cap_top(sample_date, "KOSPI", n=3)

        mock_stock.get_market_cap_by_ticker.assert_called_once_with(
            sample_date, "KOSPI"
        )
        assert len(result) == 3
        # 시가총액 내림차순 정렬 확인
        assert result["시가총액"].iloc[0] >= result["시가총액"].iloc[1]

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_market_cap_top_empty(
        self,
        mock_stock,
        sample_date,
    ):
        """빈 데이터가 반환되면 빈 DataFrame을 반환한다."""
        mock_stock.get_market_cap_by_ticker.return_value = pd.DataFrame()

        collector = PykrxCollector()
        result = collector.get_market_cap_top(sample_date)

        assert result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_sector_performance(
        self,
        mock_stock,
        sample_start_date,
        sample_end_date,
    ):
        """섹터별 등락률을 정상적으로 반환한다."""
        # 섹터 목록 모킹
        sector_listing = pd.DataFrame(
            {"지수명": ["코스피", "코스피 200"]},
            index=["1001", "1028"],
        )
        mock_stock.get_index_listing_date.return_value = sector_listing

        # 각 섹터의 OHLCV 모킹
        ohlcv_data = pd.DataFrame({
            "시가": [2800, 2850],
            "고가": [2820, 2870],
            "저가": [2780, 2830],
            "종가": [2800, 2860],
            "거래량": [1000000, 1100000],
        })
        mock_stock.get_index_ohlcv_by_date.return_value = ohlcv_data

        collector = PykrxCollector()
        result = collector.get_sector_performance(
            sample_start_date, sample_end_date
        )

        assert not result.empty
        assert "지수명" in result.columns
        assert "등락률" in result.columns

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_sector_performance_empty_listing(
        self,
        mock_stock,
        sample_start_date,
        sample_end_date,
    ):
        """섹터 목록이 비어있으면 빈 DataFrame을 반환한다."""
        mock_stock.get_index_listing_date.return_value = pd.DataFrame()

        collector = PykrxCollector()
        result = collector.get_sector_performance(
            sample_start_date, sample_end_date
        )

        assert result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_trading_by_ticker(
        self,
        mock_stock,
        sample_date,
    ):
        """종목별 투자자 매매동향을 정상적으로 반환한다."""
        trading_df = pd.DataFrame(
            {
                "매도거래량": [1000, 2000],
                "매수거래량": [1500, 1800],
                "순매수거래량": [500, -200],
            },
            index=["005930", "000660"],
        )
        mock_stock.get_market_trading_value_by_ticker.return_value = trading_df

        collector = PykrxCollector()
        result = collector.get_trading_by_ticker(
            sample_date, "KOSPI", "외국인"
        )

        mock_stock.get_market_trading_value_by_ticker.assert_called_once_with(
            sample_date, "KOSPI", "외국인"
        )
        assert not result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_market_ohlcv(
        self,
        mock_stock,
        sample_date,
    ):
        """네이버 API에서 종목 등락률을 수집하여 ADR 계산에 사용한다."""
        page1_data = {
            "stocks": [
                {"itemCode": "005930", "stockName": "삼성전자", "closePrice": "70,500",
                 "accumulatedTradingVolume": "1,000,000", "fluctuationsRatio": "1.5"},
                {"itemCode": "000660", "stockName": "SK하이닉스", "closePrice": "131,000",
                 "accumulatedTradingVolume": "500,000", "fluctuationsRatio": "-0.8"},
            ],
            "totalCount": 2,
        }
        empty_data = {"stocks": [], "totalCount": 2}

        collector = PykrxCollector()
        collector._naver_get = MagicMock(side_effect=[page1_data, empty_data])

        result = collector.get_market_ohlcv(sample_date, "KOSPI")

        assert not result.empty
        assert "등락률" in result.columns
        assert "거래량" in result.columns
        assert len(result) == 2

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_get_market_ohlcv_empty(
        self,
        mock_stock,
        sample_date,
    ):
        """네이버 API 실패 시 빈 DataFrame을 반환한다."""
        collector = PykrxCollector()
        collector._naver_get = MagicMock(return_value=None)
        result = collector.get_market_ohlcv(sample_date)

        assert result.empty

    @patch("alphapulse.market.collectors.pykrx_collector.stock")
    def test_caching_hit(
        self,
        mock_stock,
        sample_investor_trading_df,
        sample_start_date,
        sample_end_date,
    ):
        """캐시가 있으면 API를 호출하지 않는다."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = sample_investor_trading_df

        collector = PykrxCollector(cache=mock_cache)
        result = collector.get_investor_trading(
            sample_start_date, sample_end_date
        )

        # 캐시 히트이므로 pykrx API가 호출되지 않아야 한다
        mock_stock.get_market_trading_value_by_date.assert_not_called()
        assert not result.empty


# ---------------------------------------------------------------------------
# FdrCollector 테스트
# ---------------------------------------------------------------------------

class TestFdrCollector:
    """FdrCollector 테스트. FinanceDataReader를 모킹한다."""

    def test_to_dash_date(self):
        """YYYYMMDD -> YYYY-MM-DD 변환을 확인한다."""
        assert _to_dash_date("20260313") == "2026-03-13"
        assert _to_dash_date("20260101") == "2026-01-01"

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_exchange_rate(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """USD/KRW 환율을 정상적으로 반환한다."""
        exchange_df = pd.DataFrame(
            {"Close": [1350.0, 1355.0, 1348.0]},
            index=pd.date_range("2026-03-09", periods=3, freq="B"),
        )
        mock_fdr.DataReader.return_value = exchange_df

        collector = FdrCollector()
        result = collector.get_exchange_rate(
            sample_start_date, sample_end_date
        )

        mock_fdr.DataReader.assert_called_once_with(
            "USD/KRW", "2026-03-09", "2026-03-13"
        )
        assert not result.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_exchange_rate_empty(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """빈 데이터가 반환되면 빈 DataFrame을 반환한다."""
        mock_fdr.DataReader.return_value = pd.DataFrame()

        collector = FdrCollector()
        result = collector.get_exchange_rate(
            sample_start_date, sample_end_date
        )

        assert result.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_exchange_rate_none(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """None이 반환되면 빈 DataFrame을 반환한다."""
        mock_fdr.DataReader.return_value = None

        collector = FdrCollector()
        result = collector.get_exchange_rate(
            sample_start_date, sample_end_date
        )

        assert result.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_global_indices(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """글로벌 지수를 정상적으로 반환한다."""
        index_df = pd.DataFrame(
            {"Close": [5000.0, 5050.0]},
            index=pd.date_range("2026-03-09", periods=2, freq="B"),
        )
        mock_fdr.DataReader.return_value = index_df

        collector = FdrCollector()
        result = collector.get_global_indices(
            sample_start_date, sample_end_date
        )

        assert isinstance(result, dict)
        assert "SP500" in result
        assert "NASDAQ" in result
        assert "SSEC" in result
        assert "N225" in result
        for name, df in result.items():
            assert not df.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_global_indices_partial_failure(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """일부 지수 조회 실패 시 해당 지수만 빈 DataFrame으로 반환한다."""
        index_df = pd.DataFrame(
            {"Close": [5000.0]},
            index=pd.date_range("2026-03-09", periods=1),
        )

        def side_effect(ticker, start, end):
            if ticker == "SSEC":
                raise ConnectionError("connection failed")
            return index_df

        mock_fdr.DataReader.side_effect = side_effect

        collector = FdrCollector()
        result = collector.get_global_indices(
            sample_start_date, sample_end_date
        )

        assert not result["SP500"].empty
        assert result["SSEC"].empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_bond_yields_kr(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """한국 국채 수익률을 정상적으로 반환한다."""
        bond_df = pd.DataFrame(
            {"Close": [3.5, 3.6]},
            index=pd.date_range("2026-03-09", periods=2, freq="B"),
        )
        mock_fdr.DataReader.return_value = bond_df

        collector = FdrCollector()
        result = collector.get_bond_yields_kr(
            sample_start_date, sample_end_date
        )

        assert not result.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_get_bond_yields_kr_empty(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """채권 데이터가 없으면 빈 DataFrame을 반환한다."""
        mock_fdr.DataReader.return_value = pd.DataFrame()

        collector = FdrCollector()
        result = collector.get_bond_yields_kr(
            sample_start_date, sample_end_date
        )

        assert result.empty


# ---------------------------------------------------------------------------
# FredCollector 테스트
# ---------------------------------------------------------------------------

class TestFredCollector:
    """FredCollector 테스트. fredapi를 모킹한다."""

    def test_no_api_key_returns_empty(self):
        """API 키가 없으면 빈 DataFrame을 반환한다."""
        collector = FredCollector(api_key="")
        result = collector.get_us_treasury_10y("20260309", "20260313")

        assert result.empty

    def test_no_api_key_fed_rate_returns_empty(self):
        """API 키 없이 연방기금금리를 요청하면 빈 DataFrame을 반환한다."""
        collector = FredCollector(api_key="")
        result = collector.get_fed_rate("20260309", "20260313")

        assert result.empty

    @patch("alphapulse.market.collectors.fred_collector.FRED_API_KEY", "")
    def test_no_env_api_key(self):
        """환경변수 API 키도 없으면 빈 DataFrame을 반환한다."""
        collector = FredCollector()
        assert collector.fred is None
        result = collector.get_us_treasury_10y("20260309", "20260313")
        assert result.empty

    @patch("fredapi.Fred")
    def test_get_us_treasury_10y_with_key(self, MockFred):
        """API 키가 있으면 FRED에서 데이터를 조회한다."""
        mock_fred_instance = MagicMock()
        MockFred.return_value = mock_fred_instance

        series_data = pd.Series(
            [4.2, 4.3, 4.1],
            index=pd.date_range("2026-03-09", periods=3, freq="B"),
            name="DGS10",
        )
        mock_fred_instance.get_series.return_value = series_data

        collector = FredCollector(api_key="test_key")
        result = collector.get_us_treasury_10y("20260309", "20260313")

        assert not result.empty
        assert "DGS10" in result.columns

    @patch("fredapi.Fred")
    def test_get_fed_rate_with_key(self, MockFred):
        """API 키가 있으면 연방기금금리를 조회한다."""
        mock_fred_instance = MagicMock()
        MockFred.return_value = mock_fred_instance

        series_data = pd.Series(
            [5.25, 5.25],
            index=pd.date_range("2026-03-09", periods=2, freq="B"),
            name="FEDFUNDS",
        )
        mock_fred_instance.get_series.return_value = series_data

        collector = FredCollector(api_key="test_key")
        result = collector.get_fed_rate("20260309", "20260313")

        assert not result.empty
        assert "FEDFUNDS" in result.columns

    @patch("fredapi.Fred")
    def test_get_series_empty(self, MockFred):
        """FRED가 빈 시리즈를 반환하면 빈 DataFrame을 반환한다."""
        mock_fred_instance = MagicMock()
        MockFred.return_value = mock_fred_instance
        mock_fred_instance.get_series.return_value = pd.Series(
            dtype=float
        )

        collector = FredCollector(api_key="test_key")
        result = collector.get_us_treasury_10y("20260309", "20260313")

        assert result.empty


# ---------------------------------------------------------------------------
# KrxScraper 테스트
# ---------------------------------------------------------------------------

class TestKrxScraper:
    """KrxScraper 테스트. 네이버 금융 크롤링을 모킹한다."""

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_program_trading_success(self, MockSession):
        """프로그램 매매 데이터를 정상적으로 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        html = """<table class="type_1"><tr>
        <th>시간</th><th>차익매수</th><th>차익매도</th><th>차익순매수</th>
        <th>비차익매수</th><th>비차익매도</th><th>비차익순매수</th>
        <th>전체매수</th><th>전체매도</th><th>전체순매수</th></tr>
        <tr><td>26.03.13</td><td>100</td><td>200</td><td>-100</td>
        <td>500</td><td>300</td><td>200</td>
        <td>600</td><td>500</td><td>100</td></tr></table>"""
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_program_trading("20260313")

        assert not result.empty
        assert "비차익순매수" in result.columns

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_program_trading_failure(self, MockSession):
        """스크래핑 실패 시 빈 DataFrame을 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_session.get.side_effect = Exception("connection error")

        scraper = KrxScraper()
        result = scraper.get_program_trading("20260313")

        assert result.empty

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_program_trading_empty_response(self, MockSession):
        """빈 테이블이면 빈 DataFrame을 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        mock_response = MagicMock()
        mock_response.text = "<table class='type_1'><tr><th>시간</th></tr></table>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_program_trading("20260313")

        assert result.empty

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_vkospi_success(self, MockSession):
        """V-KOSPI 데이터를 정상적으로 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        html = """<table class="type_2">
        <tr><td>2026.03.13</td><td>18.50</td><td>0.30</td></tr>
        <tr><td>2026.03.12</td><td>18.20</td><td>-0.10</td></tr>
        </table>"""
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_vkospi("20260309", "20260313")

        assert not result.empty
        assert "Close" in result.columns
        assert result["Close"].iloc[0] == 18.50

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_vkospi_failure(self, MockSession):
        """V-KOSPI 스크래핑 실패 시 빈 DataFrame을 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_session.get.side_effect = Exception("timeout")

        scraper = KrxScraper()
        result = scraper.get_vkospi("20260309", "20260313")

        assert result.empty

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_sector_performance(self, MockSession):
        """업종별 등락률을 정상적으로 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        html = """<table class="type_1">
        <tr><td>전기전자</td><td>+2.50%</td><td>3</td><td>1</td></tr>
        <tr><td>화학</td><td>-0.80%</td><td>2</td><td>3</td></tr>
        </table>"""
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_sector_performance()

        assert not result.empty
        assert "업종명" in result.columns
        assert "등락률" in result.columns

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_deposit_success(self, MockSession):
        """고객 예탁금을 네이버 금융에서 수집한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        html = """<table class="type_1">
        <tr><td>26.03.19</td><td>1,156,443</td><td>33,635</td><td>328,374</td></tr>
        <tr><td>26.03.18</td><td>1,122,807</td><td>24,975</td><td>330,142</td></tr>
        </table>"""
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_deposit("20260309", "20260313")

        assert not result.empty
        assert "예탁금" in result.columns

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_deposit_failure(self, MockSession):
        """예탁금 크롤링 실패 시 빈 DataFrame을 반환한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_session.get.side_effect = Exception("network error")

        scraper = KrxScraper()
        result = scraper.get_deposit("20260309", "20260313")

        assert result.empty

    @patch("alphapulse.market.collectors.krx_scraper.requests.Session")
    def test_get_credit_balance(self, MockSession):
        """신용잔고를 예탁금 데이터에서 추출한다."""
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        html = """<table class="type_1">
        <tr><td>26.03.19</td><td>1,156,443</td><td>33,635</td><td>328,374</td></tr>
        </table>"""
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        scraper = KrxScraper()
        result = scraper.get_credit_balance("20260309", "20260313")

        assert not result.empty
        assert "신용잔고" in result.columns


# ---------------------------------------------------------------------------
# 캐시 통합 테스트
# ---------------------------------------------------------------------------

class TestCacheIntegration:
    """캐시 통합 테스트. 캐시 히트/미스 동작을 검증한다."""

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_fdr_cache_hit(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """FdrCollector에서 캐시 히트 시 API를 호출하지 않는다."""
        mock_cache = MagicMock()
        cached_df = pd.DataFrame({"Close": [1350.0]})
        mock_cache.get.return_value = cached_df

        collector = FdrCollector(cache=mock_cache)
        result = collector.get_exchange_rate(
            sample_start_date, sample_end_date
        )

        mock_fdr.DataReader.assert_not_called()
        assert not result.empty

    @patch("alphapulse.market.collectors.fdr_collector.fdr")
    def test_fdr_cache_miss(
        self,
        mock_fdr,
        sample_start_date,
        sample_end_date,
    ):
        """FdrCollector에서 캐시 미스 시 API를 호출하고 캐시에 저장한다."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        exchange_df = pd.DataFrame(
            {"Close": [1350.0]},
            index=pd.date_range("2026-03-09", periods=1),
        )
        mock_fdr.DataReader.return_value = exchange_df

        collector = FdrCollector(cache=mock_cache)
        result = collector.get_exchange_rate(
            sample_start_date, sample_end_date
        )

        mock_fdr.DataReader.assert_called_once()
        mock_cache.set.assert_called_once()
        assert not result.empty
