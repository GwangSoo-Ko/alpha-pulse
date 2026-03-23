import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from alphapulse.core.notifier import TelegramNotifier


@pytest.fixture
def notifier():
    return TelegramNotifier(bot_token="test-token", chat_id="12345")


def test_markdown_to_html(notifier):
    md = """## 핵심 요약
- 포인트 1
- 포인트 2

## 주요 논점
- 논점 A
"""
    html = notifier._markdown_to_html(md)
    assert "<b>핵심 요약</b>" in html
    assert "• 포인트 1" in html


def test_build_message(notifier):
    msg = notifier._build_message(
        title="테스트 제목",
        category="경제",
        analysis="## 핵심 요약\n요약 내용",
        url="https://example.com",
    )
    assert "테스트 제목" in msg
    assert "경제" in msg
    assert "원문 보기" in msg


def test_escape_html(notifier):
    assert notifier._escape_html("A & B <C>") == "A &amp; B &lt;C&gt;"


def test_split_message_short(notifier):
    short = "짧은 메시지"
    parts = notifier._split_message(short)
    assert len(parts) == 1


def test_split_message_long(notifier):
    long_msg = "가나다라마바사\n" * 1000
    parts = notifier._split_message(long_msg)
    assert len(parts) >= 2
    assert all(len(p) <= 4096 for p in parts)


@pytest.mark.asyncio
async def test_send_success(notifier):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}

    with patch("alphapulse.core.notifier.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(
            title="테스트", category="경제",
            analysis="분석", url="https://example.com",
        )
        assert result is True
        mock_client.post.assert_called_once()


def test_build_message_with_source_tag(notifier):
    msg = notifier._build_message(
        title="채널 제목",
        category="채널",
        analysis="## 핵심 요약\n요약 내용",
        url="https://t.me/example/123",
        source_tag="[채널분석]",
    )
    assert "<b>[채널분석] 새 글 알림</b>" in msg
    assert "채널 제목" in msg
    assert "원문 보기" in msg


def test_build_message_no_source_tag(notifier):
    msg = notifier._build_message(
        title="일반 제목",
        category="경제",
        analysis="분석 내용",
        url="https://example.com",
    )
    assert "<b>새 글 알림</b>" in msg
    assert "[채널분석]" not in msg


@pytest.mark.asyncio
async def test_send_test_message(notifier):
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("alphapulse.core.notifier.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await notifier.send_test()
        assert result is True
