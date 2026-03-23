"""FRED(Federal Reserve Economic Data) 기반 미국 경제 데이터 수집기

fredapi 라이브러리를 통해 미국 국채 수익률, 기준금리 등을 수집한다.
API 키가 없으면 빈 DataFrame을 반환한다.
"""

import logging
import os
import ssl
from typing import Any

import pandas as pd

from alphapulse.market.collectors.base import BaseCollector, retry

# FRED_API_KEY: 환경변수에서 직접 읽기 (Config 순환 import 방지)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# macOS Python SSL 인증서 문제 우회
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

logger = logging.getLogger(__name__)


def _to_dash_date(date_str: str) -> str:
    """YYYYMMDD 형식을 YYYY-MM-DD 형식으로 변환한다.

    Args:
        date_str: YYYYMMDD 형식 날짜 문자열.

    Returns:
        YYYY-MM-DD 형식 날짜 문자열.
    """
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


class FredCollector(BaseCollector):
    """FRED 기반 미국 경제 데이터 수집기.

    미국 10년 국채 수익률, 연방기금금리 등 미국 경제 지표를 수집한다.
    API 키가 없으면 경고를 로깅하고 빈 DataFrame을 반환한다.

    Attributes:
        api_key: FRED API 키.
        fred: fredapi.Fred 인스턴스. API 키가 없으면 None.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache: Any | None = None,
    ) -> None:
        """FredCollector 초기화.

        Args:
            api_key: FRED API 키. None이면 환경변수에서 읽는다.
            cache: DataCache 인스턴스 (선택).
        """
        super().__init__(cache)
        self.api_key = api_key if api_key is not None else FRED_API_KEY
        self.fred = None

        if self.api_key:
            try:
                from fredapi import Fred

                self.fred = Fred(api_key=self.api_key)
            except Exception as e:
                self.logger.warning(f"FRED 클라이언트 초기화 실패: {e}")
        else:
            self.logger.warning(
                "FRED API 키가 설정되지 않았습니다. "
                "FRED_API_KEY 환경변수를 설정하세요."
            )

    def _get_series(
        self,
        series_id: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """FRED 시리즈 데이터를 조회한다.

        Args:
            series_id: FRED 시리즈 ID.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            시리즈 데이터 DataFrame. API 키가 없거나 조회 실패 시 빈 DataFrame.
        """
        if self.fred is None:
            return pd.DataFrame()

        cache_key = f"fred:{series_id}:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        start_fmt = _to_dash_date(start)
        end_fmt = _to_dash_date(end)

        series = self.fred.get_series(
            series_id,
            observation_start=start_fmt,
            observation_end=end_fmt,
        )

        if series is None or series.empty:
            self.logger.warning(
                f"FRED 데이터 없음: {series_id} {start}~{end}"
            )
            return pd.DataFrame()

        df = series.to_frame(name=series_id)
        self._set_cached(cache_key, df)
        return df

    @retry()
    def get_us_treasury_10y(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """미국 10년 국채 수익률을 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            미국 10년 국채 수익률 DataFrame. column: DGS10.
        """
        return self._get_series("DGS10", start, end)

    @retry()
    def get_fed_rate(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """미국 연방기금금리를 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            연방기금금리 DataFrame. column: FEDFUNDS.
        """
        return self._get_series("FEDFUNDS", start, end)

    @retry()
    def get_kr_long_term_rate(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """한국 장기 금리를 조회한다 (FRED).

        OECD 한국 장기 금리 데이터(월간)를 사용한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            한국 장기 금리 DataFrame. column: IRLTLT01KRM156N.
        """
        return self._get_series("IRLTLT01KRM156N", start, end)
