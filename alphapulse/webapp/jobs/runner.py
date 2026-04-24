"""JobRunner — asyncio 백그라운드 실행기.

ARQ 호환 시그니처: future에서 `async def(ctx, *args)` worker로 이식 가능.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Callable

from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.notifications import NotificationStore

logger = logging.getLogger(__name__)

# Job kind → 사용자 표시 라벨 및 상세 경로 prefix
_KIND_LABELS: dict[str, tuple[str, str]] = {
    "backtest": ("백테스트", "/backtest"),
    "screening": ("스크리닝", "/screening"),
    "data_update": ("데이터 업데이트", "/data"),
    "market_pulse": ("Market Pulse", "/market/pulse"),
    "content_monitor": ("콘텐츠 모니터", "/content"),
    "briefing": ("브리핑", "/briefings"),
}


class JobRunner:
    """동기 함수를 백그라운드 스레드로 실행하고 진행률을 DB에 기록."""

    def __init__(
        self,
        job_repo: JobRepository,
        notification_store: NotificationStore | None = None,
    ) -> None:
        self.jobs = job_repo
        self.notification_store = notification_store

    async def run(self, job_id: str, func: Callable, *args, **kwargs) -> None:
        """func를 실행 — `progress_callback` kwarg에 진행률 훅 주입."""
        self.jobs.update_status(
            job_id, "running", started_at=time.time()
        )

        def _on_progress(
            current: int, total: int, text: str = "",
        ) -> None:
            ratio = current / total if total > 0 else 0.0
            self.jobs.update_progress(job_id, ratio, text)

        kwargs = {**kwargs, "progress_callback": _on_progress}
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            self.jobs.update_status(
                job_id, "done",
                result_ref=str(result) if result is not None else None,
                finished_at=time.time(),
            )
            self._emit_done(job_id)
        except Exception as e:
            logger.exception("job %s failed", job_id)
            self.jobs.update_status(
                job_id, "failed",
                error=f"{type(e).__name__}: {e}",
                finished_at=time.time(),
            )
            self._emit_failed(job_id, e)

    def _emit_done(self, job_id: str) -> None:
        if self.notification_store is None:
            return
        try:
            job = self.jobs.get(job_id)
            if job is None:
                return
            label, path = _KIND_LABELS.get(job.kind, (job.kind, "/"))
            self.notification_store.add(
                kind="job",
                level="info",
                title=f"{label} Job 완료",
                body=self._summarize_params(job.params),
                link=f"{path}/jobs/{job_id}",
            )
        except Exception as e:
            logger.warning(
                "notification add failed for done %s: %s", job_id, e,
            )

    def _emit_failed(self, job_id: str, err: Exception) -> None:
        if self.notification_store is None:
            return
        try:
            job = self.jobs.get(job_id)
            if job is None:
                return
            label, path = _KIND_LABELS.get(job.kind, (job.kind, "/"))
            msg = f"{type(err).__name__}: {err}"
            self.notification_store.add(
                kind="job",
                level="error",
                title=f"{label} Job 실패",
                body=msg[:200],
                link=f"{path}/jobs/{job_id}",
            )
        except Exception as e:
            logger.warning(
                "notification add failed for failed %s: %s", job_id, e,
            )

    @staticmethod
    def _summarize_params(params: dict) -> str:
        if not params:
            return ""
        items = [f"{k}={v}" for k, v in list(params.items())[:3]]
        return ", ".join(items)


def recover_orphans(job_repo: JobRepository) -> int:
    """프로세스 재시작 시 `running` 상태인 Job을 `failed`로 정리."""
    orphans = job_repo.list_by_status("running")
    for j in orphans:
        job_repo.update_status(
            j.id, "failed",
            error="process restarted while job was running",
            finished_at=time.time(),
        )
    return len(orphans)
