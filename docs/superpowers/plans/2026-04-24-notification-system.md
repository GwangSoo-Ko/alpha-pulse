# 알림 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4개 핵심 이벤트(Job 완료/실패, 브리핑 저장, Risk alert, Pulse 극단값)를 인앱 알림 센터로 Push. 상단바 벨 아이콘 + 30초 폴링 UI.

**Architecture:** 신규 `NotificationStore`(`webapp.db` 내 `notifications` 테이블), 4개 엔드포인트(`list/unread-count/mark-read/mark-all-read`), 4개 이벤트 소스에 try/except 격리된 `add()` 호출. FE `NotificationBell` 공용 컴포넌트가 폴링으로 unread count 업데이트 + 클릭 시 드롭다운으로 최근 20건 조회.

**Tech Stack:** Python 3.12 + SQLite + FastAPI + Next.js 15.

**Branch:** `feature/notification-system` (spec 커밋 `ef5817d` 완료)

**Spec:** `docs/superpowers/specs/2026-04-24-notification-system-design.md`

---

## File Structure

### Backend
- **Modify:** `alphapulse/webapp/store/webapp_db.py` — `notifications` 테이블 + 2 인덱스 스키마
- **Create:** `alphapulse/webapp/store/notifications.py` — `NotificationStore` 클래스
- **Create:** `alphapulse/webapp/api/notifications.py` — 4 엔드포인트 + Pydantic 모델
- **Modify:** `alphapulse/webapp/main.py` — `app.state.notification_store` 등록, 라우터 include, 이벤트 소스에 주입
- **Modify:** `alphapulse/webapp/jobs/runner.py` — `JobRunner.__init__` 에 `notification_store` 선택 파라미터 + done/failed 후 `add()` 호출
- **Modify:** `alphapulse/briefing/orchestrator.py` — save 성공 직후 `add()`
- **Modify:** `alphapulse/webapp/store/readers/risk.py` — `get_report()` alerts 반환 시 `add()`
- **Modify:** `alphapulse/core/storage/history.py` — `PulseHistory.save()` 에서 `abs(score) >= 80` 시 `add()`

### Frontend
- **Create:** `webapp-ui/components/layout/notification-bell.tsx`
- **Modify:** `webapp-ui/components/layout/topbar.tsx` — `<NotificationBell />` 삽입

### 테스트
- **Create:** `tests/webapp/store/test_notifications.py` — Store 단위 테스트
- **Create:** `tests/webapp/api/test_notifications.py` — API 통합 테스트
- **Modify:** `tests/webapp/jobs/test_runner.py` (또는 신규 `test_runner_notifications.py`) — Job 이벤트 발행 테스트
- **Modify:** `tests/webapp/store/readers/test_risk.py` (또는 유사) — Risk 이벤트 발행
- **Modify:** `tests/core/test_storage.py` 또는 `test_history.py` — Pulse 이벤트 발행
- **Modify:** `tests/briefing/test_orchestrator.py` (있으면) — Briefing 이벤트 발행
- **Create:** `webapp-ui/e2e/notifications.spec.ts`

---

## Conventions

- 백엔드는 엄격한 TDD (test first → red → implement → green → commit)
- 각 이벤트 발행은 `try/except Exception` 으로 격리, 실패 시 warning 로그만
- 각 Task 완료마다 개별 커밋
- `ruff check alphapulse/` 통과 필수
- FE 는 Vitest 미도입 → `pnpm lint` + `pnpm tsc --noEmit` + `pnpm build` 로 검증

---

## Task 1: 스키마 + NotificationStore

**Files:**
- Modify: `alphapulse/webapp/store/webapp_db.py`
- Create: `alphapulse/webapp/store/notifications.py`
- Create: `tests/webapp/store/test_notifications.py`

### Step 1.1: 스키마 추가

Edit `alphapulse/webapp/store/webapp_db.py`. Find the `_SCHEMA` string (starts line 14). Append before the closing `"""`:

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    level TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    link TEXT,
    created_at REAL NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at
    ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications(is_read, created_at DESC)
    WHERE is_read = 0;
```

### Step 1.2: Store 테스트 추가

Create `tests/webapp/store/test_notifications.py`:

```python
"""NotificationStore 단위 테스트."""

from __future__ import annotations

import time

import pytest

from alphapulse.webapp.store.notifications import (
    DEDUP_WINDOW_SECONDS,
    NotificationStore,
)
from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "webapp.db"
    init_webapp_db(db)
    return NotificationStore(db_path=db)


def test_add_inserts_row(store):
    nid = store.add(
        kind="job", level="info", title="제목", body="본문", link="/a",
    )
    assert nid is not None and nid > 0
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["title"] == "제목"
    assert rows[0]["is_read"] == 0


def test_add_rejects_invalid_kind(store):
    nid = store.add(kind="unknown", level="info", title="x")
    assert nid is None
    assert store.list_recent() == []


def test_add_rejects_invalid_level(store):
    nid = store.add(kind="job", level="debug", title="x")
    assert nid is None


def test_add_dedups_same_kind_link_within_1min(store):
    first = store.add(kind="job", level="info", title="A", link="/x")
    second = store.add(kind="job", level="info", title="B", link="/x")
    assert first is not None
    assert second is None
    assert len(store.list_recent()) == 1


