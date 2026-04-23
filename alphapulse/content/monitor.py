import asyncio
import logging
from typing import TypedDict

from alphapulse.content.agents import AnalysisOrchestrator
from alphapulse.content.category_filter import CategoryFilter
from alphapulse.content.crawler import BlogCrawler
from alphapulse.content.detector import PostDetector
from alphapulse.content.reporter import ReportWriter
from alphapulse.core.config import Config
from alphapulse.core.notifier import TelegramNotifier


class RunOnceSummary(TypedDict):
    processed: int
    skipped: int
    no_new: bool


logger = logging.getLogger("alphapulse.content")

_cfg = Config()


class BlogMonitor:
    def __init__(
        self,
        blog_id: str = _cfg.BLOG_ID,
        state_file: str = _cfg.STATE_FILE,
        reports_dir: str = _cfg.REPORTS_DIR,
        gemini_api_key: str = _cfg.GEMINI_API_KEY,
        telegram_bot_token: str = _cfg.TELEGRAM_BOT_TOKEN,
        telegram_chat_id: str = _cfg.TELEGRAM_CHAT_ID,
    ):
        self.detector = PostDetector(blog_id=blog_id, state_file=state_file)
        self.category_filter = CategoryFilter()
        self.crawler = BlogCrawler()
        self.analyzer = AnalysisOrchestrator(api_key=gemini_api_key)
        self.reporter = ReportWriter(reports_dir=reports_dir)
        self.notifier = TelegramNotifier(
            bot_token=telegram_bot_token, chat_id=telegram_chat_id
        )
        self.blog_id = blog_id

    async def run_once(
        self, force_latest: int = 0, send_telegram: bool = True
    ) -> RunOnceSummary:
        """신규 포스트 처리.

        Returns:
            요약 dict: {processed: int, skipped: int, no_new: bool}
        """
        logger.info("모니터링 시작...")
        posts = self.detector.fetch_new_posts(force_latest=force_latest)

        if not posts:
            logger.info("새 글 없음")
            return {"processed": 0, "skipped": 0, "no_new": True}

        logger.info(f"{len(posts)}개 새 글 발견")
        target_posts, skipped = self.category_filter.filter_posts(posts)

        if not target_posts:
            logger.info("대상 카테고리 글 없음")
            for post in posts:
                self.detector.mark_seen(post["id"])
            return {"processed": 0, "skipped": len(skipped), "no_new": False}

        logger.info(f"대상 글 {len(target_posts)}개, 스킵 {len(skipped)}개")

        processed = 0
        for post in target_posts:
            try:
                ok = await self._process_post(post, send_telegram=send_telegram)
                if ok:
                    processed += 1
            except Exception as e:
                logger.error(f'글 처리 실패 "{post["title"]}": {e}')
            finally:
                self.detector.mark_seen(post["id"])

        for post in skipped:
            self.detector.mark_seen(post["id"])

        return {"processed": processed, "skipped": len(skipped), "no_new": False}

    async def _process_post(self, post: dict, send_telegram: bool = True) -> bool:
        logger.info(f'처리 중: "{post["title"]}"')

        crawl_result = await self.crawler.crawl(
            self.blog_id, post["id"], rss_summary=post.get("summary_rss", "")
        )

        if not crawl_result["success"]:
            logger.error(f'크롤링 실패: "{post["title"]}"')
            return False

        if not post.get("category") and crawl_result.get("category"):
            post["category"] = crawl_result["category"]

        analysis = await self.analyzer.analyze(post["title"], crawl_result["content"])

        report_path = self.reporter.save(
            title=post["title"],
            url=post["link"],
            published=post.get("published", ""),
            category=post.get("category", ""),
            analysis=analysis,
            original_content=crawl_result["content"],
        )

        try:
            from alphapulse.webapp.store.readers.content import ContentReader

            ContentReader(
                reports_dir=self.reporter.reports_dir,
                fts_db_path=_cfg.CONTENT_SEARCH_DB,
            ).upsert_index(report_path.name)
        except Exception as e:
            logger.warning("content_search upsert failed for %s: %s", report_path.name, e)

        if send_telegram:
            await self.notifier.send(
                title=post["title"],
                category=post.get("category", ""),
                analysis=analysis,
                url=post["link"],
                report_path=report_path,
            )

        logger.info(f'완료: "{post["title"]}" → {report_path.name}')
        return True

    async def run_daemon(self, interval: int = _cfg.CHECK_INTERVAL, send_telegram: bool = True):
        logger.info(f"데몬 모드 시작 (주기: {interval}초)")
        while True:
            try:
                await self.run_once(send_telegram=send_telegram)
            except Exception as e:
                logger.error(f"루프 에러: {e}")
            await asyncio.sleep(interval)
