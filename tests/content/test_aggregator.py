import pytest
import asyncio
from datetime import datetime
from alphapulse.content.aggregator import MessageAggregator


@pytest.fixture
def collected_threads():
    return []


@pytest.fixture
def aggregator(collected_threads):
    async def on_ready(thread):
        collected_threads.append(thread)
    return MessageAggregator(window_seconds=1, on_thread_ready=on_ready, min_chars=0)


@pytest.mark.asyncio
async def test_add_message_buffers(aggregator):
    await aggregator.add_message(
        channel_id=123, channel_name="테스트채널",
        text="메시지1", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    assert 123 in aggregator.buffers
    assert len(aggregator.buffers[123]) == 1


@pytest.mark.asyncio
async def test_skip_empty_text(aggregator):
    await aggregator.add_message(
        channel_id=123, channel_name="채널",
        text="", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    assert 123 not in aggregator.buffers


@pytest.mark.asyncio
async def test_skip_none_text(aggregator):
    await aggregator.add_message(
        channel_id=123, channel_name="채널",
        text=None, timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    assert 123 not in aggregator.buffers


@pytest.mark.asyncio
async def test_flush_after_window(aggregator, collected_threads):
    await aggregator.add_message(
        channel_id=123, channel_name="경제채널",
        text="CPI 발표", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await aggregator.add_message(
        channel_id=123, channel_name="경제채널",
        text="예상치 상회", timestamp=datetime(2026, 3, 16, 12, 0, 30)
    )
    # Wait for window to expire (1 second window in test)
    await asyncio.sleep(1.5)
    assert len(collected_threads) == 1
    assert collected_threads[0]["channel_name"] == "경제채널"
    assert "CPI 발표" in collected_threads[0]["content"]
    assert "예상치 상회" in collected_threads[0]["content"]


@pytest.mark.asyncio
async def test_timer_reset_on_new_message(aggregator, collected_threads):
    await aggregator.add_message(
        channel_id=123, channel_name="채널",
        text="메시지1", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await asyncio.sleep(0.5)  # Half the window
    # New message resets timer
    await aggregator.add_message(
        channel_id=123, channel_name="채널",
        text="메시지2", timestamp=datetime(2026, 3, 16, 12, 0, 30)
    )
    await asyncio.sleep(0.7)  # Still within new window
    assert len(collected_threads) == 0  # Not flushed yet
    await asyncio.sleep(0.8)  # Now past window
    assert len(collected_threads) == 1
    assert len(collected_threads[0]["messages"]) == 2


@pytest.mark.asyncio
async def test_separate_channels(aggregator, collected_threads):
    await aggregator.add_message(
        channel_id=100, channel_name="채널A",
        text="A 메시지", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await aggregator.add_message(
        channel_id=200, channel_name="채널B",
        text="B 메시지", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await asyncio.sleep(1.5)
    assert len(collected_threads) == 2
    names = {t["channel_name"] for t in collected_threads}
    assert names == {"채널A", "채널B"}


@pytest.mark.asyncio
async def test_skip_short_thread(collected_threads):
    async def on_ready(thread):
        collected_threads.append(thread)
    agg = MessageAggregator(window_seconds=1, on_thread_ready=on_ready, min_chars=20)
    await agg.add_message(
        channel_id=123, channel_name="채널",
        text="짧음", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await asyncio.sleep(1.5)
    assert len(collected_threads) == 0  # Too short, skipped


def test_format_thread():
    agg = MessageAggregator(window_seconds=300)
    messages = [
        {"text": "CPI 발표됨", "timestamp": datetime(2026, 3, 16, 12, 0, 0)},
        {"text": "예상치 상회", "timestamp": datetime(2026, 3, 16, 12, 0, 30)},
        {"text": "연준 금리 인하 후퇴", "timestamp": datetime(2026, 3, 16, 12, 3, 0)},
    ]
    result = agg.format_thread("경제채널", messages)
    assert result["channel_name"] == "경제채널"
    assert "12:00" in result["title"]
    assert "12:03" in result["title"]
    assert "3개" in result["title"]
    assert "CPI 발표됨" in result["content"]
    assert "예상치 상회" in result["content"]
