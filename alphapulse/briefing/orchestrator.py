"""일일 브리핑 파이프라인 조율."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from alphapulse.core.config import Config
from alphapulse.core.storage import DataCache, PulseHistory
from alphapulse.market.engine.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class BriefingOrchestrator:
    """정량 + 정성 + AI 해설을 조합하여 일일 브리핑을 생성한다."""

    def __init__(self, reports_dir: str | None = None):
        self.config = Config()
        self.reports_dir = Path(reports_dir or self.config.REPORTS_DIR)
        self.config.ensure_data_dir()
        self.cache = DataCache(self.config.CACHE_DB)
        self.history = PulseHistory(self.config.HISTORY_DB)

    def run_quantitative(self, date: str | None = None) -> dict:
        """정량 파이프라인 실행 → Market Pulse Score."""
        engine = SignalEngine(cache=self.cache, history=self.history)
        return engine.run(date=date)

    def collect_recent_content(self, hours: int = 24) -> list[str]:
        """reports/ 디렉토리에서 최근 N시간 내 정성 분석 요약을 수집."""
        if not self.reports_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(hours=hours)
        summaries = []
        for md_file in sorted(self.reports_dir.glob("*.md"), reverse=True):
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            if mtime < cutoff:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
                summary = self._extract_summary(text, md_file.name)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                logger.warning(f"리포트 읽기 실패: {md_file.name}: {e}")
        return summaries

    def _extract_summary(self, text: str, filename: str) -> str | None:
        """마크다운 리포트에서 핵심 요약 섹션을 추출."""
        lines = text.split("\n")
        in_summary = False
        summary_lines = []
        for line in lines:
            if "핵심 요약" in line or "## 핵심" in line:
                in_summary = True
                continue
            if in_summary:
                if line.startswith("## ") or line.startswith("---"):
                    break
                if line.strip():
                    summary_lines.append(line.strip())
        if summary_lines:
            return f"[{filename}] " + " ".join(summary_lines[:5])
        return None

    async def run_async(self, date: str | None = None, send_telegram: bool = True) -> dict:
        """전체 브리핑 파이프라인 실행 (async entry point)."""
        # [0-1] 피드백: 전일 시장 결과 수집 + 미확정 시그널 평가
        feedback_context = None
        daily_result_msg = ""
        feedback_store = None
        yesterday = None
        if self.config.FEEDBACK_ENABLED:
            try:
                from alphapulse.core.storage.feedback import FeedbackStore
                from alphapulse.feedback.collector import FeedbackCollector
                from alphapulse.feedback.summarizer import FeedbackSummarizer

                feedback_store = FeedbackStore(self.config.DATA_DIR / "feedback.db")
                collector = FeedbackCollector(db_path=self.config.DATA_DIR / "feedback.db")
                await asyncio.to_thread(collector.collect_and_evaluate)

                summarizer = FeedbackSummarizer(store=feedback_store)
                feedback_context = summarizer.generate_ai_context(self.config.FEEDBACK_LOOKBACK_DAYS)
                yesterday = feedback_store.get_yesterday()
                daily_result_msg = summarizer.format_daily_result(yesterday)
                logger.info("피드백 수집/평가 완료")
            except Exception as e:
                logger.warning(f"피드백 수집 실패, 스킵: {e}")

        # [0-2] 뉴스 수집
        news = {"articles": []}
        if self.config.FEEDBACK_ENABLED and self.config.FEEDBACK_NEWS_ENABLED:
            try:
                from alphapulse.feedback.news_collector import NewsCollector
                news_collector = NewsCollector()
                news = await news_collector.collect_market_news()
                logger.info(f"장 후 뉴스 {len(news.get('articles', []))}건 수집")
            except Exception as e:
                logger.warning(f"뉴스 수집 실패, 스킵: {e}")

        # [0-3] 사후 분석 (전일 시그널 + 결과가 있을 때만)
        post_analysis = None
        if self.config.FEEDBACK_ENABLED and yesterday is not None and yesterday.get("return_1d") is not None:
            try:
                from alphapulse.feedback.agents.orchestrator import PostMarketOrchestrator
                post_orch = PostMarketOrchestrator()
                post_analysis = await post_orch.analyze(
                    signal=yesterday,
                    news=news,
                    content_summaries=self.collect_recent_content(hours=48),
                )
                # 분석 결과를 DB에 저장
                feedback_store.update_analysis(
                    date=yesterday["date"],
                    post_analysis=post_analysis.get("senior_synthesis", ""),
                    news_summary="\n".join(
                        a.get("title", "") for a in news.get("articles", [])[:5]
                    ),
                    blind_spots=post_analysis.get("blind_spots", ""),
                )
                logger.info("사후 분석 완료 및 저장")
            except Exception as e:
                logger.warning(f"사후 분석 실패, 스킵: {e}")

        # [1] 정량 분석 (sync — thread에서 실행)
        logger.info("정량 분석 실행 중...")
        pulse_result = await asyncio.to_thread(self.run_quantitative, date)

        # [2] 최근 정성 분석 수집
        logger.info("최근 정성 분석 수집 중...")
        content_summaries = self.collect_recent_content(hours=24)

        # [3] AI Commentary + SeniorSynthesis (async, 같은 이벤트 루프 내)
        commentary = None
        try:
            from alphapulse.agents.commentary import MarketCommentaryAgent
            agent = MarketCommentaryAgent()
            commentary = await agent.generate(pulse_result, content_summaries,
                                               feedback_context=feedback_context)
            logger.info("AI Commentary 생성 완료")
        except Exception as e:
            logger.warning(f"AI Commentary 생성 실패, 스킵: {e}")

        synthesis = None
        try:
            from alphapulse.agents.synthesis import SeniorSynthesisAgent
            synth_agent = SeniorSynthesisAgent()
            synthesis = await synth_agent.synthesize(pulse_result, content_summaries, commentary,
                                                     feedback_context=feedback_context)
            logger.info("종합 판단 생성 완료")
        except Exception as e:
            logger.warning(f"종합 판단 생성 실패, 스킵: {e}")

        # [4] Format
        from alphapulse.briefing.formatter import BriefingFormatter
        formatter = BriefingFormatter()
        quant_msg = formatter.format_quantitative(pulse_result, daily_result_msg=daily_result_msg)

        # Check if Monday for weekly summary
        is_monday = datetime.now().weekday() == 0
        weekly_msg = ""
        if is_monday and self.config.FEEDBACK_ENABLED:
            try:
                from alphapulse.feedback.summarizer import FeedbackSummarizer as _FS
                _summarizer = _FS(store=feedback_store) if feedback_store else None
                weekly_msg = _summarizer.format_weekly_summary() if _summarizer else ""
            except Exception:
                weekly_msg = ""

        synth_msg = formatter.format_synthesis(pulse_result, content_summaries, commentary, weekly_summary=weekly_msg)

        # [5] Send via Telegram (async, 단일 이벤트 루프 내)
        if send_telegram:
            from alphapulse.core.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            await notifier._send_message(quant_msg)
            await notifier._send_message(synth_msg)

        # [6] Save history
        self.history.save(
            pulse_result["date"], pulse_result["score"],
            pulse_result["signal"], pulse_result.get("details", {})
        )

        # [7] 오늘 시그널을 feedback DB에 기록
        if self.config.FEEDBACK_ENABLED:
            try:
                from alphapulse.core.storage.feedback import FeedbackStore
                feedback_store = FeedbackStore(self.config.DATA_DIR / "feedback.db")
                feedback_store.save_signal(
                    date=pulse_result["date"],
                    score=pulse_result["score"],
                    signal=pulse_result["signal"],
                    indicator_scores=pulse_result.get("indicator_scores", {}),
                )
                logger.info(f"오늘 시그널 피드백 DB 기록: {pulse_result['date']}")
            except Exception as e:
                logger.warning(f"시그널 피드백 기록 실패: {e}")

        return {
            "pulse_result": pulse_result,
            "content_summaries": content_summaries,
            "commentary": commentary,
            "synthesis": synthesis,
            "quant_msg": quant_msg,
            "synth_msg": synth_msg,
            "feedback_context": feedback_context,
            "daily_result_msg": daily_result_msg,
            "news": news,
            "post_analysis": post_analysis,
            "generated_at": datetime.now().isoformat(),
        }

    def run(self, date: str | None = None, send_telegram: bool = True) -> dict:
        """Sync wrapper — CLI에서 호출."""
        return asyncio.run(self.run_async(date=date, send_telegram=send_telegram))
