"""JobRepository.create_or_return_running_* 원자성 + 중복 감지 테스트."""

from alphapulse.webapp.store.jobs import JobRepository


def test_by_kind_and_date_creates_new_when_none_exists(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    job, created = repo.create_or_return_running_by_kind_and_date(
        kind="market_pulse", date="20260420",
        job_id="job-1", params={"date": "20260420"}, user_id=1,
    )
    assert created is True
    assert job.id == "job-1"
    assert job.kind == "market_pulse"
    assert job.status == "pending"


def test_by_kind_and_date_returns_existing_when_running(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="existing", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("existing", "running")

    job, created = repo.create_or_return_running_by_kind_and_date(
        kind="market_pulse", date="20260420",
        job_id="new", params={"date": "20260420"}, user_id=1,
    )
    assert created is False
    assert job.id == "existing"
    # new Job 은 생성되지 않았어야 함
    assert repo.get("new") is None


def test_by_kind_and_date_creates_when_different_date(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-a", kind="market_pulse",
        params={"date": "20260419"}, user_id=1,
    )
    repo.update_status("job-a", "running")

    job, created = repo.create_or_return_running_by_kind_and_date(
        kind="market_pulse", date="20260420",
        job_id="job-b", params={"date": "20260420"}, user_id=1,
    )
    assert created is True
    assert job.id == "job-b"


def test_by_kind_and_date_ignores_finished_same_date(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="finished", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("finished", "done")

    job, created = repo.create_or_return_running_by_kind_and_date(
        kind="market_pulse", date="20260420",
        job_id="new", params={"date": "20260420"}, user_id=1,
    )
    assert created is True
    assert job.id == "new"


def test_by_kind_creates_when_none(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    job, created = repo.create_or_return_running_by_kind(
        kind="content_monitor",
        job_id="cm-1", params={}, user_id=1,
    )
    assert created is True
    assert job.id == "cm-1"


def test_by_kind_returns_existing(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="cm-running", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("cm-running", "running")

    job, created = repo.create_or_return_running_by_kind(
        kind="content_monitor",
        job_id="cm-new", params={}, user_id=1,
    )
    assert created is False
    assert job.id == "cm-running"
    assert repo.get("cm-new") is None


def test_by_kind_creates_when_different_kind_running(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="other", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    repo.update_status("other", "running")

    # 다른 kind 는 영향 없음
    job, created = repo.create_or_return_running_by_kind(
        kind="content_monitor",
        job_id="cm-1", params={}, user_id=1,
    )
    assert created is True
    assert job.id == "cm-1"