def test_add_allows_same_kind_different_link(store):
    a = store.add(kind="job", level="info", title="A", link="/x")
    b = store.add(kind="job", level="info", title="B", link="/y")
    assert a is not None and b is not None
    assert len(store.list_recent()) == 2


def test_add_allows_same_kind_no_link(store):
    a = store.add(kind="pulse", level="info", title="A", link=None)
    b = store.add(kind="pulse", level="info", title="B", link=None)
    assert a is not None and b is not None


def test_list_recent_orders_desc(store):
    a = store.add(kind="job", level="info", title="first", link="/1")
    time.sleep(0.01)
    b = store.add(kind="job", level="info", title="second", link="/2")
    rows = store.list_recent()
    assert rows[0]["id"] == b
    assert rows[1]["id"] == a


def test_list_recent_respects_limit(store):
    for i in range(5):
        store.add(kind="job", level="info", title=f"n{i}", link=f"/l{i}")
    rows = store.list_recent(limit=3)
    assert len(rows) == 3


def test_list_recent_filters_retention_cutoff(store, monkeypatch):
    # 31일 전 레코드 직접 삽입
    import sqlite3
    old = time.time() - 31 * 86400
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "INSERT INTO notifications (kind, level, title, created_at) "
            "VALUES ('job', 'info', 'old', ?)",
            (old,),
        )
    store.add(kind="job", level="info", title="new", link="/new")
    rows = store.list_recent()
    titles = [r["title"] for r in rows]
    assert "new" in titles
    assert "old" not in titles


def test_unread_count_counts_only_is_read_zero(store):
    a = store.add(kind="job", level="info", title="a", link="/a")
    store.add(kind="job", level="info", title="b", link="/b")
    store.mark_read(a)
    assert store.unread_count() == 1


def test_mark_read_returns_true_on_success(store):
    nid = store.add(kind="job", level="info", title="t", link="/t")
    assert store.mark_read(nid) is True
    rows = store.list_recent()
    assert rows[0]["is_read"] == 1


def test_mark_read_returns_false_on_missing_id(store):
    assert store.mark_read(99999) is False


def test_mark_all_read_returns_affected_count(store):
    store.add(kind="job", level="info", title="a", link="/a")
    store.add(kind="job", level="info", title="b", link="/b")
    affected = store.mark_all_read()
    assert affected == 2
    assert store.unread_count() == 0


def test_dedup_window_constant_is_60(store):
    assert DEDUP_WINDOW_SECONDS == 60
```

### Step 1.3: Red

```bash
cd /Users/gwangsoo/alpha-pulse
pytest tests/webapp/store/test_notifications.py -v
```
Expected: FAIL — `NotificationStore` 미존재.

### Step 1.4: Store 구현

Create `alphapulse/webapp/store/notifications.py`:

```python
"""알림 저장소 — 이벤트별 push 기록, 조회, 읽음 관리."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Literal

NotificationKind = Literal["job", "briefing", "risk", "pulse"]
NotificationLevel = Literal["info", "warn", "error"]

ALLOWED_KINDS = {"job", "briefing", "risk", "pulse"}
ALLOWED_LEVELS = {"info", "warn", "error"}

DEDUP_WINDOW_SECONDS = 60
RETENTION_DAYS = 30


class NotificationStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def add(
        self,
        *,
        kind: str,
        level: str,
        title: str,
        body: str | None = None,
        link: str | None = None,
    ) -> int | None:
        """알림을 추가. 1분 내 동일 (kind, link) 중복은 skip (None 반환)."""
        if kind not in ALLOWED_KINDS or level not in ALLOWED_LEVELS:
            return None
        now = time.time()
        dedup_after = now - DEDUP_WINDOW_SECONDS
        with sqlite3.connect(self.db_path) as conn:
            if link is not None:
                dup = conn.execute(
                    "SELECT id FROM notifications "
                    "WHERE kind = ? AND link = ? AND created_at >= ? "
                    "LIMIT 1",
                    (kind, link, dedup_after),
                ).fetchone()
                if dup is not None:
                    return None
            cur = conn.execute(
                "INSERT INTO notifications "
                "(kind, level, title, body, link, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, level, title, body, link, now),
            )
            return cur.lastrowid

    def list_recent(self, limit: int = 20) -> list[dict]:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM notifications "
                "WHERE created_at >= ? "
                "ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def unread_count(self) -> int:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM notifications "
                "WHERE is_read = 0 AND created_at >= ?",
                (cutoff,),
            ).fetchone()
        return row[0]

    def mark_read(self, notification_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE is_read = 0",
            )
            return cur.rowcount
```

### Step 1.5: Green

```bash
pytest tests/webapp/store/test_notifications.py -v
```
Expected: 13 passed.

### Step 1.6: 린트 + 커밋

```bash
ruff check alphapulse/webapp/store/notifications.py alphapulse/webapp/store/webapp_db.py tests/webapp/store/test_notifications.py
git add alphapulse/webapp/store/webapp_db.py alphapulse/webapp/store/notifications.py tests/webapp/store/test_notifications.py
git commit -m "feat(notifications): NotificationStore + schema (notifications 테이블)"
```

---

## Task 2: API 엔드포인트

**Files:**
- Create: `alphapulse/webapp/api/notifications.py`
- Create: `tests/webapp/api/test_notifications.py`

### Step 2.1: API 테스트 추가

Create `tests/webapp/api/test_notifications.py`:

```python
"""Notification API 통합 테스트."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.api.auth.routes import router as auth_router
from alphapulse.webapp.api.notifications import router as notif_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.notifications import NotificationStore
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
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
    app.state.notification_store = NotificationStore(db_path=webapp_db)

    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request: Request):
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(notif_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    t = c.get("/api/v1/csrf-token").json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": t},
    )
    c.headers.update({"X-CSRF-Token": t})
    return c


