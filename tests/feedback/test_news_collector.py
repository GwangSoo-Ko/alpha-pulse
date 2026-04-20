from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.feedback.news_collector import NewsCollector


@pytest.fixture
def collector():
    return NewsCollector()


def test_parse_articles():
    """HTML 파싱 테스트 (mock HTML)"""
    collector = NewsCollector()
    mock_html = '''
    <ul class="newsList">
        <li>
            <a href="/news/read?article_id=123&office_id=001" class="articleSubject">
                코스피 1.2% 상승 외국인 순매수
            </a>
            <span class="articleSummary">
                외국인 8천억 순매수에 코스피가 상승했다.
            </span>
            <span class="wdate">2026-04-03 16:30</span>
            <span class="press">한국경제</span>
        </li>
    </ul>
    '''
    articles = collector._parse_articles(mock_html)
    assert len(articles) >= 1
    assert "코스피" in articles[0]["title"]


@pytest.mark.asyncio
@patch("alphapulse.feedback.news_collector.httpx.AsyncClient")
async def test_collect_market_news(mock_client_cls):
    """뉴스 수집 전체 파이프라인 (mock HTTP)"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '''
    <ul class="newsList">
        <li>
            <a href="/news/read?article_id=123" class="articleSubject">테스트 뉴스 제목</a>
            <span class="articleSummary">테스트 요약입니다.</span>
            <span class="wdate">2026-04-03 16:30</span>
            <span class="press">테스트신문</span>
        </li>
    </ul>
    '''
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    collector = NewsCollector()
    result = await collector.collect_market_news()
    assert "articles" in result
    assert isinstance(result["articles"], list)


def test_collect_market_news_empty():
    """결과 없을 때"""
    collector = NewsCollector()
    articles = collector._parse_articles("<html></html>")
    assert articles == []
