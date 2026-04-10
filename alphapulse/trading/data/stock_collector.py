"""주가 수집기 — pykrx 우선 + 네이버 금융 폴백.

개별 종목 OHLCV는 pykrx가 1회 호출로 전체 기간을 반환 (빠름).
pykrx 실패 시 네이버 금융 페이지별 스크래핑으로 폴백.
종목 목록은 네이버 금융에서 수집 (KRX 로그인 불필요).
"""

import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

NAVER_SISE_URL = "https://finance.naver.com/item/sise_day.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}


class StockCollector:
    """종목별 주가 데이터 수집기.

    OHLCV: pykrx 우선 (1회 호출, 빠름) → 네이버 폴백 (페이지별, 느림).
    종목 목록: 네이버 금융 시가총액 페이지.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect_ohlcv(self, code: str, start: str, end: str) -> None:
        """종목의 일별 OHLCV를 수집하여 DB에 저장한다.

        pykrx로 1회 호출 시도 후, 실패 시 네이버 금융 폴백.

        Args:
            code: 종목코드 (예: "005930").
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        # 1차: pykrx (1회 호출로 전체 기간, 빠름)
        if self._collect_ohlcv_pykrx(code, start, end):
            return

        # 2차: 네이버 금융 (페이지별, 느림)
        self._collect_ohlcv_naver(code, start, end)

    def _collect_ohlcv_pykrx(self, code: str, start: str, end: str) -> bool:
        """pykrx로 OHLCV를 수집한다. 성공 시 True.

        pykrx 개별 종목 OHLCV는 KRX 로그인 없이 동작한다.
        """
        try:
            from pykrx import stock

            df = stock.get_market_ohlcv(start, end, code)
            if df.empty:
                return False

            rows = []
            for dt in df.index:
                date_str = dt.strftime("%Y%m%d")
                row = df.loc[dt]
                rows.append((
                    code, date_str,
                    float(row["시가"]), float(row["고가"]),
                    float(row["저가"]), float(row["종가"]),
                    int(row["거래량"]), 0,
                ))

            if rows:
                self.store.save_ohlcv_bulk(rows)
                logger.debug("OHLCV (pykrx): %s (%d건)", code, len(rows))
            return True

        except Exception as e:
            logger.debug("pykrx OHLCV 실패: %s: %s (네이버 폴백)", code, e)
            return False

    def _collect_ohlcv_naver(self, code: str, start: str, end: str) -> None:
        """네이버 금융에서 OHLCV를 페이지별로 스크래핑한다 (느림)."""
        rows = []
        page = 1
        max_pages = 100

        while page <= max_pages:
            try:
                resp = requests.get(
                    NAVER_SISE_URL,
                    params={"code": code, "page": page},
                    headers=HEADERS,
                    timeout=10,
                )
                resp.raise_for_status()
            except Exception as e:
                logger.warning("OHLCV 수집 실패: %s page %d: %s", code, page, e)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one("table.type2")
            if not table:
                break

            page_rows = table.select("tr")
            found_data = False
            reached_start = False

            for tr in page_rows:
                tds = tr.select("td span")
                if len(tds) < 7:
                    continue

                found_data = True
                date_str = tds[0].text.strip().replace(".", "")

                if date_str > end:
                    continue
                if date_str < start:
                    reached_start = True
                    break

                try:
                    close = int(tds[1].text.strip().replace(",", ""))
                    open_ = int(tds[3].text.strip().replace(",", ""))
                    high = int(tds[4].text.strip().replace(",", ""))
                    low = int(tds[5].text.strip().replace(",", ""))
                    volume = int(tds[6].text.strip().replace(",", ""))
                    rows.append((code, date_str, open_, high, low, close, volume, 0))
                except (ValueError, IndexError):
                    continue

            if reached_start or not found_data:
                break

            page += 1
            time.sleep(0.3)

        if rows:
            self.store.save_ohlcv_bulk(rows)
            logger.debug("OHLCV (naver): %s (%d건)", code, len(rows))

    def collect_stock_list(self, date: str, market: str = "KOSPI") -> list[dict]:
        """네이버 금융에서 종목 목록을 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (사용하지 않으나 인터페이스 호환).
            market: 시장 ("KOSPI" | "KOSDAQ").

        Returns:
            종목 정보 딕셔너리 리스트.
        """
        sosok = "0" if market == "KOSPI" else "1"
        base_url = "https://finance.naver.com/sise/sise_market_sum.naver"
        results: list[dict] = []

        for page in range(1, 50):
            try:
                resp = requests.get(
                    base_url,
                    params={"sosok": sosok, "page": page},
                    headers=HEADERS,
                    timeout=10,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a.tltle")
                if not links:
                    break
                for a in links:
                    code = a["href"].split("=")[-1]
                    name = a.text.strip()
                    self.store.upsert_stock(code, name, market)
                    results.append({"code": code, "name": name, "market": market})
            except Exception:
                break
            time.sleep(0.3)

        logger.info("%s 종목 %d개 저장", market, len(results))
        return results
