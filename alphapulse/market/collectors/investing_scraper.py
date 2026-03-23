"""investing.com 데이터 수집기

KOSPI200 선물 시세, V-KOSPI 등 한국 파생상품 데이터를 수집한다.
"""

import logging
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from alphapulse.market.collectors.base import BaseCollector, retry

logger = logging.getLogger(__name__)

INVESTING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
REQUEST_TIMEOUT = 15


def _parse_number(text: str) -> float:
    """'1,234.56' 또는 '+5.17' 형태의 문자열을 float로 변환"""
    if not text:
        return 0.0
    cleaned = text.replace(",", "").replace("+", "").replace("%", "").strip()
    cleaned = cleaned.replace("(", "").replace(")", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_volume(text: str) -> float:
    """'49.38K', '169.35M' 형태의 거래량 문자열을 숫자로 변환"""
    if not text:
        return 0.0
    text = text.strip().upper()
    multiplier = 1
    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]
    try:
        return float(text.replace(",", "")) * multiplier
    except ValueError:
        return 0.0


class InvestingScraper(BaseCollector):
    """investing.com 데이터 수집기"""

    def __init__(self, cache: Any | None = None) -> None:
        super().__init__(cache)
        self.session = requests.Session()
        self.session.headers.update(INVESTING_HEADERS)

    def _get_historical(self, path: str, n: int = 5) -> pd.DataFrame:
        """investing.com historical data 테이블을 파싱한다."""
        url = f"https://kr.investing.com/indices/{path}-historical-data"
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # 헤더 확인
            header_cells = rows[0].find_all(["th", "td"])
            header = [c.get_text(strip=True) for c in header_cells]
            if "종가" not in header and "Close" not in header:
                continue

            data_rows = []
            for row in rows[1:n + 1]:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                data_rows.append({
                    "date": texts[0],
                    "Close": _parse_number(texts[1]),
                    "Open": _parse_number(texts[2]),
                    "High": _parse_number(texts[3]),
                    "Low": _parse_number(texts[4]),
                    "Volume": _parse_volume(texts[5]) if len(texts) > 5 else 0,
                    "Change": _parse_number(texts[6]) if len(texts) > 6 else 0,
                })

            if data_rows:
                return pd.DataFrame(data_rows)

        return pd.DataFrame()

    def _get_current_price(self, path: str) -> dict:
        """investing.com 현재가 정보를 파싱한다."""
        url = f"https://kr.investing.com/indices/{path}"
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {}
        for tag in soup.find_all("span", attrs={"data-test": True}):
            dt = tag.get("data-test", "")
            if "instrument-price" in dt:
                result[dt] = tag.get_text(strip=True)

        return result

    @retry()
    def get_vkospi(self) -> pd.DataFrame:
        """V-KOSPI(변동성 지수) -- investing.com 일별 시세"""
        cache_key = "investing:vkospi"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            df = self._get_historical("kospi-volatility", n=10)
            if df.empty:
                self.logger.warning("V-KOSPI 데이터 없음 (investing.com)")
                return pd.DataFrame()

            self._set_cached(cache_key, df)
            return df

        except Exception as e:
            self.logger.warning(f"V-KOSPI 수집 실패 (investing.com): {e}")
            return pd.DataFrame()

    @retry()
    def get_futures_basis(self) -> dict:
        """
        KOSPI200 선물 베이시스(괴리율) 계산.

        investing.com에서 선물/현물 일별 시세를 가져와 같은 거래일 기준으로 비교한다.
        - 선물 프리미엄(콘탱고): 강세 심리
        - 선물 디스카운트(백워데이션): 약세 심리

        Returns:
            dict with: basis_pct, futures_price, spot_price, date, details
        """
        cache_key = "investing:futures_basis"
        cached_result = self._get_cached(cache_key)
        if cached_result is not None:
            if not cached_result.empty:
                return cached_result.iloc[0].to_dict()

        try:
            # 선물 시세 (korea-200-futures)
            futures_df = self._get_historical("korea-200-futures", n=5)
            # 현물 시세 (kospi-200)
            spot_df = self._get_historical("kospi-200", n=5)

            if futures_df.empty or spot_df.empty:
                self.logger.warning("선물/현물 데이터 부족으로 베이시스 계산 불가")
                return {}

            # 같은 거래일 기준으로 매칭
            futures_dates = set(futures_df["date"].tolist())
            spot_dates = set(spot_df["date"].tolist())
            common_dates = futures_dates & spot_dates

            if common_dates:
                # 공통 날짜 중 가장 최근 날짜 사용
                latest_date = sorted(common_dates, reverse=True)[0]
                futures_row = futures_df[futures_df["date"] == latest_date].iloc[0]
                spot_row = spot_df[spot_df["date"] == latest_date].iloc[0]
                match_date = latest_date
            else:
                # 공통 날짜가 없으면 선물 최신 날짜 기준 (선물 마감이 더 빠를 수 있음)
                futures_row = futures_df.iloc[0]
                # 현물에서 선물보다 같거나 이전 날짜 찾기
                spot_row = spot_df.iloc[0]
                for _, row in spot_df.iterrows():
                    if row["date"] <= futures_row["date"]:
                        spot_row = row
                        break
                match_date = futures_row["date"]
                self.logger.info(f"선물({futures_row['date']})과 현물({spot_row['date']}) 날짜 불일치 -- 근접 날짜 사용")

            futures_price = float(futures_row["Close"])
            spot_price = float(spot_row["Close"])

            if spot_price == 0:
                return {}

            basis_pct = ((futures_price - spot_price) / spot_price) * 100

            result = {
                "basis_pct": round(basis_pct, 2),
                "futures_price": futures_price,
                "spot_price": spot_price,
                "date": match_date,
            }

            self._set_cached(cache_key, pd.DataFrame([result]))
            return result

        except Exception as e:
            self.logger.warning(f"선물 베이시스 수집 실패: {e}")
            return {}

    @retry()
    def get_us_futures(self) -> dict:
        """미국 S&P500/나스닥 선물 실시간 변동률 -- investing.com

        한국 장중에 미국 선물 변동을 확인하여 글로벌 리스크 실시간 반영.

        Returns:
            dict with: SP500_futures (변동%), NASDAQ_futures (변동%)
        """
        cache_key = "investing:us_futures"
        cached = self._get_cached(cache_key)
        if cached is not None and not cached.empty:
            return cached.iloc[0].to_dict()

        try:
            result = {}
            targets = {
                "SP500_futures": "us-spx-500-futures",
                "NASDAQ_futures": "nq-100-futures",
            }
            for key, path in targets.items():
                price_info = self._get_current_price(path)
                pct_text = price_info.get("instrument-price-change-percent", "")
                result[key] = _parse_number(pct_text)

            if result:
                self._set_cached(cache_key, pd.DataFrame([result]))
            return result

        except Exception as e:
            self.logger.warning(f"미국 선물 수집 실패: {e}")
            return {}
