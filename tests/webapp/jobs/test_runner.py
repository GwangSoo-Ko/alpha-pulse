"""JobRunner 테스트."""
import uuid

import pytest

from alphapulse.webapp.jobs.runner import JobRunner, recover_orphans
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.notifications import NotificationStore


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


@pytest.fixture
def notif_store(webapp_db):
    return NotificationStore(db_path=webapp_db)


@pytest.fixture
def runner_with_notif(jobs, notif_store):
    return JobRunner(job_repo=jobs, notification_store=notif_store)


async def test_job_done_emits_notification(
    jobs, runner_with_notif, notif_store,
):
    jid = str(uuid.uuid4())
    jobs.create(
        job_id=jid, kind="backtest",
        params={"date": "20260420"}, user_id=1,
    )

    def work(*, progress_callback):
        return "ok"

    await runner_with_notif.run(jid, work)
    rows = notif_store.list_recent()
    assert len(rows) == 1
    assert rows[0]["kind"] == "job"
    assert rows[0]["level"] == "info"
    assert "완료" in rows[0]["title"]
    assert f"/backtest/jobs/{jid}" in (rows[0]["link"] or "")


async def test_job_failed_emits_notification(
    jobs, runner_with_notif, notif_store,
):
    jid = str(uuid.uuid4())
    jobs.create(
        job_id=jid, kind="briefing",
        params={"date": "20260420"}, user_id=1,
    )

    def boom(*, progress_callback):
        raise RuntimeError("kaboom")

    await runner_with_notif.run(jid, boom)
    rows = notif_store.list_recent()
    assert len(rows) == 1
    assert rows[0]["kind"] == "job"
    assert rows[0]["level"] == "error"
    assert "실패" in rows[0]["title"]
    assert "RuntimeError" in (rows[0]["body"] or "")


async def test_job_without_notification_store_no_crash(jobs):
    """notification_store=None 이어도 기존 동작 유지."""
    runner_no_notif = JobRunner(job_repo=jobs)
    jid = str(uuid.uuid4())
    jobs.create(
        job_id=jid, kind="screening", params={}, user_id=1,
    )

    def work(*, progress_callback):
        return "ok"

    # 에러 없이 완료, notification_store 없음
    await runner_no_notif.run(jid, work)
    j = jobs.get(jid)
    assert j.status == "done"


async def test_job_done_resilient_to_notification_store_error(
    jobs, monkeypatch, webapp_db,
):
    """notification_store.add가 예외를 던져도 Job 은 'done' 으로 지속된다."""
    from alphapulse.webapp.store.notifications import NotificationStore

    store = NotificationStore(db_path=webapp_db)

    def boom(*args, **kwargs):
        raise RuntimeError("store broken")

    monkeypatch.setattr(store, "add", boom)
    runner = JobRunner(job_repo=jobs, notification_store=store)

    jid = str(uuid.uuid4())
    jobs.create(
        job_id=jid, kind="backtest", params={}, user_id=1,
    )

    def work(*, progress_callback):
        return "ok"

    await runner.run(jid, work)
    j = jobs.get(jid)
    assert j.status == "done"
    assert j.result_ref == "ok"
