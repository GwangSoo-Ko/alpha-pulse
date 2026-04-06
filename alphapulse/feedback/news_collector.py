"""네이버 금융 뉴스 수집 — 장 마감 후 시황 기사."""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

NAVER_FINANCE_NEWS_URL = "https://finance.naver.com/news/mainnews.naver"
HEADERS = {"User-Agent": "Mozilla/5.0"}


class NewsCollector:
    """네이버 금융 뉴스 크롤링."""

    def __init__(self):
        self.config = Config()
        self.max_articles = self.config.FEEDBACK_NEWS_COUNT

    def _parse_articles(self, html: str) -> list[dict]:
        """HTML에서 뉴스 기사 목록 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        articles = []

        # 네이버 금융 메인뉴스 구조
        for item in soup.select("li"):
            title_tag = item.select_one("a.articleSubject") or item.select_one("a[href*='article_id']")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            if not title:
                continue

            href = title_tag.get("href", "")
            url = f"https://finance.naver.com{href}" if href.startswith("/") else href

            summary_tag = item.select_one(".articleSummary") or item.select_one("span.lede")
            summary = summary_tag.get_text(strip=True)[:200] if summary_tag else ""

            date_tag = item.select_one(".wdate") or item.select_one("span.date")
            published = date_tag.get_text(strip=True) if date_tag else ""

            source_tag = item.select_one(".press") or item.select_one("span.infoPressNm")
            source = source_tag.get_text(strip=True) if source_tag else ""

            articles.append({
                "title": title,
                "source": source,
                "published": published,
                "summary": summary,
                "url": url,
            })

            if len(articles) >= self.max_articles:
                break

        return articles

    async def collect_market_news(self, date: str | None = None) -> dict:
        """네이버 금융 뉴스 수집 (장 마감 후 시황)."""
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
                resp = await client.get(NAVER_FINANCE_NEWS_URL)
                if resp.status_code != 200:
                    logger.warning(f"뉴스 수집 실패: HTTP {resp.status_code}")
                    return {"collected_at": datetime.now().isoformat(), "articles": []}

                articles = self._parse_articles(resp.text)
                logger.info(f"뉴스 {len(articles)}건 수집")
                return {
                    "collected_at": datetime.now().isoformat(),
                    "articles": articles,
                }

        except Exception as e:
            logger.warning(f"뉴스 수집 실패: {e}")
            return {"collected_at": datetime.now().isoformat(), "articles": []}
