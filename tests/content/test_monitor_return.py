"""BlogMonitor.run_once 반환값 스모크."""
from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.content.monitor import BlogMonitor


@pytest.mark.asyncio
async def test_run_once_returns_no_new_when_empty():
    with patch("alphapulse.content.monitor.PostDetector") as PD, \
         patch("alphapulse.content.monitor.CategoryFilter"), \
         patch("alphapulse.content.monitor.BlogCrawler"), \
         patch("alphapulse.content.monitor.AnalysisOrchestrator"), \
         patch("alphapulse.content.monitor.ReportWriter"), \
         patch("alphapulse.content.monitor.TelegramNotifier"):
        PD.return_value.fetch_new_posts.return_value = []

        monitor = BlogMonitor(
            blog_id="x", state_file="/tmp/s.json",
            reports_dir="/tmp/r", gemini_api_key="k",
            telegram_bot_token="t", telegram_chat_id="c",
        )
        result = await monitor.run_once(send_telegram=False)

    assert result == {"processed": 0, "skipped": 0, "no_new": True}


@pytest.mark.asyncio
async def test_run_once_returns_counts():
    with patch("alphapulse.content.monitor.PostDetector") as PD, \
         patch("alphapulse.content.monitor.CategoryFilter") as CF, \
         patch("alphapulse.content.monitor.BlogCrawler"), \
         patch("alphapulse.content.monitor.AnalysisOrchestrator"), \
         patch("alphapulse.content.monitor.ReportWriter"), \
         patch("alphapulse.content.monitor.TelegramNotifier"):
        PD.return_value.fetch_new_posts.return_value = [
            {"id": "p1", "title": "A", "category": "경제"},
            {"id": "p2", "title": "B", "category": "스포츠"},
        ]
        CF.return_value.filter_posts.return_value = (
            [{"id": "p1", "title": "A", "category": "경제"}],  # targets
            [{"id": "p2", "title": "B", "category": "스포츠"}],  # skipped
        )

        monitor = BlogMonitor(
            blog_id="x", state_file="/tmp/s.json",
            reports_dir="/tmp/r", gemini_api_key="k",
            telegram_bot_token="t", telegram_chat_id="c",
        )
        monitor._process_post = AsyncMock(return_value=True)
        result = await monitor.run_once(send_telegram=False)

    assert result == {"processed": 1, "skipped": 1, "no_new": False}
