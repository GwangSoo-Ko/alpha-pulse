"""한국 주식시장 데이터 수집기

네이버 증권 모바일 API + pykrx를 통해 KRX 시장 데이터를 수집한다.
pykrx의 일부 API가 KRX 변경으로 동작하지 않으므로 네이버 API로 보완한다.
"""

import logging
from typing import Any

import pandas as pd
import requests
from pykrx import stock

from alphapulse.market.collectors.base import BaseCollector, retry

logger = logging.getLogger(__name__)

NAVER_API_BASE = "https://m.stock.naver.com/api"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 시장 코드 매핑
MARKET_INDEX = {
    "KOSPI": "KOSPI",
    "KOSDAQ": "KOSDAQ",
}


class PykrxCollector(BaseCollector):
    """한국 시장 데이터 수집기 (네이버 API + pykrx 혼용)"""

    def __init__(self, cache: Any | None = None) -> None:
        super().__init__(cache)
        self._session = requests.Session()
        self._session.headers.update(NAVER_HEADERS)

    def _naver_get(self, path: str, params: dict | None = None) -> dict | list | None:
        """네이버 증권 모바일 API 호출"""
        try:
            resp = self._session.get(f"{NAVER_API_BASE}/{path}", params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            self.logger.debug(f"네이버 API 호출 실패 ({path}): {e}")
        return None

    @retry()
    def get_investor_trading(
        self, start: str, end: str, market: str = "KOSPI"
    ) -> pd.DataFrame:
        """투자자별 매매동향 (네이버 API -> pykrx 폴백)"""
        cache_key = f"pykrx:investor_trading:{market}:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        index_code = MARKET_INDEX.get(market, market)

        # 네이버 API에서 일별 투자자 동향 가져오기
        data = self._naver_get(f"index/{index_code}/trend", {"page": 1, "pageSize": 1})
        if data and isinstance(data, dict) and "personalValue" in data:
            def parse_val(v):
                return int(v.replace(",", "").replace("+", "")) * 100_000_000  # 억 단위

            df = pd.DataFrame([{
                "개인": parse_val(data["personalValue"]),
                "외국인합계": parse_val(data["foreignValue"]),
                "기관합계": parse_val(data["institutionalValue"]),
                "기타법인": 0,
            }], index=pd.DatetimeIndex([pd.Timestamp(data["bizdate"])]))
            self._set_cached(cache_key, df)
            return df

        # pykrx 폴백
        try:
            df = stock.get_market_trading_value_by_date(start, end, market)
            if not df.empty:
                columns = ["기관합계", "기타법인", "개인", "외국인합계"]
                available = [c for c in columns if c in df.columns]
                df = df[available]
                self._set_cached(cache_key, df)
                return df
        except Exception as e:
            self.logger.debug(f"pykrx 투자자 매매동향 실패: {e}")

        self.logger.warning(f"투자자별 매매동향 데이터 없음: {market} {start}~{end}")
        return pd.DataFrame()

    @retry()
    def get_investor_trading_futures(self, start: str, end: str) -> pd.DataFrame:
        """선물 투자자별 매매동향"""
        cache_key = f"pykrx:investor_trading_futures:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            df = stock.get_market_trading_value_by_date(start, end, "선물")
            if not df.empty:
                self._set_cached(cache_key, df)
                return df
        except Exception as e:
            self.logger.debug(f"pykrx 선물 매매동향 실패: {e}")

        self.logger.warning(f"선물 매매동향 데이터 없음: {start}~{end}")
        return pd.DataFrame()

    @retry()
    def get_market_cap_top(
        self, date: str, market: str = "KOSPI", n: int = 10
    ) -> pd.DataFrame:
        """시가총액 상위 종목 (네이버 API)"""
        cache_key = f"pykrx:market_cap_top:{market}:{date}:{n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # 네이버 API - 시총 상위 종목
        self._naver_get(f"index/{MARKET_INDEX.get(market, market)}/price",
                        {"page": 1, "pageSize": n})
        # pykrx 폴백
        try:
            df = stock.get_market_cap_by_ticker(date, market)
            if not df.empty:
                df = df.sort_values("시가총액", ascending=False).head(n)
                self._set_cached(cache_key, df)
                return df
        except Exception as e:
            self.logger.debug(f"pykrx 시가총액 실패: {e}")

        self.logger.warning(f"시가총액 데이터 없음: {market} {date}")
        return pd.DataFrame()

    @retry()
    def get_sector_performance(self, start: str, end: str) -> pd.DataFrame:
        """KOSPI 섹터별 등락률"""
        cache_key = f"pykrx:sector_performance:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            sector_list = stock.get_index_listing_date("KOSPI")
            if not sector_list.empty:
                results = []
                for ticker in sector_list.index:
                    try:
                        name = sector_list.loc[ticker, "지수명"]
                        ohlcv = stock.get_index_ohlcv_by_date(start, end, ticker)
                        if ohlcv.empty:
                            continue
                        first_close = ohlcv["종가"].iloc[0]
                        last_close = ohlcv["종가"].iloc[-1]
                        if first_close > 0:
                            change_pct = (last_close / first_close - 1) * 100
                        else:
                            change_pct = 0.0
                        results.append({"지수명": name, "등락률": round(change_pct, 2)})
                    except Exception:
                        continue
                if results:
                    df = pd.DataFrame(results)
                    self._set_cached(cache_key, df)
                    return df
        except Exception as e:
            self.logger.debug(f"pykrx 업종 조회 실패: {e}")

        self.logger.warning(f"섹터 성과 데이터 없음: {start}~{end}")
        return pd.DataFrame()

    @retry()
    def get_trading_by_ticker(
        self, date: str, market: str = "KOSPI", investor: str = "외국인"
    ) -> pd.DataFrame:
        """종목별 투자자 매매동향"""
        cache_key = f"pykrx:trading_by_ticker:{market}:{investor}:{date}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            df = stock.get_market_trading_value_by_ticker(date, market, investor)
            if not df.empty:
                self._set_cached(cache_key, df)
                return df
        except Exception as e:
            self.logger.debug(f"pykrx 종목별 매매동향 실패: {e}")

        self.logger.warning(f"종목별 매매동향 데이터 없음: {market} {investor} {date}")
        return pd.DataFrame()

    @retry()
    def get_market_ohlcv(self, date: str, market: str = "KOSPI") -> pd.DataFrame:
        """전 종목 등락률 + 거래량 (ADR 계산용)

        네이버 증권 시총 종목 API에서 상위 500종목의 등락률/거래량을 수집한다.
        pykrx get_market_ohlcv_by_ticker는 KRX API 변경으로 현재 동작하지 않는다.
        """
        cache_key = f"naver:market_ohlcv:{market}:{date}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # 네이버 시총 종목 API -- 500종목 (5페이지)
        index_code = MARKET_INDEX.get(market, market)
        all_stocks = []
        for page in range(1, 6):
            data = self._naver_get(
                f"stocks/marketValue/{index_code}",
                {"page": page, "pageSize": 100},
            )
            if not data or not isinstance(data, dict):
                break
            stocks = data.get("stocks", [])
            if not stocks:
                break
            all_stocks.extend(stocks)

        if not all_stocks:
            self.logger.warning(f"종목 등락률 데이터 없음: {market}")
            return pd.DataFrame()

        rows = []
        for s in all_stocks:
            try:
                rows.append({
                    "종목코드": s.get("itemCode", ""),
                    "종목명": s.get("stockName", ""),
                    "종가": float(s.get("closePrice", "0").replace(",", "")),
                    "거래량": float(s.get("accumulatedTradingVolume", "0").replace(",", "")),
                    "등락률": float(s.get("fluctuationsRatio", "0")),
                })
            except (ValueError, AttributeError):
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        self._set_cached(cache_key, df)
        self.logger.info(f"네이버 API에서 {market} {len(df)}종목 등락률 수집 (ADR 계산용)")
        return df
