import pytest
import json
from unittest.mock import patch, MagicMock
from alphapulse.content.detector import PostDetector


@pytest.fixture
def detector(tmp_path):
    state_file = tmp_path / ".monitor_state.json"
    return PostDetector(blog_id="ranto28", state_file=str(state_file))


def _make_entry(title, log_no, category=None, summary="요약"):
    entry = MagicMock()
    entry.title = title
    entry.link = f"https://blog.naver.com/ranto28/{log_no}"
    entry.get = lambda k, d=None: {"summary": summary, "published": "Mon, 16 Mar 2026"}.get(k, d)
    entry.tags = [MagicMock(term=category)] if category else []
    return entry


def test_extract_log_no(detector):
    assert detector._extract_log_no("https://blog.naver.com/ranto28/223001") == "223001"


def test_extract_log_no_none(detector):
    assert detector._extract_log_no("https://blog.naver.com/ranto28/") is None


def test_new_posts_detected(detector):
    with patch("alphapulse.content.detector.feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = [_make_entry("테스트 글", "223001", "경제")]
        mock_parse.return_value.bozo = False
        posts = detector.fetch_new_posts()
        assert len(posts) == 1
        assert posts[0]["title"] == "테스트 글"
        assert posts[0]["id"] == "223001"
        assert posts[0]["category"] == "경제"


def test_seen_posts_skipped(detector):
    detector._mark_seen("223001")
    with patch("alphapulse.content.detector.feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = [_make_entry("테스트 글", "223001")]
        mock_parse.return_value.bozo = False
        posts = detector.fetch_new_posts()
        assert len(posts) == 0


def test_state_file_max_200(detector):
    for i in range(250):
        detector._mark_seen(str(i))
    state = detector._load_state()
    assert len(state["seen_ids"]) == 200


def test_force_latest(detector):
    detector._mark_seen("223001")
    with patch("alphapulse.content.detector.feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = [
            _make_entry("글1", "223001"),
            _make_entry("글2", "223002"),
            _make_entry("글3", "223003"),
        ]
        mock_parse.return_value.bozo = False
        posts = detector.fetch_new_posts(force_latest=2)
        assert len(posts) == 2


def test_bozo_feed_returns_empty(detector):
    with patch("alphapulse.content.detector.feedparser.parse") as mock_parse:
        mock_parse.return_value.bozo = True
        mock_parse.return_value.bozo_exception = Exception("bad feed")
        posts = detector.fetch_new_posts()
        assert len(posts) == 0