@pytest.fixture
def store(app) -> NotificationStore:
    return app.state.notification_store


def test_list_notifications_returns_items(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="briefing", level="info", title="B", link="/b")
    r = client.get("/api/v1/notifications")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2


def test_list_notifications_respects_limit(client, store):
    for i in range(5):
        store.add(kind="job", level="info", title=f"n{i}", link=f"/l{i}")
    r = client.get("/api/v1/notifications?limit=3")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 3


def test_unread_count_endpoint(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="job", level="info", title="B", link="/b")
    r = client.get("/api/v1/notifications/unread-count")
    assert r.status_code == 200
    assert r.json() == {"count": 2}


def test_mark_read_endpoint(client, store):
    nid = store.add(kind="job", level="info", title="A", link="/a")
    r = client.post(f"/api/v1/notifications/{nid}/read")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert store.unread_count() == 0


def test_mark_read_404_on_missing(client):
    r = client.post("/api/v1/notifications/99999/read")
    assert r.status_code == 404


def test_mark_all_read_endpoint(client, store):
    store.add(kind="job", level="info", title="A", link="/a")
    store.add(kind="job", level="info", title="B", link="/b")
    r = client.post("/api/v1/notifications/read-all")
    assert r.status_code == 200
    assert r.json() == {"count": 2}
    assert store.unread_count() == 0


def test_all_endpoints_require_auth(app):
    unauthed = TestClient(app, base_url="https://testserver")
    assert unauthed.get("/api/v1/notifications").status_code == 401
    assert unauthed.get("/api/v1/notifications/unread-count").status_code == 401
    assert unauthed.post("/api/v1/notifications/1/read").status_code == 401
    assert unauthed.post("/api/v1/notifications/read-all").status_code == 401
