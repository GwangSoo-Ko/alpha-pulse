import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from alphapulse.content.monitor import BlogMonitor


@pytest.fixture
def blog_monitor(tmp_path):
    return BlogMonitor(
        blog_id="ranto28",
        state_file=str(tmp_path / ".state.json"),
        reports_dir=str(tmp_path / "reports"),
        gemini_api_key="test-key",
        telegram_bot_token="test-token",
        telegram_chat_id="12345",
    )


@pytest.mark.asyncio
async def test_process_post_success(blog_monitor):
    post = {
        "id": "123",
        "title": "테스트 글",
        "link": "https://blog.naver.com/ranto28/123",
        "published": "2026-03-16",
        "summary_rss": "RSS 요약",
        "category": "경제",
    }

    with patch.object(blog_monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(blog_monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze, \
         patch.object(blog_monitor.notifier, "send", new_callable=AsyncMock) as mock_send:

        mock_crawl.return_value = {
            "success": True,
            "content": "크롤링된 본문 " * 50,
            "method": "direct",
            "category": "경제",
        }
        mock_analyze.return_value = "## 핵심 요약\n분석 결과"
        mock_send.return_value = True

        result = await blog_monitor._process_post(post, send_telegram=False)
        assert result is True
        mock_crawl.assert_called_once()
        mock_analyze.assert_called_once()


@pytest.mark.asyncio
async def test_process_post_crawl_failure(blog_monitor):
    post = {
        "id": "123", "title": "실패 글",
        "link": "https://blog.naver.com/ranto28/123",
        "published": "2026-03-16", "summary_rss": "", "category": "경제",
    }

    with patch.object(blog_monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = {"success": False, "content": "", "method": "failed", "category": None}
        result = await blog_monitor._process_post(post, send_telegram=False)
        assert result is False


@pytest.mark.asyncio
async def test_run_once_filters_categories(blog_monitor):
    with patch.object(blog_monitor.detector, "fetch_new_posts") as mock_fetch, \
         patch.object(blog_monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(blog_monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze:

        mock_fetch.return_value = [
            {"id": "1", "title": "경제 뉴스", "link": "https://blog.naver.com/ranto28/1",
             "published": "2026-03-16", "summary_rss": "요약", "category": "경제"},
            {"id": "2", "title": "여행기", "link": "https://blog.naver.com/ranto28/2",
             "published": "2026-03-16", "summary_rss": "요약", "category": "여행"},
        ]
        mock_crawl.return_value = {
            "success": True, "content": "본문 " * 100, "method": "direct", "category": "경제",
        }
        mock_analyze.return_value = "## 핵심 요약\n분석"

        await blog_monitor.run_once(send_telegram=False)

        # Only the 경제 post should be crawled
        mock_crawl.assert_called_once()
        mock_analyze.assert_called_once()


@pytest.mark.asyncio
async def test_run_once_no_new_posts(blog_monitor):
    with patch.object(blog_monitor.detector, "fetch_new_posts") as mock_fetch:
        mock_fetch.return_value = []
        await blog_monitor.run_once(send_telegram=False)
        # Should complete without error
