"""JobRunner 테스트."""
import asyncio
import uuid

import pytest

from alphapulse.webapp.jobs.runner import JobRunner, recover_orphans
from alphapulse.webapp.store.jobs import JobRepository


@pytest.fixture
def jobs(webapp_db):
    return JobRepository(db_path=webapp_db)


@pytest.fixture
def runner(jobs):
    return JobRunner(job_repo=jobs)


class TestJobRunner:
    async def test_runs_sync_function_with_progress(self, jobs, runner):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )

        def fake_backtest(*, progress_callback):
            for i in range(3):
                progress_callback(i, 3, f"step {i}")
            return "run_result"

        await runner.run(jid, fake_backtest)
        j = jobs.get(jid)
        assert j.status == "done"
        assert j.result_ref == "run_result"
        assert j.finished_at is not None

    async def test_failure_recorded(self, jobs, runner):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )

        def boom(*, progress_callback):
            raise RuntimeError("boom")

        await runner.run(jid, boom)
        j = jobs.get(jid)
        assert j.status == "failed"
        assert "boom" in j.error

    async def test_progress_updates(self, jobs, runner):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )

        def slow(*, progress_callback):
            progress_callback(1, 2, "halfway")
            return "x"

        await runner.run(jid, slow)
        j = jobs.get(jid)
        assert j.status == "done"
        # 마지막 progress_text 보존
        assert j.progress_text == "halfway"


def test_recover_orphans(webapp_db):
    jobs = JobRepository(db_path=webapp_db)
    jid = str(uuid.uuid4())
    jobs.create(
        job_id=jid, kind="backtest", params={}, user_id=1,
    )
    jobs.update_status(jid, "running", started_at=0)
    n = recover_orphans(job_repo=jobs)
    assert n == 1
    j = jobs.get(jid)
    assert j.status == "failed"
    assert j.error is not None
