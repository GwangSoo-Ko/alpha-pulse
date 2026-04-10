"""공매도 수집기 — KRX data.krx.co.kr crawl4ai 기반.

KRX 공매도 통계 페이지를 crawl4ai로 렌더링하여
종목별 일별 공매도 수량/금액/잔고를 수집한다.
"""

import logging
from pathlib import Path

from bs4 import BeautifulSoup

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)

KRX_SHORT_URL = (
    "https://data.krx.co.kr/comm/srt/srtLoader/index.cmd"
    "?screenId=MDCSTAT300&isuCd={code}"
)


class ShortCollector:
    """공매도 수집기 (KRX crawl4ai 기반).

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    async def collect_async(self, code: str, start: str, end: str) -> int:
        """공매도 데이터를 KRX에서 crawl4ai로 수집하여 DB에 저장한다.

        Args:
            code: 종목코드 (예: "005930").
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).

        Returns:
            저장된 행 수. 실패 시 0.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            url = KRX_SHORT_URL.format(code=code)
            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                delay_before_return_html=5.0,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if not result.success or not result.html:
                    logger.debug("공매도 크롤링 실패: %s", code)
                    return 0

                rows = self._parse_short_data(result.html, code, start, end)
                if rows:
                    self.store.save_short_interest_bulk(rows)
                    logger.info("공매도 저장: %s (%d건)", code, len(rows))
                return len(rows)

        except Exception as e:
            logger.debug("공매도 수집 실패: %s: %s", code, e)
            return 0

    def collect(self, code: str, start: str, end: str) -> None:
        """동기 인터페이스 (BulkCollector 호환).

        이 메서드는 안내만 출력한다. 실제 수집은 collect_async()를 사용해야 한다.
        """
        logger.info(
            "공매도 수집: %s. 'ap trading data collect-short' 또는 "
            "collect_async()를 사용하세요.",
            code,
        )

    def _parse_short_data(
        self, html: str, code: str, start: str, end: str
    ) -> list[tuple]:
        """KRX 공매도 HTML에서 데이터를 파���한다.

        Args:
            html: crawl4ai가 렌더링한 HTML.
            code: 종목코드.
            start: 시작일 필터.
            end: 종료일 필터.

        Returns:
            (code, date, short_volume, short_balance,
             short_ratio, credit_balance, lending_balance) 튜플 리스트.
        """
        soup = BeautifulSoup(html, "html.parser")
        rows = []

        # KRX 테이블: 일자, 전체, 업틱룰적용, 업틱룰예외, 순보유잔고수량,
        #            전체(금액), 업틱룰적용(금액), 업틱룰예외(금액), 순보유잔고금액
        for table in soup.select("table"):
            trs = table.select("tr")
            if len(trs) < 3:
                continue

            # 헤더에 '일자'와 '공매도' 또는 '잔고' 포함 여부 확인
            header_text = " ".join(
                th.get_text(strip=True) for th in trs[0].select("th")
            )
            if "일자" not in header_text:
                continue

            for tr in trs[1:]:
                tds = tr.select("td")
                if len(tds) < 5:
                    continue

                date_text = tds[0].get_text(strip=True).replace("/", "")
                if len(date_text) != 8 or not date_text.isdigit():
                    continue

                # 날짜 범위 필터
                if date_text < start or date_text > end:
                    continue

                short_volume = self._parse_int(tds[1].get_text(strip=True))
                short_balance_text = tds[4].get_text(strip=True)
                short_balance = self._parse_int(short_balance_text)

                # 거래량 대비 공매도 비율은 별도 계산 필요 (OHLCV 거래량 참조)
                short_ratio = 0.0

                # credit_balance, lending_balance는 이 페이��에서 제공되��� 않음
                # short_balance를 lending_balance로 매핑
                rows.append((
                    code,
                    date_text,
                    short_volume if short_volume else 0,
                    short_balance if short_balance else 0,
                    short_ratio,
                    0,  # credit_balance — 별도 소스 필요
                    short_balance if short_balance else 0,  # lending_balance
                ))

            if rows:
                break  # 데이터 테이블을 찾았으면 종료

        return rows

    @staticmethod
    def _parse_int(text: str) -> int | None:
        """'1,259,931' 형태를 int로 변환한다."""
        cleaned = text.replace(",", "").replace("-", "").strip()
        if not cleaned or cleaned == "0":
            return 0
        try:
            return int(cleaned)
        except ValueError:
            return None
