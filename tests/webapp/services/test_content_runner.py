"""ContentRunner — Job 어댑터 테스트."""
import asyncio
from unittest.mock import AsyncMock, patch


def test_runs_blog_monitor_and_returns_summary():
    """BlogMonitor.run_once 를 호출하고 result_ref 로 요약 문자열 반환."""
    from alphapulse.webapp.services.content_runner import run_content_monitor_async

    mock_monitor = AsyncMock()
    mock_monitor.run_once.return_value = {
        "processed": 2, "skipped": 1, "no_new": False,
    }

    progress_calls: list[tuple[int, int, str]] = []
    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.services.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        result = asyncio.run(
            run_content_monitor_async(progress_callback=on_progress),
        )

    # BlogMonitor.run_once called with send_telegram=False
    mock_monitor.run_once.assert_awaited_once_with(send_telegram=False)

    # 결과 문자열 포맷: "처리 2개, 스킵 1개"
    assert "2" in result and "1" in result
    assert progress_calls[0] == (0, 1, "BlogPulse 모니터링 시작")
    assert progress_calls[-1][0] == 1 and progress_calls[-1][1] == 1


def test_handles_no_new_posts():
    from alphapulse.webapp.services.content_runner import run_content_monitor_async

    mock_monitor = AsyncMock()
    mock_monitor.run_once.return_value = {"processed": 0, "skipped": 0, "no_new": True}
    with patch(
        "alphapulse.webapp.services.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        result = asyncio.run(
            run_content_monitor_async(progress_callback=lambda *_: None),
        )
    # no_new 일 때는 "새 글 없음" 포함
    assert "새 글 없음" in result


def test_propagates_exception():
    import pytest

    from alphapulse.webapp.services.content_runner import run_content_monitor_async

    mock_monitor = AsyncMock()
    mock_monitor.run_once.side_effect = RuntimeError("crawl failed")
    with patch(
        "alphapulse.webapp.services.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        with pytest.raises(RuntimeError, match="crawl failed"):
            asyncio.run(
                run_content_monitor_async(progress_callback=lambda *_: None),
            )
