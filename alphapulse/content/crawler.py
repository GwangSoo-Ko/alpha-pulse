import asyncio
import logging
import re

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_cfg = Config()

NOISE_PATTERNS = [
    "이웃추가", "블로그 홈", "카테고리 이동", "포스트 목록",
    "공감한 사람", "댓글을 입력", "공유하기", "본문 기타 기능",
    "JavaScript",
]


class BlogCrawler:
    def __init__(self, max_retries: int = _cfg.MAX_RETRIES):
        self.max_retries = max_retries

    async def crawl(self, blog_id: str, log_no: str, rss_summary: str = "") -> dict:
        urls = self._build_urls(blog_id, log_no)

        for i, url in enumerate(urls):
            method = ["direct", "mobile", "postview"][i]
            try:
                result = await self._try_crawl(url, method)
                if result and len(result.get("content", "")) > 200:
                    result["content"] = self._clean_content(result["content"])
                    return result
            except Exception as e:
                logger.warning(f"크롤링 실패 ({method}): {e}")

        if rss_summary:
            logger.info("모든 크롤링 실패, RSS 요약으로 폴백")
            return self._make_fallback_result(rss_summary)

        return {"success": False, "content": "", "method": "failed", "category": None}

    async def _try_crawl(self, url: str, method: str) -> dict | None:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_config = BrowserConfig(headless=True)
        run_config = CrawlerRunConfig(
            wait_until="networkidle",
            delay_before_return_html=3.0,
        )

        for attempt in range(self.max_retries):
            try:
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    result = await crawler.arun(url=url, config=run_config)
                    if result.success and result.markdown and len(result.markdown.raw_markdown) > 200:
                        category = self._extract_category_from_html(result.html or "")
                        return {
                            "success": True,
                            "content": result.markdown.raw_markdown,
                            "method": method,
                            "category": category,
                        }
                    elif result.success:
                        # 크롤링은 성공했지만 본문이 부족 → 이 URL은 재시도해도 같은 결과
                        logger.info(f"본문 부족 ({len(result.markdown.raw_markdown if result.markdown else '')}자), 다음 URL로 전환")
                        return None
            except Exception as e:
                logger.warning(f"크롤링 시도 {attempt + 1}/{self.max_retries} 실패: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)

        return None

    def _build_urls(self, blog_id: str, log_no: str) -> list[str]:
        return [
            f"https://blog.naver.com/{blog_id}/{log_no}",
            f"https://m.blog.naver.com/{blog_id}/{log_no}",
            f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}",
        ]

    def _clean_content(self, text: str) -> str:
        lines = text.split("\n")
        cleaned = [
            line for line in lines
            if not any(noise in line for noise in NOISE_PATTERNS)
        ]
        return "\n".join(cleaned).strip()

    def _extract_category_from_html(self, html: str) -> str | None:
        patterns = [
            r'class="blog_category"[^>]*>([^<]+)<',
            r'class="wrap_blog_category"[^>]*>([^<]+)<',
            r'class="category"[^>]*>([^<]+)<',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return None

    def _make_fallback_result(self, rss_summary: str) -> dict:
        if not rss_summary:
            return {"success": False, "content": "", "method": "rss_fallback", "category": None}
        return {
            "success": True,
            "content": rss_summary,
            "method": "rss_fallback",
            "category": None,
        }
