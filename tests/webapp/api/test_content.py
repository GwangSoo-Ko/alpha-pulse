"""Content API — GET endpoints."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.content import router as content_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


def _write_report(
    dirpath: Path,
    filename: str,
    *,
    title: str = "테스트",
    category: str = "경제",
    published: str = "2026-04-20",
    analyzed_at: str = "2026-04-20 15:30:00",
    body: str = "본문",
) -> None:
    content = (
        f'---\ntitle: "{title}"\nsource: "https://x.y"\n'
        f'published: "{published}"\nanalyzed_at: "{analyzed_at}"\n'
        f'category: "{category}"\n---\n\n{body}\n'
    )
    (dirpath / filename).write_text(content, encoding="utf-8")


@pytest.fixture
def reports_dir(tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture
def app(webapp_db, reports_dir):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.state.job_runner = JobRunner(job_repo=app.state.jobs)
    app.state.content_reader = ContentReader(reports_dir=reports_dir)
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    # /api/v1/csrf-token endpoint (CSRFMiddleware 는 state 만 설정, 라우트 별도)
    from fastapi import Request
    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(content_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/csrf-token")
    token = r.json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"x-csrf-token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


def test_list_reports_empty(client):
    r = client.get("/api/v1/content/reports")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["categories"] == []


def test_list_reports_returns_items(client, reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", category="경제")
    _write_report(reports_dir, "b.md", title="글 B", category="주식")
    r = client.get("/api/v1/content/reports")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    titles = {i["title"] for i in body["items"]}
    assert titles == {"글 A", "글 B"}


def test_list_reports_category_filter_multiple(client, reports_dir):
    _write_report(reports_dir, "a.md", title="A", category="경제")
    _write_report(reports_dir, "b.md", title="B", category="주식")
    _write_report(reports_dir, "c.md", title="C", category="사회")
    r = client.get("/api/v1/content/reports?category=경제&category=주식")
    body = r.json()
    titles = {i["title"] for i in body["items"]}
    assert titles == {"A", "B"}


def test_list_reports_query(client, reports_dir):
    _write_report(reports_dir, "a.md", title="버핏의 투자")
    _write_report(reports_dir, "b.md", title="테슬라 주가")
    r = client.get("/api/v1/content/reports?q=버핏")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "버핏의 투자"


def test_list_reports_date_range(client, reports_dir):
    _write_report(reports_dir, "a.md", title="A", published="2026-03-10")
    _write_report(reports_dir, "b.md", title="B", published="2026-04-15")
    r = client.get("/api/v1/content/reports?from=20260401&to=20260430")
    body = r.json()
    titles = {i["title"] for i in body["items"]}
    assert titles == {"B"}


def test_list_reports_size_out_of_range(client):
    r = client.get("/api/v1/content/reports?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/content/reports?size=500")
    assert r.status_code == 422


def test_detail_returns_report(client, reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", body="본문 내용")
    r = client.get("/api/v1/content/reports/a.md")
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "a.md"
    assert body["title"] == "글 A"
    assert "본문 내용" in body["body"]


def test_detail_404_when_missing(client):
    r = client.get("/api/v1/content/reports/missing.md")
    assert r.status_code == 404


def test_detail_rejects_path_traversal(client):
    r = client.get("/api/v1/content/reports/..%2Fetc%2Fpasswd")
    assert r.status_code == 400


def test_detail_rejects_non_md_extension(client):
    r = client.get("/api/v1/content/reports/file.txt")
    assert r.status_code == 400


def test_detail_rejects_slash_in_name(client):
    r = client.get("/api/v1/content/reports/sub%2Ffile.md")
    assert r.status_code == 400


def test_list_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/content/reports")
    assert r.status_code == 401


def test_detail_rejects_backslash_in_name(client):
    r = client.get("/api/v1/content/reports/sub%5Cfile.md")
    assert r.status_code == 400


def test_detail_rejects_null_byte_in_name(client):
    r = client.get("/api/v1/content/reports/file%00.md")
    assert r.status_code == 400


def test_detail_requires_auth(app):
    from fastapi.testclient import TestClient
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/content/reports/anything.md")
    assert r.status_code == 401


def test_run_creates_job_and_returns_id(client, monkeypatch):
    """POST /monitor/run → BackgroundTasks 스케줄, reused=false."""
    async def fake_runner_run(self, job_id, func, **kwargs):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is False
    assert "job_id" in body


def test_run_reuses_existing_job(client, app, monkeypatch):
    """같은 kind 의 running Job 있으면 그 id 반환, reused=true."""
    app.state.jobs.create(
        job_id="existing", kind="content_monitor",
        params={}, user_id=1,
    )
    app.state.jobs.update_status("existing", "running")

    async def fake_runner_run(self, job_id, func, **kwargs):
        raise AssertionError("should not be called")
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "existing"
    assert body["reused"] is True


def test_run_audit_log(client, app, monkeypatch):
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )
    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    assert app.state.audit.log.called
    assert app.state.audit.log.call_args.args[0] == "webapp.content.monitor.run"