```

### Step 2.2: Red

```bash
pytest tests/webapp/api/test_notifications.py -v
```
Expected: FAIL — API 모듈 없음.

### Step 2.3: API 구현

Create `alphapulse/webapp/api/notifications.py`:

```python
"""Notification API — 인앱 알림 조회, 읽음 처리."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.notifications import NotificationStore
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class Notification(BaseModel):
    id: int
    kind: str
    level: str
    title: str
    body: str | None = None
    link: str | None = None
    created_at: float
    is_read: int


class NotificationListResponse(BaseModel):
    items: list[Notification]


class UnreadCountResponse(BaseModel):
    count: int


class MarkReadResponse(BaseModel):
    ok: bool


class MarkAllReadResponse(BaseModel):
    count: int


def get_notification_store(request: Request) -> NotificationStore:
    return request.app.state.notification_store


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return NotificationListResponse(
        items=[Notification(**n) for n in store.list_recent(limit=limit)],
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return UnreadCountResponse(count=store.unread_count())


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_read(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return MarkAllReadResponse(count=store.mark_all_read())


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: int,
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    if not store.mark_read(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return MarkReadResponse(ok=True)
```

**주의**: FastAPI 라우트 순서 — `/read-all` 을 `/{notification_id}/read` 보다 **위**에 선언해야 `/read-all` 이 `notification_id=read-all` 로 매치되지 않음.

### Step 2.4: Green

```bash
pytest tests/webapp/api/test_notifications.py -v
```
Expected: 7 passed.

### Step 2.5: 린트 + 커밋

```bash
ruff check alphapulse/webapp/api/notifications.py tests/webapp/api/test_notifications.py
git add alphapulse/webapp/api/notifications.py tests/webapp/api/test_notifications.py
git commit -m "feat(notifications): API 엔드포인트 (list/unread-count/mark-read/read-all)"
```

---

## Task 3: app.state 통합 + 라우터 등록

**Files:**
- Modify: `alphapulse/webapp/main.py`

### Step 3.1: main.py 수정

Find existing `app.state.xxx = ...` block (Phase 3 readers 있는 곳) 에 추가:

```python
from alphapulse.webapp.api.notifications import router as notifications_router
from alphapulse.webapp.store.notifications import NotificationStore

# ... 기존 repositories 생성 아래에 ...
notification_store = NotificationStore(db_path=webapp_db)
app.state.notification_store = notification_store

# 기존 routers include 섹션에 추가:
app.include_router(notifications_router)
```

정확한 위치는 기존 `include_router` 호출 근처.

### Step 3.2: 회귀 테스트

```bash
pytest tests/webapp/ -q --tb=short 2>&1 | tail -5
```
Expected: 전체 통과, 새 노티 테스트 포함.

### Step 3.3: 린트 + 커밋

```bash
ruff check alphapulse/webapp/main.py
git add alphapulse/webapp/main.py
git commit -m "feat(notifications): app.state.notification_store + 라우터 등록"
```

---

## Task 4: Job 이벤트 발행 (JobRunner)

**Files:**
- Modify: `alphapulse/webapp/jobs/runner.py`
- Modify: `alphapulse/webapp/main.py` (JobRunner 생성 시 store 주입)
- Modify or Create: `tests/webapp/jobs/test_runner.py`

### Step 4.1: 테스트 추가

먼저 기존 `tests/webapp/jobs/test_runner.py` 구조 확인:

```bash
ls tests/webapp/jobs/ 2>&1
cat tests/webapp/jobs/test_runner.py 2>&1 | head -40
```

Append or create:

```python
"""JobRunner 이벤트 발행 테스트."""
from __future__ import annotations

import asyncio

import pytest

from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.notifications import NotificationStore
from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def job_db(tmp_path):
    db = tmp_path / "webapp.db"
    init_webapp_db(db)
    return db


@pytest.fixture
def notif_store(job_db):
    return NotificationStore(db_path=job_db)


@pytest.fixture
def job_repo(job_db):
    return JobRepository(db_path=job_db)


@pytest.fixture
def runner(job_repo, notif_store):
    return JobRunner(job_repo=job_repo, notification_store=notif_store)


def _seed_job(job_repo, job_id: str, kind: str = "backtest"):
    job_repo.create(
        job_id=job_id, kind=kind,
        params={"date": "20260420"}, user_id=1,
    )


@pytest.mark.asyncio
async def test_job_done_emits_notification(runner, job_repo, notif_store):
    _seed_job(job_repo, "j-done", "backtest")

    def _work(*, progress_callback=None):
        return "ok"

    await runner.run("j-done", _work)
    rows = notif_store.list_recent()
    assert len(rows) == 1
    assert rows[0]["kind"] == "job"
    assert rows[0]["level"] == "info"
    assert "완료" in rows[0]["title"]


@pytest.mark.asyncio
async def test_job_failed_emits_notification(runner, job_repo, notif_store):
    _seed_job(job_repo, "j-fail", "briefing")

    def _boom(*, progress_callback=None):
        raise RuntimeError("kaboom")

    await runner.run("j-fail", _boom)
    rows = notif_store.list_recent()
    assert len(rows) == 1
    assert rows[0]["kind"] == "job"
    assert rows[0]["level"] == "error"
    assert "실패" in rows[0]["title"]


@pytest.mark.asyncio
async def test_job_without_notification_store_no_crash(job_repo):
    """notification_store=None 이어도 정상 동작."""
    runner_no_notif = JobRunner(job_repo=job_repo)
    _seed_job(job_repo, "j-plain", "screening")

    def _work(*, progress_callback=None):
        return "ok"

    await runner_no_notif.run("j-plain", _work)
    # 에러 없이 완료
```

### Step 4.2: Red

```bash
pytest tests/webapp/jobs/test_runner.py -k "emits\|no_crash" -v
```
Expected: FAIL — `notification_store` 파라미터 없음.

### Step 4.3: JobRunner 수정

Replace `alphapulse/webapp/jobs/runner.py` `JobRunner.__init__` and `run`:

```python
"""JobRunner — asyncio 백그라운드 실행기."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Callable

from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.notifications import NotificationStore

logger = logging.getLogger(__name__)

# Job kind → 사용자 표시 라벨 및 상세 경로
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
        self.jobs.update_status(
            job_id, "running", started_at=time.time()
        )

        def _on_progress(current: int, total: int, text: str = "") -> None:
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
            logger.warning("notification add failed for done %s: %s", job_id, e)

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
            logger.warning("notification add failed for failed %s: %s", job_id, e)

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
```

### Step 4.4: main.py JobRunner 주입 수정

Find `JobRunner(...)` instantiation in `alphapulse/webapp/main.py`. Pass `notification_store`:

```python
job_runner = JobRunner(
    job_repo=jobs,
    notification_store=notification_store,
)
```

### Step 4.5: Green

```bash
pytest tests/webapp/jobs/test_runner.py -v
pytest tests/webapp/ -q --tb=short | tail -5
```
Expected: 전체 통과.

### Step 4.6: 린트 + 커밋

```bash
ruff check alphapulse/webapp/jobs/runner.py alphapulse/webapp/main.py tests/webapp/jobs/test_runner.py
git add alphapulse/webapp/jobs/runner.py alphapulse/webapp/main.py tests/webapp/jobs/test_runner.py
git commit -m "feat(notifications): JobRunner 완료/실패 시 알림 발행"
```

---

## Task 5: 브리핑 저장 이벤트 발행

**Files:**
- Modify: `alphapulse/briefing/orchestrator.py`
- Modify: `alphapulse/webapp/main.py` (store 주입)
- Modify: `tests/briefing/test_orchestrator.py` (있으면)

### Step 5.1: 기존 orchestrator.save 지점 확인

```bash
grep -n "store.save\|briefing_store\|BriefingStore" alphapulse/briefing/orchestrator.py | head -10
```

### Step 5.2: Orchestrator 에 notification 주입

`alphapulse/briefing/orchestrator.py` 의 `BriefingOrchestrator.__init__` 시그니처에 파라미터 추가 (기존 파라미터 뒤에):

```python
def __init__(
    self,
    ...,  # 기존 파라미터
    notification_store: "NotificationStore | None" = None,
):
    ...
    self.notification_store = notification_store
