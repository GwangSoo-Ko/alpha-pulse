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

logger = logging.getLogger(__name__)


class JobRunner:
    """동기 함수를 백그라운드 스레드로 실행하고 진행률을 DB에 기록."""

    def __init__(self, job_repo: JobRepository) -> None:
        self.jobs = job_repo

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
        except Exception as e:
            logger.exception("job %s failed", job_id)
            self.jobs.update_status(
                job_id, "failed",
                error=f"{type(e).__name__}: {e}",
                finished_at=time.time(),
            )


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
