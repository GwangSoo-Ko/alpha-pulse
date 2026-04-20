import pytest

from alphapulse.content.category_filter import CategoryFilter


@pytest.fixture
def cf():
    return CategoryFilter(target_categories=["경제", "주식", "국제정세", "사회"])


def test_exact_match(cf):
    assert cf.is_target_category("경제") is True


def test_partial_match(cf):
    assert cf.is_target_category("경제 이야기") is True


def test_non_target(cf):
    assert cf.is_target_category("여행") is False


def test_none_category(cf):
    assert cf.is_target_category(None) is False


def test_empty_category(cf):
    assert cf.is_target_category("") is False


def test_filter_posts(cf):
    posts = [
        {"id": "1", "title": "경제 뉴스", "category": "경제"},
        {"id": "2", "title": "여행기", "category": "여행"},
        {"id": "3", "title": "주식 분석", "category": "주식"},
        {"id": "4", "title": "알 수 없음", "category": None},
    ]
    target, skipped = cf.filter_posts(posts)
    assert len(target) == 2
    assert len(skipped) == 2
    assert target[0]["id"] == "1"
    assert target[1]["id"] == "3"