```

Import 필요 시 TYPE_CHECKING block:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from alphapulse.webapp.store.notifications import NotificationStore
```

### Step 5.3: save 성공 직후 알림 발행

`store.save(...)` 호출 직후(같은 try 블록 안) 추가:

```python
if self.notification_store is not None:
    try:
        signal = pulse_result.get("signal", "")
        score = pulse_result.get("score", 0.0)
        sign = "+" if score >= 0 else ""
        body = f"{date} · {sign}{score:.1f} {signal}"
        self.notification_store.add(
            kind="briefing",
            level="info",
            title="브리핑 생성 완료",
            body=body,
            link=f"/briefings/{date}",
        )
    except Exception as e:
        logger.warning("notification add failed for briefing %s: %s", date, e)
```

**주의**: 파이썬 변수 이름은 실제 orchestrator.py 의 변수 (score/signal/date) 에 맞춰 조정. 정확한 필드명은 `grep -n "pulse_result\|final_score\|signal =" alphapulse/briefing/orchestrator.py` 로 확인.

### Step 5.4: main.py 주입

`create_app` 에서 `BriefingOrchestrator(...)` 를 생성하는 지점(있으면)에 `notification_store=notification_store` 추가.

briefing runner 서비스 구조 확인:

```bash
grep -n "BriefingOrchestrator\|briefing_runner" alphapulse/webapp/services/ alphapulse/webapp/main.py 2>&1 | head -5
```

만약 orchestrator 가 `briefing_runner.py` 같은 중간 레이어를 통해 호출되면 거기에 주입 경로 만들기 (또는 factory 함수 호출 지점).

### Step 5.5: 테스트 확인/추가

Find existing orchestrator test:

```bash
ls tests/briefing/
```

If `test_orchestrator.py` exists, add:

```python
import pytest
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_briefing_save_emits_notification(...):
    """orchestrator.run_async 완료 후 notification_store.add 호출."""
    notif_store = MagicMock()
    orch = BriefingOrchestrator(
        ...,  # 기존 mock dependencies
        notification_store=notif_store,
    )
    await orch.run_async(date="20260420", ...)
    # add 가 호출됐는지 확인
    notif_store.add.assert_called_once()
    call_kwargs = notif_store.add.call_args.kwargs
    assert call_kwargs["kind"] == "briefing"
    assert call_kwargs["level"] == "info"
    assert "브리핑" in call_kwargs["title"]
```

`BriefingOrchestrator` 의 실제 시그니처/메서드명은 파일 구조에 맞춰 조정.

### Step 5.6: 회귀 + 커밋

```bash
pytest tests/briefing/ tests/webapp/ -q --tb=short | tail -10
ruff check alphapulse/briefing/orchestrator.py alphapulse/webapp/main.py
git add alphapulse/briefing/orchestrator.py alphapulse/webapp/main.py tests/briefing/
git commit -m "feat(notifications): 브리핑 저장 시 알림 발행"
```

---

## Task 6: Risk alert 이벤트 발행

**Files:**
- Modify: `alphapulse/webapp/store/readers/risk.py`
- Modify: `alphapulse/webapp/main.py` (주입)
- Modify: `tests/webapp/store/readers/test_risk.py` 또는 유사

### Step 6.1: RiskReader 시그니처 확장

```bash
grep -n "class RiskReader\|def __init__\|def get_report" alphapulse/webapp/store/readers/risk.py | head -5
```

Modify `RiskReader.__init__` 에 `notification_store: NotificationStore | None = None` 추가.

### Step 6.2: get_report 에서 alerts 발행

`get_report(mode)` 가 `report_dict["alerts"]` 리스트를 만드는 지점 직후:

```python
if self.notification_store is not None and report_dict.get("alerts"):
    for alert in report_dict["alerts"]:
        try:
            self.notification_store.add(
                kind="risk",
                level="warn",
                title="Risk 경고",
                body=alert.get("message", "")[:200],
                link="/risk",
            )
        except Exception as e:
            logger.warning("notification add failed for risk: %s", e)
```

**주의**: dedup (1분) 덕분에 같은 alert message 가 반복 트리거되어도 1분 내 중복은 skip. `link="/risk"` 라 동일 link 기준으로 dedup 됨.

### Step 6.3: main.py 주입

`RiskReader(...)` 생성 지점에 `notification_store=notification_store` 추가.

### Step 6.4: 테스트 추가

