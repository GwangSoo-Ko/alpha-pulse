"""JobRepository.find_running_by_kind_and_date 테스트."""

from alphapulse.webapp.store.jobs import JobRepository


def test_returns_none_when_no_matching_job(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_returns_job_when_running_with_matching_date(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-1", "running")

    hit = repo.find_running_by_kind_and_date("market_pulse", "20260420")
    assert hit is not None
    assert hit.id == "job-1"


def test_ignores_finished_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-1", "done")

    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_ignores_different_date(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260419"}, user_id=1,
    )
    repo.update_status("job-1", "running")

    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_ignores_different_kind(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="screening",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-1", "running")

    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_also_matches_pending_state(webapp_db):
    """pending 상태(생성 직후)도 중복으로 간주한다."""
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    # status 기본 = pending
    hit = repo.find_running_by_kind_and_date("market_pulse", "20260420")
    assert hit is not None


def test_ignores_cancelled_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-1", "cancelled")

    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_ignores_failed_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-1", "failed")

    assert repo.find_running_by_kind_and_date("market_pulse", "20260420") is None


def test_returns_most_recent_when_multiple_match(webapp_db):
    """동일 kind/date 에 2건 매칭되면 최신 Job 반환 (ORDER BY created_at DESC)."""
    import time
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-old", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-old", "running")
    # created_at 차이 확보 (float seconds → 10ms sleep 충분)
    time.sleep(0.01)
    repo.create(
        job_id="job-new", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("job-new", "running")

    hit = repo.find_running_by_kind_and_date("market_pulse", "20260420")
    assert hit is not None
    assert hit.id == "job-new"
