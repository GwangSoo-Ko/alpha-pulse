"""KRX/네이버금융 데이터 수집기

네이버 금융에서 프로그램 매매, V-KOSPI, 업종 등락률, 고객 예탁금 등을 수집한다.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from alphapulse.market.collectors.base import BaseCollector, retry

logger = logging.getLogger(__name__)

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
NAVER_API_BASE = "https://m.stock.naver.com/api"
REQUEST_TIMEOUT = 10


def _parse_number(text: str) -> float:
    """'1,234' 또는 '+1,234' 형태의 문자열을 float로 변환"""
    if not text:
        return 0.0
    cleaned = text.replace(",", "").replace("+", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class KrxScraper(BaseCollector):
    """KRX/네이버 금융 데이터 수집기"""

    def __init__(self, cache: Any | None = None) -> None:
        super().__init__(cache)
        self.session = requests.Session()
        self.session.headers.update(NAVER_HEADERS)

    @retry()
    def get_investor_trend_daily(self, days: int = 10) -> pd.DataFrame:
        """투자자별 일별 매매동향 (네이버 금융 크롤링, 최근 N거래일)

        네이버 금융 investorDealTrendDay 페이지에서 일별 투자자 순매수를 수집한다.
        수급 추세 분석(5일 누적)에 사용된다.

        Args:
            days: 수집할 거래일 수 (기본 10일).

        Returns:
            DataFrame with columns: 날짜, 개인, 외국인, 기관합계, 기타법인 (억원 단위).
        """
        cache_key = "naver:investor_trend_daily"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            bizdate = datetime.now().strftime("%Y%m%d")

            # KOSPI(sosok=00) + KOSDAQ(sosok=01) 합산
            combined_rows = {}
            for sosok in ["00", "01"]:
                url = (
                    f"https://finance.naver.com/sise/investorDealTrendDay.naver"
                    f"?bizdate={bizdate}&sosok={sosok}"
                )
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", {"class": "type_1"})
                if not table:
                    continue

                count = 0
                for row in table.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) < 6:
                        continue
                    date_text = cols[0].get_text(strip=True)
                    if not date_text or "." not in date_text:
                        continue

                    personal = _parse_number(cols[1].get_text(strip=True))
                    foreign = _parse_number(cols[2].get_text(strip=True))
                    institutional = _parse_number(cols[3].get_text(strip=True))
                    others = _parse_number(cols[-1].get_text(strip=True))

                    if date_text in combined_rows:
                        combined_rows[date_text]["개인"] += personal
                        combined_rows[date_text]["외국인"] += foreign
                        combined_rows[date_text]["기관합계"] += institutional
                        combined_rows[date_text]["기타법인"] += others
                    else:
                        combined_rows[date_text] = {
                            "날짜": date_text,
                            "개인": personal,
                            "외국인": foreign,
                            "기관합계": institutional,
                            "기타법인": others,
                        }

                    count += 1
                    if count >= days:
                        break

            if not combined_rows:
                self.logger.warning("투자자 일별 매매동향 데이터 행 없음")
                return pd.DataFrame()

            # 날짜 내림차순 정렬
            data_rows = sorted(combined_rows.values(),
                               key=lambda x: x["날짜"], reverse=True)[:days]

            df = pd.DataFrame(data_rows)
            self._set_cached(cache_key, df)
            return df

        except Exception as e:
            self.logger.warning(f"투자자 일별 매매동향 수집 실패: {e}")
            return pd.DataFrame()

    @retry()
    def get_total_market_cap(self, market: str = "KOSPI") -> dict:
        """전체 시장 시가총액 합계 (네이버 모바일 API)

        네이버 증권 시총 종목 API에서 전 종목의 시가총액을 합산한다.
        신용잔고 과열 판단(시총 대비 비율)에 사용된다.

        Args:
            market: 시장 구분 ("KOSPI" 또는 "KOSDAQ").

        Returns:
            dict with keys: KOSPI, KOSDAQ, total (각각 억원 단위).
        """
        cache_key = "naver:total_market_cap"
        cached = self._get_cached(cache_key)
        if cached is not None:
            # cached는 DataFrame이므로 dict로 변환
            if not cached.empty:
                return cached.iloc[0].to_dict()

        try:
            totals = {}
            for mkt in ["KOSPI", "KOSDAQ"]:
                total_cap = 0
                for page in range(1, 26):  # 최대 25페이지 (2500종목)
                    url = f"{NAVER_API_BASE}/stocks/marketValue/{mkt}"
                    resp = self.session.get(
                        url,
                        params={"page": page, "pageSize": 100},
                        timeout=REQUEST_TIMEOUT,
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    if not data or not isinstance(data, dict):
                        break
                    stocks = data.get("stocks", [])
                    if not stocks:
                        break
                    for s in stocks:
                        try:
                            # marketValue는 문자열, 억원 단위
                            mv_str = s.get("marketValue", "0")
                            if isinstance(mv_str, str):
                                mv = float(mv_str.replace(",", ""))
                            else:
                                mv = float(mv_str)
                            total_cap += mv
                        except (ValueError, TypeError):
                            continue
                totals[mkt] = total_cap

            totals["total"] = totals.get("KOSPI", 0) + totals.get("KOSDAQ", 0)

            if totals["total"] == 0:
                self.logger.warning("시가총액 데이터 수집 실패: 합계 0")
                return {}

            # 캐시에 DataFrame으로 저장
            self._set_cached(cache_key, pd.DataFrame([totals]))
            return totals

        except Exception as e:
            self.logger.warning(f"시가총액 수집 실패: {e}")
            return {}

    @retry()
    def get_program_trading(self, date: str) -> pd.DataFrame:
        """프로그램 매매(차익/비차익) 일별 데이터 -- bizdate 파라미터로 거래일 지정"""
        cache_key = f"krx:program_trading:{date}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # YYYYMMDD -> bizdate 파라미터
            url = f"https://finance.naver.com/sise/programDealTrendDay.naver?bizdate={date}"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "type_1"})
            if not table:
                self.logger.warning(f"프로그램 매매 테이블 없음: {date}")
                return pd.DataFrame()

            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 9:
                    row_date = cols[0].get_text(strip=True)
                    if not row_date or "." not in row_date:
                        continue

                    # 첫 번째 행 = 가장 최근 거래일 데이터
                    df = pd.DataFrame([{
                        "날짜": row_date,
                        "차익매수": _parse_number(cols[1].get_text(strip=True)) * 100_000_000,
                        "차익매도": _parse_number(cols[2].get_text(strip=True)) * 100_000_000,
                        "차익순매수": _parse_number(cols[3].get_text(strip=True)) * 100_000_000,
                        "비차익매수": _parse_number(cols[4].get_text(strip=True)) * 100_000_000,
                        "비차익매도": _parse_number(cols[5].get_text(strip=True)) * 100_000_000,
                        "비차익순매수": _parse_number(cols[6].get_text(strip=True)) * 100_000_000,
                    }])
                    self._set_cached(cache_key, df)
                    return df

            self.logger.warning(f"프로그램 매매 데이터 행 없음: {date}")
            return pd.DataFrame()

        except Exception as e:
            self.logger.warning(f"프로그램 매매 수집 실패: {date}: {e}")
            return pd.DataFrame()

    @retry()
    def get_vkospi(self, start: str, end: str) -> pd.DataFrame:
        """V-KOSPI(변동성 지수) -- 네이버 금융 일별 시세"""
        cache_key = f"krx:vkospi:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            url = "https://finance.naver.com/sise/sise_index_day.naver?code=V_KOSPI200"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table.type_2 tr")

            data_rows = []
            for row in rows:
                tds = row.find_all("td")
                if len(tds) >= 2:
                    date_text = tds[0].get_text(strip=True)
                    close_text = tds[1].get_text(strip=True)
                    if date_text and close_text and "." in date_text:
                        close_val = _parse_number(close_text)
                        if close_val > 0:
                            data_rows.append({"Close": close_val})
                            if len(data_rows) >= 5:
                                break

            if not data_rows:
                self.logger.warning(f"V-KOSPI 데이터 없음: {start}~{end}")
                return pd.DataFrame()

            df = pd.DataFrame(data_rows)
            self._set_cached(cache_key, df)
            return df

        except Exception as e:
            self.logger.warning(f"V-KOSPI 수집 실패: {start}~{end}: {e}")
            return pd.DataFrame()

    @retry()
    def get_sector_performance(self) -> pd.DataFrame:
        """업종별 등락률 -- 네이버 금융 크롤링 (79개 업종)"""
        cache_key = "naver:sector_performance"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "type_1"})
            if not table:
                return pd.DataFrame()

            results = []
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) >= 2:
                    name = tds[0].get_text(strip=True)
                    change_text = tds[1].get_text(strip=True)
                    if name and change_text:
                        change = float(change_text.replace("%", "").replace("+", "").replace(",", ""))
                        results.append({"업종명": name, "등락률": change})

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)
            self._set_cached(cache_key, df)
            return df

        except Exception as e:
            self.logger.warning(f"업종별 등락률 수집 실패: {e}")
            return pd.DataFrame()

    @retry()
    def get_deposit(self, start: str, end: str) -> pd.DataFrame:
        """고객 예탁금 -- 네이버 금융 크롤링"""
        cache_key = f"naver:deposit:{start}:{end}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            url = "https://finance.naver.com/sise/sise_deposit.naver"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "type_1"})
            if not table:
                return pd.DataFrame()

            # 컬럼: 날짜, 고객예탁금, 신용잔고, 주식형펀드
            data_rows = []
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) >= 3:
                    date_text = tds[0].get_text(strip=True)
                    if not date_text or "." not in date_text:
                        continue
                    deposit = _parse_number(tds[1].get_text(strip=True))
                    credit = _parse_number(tds[2].get_text(strip=True))
                    if deposit > 0:
                        data_rows.append({
                            "날짜": date_text,
                            "예탁금": deposit * 100_000_000,  # 억 단위
                            "신용잔고": credit * 100_000_000,
                        })
                    if len(data_rows) >= 10:
                        break

            if not data_rows:
                return pd.DataFrame()

            df = pd.DataFrame(data_rows)
            self._set_cached(cache_key, df)
            return df

        except Exception as e:
            self.logger.warning(f"고객 예탁금 수집 실패: {e}")
            return pd.DataFrame()

    @retry()
    def get_credit_balance(self, start: str, end: str) -> pd.DataFrame:
        """신용잔고 -- 예탁금 데이터에 포함되어 있으므로 get_deposit에서 함께 제공"""
        # get_deposit()에서 신용잔고도 함께 수집하므로 별도 호출 불필요
        deposit_df = self.get_deposit(start, end)
        if deposit_df.empty or "신용잔고" not in deposit_df.columns:
            return pd.DataFrame()
        return deposit_df[["날짜", "신용잔고"]]

    def get_spot_futures_trend(self) -> dict:
        """KOSPI vs KPI200 투자자 동향으로 현선물 방향 비교 -- 네이버 모바일 API"""
        try:
            results = {}
            for code in ["KOSPI", "KPI200"]:
                resp = self.session.get(
                    f"{NAVER_API_BASE}/index/{code}/trend",
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200 and resp.text:
                    data = resp.json()
                    results[code] = {
                        "foreign": _parse_number(data.get("foreignValue", "0")),
                        "institutional": _parse_number(data.get("institutionalValue", "0")),
                        "personal": _parse_number(data.get("personalValue", "0")),
                        "date": data.get("bizdate", ""),
                    }
            return results
        except Exception as e:
            self.logger.warning(f"현선물 투자자 동향 수집 실패: {e}")
            return {}