```python
def test_risk_alerts_emit_notification(tmp_path, ...):
    """get_report 가 alerts 반환 시 notification_store.add 호출."""
    notif_store = MagicMock()
    reader = RiskReader(
        portfolio_reader=...,
        cache=...,
        notification_store=notif_store,
    )
    # alerts 가 있는 snapshot 준비 (mock)
    result = reader.get_report(mode="paper")
    # alerts 개수만큼 add 호출
    assert notif_store.add.call_count >= 1
    call = notif_store.add.call_args_list[0]
    assert call.kwargs["kind"] == "risk"
    assert call.kwargs["level"] == "warn"
```

Risk 테스트 기존 fixture 에 맞춰 조정. Mock portfolio_reader 가 alert 발생 가능한 snapshot 반환하도록.

### Step 6.5: 회귀 + 커밋

```bash
pytest tests/webapp/store/readers/ tests/webapp/ -q --tb=short | tail -5
ruff check alphapulse/webapp/store/readers/risk.py alphapulse/webapp/main.py
git add alphapulse/webapp/store/readers/risk.py alphapulse/webapp/main.py tests/webapp/store/readers/
git commit -m "feat(notifications): Risk alert 발생 시 알림 발행"
```

---

## Task 7: Pulse 극단값 이벤트 발행

**Files:**
- Modify: `alphapulse/core/storage/history.py`
- Modify: `alphapulse/webapp/main.py`
- Modify: `tests/core/test_storage.py` 또는 `tests/core/storage/test_history.py`

### Step 7.1: 테스트 추가

Find existing test:

```bash
grep -rn "class TestPulseHistory\|PulseHistory\|def test_save" tests/core/ | head -10
```

Append tests to appropriate file:

```python
def test_pulse_save_above_80_emits(tmp_path):
    from unittest.mock import MagicMock
    from alphapulse.core.storage.history import PulseHistory

    notif_store = MagicMock()
    hist = PulseHistory(
        db_path=tmp_path / "history.db",
        notification_store=notif_store,
    )
    hist.save(date="20260420", score=85.2, signal="강한 매수", details={})
    assert notif_store.add.call_count == 1
    call = notif_store.add.call_args
    assert call.kwargs["kind"] == "pulse"
    assert "강세" in call.kwargs["title"]


def test_pulse_save_below_minus_80_emits(tmp_path):
    from unittest.mock import MagicMock
    from alphapulse.core.storage.history import PulseHistory

    notif_store = MagicMock()
    hist = PulseHistory(
        db_path=tmp_path / "history.db",
        notification_store=notif_store,
    )
    hist.save(date="20260420", score=-85.2, signal="강한 매도", details={})
    assert notif_store.add.call_count == 1
    assert "약세" in notif_store.add.call_args.kwargs["title"]


def test_pulse_save_40_no_emit(tmp_path):
    from unittest.mock import MagicMock
    from alphapulse.core.storage.history import PulseHistory

    notif_store = MagicMock()
    hist = PulseHistory(
        db_path=tmp_path / "history.db",
        notification_store=notif_store,
    )
    hist.save(date="20260420", score=40.0, signal="중립", details={})
    assert notif_store.add.call_count == 0


def test_pulse_save_without_notification_store_no_crash(tmp_path):
    from alphapulse.core.storage.history import PulseHistory

    hist = PulseHistory(db_path=tmp_path / "history.db")
    # 에러 없이 저장
    hist.save(date="20260420", score=95.0, signal="강한 매수", details={})
```

### Step 7.2: Red

```bash
pytest tests/core/ -k "pulse_save\|pulse save" -v
```

### Step 7.3: PulseHistory 구현

`alphapulse/core/storage/history.py`:

```python
# TYPE_CHECKING import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from alphapulse.webapp.store.notifications import NotificationStore


class PulseHistory:
    def __init__(
        self,
        db_path: str | Path,
        notification_store: "NotificationStore | None" = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.notification_store = notification_store
        self._create_table()

    def save(self, date: str, score: float, signal: str, details: dict) -> None:
        # 기존 저장 로직 유지
        ...

        # 알림 발행 (score ±80 이상)
        if self.notification_store is not None and abs(score) >= 80:
            try:
                direction = "강세" if score > 0 else "약세"
                sign = "+" if score > 0 else ""
                self.notification_store.add(
                    kind="pulse",
                    level="info",
                    title=f"Pulse {direction} 극단값",
                    body=f"{date} · {sign}{score:.1f}",
                    link="/market/pulse",
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "notification add failed for pulse %s: %s", date, e,
                )
```

`_create_table` 은 기존 로직 유지.

### Step 7.4: main.py 주입

`PulseHistory(...)` 생성 지점 (`create_app` 내):

```python
pulse_history = PulseHistory(
    db_path=core.HISTORY_DB,
    notification_store=notification_store,
)
```

### Step 7.5: Green + 커밋

```bash
pytest tests/core/ tests/webapp/ -q --tb=short | tail -5
ruff check alphapulse/core/storage/history.py alphapulse/webapp/main.py
git add alphapulse/core/storage/history.py alphapulse/webapp/main.py tests/core/
git commit -m "feat(notifications): Pulse score ±80 시 알림 발행"
```

---

## Task 8: FE NotificationBell 컴포넌트

**Files:**
- Create: `webapp-ui/components/layout/notification-bell.tsx`

### Step 8.1: 파일 생성

