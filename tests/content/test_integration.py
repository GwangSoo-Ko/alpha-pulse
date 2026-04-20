from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.content.monitor import BlogMonitor


@pytest.mark.asyncio
async def test_full_pipeline_target_post(tmp_path):
    """대상 카테고리 글이 전체 파이프라인을 통과하는지 검증"""
    monitor = BlogMonitor(
        blog_id="ranto28",
        state_file=str(tmp_path / ".state.json"),
        reports_dir=str(tmp_path / "reports"),
        gemini_api_key="test",
        telegram_bot_token="test",
        telegram_chat_id="123",
    )

    with patch.object(monitor.detector, "fetch_new_posts") as mock_fetch, \
         patch.object(monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze, \
         patch.object(monitor.notifier, "send", new_callable=AsyncMock) as mock_send:

        mock_fetch.return_value = [
            {"id": "1", "title": "미국 금리 전망", "link": "https://blog.naver.com/ranto28/1",
             "published": "2026-03-16", "summary_rss": "금리 요약", "category": "경제"},
        ]
        mock_crawl.return_value = {
            "success": True, "content": "미국 연준이 금리를 " * 50,
            "method": "direct", "category": "경제",
        }
        mock_analyze.return_value = "## 핵심 요약\n미국 금리 인하 전망 분석"
        mock_send.return_value = True

        await monitor.run_once(send_telegram=True)

        mock_crawl.assert_called_once()
        mock_analyze.assert_called_once()
        mock_send.assert_called_once()

        reports = list((tmp_path / "reports").glob("*.md"))
        assert len(reports) == 1
        content = reports[0].read_text()
        assert "미국 금리 전망" in content
        assert "핵심 요약" in content


@pytest.mark.asyncio
async def test_full_pipeline_mixed_categories(tmp_path):
    """대상/비대상 카테고리가 섞인 경우 필터링 검증"""
    monitor = BlogMonitor(
        blog_id="ranto28",
        state_file=str(tmp_path / ".state.json"),
        reports_dir=str(tmp_path / "reports"),
        gemini_api_key="test",
        telegram_bot_token="test",
        telegram_chat_id="123",
    )

    with patch.object(monitor.detector, "fetch_new_posts") as mock_fetch, \
         patch.object(monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze, \
         patch.object(monitor.notifier, "send", new_callable=AsyncMock) as mock_send:

        mock_fetch.return_value = [
            {"id": "1", "title": "경제 뉴스", "link": "https://blog.naver.com/ranto28/1",
             "published": "2026-03-16", "summary_rss": "요약1", "category": "경제"},
            {"id": "2", "title": "여행 후기", "link": "https://blog.naver.com/ranto28/2",
             "published": "2026-03-16", "summary_rss": "요약2", "category": "여행"},
            {"id": "3", "title": "주식 분석", "link": "https://blog.naver.com/ranto28/3",
             "published": "2026-03-16", "summary_rss": "요약3", "category": "주식"},
        ]
        mock_crawl.return_value = {
            "success": True, "content": "본문 내용 " * 100,
            "method": "direct", "category": None,
        }
        mock_analyze.return_value = "## 핵심 요약\n분석 결과"
        mock_send.return_value = True

        await monitor.run_once(send_telegram=True)

        assert mock_crawl.call_count == 2  # 경제 + 주식만
        assert mock_analyze.call_count == 2
        assert mock_send.call_count == 2

        reports = list((tmp_path / "reports").glob("*.md"))
        assert len(reports) == 2


@pytest.mark.asyncio
async def test_full_pipeline_no_telegram(tmp_path):
    """텔레그램 전송 없이 보고서만 생성"""
    monitor = BlogMonitor(
        blog_id="ranto28",
        state_file=str(tmp_path / ".state.json"),
        reports_dir=str(tmp_path / "reports"),
        gemini_api_key="test",
        telegram_bot_token="test",
        telegram_chat_id="123",
    )

    with patch.object(monitor.detector, "fetch_new_posts") as mock_fetch, \
         patch.object(monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze, \
         patch.object(monitor.notifier, "send", new_callable=AsyncMock) as mock_send:

        mock_fetch.return_value = [
            {"id": "1", "title": "사회 이슈", "link": "https://blog.naver.com/ranto28/1",
             "published": "2026-03-16", "summary_rss": "요약", "category": "사회"},
        ]
        mock_crawl.return_value = {
            "success": True, "content": "사회 이슈 내용 " * 50,
            "method": "direct", "category": "사회",
        }
        mock_analyze.return_value = "## 핵심 요약\n사회 분석"

        await monitor.run_once(send_telegram=False)

        mock_send.assert_not_called()
        reports = list((tmp_path / "reports").glob("*.md"))
        assert len(reports) == 1


@pytest.mark.asyncio
async def test_pipeline_resilience_on_crawl_failure(tmp_path):
    """한 글 크롤링 실패 시 나머지 글은 계속 처리"""
    monitor = BlogMonitor(
        blog_id="ranto28",
        state_file=str(tmp_path / ".state.json"),
        reports_dir=str(tmp_path / "reports"),
        gemini_api_key="test",
        telegram_bot_token="test",
        telegram_chat_id="123",
    )

    with patch.object(monitor.detector, "fetch_new_posts") as mock_fetch, \
         patch.object(monitor.crawler, "crawl", new_callable=AsyncMock) as mock_crawl, \
         patch.object(monitor.analyzer, "analyze", new_callable=AsyncMock) as mock_analyze, \
         patch.object(monitor.notifier, "send", new_callable=AsyncMock) as mock_send:

        mock_fetch.return_value = [
            {"id": "1", "title": "실패할 글", "link": "https://blog.naver.com/ranto28/1",
             "published": "2026-03-16", "summary_rss": "", "category": "경제"},
            {"id": "2", "title": "성공할 글", "link": "https://blog.naver.com/ranto28/2",
             "published": "2026-03-16", "summary_rss": "요약", "category": "주식"},
        ]
        mock_crawl.side_effect = [
            {"success": False, "content": "", "method": "failed", "category": None},
            {"success": True, "content": "성공 본문 " * 50, "method": "direct", "category": "주식"},
        ]
        mock_analyze.return_value = "## 핵심 요약\n분석"
        mock_send.return_value = True

        await monitor.run_once(send_telegram=False)

        assert mock_crawl.call_count == 2
        assert mock_analyze.call_count == 1  # only the successful one
        reports = list((tmp_path / "reports").glob("*.md"))
        assert len(reports) == 1
