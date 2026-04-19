"""JobRepository 테스트."""
import json
import time
import uuid

import pytest

from alphapulse.webapp.store.jobs import JobRepository


@pytest.fixture
def jobs(webapp_db):
    return JobRepository(db_path=webapp_db)


class TestJobs:
    def test_create_and_get(self, jobs):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest",
            params={"strategy": "momentum"}, user_id=1,
        )
        j = jobs.get(jid)
        assert j is not None
        assert j.kind == "backtest"
        assert j.status == "pending"
        assert j.params == {"strategy": "momentum"}

    def test_update_status_running(self, jobs):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        jobs.update_status(jid, "running", started_at=time.time())
        j = jobs.get(jid)
        assert j.status == "running"
        assert j.started_at is not None

    def test_update_progress(self, jobs):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        jobs.update_progress(jid, 0.42, "2024-03-15")
        j = jobs.get(jid)
        assert j.progress == 0.42
        assert j.progress_text == "2024-03-15"

    def test_mark_done(self, jobs):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        jobs.update_status(
            jid, "done",
            result_ref="run_abc", finished_at=time.time(),
        )
        j = jobs.get(jid)
        assert j.status == "done"
        assert j.result_ref == "run_abc"
        assert j.finished_at is not None

    def test_mark_failed(self, jobs):
        jid = str(uuid.uuid4())
        jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        jobs.update_status(
            jid, "failed",
            error="boom", finished_at=time.time(),
        )
        j = jobs.get(jid)
        assert j.status == "failed"
        assert j.error == "boom"

    def test_list_running_for_cleanup(self, jobs):
        jid1 = str(uuid.uuid4())
        jid2 = str(uuid.uuid4())
        jobs.create(
            job_id=jid1, kind="backtest", params={}, user_id=1,
        )
        jobs.create(
            job_id=jid2, kind="backtest", params={}, user_id=1,
        )
        jobs.update_status(jid1, "running", started_at=time.time())
        jobs.update_status(jid2, "done", finished_at=time.time())
        running = jobs.list_by_status("running")
        assert len(running) == 1
        assert running[0].id == jid1
