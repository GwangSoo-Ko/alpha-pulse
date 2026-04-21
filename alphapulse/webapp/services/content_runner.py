"""ContentRunner — Job 에서 호출되는 BlogMonitor 실행 async 헬퍼.

BlogMonitor.run_once() 는 coroutine function 이므로 JobRunner 의
asyncio.to_thread 경로를 우회하고 직접 await 된다 (Task 2 에서 추가됨).
웹에서 실행되는 Job 은 텔레그램 발송을 끄고(`send_telegram=False`) 조용히 수집만.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.content.monitor import BlogMonitor


async def run_content_monitor_async(
    *,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """BlogMonitor.run_once(send_telegram=False) 실행.

    Args:
        progress_callback: Job 진행률 훅 (current, total, text).

    Returns:
        요약 문자열 (Job.result_ref 로 저장): "처리 N개, 스킵 M개"
        또는 "새 글 없음".
    """
    progress_callback(0, 1, "BlogPulse 모니터링 시작")
    monitor = BlogMonitor()
    summary = await monitor.run_once(send_telegram=False)
    if summary["no_new"]:
        text = "새 글 없음"
    else:
        text = f"처리 {summary['processed']}개, 스킵 {summary['skipped']}개"
    progress_callback(1, 1, text)
    return text
