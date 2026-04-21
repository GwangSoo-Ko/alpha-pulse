"""JobRunner — coroutine function 지원 테스트."""
import asyncio

import pytest

from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.store.jobs import JobRepository


@pytest.fixture
def setup(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    runner = JobRunner(job_repo=repo)
    return repo, runner


def test_sync_function_still_works(setup):
    """기존 sync 함수는 asyncio.to_thread 로 계속 실행."""
    repo, runner = setup
    repo.create(job_id="j1", kind="screening", params={}, user_id=1)

    def sync_task(progress_callback=None) -> str:
        if progress_callback:
            progress_callback(1, 1, "done")
        return "sync-result"

    asyncio.run(runner.run("j1", sync_task))

    j = repo.get("j1")
    assert j is not None
    assert j.status == "done"
    assert j.result_ref == "sync-result"


def test_async_function_awaited_directly(setup):
    """async def 함수는 await 로 직접 실행 (to_thread 사용 안 함)."""
    repo, runner = setup
    repo.create(job_id="j2", kind="content_monitor", params={}, user_id=1)

    async def async_task(progress_callback=None) -> str:
        if progress_callback:
            progress_callback(1, 1, "done")
        await asyncio.sleep(0)  # 진짜 async 동작 확인
        return "async-result"

    asyncio.run(runner.run("j2", async_task))

    j = repo.get("j2")
    assert j is not None
    assert j.status == "done"
    assert j.result_ref == "async-result"


def test_async_function_exception_marked_failed(setup):
    """async 함수 예외도 기존처럼 Job failed 로 마킹."""
    repo, runner = setup
    repo.create(job_id="j3", kind="content_monitor", params={}, user_id=1)

    async def async_failing(progress_callback=None) -> str:
        raise RuntimeError("boom")

    asyncio.run(runner.run("j3", async_failing))

    j = repo.get("j3")
    assert j is not None
    assert j.status == "failed"
    assert j.error is not None
    assert "boom" in j.error