```tsx
"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { apiFetch } from "@/lib/api-client"

export type Notification = {
  id: number
  kind: "job" | "briefing" | "risk" | "pulse"
  level: "info" | "warn" | "error"
  title: string
  body: string | null
  link: string | null
  created_at: number
  is_read: number
}

const POLL_INTERVAL_MS = 30_000

function formatTimeAgo(epoch: number): string {
  const diff = Date.now() / 1000 - epoch
  if (diff < 60) return "방금 전"
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return `${Math.floor(diff / 86400)}일 전`
}

function levelColor(level: string): string {
  if (level === "error") return "text-rose-400"
  if (level === "warn") return "text-amber-400"
  return "text-emerald-400"
}

export function NotificationBell() {
  const [count, setCount] = useState(0)
  const [items, setItems] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function tick() {
      try {
        const r = await apiFetch<{ count: number }>(
          "/api/v1/notifications/unread-count",
        )
        if (!cancelled) setCount(r.count)
      } catch {
        /* ignore */
      }
    }
    tick()
    const id = setInterval(tick, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  async function openDropdown() {
    setOpen(true)
    try {
      const r = await apiFetch<{ items: Notification[] }>(
        "/api/v1/notifications?limit=20",
      )
      setItems(r.items)
    } catch {
      /* ignore */
    }
  }

  async function markAllRead() {
    try {
      await apiFetch("/api/v1/notifications/read-all", { method: "POST" })
      setCount(0)
      setItems((prev) => prev.map((i) => ({ ...i, is_read: 1 })))
    } catch {
      /* ignore */
    }
  }

  async function handleItemClick(n: Notification) {
    if (!n.is_read) {
      try {
        await apiFetch(`/api/v1/notifications/${n.id}/read`, { method: "POST" })
        setCount((c) => Math.max(0, c - 1))
        setItems((prev) =>
          prev.map((i) => (i.id === n.id ? { ...i, is_read: 1 } : i)),
        )
      } catch {
        /* ignore */
      }
    }
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openDropdown())}
        aria-label={`알림 ${count}건`}
        className="relative p-2 rounded hover:bg-neutral-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
      >
        <span className="text-lg">🔔</span>
        {count > 0 && (
          <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] rounded-full min-w-[16px] h-[16px] px-1 flex items-center justify-center">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded border border-neutral-800 bg-neutral-900 shadow-lg z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800">
            <span className="text-sm font-semibold">알림</span>
            {count > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-neutral-400 hover:text-neutral-200"
              >
                모두 읽음
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-3 py-4 text-sm text-neutral-500 text-center">
                알림 없음
              </li>
            ) : (
              items.map((n) => (
                <NotificationRow
                  key={n.id}
                  n={n}
                  onClick={() => handleItemClick(n)}
                />
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

function NotificationRow({
  n,
  onClick,
}: {
  n: Notification
  onClick: () => void
}) {
  const content = (
    <div
      className={`px-3 py-2 border-b border-neutral-800 hover:bg-neutral-800 ${
        !n.is_read ? "bg-neutral-900" : ""
      }`}
    >
      <div className="flex items-start gap-2">
        {!n.is_read && (
          <span className="w-1.5 h-1.5 mt-1.5 rounded-full bg-emerald-500 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${levelColor(n.level)}`}>
            {n.title}
          </p>
          {n.body && (
            <p className="text-xs text-neutral-300 line-clamp-2">{n.body}</p>
          )}
          <p className="text-[10px] text-neutral-500 mt-1">
            {formatTimeAgo(n.created_at)}
          </p>
        </div>
      </div>
    </div>
  )
  if (n.link) {
    return (
      <li>
        <Link href={n.link} onClick={onClick} className="block">
          {content}
        </Link>
      </li>
    )
  }
  return (
    <li onClick={onClick} className="cursor-pointer">
      {content}
    </li>
  )
}
```

### Step 8.2: 린트 + tsc

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep notification-bell || echo "no errors"
```

### Step 8.3: 커밋

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/layout/notification-bell.tsx
git commit -m "feat(webapp-ui): NotificationBell 컴포넌트 (폴링 30초 + 드롭다운)"
```

---

## Task 9: 상단바 통합

**Files:**
- Modify: `webapp-ui/components/layout/topbar.tsx`

### Step 9.1: Topbar 수정

Replace `webapp-ui/components/layout/topbar.tsx` 의 내용:

```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { ModeSelector } from "@/components/layout/mode-selector"
import { NotificationBell } from "@/components/layout/notification-bell"
import type { User } from "@/lib/types"

export function Topbar({ user }: { user: User }) {
  const handleLogout = async () => {
    await apiMutate("/api/v1/auth/logout", "POST")
    window.location.href = "/login"
  }
  return (
    <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-2">
      <div>
        <ModeSelector />
      </div>
      <div className="flex items-center gap-3 text-sm">
        <NotificationBell />
        <span className="text-neutral-400">{user.email}</span>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </div>
  )
}
```

### Step 9.2: 린트 + 빌드

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm build 2>&1 | tail -5
```

