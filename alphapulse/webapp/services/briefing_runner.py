"""BriefingRunner — Job 에서 호출되는 BriefingOrchestrator 실행 async 헬퍼.

BriefingOrchestrator.run_async() 는 coroutine function — JobRunner 의
iscoroutinefunction 분기로 직접 await 된다 (Content 작업에서 추가됨).
웹 Job 은 텔레그램 발송 off — 디버깅/재확인 시 스팸 방지.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from alphapulse.briefing.orchestrator import BriefingOrchestrator

if TYPE_CHECKING:
    from alphapulse.webapp.store.notifications import NotificationStore


async def run_briefing_async(
    *,
    date: str | None,
    progress_callback: Callable[[int, int, str], None],
    notification_store: "NotificationStore | None" = None,
) -> str:
    """BriefingOrchestrator.run_async(date, send_telegram=False) 실행.

    Args:
        date: YYYYMMDD 또는 None (None 이면 오늘).
        progress_callback: (current, total, text) 진행률 훅.
        notification_store: 브리핑 생성 완료 시 알림 발행용 (옵션).

    Returns:
        저장된 date (YYYYMMDD) — Job.result_ref 로 저장되어 프론트 redirect 에 사용.
    """
    progress_callback(0, 1, "브리핑 실행 중 (3~10분 소요, 브라우저 닫아도 계속)")
    orch = BriefingOrchestrator(notification_store=notification_store)
    result = await orch.run_async(date=date, send_telegram=False)
    saved_date = result["pulse_result"]["date"]
    progress_callback(1, 1, f"완료 ({saved_date})")
    return saved_date
