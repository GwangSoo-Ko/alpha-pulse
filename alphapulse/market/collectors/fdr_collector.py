"""FinanceDataReader 기반 글로벌 시장 데이터 수집기

FinanceDataReader 라이브러리를 통해 환율, 해외 지수, 채권 수익률 등을 수집한다.
"""

import logging
from typing import Any

import FinanceDataReader as fdr
import pandas as pd

from alphapulse.market.collectors.base import BaseCollector, retry

logger = logging.getLogger(__name__)

# 글로벌 지수 티커 매핑
GLOBAL_INDEX_TICKERS: dict[str, str] = {
    "SP500": "US500",
    "NASDAQ": "IXIC",
    "SSEC": "SSEC",
    "N225": "N225",
}


def _to_dash_date(date_str: str) -> str:
    """YYYYMMDD 형식을 YYYY-MM-DD 형식으로 변환한다.

    Args:
        date_str: YYYYMMDD 형식 날짜 문자열.

    Returns:
        YYYY-MM-DD 형식 날짜 문자열.
    """
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


class FdrCollector(BaseCollector):
    """FinanceDataReader 기반 글로벌 데이터 수집기.

    환율, 해외 주요 지수, 한국 채권 수익률 등 글로벌 시장 데이터를 수집한다.
    날짜 입력은 "YYYYMMDD" 형식이며, 내부에서 "YYYY-MM-DD"로 변환한다.

    Attributes:
        cache: DataCache 인스턴스. None이면 캐시를 사용하지 않는다.
    """

    def __init__(self, cache: Any | None = None) -> None:
        """FdrCollector 초기화.

        Args:
            cache: DataCache 인스턴스 (선택).
        """
        super().__init__(cache)

    @retry()
    def get_exchange_rate(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """USD/KRW 환율 데이터를 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            USD/KRW 환율 DataFrame.
        """
        cache_key = f"fdr:exchange_rate:USDKRW:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        start_fmt = _to_dash_date(start)
        end_fmt = _to_dash_date(end)

        df = fdr.DataReader("USD/KRW", start_fmt, end_fmt)
        if df is None or df.empty:
            self.logger.warning(f"환율 데이터 없음: {start}~{end}")
            return pd.DataFrame()

        self._set_cached(cache_key, df)
        return df

    @retry()
    def get_global_indices(
        self,
        start: str,
        end: str,
    ) -> dict[str, pd.DataFrame]:
        """주요 글로벌 지수 데이터를 조회한다.

        SP500, NASDAQ, SSEC(상해종합), N225(닛케이225)를 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            지수명을 키로 하는 DataFrame dict.
            keys: SP500, NASDAQ, SSEC, N225.
        """
        cache_key_prefix = f"fdr:global_indices:{start}:{end}"
        start_fmt = _to_dash_date(start)
        end_fmt = _to_dash_date(end)

        results: dict[str, pd.DataFrame] = {}

        for name, ticker in GLOBAL_INDEX_TICKERS.items():
            cache_key = f"{cache_key_prefix}:{name}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                results[name] = cached
                continue

            try:
                df = fdr.DataReader(ticker, start_fmt, end_fmt)
                if df is None or df.empty:
                    self.logger.warning(
                        f"글로벌 지수 데이터 없음: {name} ({ticker}) {start}~{end}"
                    )
                    results[name] = pd.DataFrame()
                else:
                    # 중복 인덱스 제거
                    if df.index.duplicated().any():
                        df = df[~df.index.duplicated(keep="last")]
                    results[name] = df
                    self._set_cached(cache_key, df)
            except Exception as e:
                self.logger.warning(f"글로벌 지수 조회 실패: {name} ({ticker}): {e}")
                results[name] = pd.DataFrame()

        return results

    @retry()
    def get_bond_yields_kr(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """한국 국채 수익률 데이터를 조회한다.

        국고채 3년물, 10년물 수익률을 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            한국 국채 수익률 DataFrame. columns: KR3Y, KR10Y.
        """
        cache_key = f"fdr:bond_yields_kr:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        start_fmt = _to_dash_date(start)
        end_fmt = _to_dash_date(end)

        # 한국 국채 데이터: 여러 티커 시도
        ticker_candidates = [
            ("KR3YT=RR", "KR10YT=RR"),   # Yahoo Finance (구)
            ("KR3Y", "KR10Y"),             # Yahoo Finance (대안)
        ]

        for kr3y_ticker, kr10y_ticker in ticker_candidates:
            results: dict[str, pd.Series] = {}
            for name, ticker in [("KR3Y", kr3y_ticker), ("KR10Y", kr10y_ticker)]:
                try:
                    df = fdr.DataReader(ticker, start_fmt, end_fmt)
                    if df is not None and not df.empty:
                        results[name] = df["Close"]
                except Exception as e:
                    self.logger.debug(f"국채 티커 시도 실패: {name} ({ticker}): {e}")

            if results:
                df = pd.DataFrame(results)
                self._set_cached(cache_key, df)
                return df

        # 모든 FDR 티커 실패 -- FRED 폴백을 signal_engine에서 처리
        self.logger.debug(f"FDR 한국 국채 수익률 미제공 (FRED 폴백 예정): {start}~{end}")
        return pd.DataFrame()
