import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from pathlib import Path
from alphapulse.content.aggregator import MessageAggregator
from alphapulse.content.channel_monitor import TelegramChannelMonitor
import asyncio


@pytest.mark.asyncio
async def test_full_channel_pipeline(tmp_path):
    """메시지 수신 -> 글타래 묶기 -> 분석 -> 보고서 -> 텔레그램 전체 흐름"""

    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value="## 종합 보고서\n미국 CPI 분석 결과")

    reporter = MagicMock()
    report_path = tmp_path / "reports" / "test_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("test report")
    reporter.save = MagicMock(return_value=report_path)

    notifier = MagicMock()
    notifier.send = AsyncMock(return_value=True)

    monitor = TelegramChannelMonitor(
        api_id="12345",
        api_hash="abcdef",
        phone="+821012345678",
        channel_ids=["test_channel"],
        analyzer=analyzer,
        reporter=reporter,
        notifier=notifier,
        aggregation_window=1,  # 1초 윈도우 (테스트용)
        session_path=str(tmp_path / "test"),
        reports_dir=str(tmp_path / "reports"),
    )

    # Simulate messages arriving
    await monitor.aggregator.add_message(
        channel_id=123, channel_name="경제뉴스채널",
        text="미국 CPI 발표됨", timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await monitor.aggregator.add_message(
        channel_id=123, channel_name="경제뉴스채널",
        text="예상치 3.1% vs 실제 3.4%", timestamp=datetime(2026, 3, 16, 12, 0, 30)
    )
    await monitor.aggregator.add_message(
        channel_id=123, channel_name="경제뉴스채널",
        text="코어 CPI도 예상 상회하여 연준 금리 인하 기대 후퇴할 것으로 보임",
        timestamp=datetime(2026, 3, 16, 12, 1, 0)
    )

    # Wait for aggregation window to expire
    await asyncio.sleep(1.5)

    # Verify pipeline was called
    analyzer.analyze.assert_called_once()
    call_args = analyzer.analyze.call_args
    assert "경제뉴스채널" in call_args[0][0]  # title contains channel name
    assert "CPI" in call_args[0][1]  # content contains message text

    reporter.save.assert_called_once()
    save_kwargs = reporter.save.call_args
    assert "채널분석" in str(save_kwargs)  # source_tag

    notifier.send.assert_called_once()
    send_kwargs = notifier.send.call_args
    assert "채널분석" in str(send_kwargs)  # source_tag


@pytest.mark.asyncio
async def test_channel_pipeline_multiple_channels(tmp_path):
    """다른 채널의 글타래는 독립적으로 처리"""

    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value="## 분석\n결과")

    reporter = MagicMock()
    report_path = tmp_path / "reports" / "test.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("test")
    reporter.save = MagicMock(return_value=report_path)

    notifier = MagicMock()
    notifier.send = AsyncMock(return_value=True)

    monitor = TelegramChannelMonitor(
        api_id="12345", api_hash="abcdef", phone="+82",
        channel_ids=["ch1", "ch2"],
        analyzer=analyzer, reporter=reporter, notifier=notifier,
        aggregation_window=1,
        session_path=str(tmp_path / "test"),
        reports_dir=str(tmp_path / "reports"),
    )

    await monitor.aggregator.add_message(
        channel_id=100, channel_name="채널A",
        text="채널A의 중요한 경제 뉴스 메시지입니다",
        timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )
    await monitor.aggregator.add_message(
        channel_id=200, channel_name="채널B",
        text="채널B의 주식 시장 분석 메시지입니다",
        timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )

    await asyncio.sleep(1.5)

    assert analyzer.analyze.call_count == 2
    assert reporter.save.call_count == 2
    assert notifier.send.call_count == 2


@pytest.mark.asyncio
async def test_channel_pipeline_analysis_failure(tmp_path):
    """분석 실패 시 에러 처리 (프로세스 중단 안 됨)"""

    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(side_effect=Exception("API 장애"))

    monitor = TelegramChannelMonitor(
        api_id="12345", api_hash="abcdef", phone="+82",
        channel_ids=["ch1"],
        analyzer=analyzer, reporter=MagicMock(), notifier=MagicMock(),
        aggregation_window=1,
        session_path=str(tmp_path / "test"),
        reports_dir=str(tmp_path / "reports"),
    )

    await monitor.aggregator.add_message(
        channel_id=123, channel_name="채널",
        text="분석 실패 테스트를 위한 충분히 긴 메시지입니다",
        timestamp=datetime(2026, 3, 16, 12, 0, 0)
    )

    # Should not raise
    await asyncio.sleep(1.5)
    # Verify it attempted analysis
    analyzer.analyze.assert_called_once()
