"""종목별 투자자 수급 수집기 -- 네이버 금융 기반.

외국인/기관 순매매량을 네이버 금융에서 스크래핑한다.
"""

import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

NAVER_FRGN_URL = "https://finance.naver.com/item/frgn.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}


class FlowCollector:
    """종목별 수급 수집기 (네이버 금융 기반)."""

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, code: str, start: str, end: str) -> bool:
        """종목의 외국인/기관 순매매량을 수집하여 DB에 저장한다.

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        rows = []
        page = 1
        max_pages = 100

        while page <= max_pages:
            try:
                resp = requests.get(
                    NAVER_FRGN_URL,
                    params={"code": code, "page": page},
                    headers=HEADERS,
                    timeout=10,
                )
                resp.raise_for_status()
            except Exception as e:
                logger.warning("수급 수집 실패: %s page %d: %s", code, page, e)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            # frgn.naver의 두 번째 table.type2가 수급 데이터
            tables = soup.select("table.type2")
            if len(tables) < 2:
                break
            table = tables[1]

            page_rows = table.select("tr")
            found_data = False
            reached_start = False

            for tr in page_rows:
                tds = tr.select("td")
                if len(tds) < 9:
                    continue

                found_data = True
                date_text = tds[0].text.strip().replace(".", "")

                if date_text > end:
                    continue
                if date_text < start:
                    reached_start = True
                    break

                try:
                    # 기관순매매 (index 5), 외국인순매매 (index 6)
                    institutional = self._parse_number(tds[5].text)
                    foreign = self._parse_number(tds[6].text)
                    # 개인 = -(기관+외국인) 근사
                    individual = -(institutional + foreign)
                    # 외국인 보유율 (index 8)
                    holding_pct_text = tds[8].text.strip().replace("%", "")
                    holding_pct = (
                        float(holding_pct_text) if holding_pct_text else None
                    )
                    rows.append(
                        (code, date_text, foreign, institutional, individual,
                         holding_pct)
                    )
                except (ValueError, IndexError):
                    continue

            if reached_start or not found_data:
                break

            page += 1
            time.sleep(0.3)

        if rows:
            self.store.save_investor_flow_bulk(rows)
            logger.info("수급 저장: %s (%d건)", code, len(rows))
            return True
        return False

    @staticmethod
    def _parse_number(text: str) -> int:
        """'+1,234' 또는 '-1,234' 형태를 int로 변환한다."""
        cleaned = text.strip().replace(",", "").replace("+", "")
        if not cleaned or cleaned == "0":
            return 0
        return int(cleaned)
