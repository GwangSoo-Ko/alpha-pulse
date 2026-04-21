"""JobRepository.find_running_by_kind — kind 기반 중복 Job 감지 (date 무관)."""

from alphapulse.webapp.store.jobs import JobRepository


def test_returns_none_when_no_matching_job(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    assert repo.find_running_by_kind("content_monitor") is None


def test_returns_job_when_pending_with_matching_kind(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-1"


def test_returns_job_when_running(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "running")
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-1"


def test_ignores_done_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "done")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_failed_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "failed")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_cancelled_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "cancelled")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_different_kind(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="screening",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "running")
    assert repo.find_running_by_kind("content_monitor") is None


def test_returns_most_recent_when_multiple_match(webapp_db):
    """동일 kind 에 2건이면 최신 Job 반환 (ORDER BY created_at DESC)."""
    import time
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-old", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-old", "running")
    time.sleep(0.01)
    repo.create(
        job_id="job-new", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-new", "running")
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-new"
