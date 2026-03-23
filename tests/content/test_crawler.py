import pytest
from alphapulse.content.crawler import BlogCrawler


@pytest.fixture
def crawler():
    return BlogCrawler()


def test_build_urls(crawler):
    urls = crawler._build_urls("ranto28", "223001")
    assert len(urls) == 3
    assert "blog.naver.com/ranto28/223001" in urls[0]
    assert "m.blog.naver.com" in urls[1]
    assert "PostView.naver" in urls[2]


def test_clean_content(crawler):
    raw = """좋은 분석 내용입니다.

이웃추가
블로그 홈
카테고리 이동
공감한 사람 보러가기
댓글을 입력하세요
공유하기
JavaScript is required

실질적인 본문 내용."""
    cleaned = crawler._clean_content(raw)
    assert "이웃추가" not in cleaned
    assert "JavaScript" not in cleaned
    assert "좋은 분석 내용입니다" in cleaned
    assert "실질적인 본문 내용" in cleaned


def test_extract_category_from_html(crawler):
    html = '<div class="blog_category">경제 이야기</div>'
    cat = crawler._extract_category_from_html(html)
    assert cat == "경제 이야기"


def test_extract_category_none(crawler):
    html = '<div class="other">내용</div>'
    cat = crawler._extract_category_from_html(html)
    assert cat is None


def test_fallback_to_rss_summary(crawler):
    result = crawler._make_fallback_result("RSS 요약 텍스트입니다.")
    assert result["success"] is True
    assert result["method"] == "rss_fallback"
    assert "RSS 요약" in result["content"]


def test_fallback_failed(crawler):
    result = crawler._make_fallback_result("")
    assert result["success"] is False