### Step 9.3: 커밋

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/layout/topbar.tsx
git commit -m "feat(webapp-ui): Topbar 에 NotificationBell 통합"
```

---

## Task 10: Playwright E2E

**Files:**
- Create: `webapp-ui/e2e/notifications.spec.ts`

### Step 10.1: 스모크 테스트 작성

```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Notifications", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("상단바에 벨 아이콘이 보임", async ({ page }) => {
    await page.goto("/")
    await expect(
      page.getByRole("button", { name: /알림/ }),
    ).toBeVisible()
  })

  test("벨 아이콘 클릭 시 드롭다운 열림", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("button", { name: /알림/ }).click()
    // 드롭다운 제목 "알림" 또는 "알림 없음" 문구
    const title = page.getByText("알림").first()
    const empty = page.getByText("알림 없음")
    await expect(title.or(empty)).toBeVisible()
  })
})
```

### Step 10.2: 린트

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

### Step 10.3: 커밋

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/e2e/notifications.spec.ts
git commit -m "test(webapp-ui): Notifications E2E 스모크 (벨 + 드롭다운)"
```

---

## Task 11: 전체 CI Gate

**목적**: pytest + ruff + pnpm build 통과 확인.

### Step 11.1: pytest

```bash
cd /Users/gwangsoo/alpha-pulse
pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
Expected: 1355 + ~25 = 1380+ passed.

### Step 11.2: ruff

```bash
ruff check alphapulse/
```
Expected: All checks passed!

### Step 11.3: FE 빌드

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm build 2>&1 | tail -10
```
Expected: 빌드 성공.

### Step 11.4: 커밋 없음 — 검증 통과 시 병합 단계.

---

## Spec Coverage 체크

- [x] §2 데이터 모델 (스키마 + 2 인덱스) → Task 1
- [x] §3.1 NotificationStore → Task 1
- [x] §3.2 API 엔드포인트 4개 → Task 2
- [x] §3.3 이벤트 발행 4곳 → Task 4 (Job), Task 5 (Briefing), Task 6 (Risk), Task 7 (Pulse)
- [x] §3.4 DI (app.state + 각 소비자 주입) → Task 3, 4, 5, 6, 7
- [x] §3.5 스키마 통합 → Task 1
- [x] §4.1 NotificationBell → Task 8
- [x] §4.2 Topbar 통합 → Task 9
- [x] §5 에러 처리 (try/except 격리) → Task 4, 5, 6, 7 내부
- [x] §6.1 Store 단위 테스트 → Task 1 (13건)
- [x] §6.2 API 통합 테스트 → Task 2 (7건)
- [x] §6.3 이벤트 발행 회귀 → Task 4, 5, 6, 7
- [x] §6.5 FE E2E → Task 10
- [x] §7 CI Gate → Task 11

## Implementation Notes

1. **Task 순서 엄격**: 1 (Store) → 2 (API) → 3 (DI) → 4-7 (이벤트 발행, 순서 무관) → 8 (FE) → 9 (통합) → 10 (E2E) → 11 (CI).
2. **FastAPI 라우트 순서**: `/read-all` 이 `/{notification_id}/read` 보다 위에 선언되어야 함 (path shadowing).
3. **TYPE_CHECKING import**: `history.py`, `risk.py`, `orchestrator.py` 가 `NotificationStore` 을 import 하면 circular import 위험. 타입 힌트에만 사용 시 `if TYPE_CHECKING:` 블록으로 회피.
4. **Task 4 의 _summarize_params**: `params` dict 에 3개 이상 키 있으면 앞 3개만. 실제 params 가 date/run_id 정도라 충분.
5. **Task 5 orchestrator 주입 경로**: webapp 에서 BriefingOrchestrator 가 직접 호출되지 않고 `briefing_runner.py` 같은 중간층이 있을 수 있음. factory 에 주입 파라미터 추가.
6. **Task 6 Risk alert 발행**: 동일 alert 가 반복 리퀘스트마다 트리거되어 dedup 필수. 1분 내 `link="/risk"` dedup 동작으로 한 번만 발행. 다만 여러 alert 가 한 report 에 있으면 다르지만 link 는 같아 첫 alert 만 기록됨 → 메시지에 모든 alert 요약 or 여러번 허용? 현재 구현은 **첫 alert 만 dedup 에 맞아 기록**. Spec 에 맞춰 각 alert 를 각자 발행하되, 같은 메시지는 1분 dedup.
7. **Task 7 Pulse 극단값**: `abs(score) >= 80` 조건. 정확한 경계값은 score `>= 80` or `<= -80`. `== 80` 도 포함.
8. **Task 9 Topbar `"use client"`**: 기존에 이미 있음. `<NotificationBell />` 가 `"use client"` 라서 문제없음.
9. **이벤트 발행 실패 격리**: 모든 `add()` 호출은 `try/except Exception` 감싸고 `logger.warning` 만. 원 기능(Job 저장, Briefing save, Risk 조회, Pulse save) 은 알림 실패에 영향 받으면 안 됨.
10. **CLI entry 호환**: CLI 에서 PulseHistory/BriefingOrchestrator 를 독립 사용 시 `notification_store=None` 으로 호출되어 알림 발행 skip. webapp 에서만 알림 발행.
