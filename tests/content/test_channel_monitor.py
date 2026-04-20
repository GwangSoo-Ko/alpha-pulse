from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from alphapulse.content.channel_monitor import TelegramChannelMonitor


@pytest.fixture
def monitor(tmp_path):
    return TelegramChannelMonitor(
        api_id="12345",
        api_hash="abcdef",
        phone="+821012345678",
        channel_ids=["test_channel", "123456"],
        analyzer=MagicMock(),
        reporter=MagicMock(),
        notifier=MagicMock(),
        aggregation_window=300,
        session_path=str(tmp_path / "test"),
        reports_dir=str(tmp_path / "reports"),
    )


def test_init(monitor):
    assert len(monitor.channel_ids) == 2
    assert monitor.aggregator is not None
    assert monitor.aggregator.window == 300


def test_should_monitor_by_username(monitor):
    entity = MagicMock()
    entity.id = 999
    type(entity).username = PropertyMock(return_value="test_channel")
    assert monitor._should_monitor(entity) is True


def test_should_monitor_by_id(monitor):
    entity = MagicMock()
    entity.id = 123456
    type(entity).username = PropertyMock(return_value="other")
    assert monitor._should_monitor(entity) is True


def test_should_not_monitor_unknown(monitor):
    entity = MagicMock()
    entity.id = 999999
    type(entity).username = PropertyMock(return_value="unknown_channel")
    assert monitor._should_monitor(entity) is False


@pytest.mark.asyncio
async def test_on_thread_ready_calls_pipeline(monitor):
    thread = {
        "channel_name": "경제채널",
        "title": "[경제채널] 2026-03-16 12:00~12:03 (3개 메시지)",
        "content": "12:00 CPI 발표\n12:01 예상치 상회\n12:03 금리 인하 후퇴",
        "messages": [],
        "message_count": 3,
    }

    monitor.analyzer.analyze = AsyncMock(return_value="## 종합 보고서\n분석 결과")
    monitor.reporter.save = MagicMock(return_value=MagicMock())
    monitor.notifier.send = AsyncMock(return_value=True)

    await monitor._on_thread_ready(thread)

    monitor.analyzer.analyze.assert_called_once_with(thread["title"], thread["content"])
    monitor.reporter.save.assert_called_once()
    monitor.notifier.send.assert_called_once()

    # Check source_tag is passed
    save_kwargs = monitor.reporter.save.call_args
    assert "채널분석" in str(save_kwargs)


@pytest.mark.asyncio
async def test_on_thread_ready_handles_analysis_failure(monitor):
    thread = {
        "channel_name": "채널",
        "title": "제목",
        "content": "내용",
        "messages": [],
        "message_count": 1,
    }

    monitor.analyzer.analyze = AsyncMock(side_effect=Exception("API 실패"))

    # Should not raise, just log error
    await monitor._on_thread_ready(thread)
