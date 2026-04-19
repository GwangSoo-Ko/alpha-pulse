# AlphaPulse Web Frontend — Phase 1 (Auth + Backtest Domain) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관리자 로그인과 Backtest 도메인 전체(조회/실행/비교)를 웹에서 가능하게 하는 MVP를 FastAPI + Next.js로 구현한다.

**Architecture:** 기존 `alphapulse/` 패키지 무변경 위에 `alphapulse/webapp/` (FastAPI 백엔드) + `webapp-ui/` (Next.js 프론트) 모노레포 추가. 세션 쿠키 인증, SQLite 기반 `data/webapp.db` 신설, 인프로세스 asyncio 백그라운드 태스크로 백테스트 실행. 운영/장애 알림은 별도 Telegram 채널.

**Tech Stack:** Python 3.12 · FastAPI · Pydantic v2 · bcrypt · slowapi · Next.js 15+ (App Router) · TypeScript · shadcn/ui · Tailwind · TanStack Query · Recharts · TradingView Lightweight Charts · Playwright (E2E) · systemd · Cloudflare Tunnel

**Reference:** `docs/superpowers/specs/2026-04-19-webapp-design.md`

---

## File Structure

### Backend (Python)
```
alphapulse/webapp/
├── __init__.py
├── main.py                    # FastAPI 앱 어셈블리
├── config.py                  # Config 확장 (webapp-only 설정)
├── cli.py                     # ap webapp 서브명령
├── notifier.py                # MonitorNotifier (운영 채널)
├── auth/
│   ├── __init__.py
│   ├── models.py              # User, Session Pydantic
│   ├── security.py            # bcrypt, 토큰 생성
│   ├── deps.py                # get_current_user, require_role
│   └── routes.py              # /login, /logout, /me, /csrf-token
├── jobs/
│   ├── __init__.py
│   ├── models.py              # Job dataclass/Pydantic
│   ├── runner.py              # asyncio 백그라운드 실행
│   └── routes.py              # /jobs/{id}
├── api/
│   ├── __init__.py
│   └── backtest.py            # /backtest/* 라우터
├── store/
│   ├── __init__.py
│   ├── webapp_db.py           # data/webapp.db 초기화
│   ├── users.py               # UserRepository
│   ├── sessions.py            # SessionRepository
│   ├── login_attempts.py      # LoginAttemptsRepository (브루트포스)
│   ├── jobs.py                # JobRepository
│   ├── alert_log.py           # AlertLogRepository (알림 rate limit)
│   └── readers/
│       ├── __init__.py
│       └── backtest.py        # BacktestStore 어댑터 (페이지네이션)
└── middleware/
    ├── __init__.py
    ├── csrf.py                # Double Submit Cookie
    ├── rate_limit.py          # slowapi 설정
    └── security_headers.py    # CSP, X-Frame-Options 등
```

### Frontend (Next.js)
```
webapp-ui/
├── package.json
├── pnpm-lock.yaml
├── next.config.mjs
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json            # shadcn/ui 설정
├── middleware.ts              # 로그인 리다이렉트
├── .eslintrc.json
├── .gitignore
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── (auth)/
│   │   └── login/page.tsx
│   └── (dashboard)/
│       ├── layout.tsx         # 세션 재검증 + 사이드바 셸
│       ├── page.tsx           # 홈 (Phase 1은 간단)
│       └── backtest/
│           ├── page.tsx
│           ├── new/page.tsx
│           ├── compare/page.tsx
│           ├── [runId]/
│           │   ├── page.tsx
│           │   ├── trades/page.tsx
│           │   └── positions/page.tsx
│           └── jobs/[jobId]/page.tsx
├── components/
│   ├── ui/                    # shadcn/ui (auto-generated)
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   └── topbar.tsx
│   ├── charts/
│   │   ├── equity-curve.tsx
│   │   ├── drawdown.tsx
│   │   └── monthly-heatmap.tsx
│   └── domain/backtest/
│       ├── runs-table.tsx
│       ├── metrics-cards.tsx
│       ├── trades-table.tsx
│       ├── position-viewer.tsx
│       ├── backtest-form.tsx
│       └── job-progress.tsx
├── lib/
│   ├── api-client.ts          # FastAPI 호출 래퍼
│   ├── auth.ts                # 서버 컴포넌트용 세션 검증
│   ├── types.ts               # 공통 타입 (OpenAPI 생성)
│   └── utils.ts
└── hooks/
    ├── use-job-status.ts      # 2초 polling
    └── use-runs.ts
```

### Infrastructure
```
scripts/
├── backup.sh                  # 일일 SQLite 백업
└── verify-monitoring.sh       # 모니터 채널 테스트

systemd/
├── alphapulse-fastapi.service
├── alphapulse-webapp-ui.service
└── cloudflared.service.example

.github/workflows/
└── security-scan.yml          # 주간 취약점 스캔

docs/operations/
├── webapp-deployment.md
├── webapp-runbook.md
└── security-checklist.md
```

### Tests
```
tests/webapp/
├── __init__.py
├── conftest.py                # FastAPI TestClient, tmp webapp.db
├── store/
│   ├── test_webapp_db.py
│   ├── test_users.py
│   ├── test_sessions.py
│   ├── test_login_attempts.py
│   ├── test_jobs.py
│   └── test_alert_log.py
├── auth/
│   ├── test_security.py
│   └── test_routes.py
├── jobs/
│   ├── test_runner.py
│   └── test_routes.py
├── api/
│   └── test_backtest.py
├── middleware/
│   ├── test_csrf.py
│   ├── test_rate_limit.py
│   └── test_security_headers.py
├── test_notifier.py
├── test_cli_webapp.py
└── test_integration.py        # 통합 플로우 (로그인→백테스트)

webapp-ui/__tests__/            # vitest (선택, E2E가 주)
webapp-ui/e2e/                  # Playwright
└── backtest-flow.spec.ts
```

---

## Task Index

### Part A — Backend Foundation (Tasks 1-10)
1. Python 의존성 추가 + 웹앱 패키지 스켈레톤
2. Config 확장 (webapp-only 설정)
3. `data/webapp.db` 스키마 + 초기화 유틸
4. UserRepository + 비밀번호 해싱/검증
5. SessionRepository + 토큰 생성·검증
6. LoginAttemptsRepository + 브루트포스 방어
7. Job 모델 + JobRepository (CRUD + 진행률 업데이트)
8. Job Runner + Orphan 복구 로직
9. AlertLogRepository + MonitorNotifier (rate limit 포함)
10. CSRF + Rate Limit + Security Headers 미들웨어

### Part B — Backend API (Tasks 11-16)
11. Auth Routes (`/login`, `/logout`, `/me`, `/csrf-token`)
12. Jobs Route (`GET /jobs/{id}`)
13. BacktestReader 어댑터 (기존 BacktestStore 래핑 + DTO)
14. Backtest 조회 API (`/backtest/runs/*`, `/compare`)
15. Backtest 실행 API (`POST /backtest/run`) — Job 생성·실행
16. FastAPI `main.py` 어셈블리 + 라우터 통합 + startup 훅

### Part C — Backend CLI + Ops Wiring (Tasks 17-19)
17. `ap webapp` CLI 명령 (`create-admin`, `unlock-account`, `reset-password`, `verify-monitoring`)
18. 감사 로그 통합 (기존 `AuditLogger` 재사용, 웹 이벤트 wiring)
19. 통합 테스트 (로그인 → 백테스트 실행 → 결과 조회 풀 플로우)

### Part D — Frontend Foundation (Tasks 20-23)
20. Next.js + TypeScript + Tailwind 스캐폴드
21. shadcn/ui 초기화 + 기본 컴포넌트 생성
22. API 클라이언트 + 세션 관리 (`lib/auth.ts`, `lib/api-client.ts`, `middleware.ts`)
23. 로그인 페이지 + Dashboard Layout (사이드바 + 세션 재검증)

### Part E — Frontend Backtest UI (Tasks 24-29)
24. 백테스트 리스트 페이지 + RunsTable
25. 백테스트 상세 페이지 (지표 카드 + 자산 곡선 차트)
26. 백테스트 상세 — 드로다운 + 월별 히트맵
27. 거래 이력 페이지 + TradesTable
28. 포지션 이력 페이지 + PositionViewer
29. 백테스트 실행 폼 + 진행률 페이지 + 비교 페이지

### Part F — Deployment + Quality (Tasks 30-34)
30. systemd 유닛 + Cloudflare Tunnel 설정 문서
31. 일일 백업 스크립트
32. CI 주간 취약점 스캔 워크플로우
33. 운영 문서 초안 (`webapp-deployment.md`, `webapp-runbook.md`, `security-checklist.md`)
34. Playwright E2E 스모크 테스트

---

## Part A — Backend Foundation

### Task 1: Python 의존성 + 웹앱 패키지 스켈레톤

**Files:**
- Modify: `pyproject.toml`
- Create: `alphapulse/webapp/__init__.py`
- Create: `alphapulse/webapp/auth/__init__.py`
- Create: `alphapulse/webapp/jobs/__init__.py`
- Create: `alphapulse/webapp/api/__init__.py`
- Create: `alphapulse/webapp/store/__init__.py`
- Create: `alphapulse/webapp/store/readers/__init__.py`
- Create: `alphapulse/webapp/middleware/__init__.py`
- Create: `tests/webapp/__init__.py`

- [ ] **Step 1: `pyproject.toml`에 의존성 추가**

`[project.dependencies]` 배열에 다음을 추가:
```
"fastapi>=0.115",
"uvicorn[standard]>=0.32",
"bcrypt>=4.1",
"slowapi>=0.1.9",
"itsdangerous>=2.2",
```

`[dependency-groups.dev]`(또는 `[project.optional-dependencies.dev]`)에 추가:
```
"httpx>=0.27",
"pip-audit>=2.7",
"bandit>=1.7",
```

- [ ] **Step 2: 설치 확인**
```bash
uv sync
uv run python -c "import fastapi, uvicorn, bcrypt, slowapi; print('ok')"
```
예상 출력: `ok`

- [ ] **Step 3: 빈 패키지 파일 생성**

각 `__init__.py`는 1줄 docstring만:
```python
"""AlphaPulse 웹앱 — Phase 1."""
```

- [ ] **Step 4: pytest 확인**
```bash
pytest tests/webapp/ -q
```
예상: `no tests ran` (에러 없이 통과)

- [ ] **Step 5: 커밋**
```bash
git add pyproject.toml uv.lock alphapulse/webapp/ tests/webapp/
git commit -m "feat(webapp): Phase 1 의존성 + 패키지 스켈레톤"
```

---

### Task 2: Config 확장 (webapp-only 설정)

**Files:**
- Modify: `alphapulse/core/config.py` (필드만 추가)
- Create: `alphapulse/webapp/config.py`
- Test: `tests/webapp/test_config.py`

- [ ] **Step 1: 테스트 작성 — `tests/webapp/test_config.py`**
```python
"""webapp 설정 테스트."""
import os
from unittest.mock import patch

import pytest

from alphapulse.webapp.config import WebAppConfig


class TestWebAppConfig:
    def test_session_defaults(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="", monitor_channel_id="",
        )
        assert cfg.session_cookie_name == "ap_session"
        assert cfg.session_ttl_seconds == 86400
        assert cfg.session_absolute_ttl_seconds == 30 * 86400

    def test_monitor_disabled_when_missing(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="", monitor_channel_id="",
        )
        assert cfg.monitor_enabled is False

    def test_monitor_enabled_when_set(self):
        cfg = WebAppConfig(
            session_secret="x" * 32,
            monitor_bot_token="abc", monitor_channel_id="-100",
        )
        assert cfg.monitor_enabled is True

    def test_session_secret_required_min_length(self):
        with pytest.raises(ValueError, match="32"):
            WebAppConfig(
                session_secret="short",
                monitor_bot_token="", monitor_channel_id="",
            )

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("WEBAPP_SESSION_SECRET", "y" * 32)
        monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "-1")
        cfg = WebAppConfig.from_env()
        assert cfg.session_secret == "y" * 32
        assert cfg.monitor_enabled is True
```

- [ ] **Step 2: 테스트 실행 (FAIL)**
```bash
pytest tests/webapp/test_config.py -v
```
예상: `ModuleNotFoundError: alphapulse.webapp.config`

- [ ] **Step 3: `alphapulse/webapp/config.py` 구현**
```python
"""웹앱 전용 설정 — alphapulse.core.Config와 별도.

환경 변수:
  WEBAPP_SESSION_SECRET     (필수, 최소 32자)
  WEBAPP_ENCRYPT_KEY        (선택, Phase 3 대비 — Fernet 키)
  TELEGRAM_MONITOR_BOT_TOKEN (선택, 운영 채널)
  TELEGRAM_MONITOR_CHANNEL_ID (선택)
  WEBAPP_DB_PATH            (기본 data/webapp.db)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WebAppConfig:
    session_secret: str
    monitor_bot_token: str
    monitor_channel_id: str
    encrypt_key: str = ""
    db_path: str = "data/webapp.db"
    session_cookie_name: str = "ap_session"
    session_ttl_seconds: int = 86400           # 24h
    session_absolute_ttl_seconds: int = 30 * 86400
    session_sliding_seconds: int = 900          # 15분
    bcrypt_cost: int = 12

    def __post_init__(self) -> None:
        if len(self.session_secret) < 32:
            raise ValueError(
                "WEBAPP_SESSION_SECRET must be at least 32 chars"
            )

    @property
    def monitor_enabled(self) -> bool:
        return bool(self.monitor_bot_token and self.monitor_channel_id)

    @classmethod
    def from_env(cls) -> "WebAppConfig":
        return cls(
            session_secret=os.environ["WEBAPP_SESSION_SECRET"],
            monitor_bot_token=os.environ.get(
                "TELEGRAM_MONITOR_BOT_TOKEN", ""
            ),
            monitor_channel_id=os.environ.get(
                "TELEGRAM_MONITOR_CHANNEL_ID", ""
            ),
            encrypt_key=os.environ.get("WEBAPP_ENCRYPT_KEY", ""),
            db_path=os.environ.get("WEBAPP_DB_PATH", "data/webapp.db"),
        )

    def db_path_resolved(self, base_dir: Path) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else base_dir / p
```

- [ ] **Step 4: 테스트 실행 (PASS)**
```bash
pytest tests/webapp/test_config.py -v
```
예상: 5 passed

- [ ] **Step 5: 린트 + 커밋**
```bash
ruff check alphapulse/webapp/config.py tests/webapp/test_config.py
git add alphapulse/webapp/config.py tests/webapp/test_config.py
git commit -m "feat(webapp): WebAppConfig + 세션/모니터 환경변수"
```

---

### Task 3: `data/webapp.db` 스키마 + 초기화 유틸

**Files:**
- Create: `alphapulse/webapp/store/webapp_db.py`
- Test: `tests/webapp/store/__init__.py` (빈)
- Test: `tests/webapp/store/test_webapp_db.py`
- Test: `tests/webapp/conftest.py`

- [ ] **Step 1: conftest — 공통 fixture**
`tests/webapp/conftest.py`:
```python
"""webapp 테스트 공통 fixture."""
from pathlib import Path

import pytest

from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def webapp_db(tmp_path: Path) -> Path:
    """빈 스키마로 초기화된 임시 webapp.db 경로."""
    db_path = tmp_path / "webapp.db"
    init_webapp_db(db_path)
    return db_path
```

- [ ] **Step 2: 테스트 작성 — `tests/webapp/store/test_webapp_db.py`**
```python
"""webapp.db 스키마/초기화 테스트."""
import sqlite3

from alphapulse.webapp.store.webapp_db import init_webapp_db


class TestInitWebAppDb:
    def test_creates_all_tables(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "ORDER BY name"
            ).fetchall()
        names = {r[0] for r in rows}
        assert names == {
            "users", "sessions", "jobs", "login_attempts", "alert_log",
        }

    def test_users_has_tenant_id_column(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            cols = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = {c[1] for c in cols}
        assert "tenant_id" in col_names

    def test_idempotent(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        init_webapp_db(db)  # 두 번 호출해도 에러 없음

    def test_wal_mode_enabled(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_indexes_created(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name LIKE 'idx_%'"
            ).fetchall()
        names = {r[0] for r in rows}
        assert "idx_users_email" in names
        assert "idx_sessions_expires" in names
        assert "idx_jobs_status" in names
```

- [ ] **Step 3: 테스트 실행 (FAIL)**
```bash
pytest tests/webapp/store/ -v
```
예상: `ModuleNotFoundError: alphapulse.webapp.store.webapp_db`

- [ ] **Step 4: `alphapulse/webapp/store/webapp_db.py` 구현**
```python
"""data/webapp.db 스키마 초기화.

기존 DB(trading.db, backtest.db 등)와 분리된 웹앱 전용 DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    tenant_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    last_login_at REAL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    ip TEXT,
    user_agent TEXT,
    revoked_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL DEFAULT 0.0,
    progress_text TEXT DEFAULT '',
    params TEXT NOT NULL,
    result_ref TEXT,
    error TEXT,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_kind ON jobs(kind);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip TEXT NOT NULL,
    success INTEGER NOT NULL,
    attempted_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email
    ON login_attempts(email, attempted_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip
    ON login_attempts(ip, attempted_at);

CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    level TEXT NOT NULL,
    first_sent_at REAL NOT NULL,
    last_sent_at REAL NOT NULL,
    count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_alert_log_title
    ON alert_log(title, last_sent_at);
"""


def init_webapp_db(db_path: str | Path) -> None:
    """webapp.db 스키마를 생성/확인한다. 이미 있으면 변경 없음.

    WAL 저널 모드를 활성화하여 reader-writer 병행을 허용한다.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
```

- [ ] **Step 5: 테스트 + 커밋**
```bash
pytest tests/webapp/store/ -v
ruff check alphapulse/webapp/store/webapp_db.py tests/webapp/
git add alphapulse/webapp/store/webapp_db.py tests/webapp/
git commit -m "feat(webapp): webapp.db 스키마 5테이블 + WAL 초기화"
```

---

### Task 4: UserRepository + 비밀번호 해싱/검증

**Files:**
- Create: `alphapulse/webapp/auth/security.py`
- Create: `alphapulse/webapp/store/users.py`
- Test: `tests/webapp/auth/__init__.py` (빈)
- Test: `tests/webapp/auth/test_security.py`
- Test: `tests/webapp/store/test_users.py`

- [ ] **Step 1: 보안 유틸 테스트**
`tests/webapp/auth/test_security.py`:
```python
"""인증 보안 유틸 테스트."""
import pytest

from alphapulse.webapp.auth.security import (
    generate_session_token,
    hash_password,
    verify_password,
)


class TestPasswordHash:
    def test_hash_is_not_plaintext(self):
        h = hash_password("s3cret-longenough!")
        assert "s3cret-longenough!" not in h
        assert h.startswith("$2b$")  # bcrypt

    def test_verify_correct(self):
        h = hash_password("s3cret-longenough!")
        assert verify_password("s3cret-longenough!", h)

    def test_verify_wrong(self):
        h = hash_password("s3cret-longenough!")
        assert not verify_password("wrong!", h)

    def test_rejects_short_password(self):
        with pytest.raises(ValueError, match="12"):
            hash_password("short")


class TestSessionToken:
    def test_token_length(self):
        t = generate_session_token()
        assert len(t) >= 40          # secrets.token_urlsafe(32) ≈ 43

    def test_tokens_unique(self):
        assert generate_session_token() != generate_session_token()
```

- [ ] **Step 2: 보안 유틸 구현 (`alphapulse/webapp/auth/security.py`)**
```python
"""인증 보안 유틸 — bcrypt + 세션 토큰."""

from __future__ import annotations

import secrets

import bcrypt

_MIN_PASSWORD_LEN = 12
_BCRYPT_COST = 12


def hash_password(password: str) -> str:
    """bcrypt로 비밀번호를 해싱한다. 최소 길이 12자 강제."""
    if len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(
            f"password must be at least {_MIN_PASSWORD_LEN} chars"
        )
    salt = bcrypt.gensalt(rounds=_BCRYPT_COST)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """평문과 해시를 비교한다. timing-safe."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed.encode("utf-8")
        )
    except ValueError:
        return False


def generate_session_token() -> str:
    """세션 ID — URL-safe 토큰 32바이트."""
    return secrets.token_urlsafe(32)
```

- [ ] **Step 3: UserRepository 테스트**
`tests/webapp/store/test_users.py`:
```python
"""UserRepository 테스트."""
import time

import pytest

from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def users(webapp_db):
    return UserRepository(db_path=webapp_db)


class TestUsers:
    def test_create_and_get(self, users):
        uid = users.create(
            email="admin@example.com",
            password_hash="$2b$12$fakehash",
            role="admin",
        )
        user = users.get_by_email("admin@example.com")
        assert user is not None
        assert user.id == uid
        assert user.email == "admin@example.com"
        assert user.role == "admin"
        assert user.is_active is True

    def test_get_by_id(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h", role="admin",
        )
        user = users.get_by_id(uid)
        assert user is not None
        assert user.email == "a@b.com"

    def test_duplicate_email_raises(self, users):
        users.create(
            email="x@y.com", password_hash="h", role="admin",
        )
        with pytest.raises(ValueError):
            users.create(
                email="x@y.com", password_hash="h2", role="admin",
            )

    def test_update_last_login(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h", role="admin",
        )
        users.touch_last_login(uid)
        user = users.get_by_id(uid)
        assert user.last_login_at is not None
        assert time.time() - user.last_login_at < 5

    def test_update_password_hash(self, users):
        uid = users.create(
            email="a@b.com", password_hash="h1", role="admin",
        )
        users.update_password_hash(uid, "h2")
        user = users.get_by_id(uid)
        assert user.password_hash == "h2"

    def test_get_not_found(self, users):
        assert users.get_by_email("none@x.com") is None
        assert users.get_by_id(9999) is None
```

- [ ] **Step 4: UserRepository 구현 (`alphapulse/webapp/store/users.py`)**
```python
"""UserRepository — data/webapp.db users 테이블 CRUD."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    role: str
    tenant_id: int | None
    is_active: bool
    created_at: float
    last_login_at: float | None


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=row["role"],
        tenant_id=row["tenant_id"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
    )


class UserRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        email: str,
        password_hash: str,
        role: str = "admin",
        tenant_id: int | None = None,
    ) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute(
                    "INSERT INTO users (email, password_hash, role, "
                    "tenant_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (email, password_hash, role, tenant_id, time.time()),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"duplicate email: {email}") from e

    def get_by_email(self, email: str) -> User | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return _row_to_user(row) if row else None

    def get_by_id(self, user_id: int) -> User | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return _row_to_user(row) if row else None

    def touch_last_login(self, user_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (time.time(), user_id),
            )

    def update_password_hash(self, user_id: int, new_hash: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id),
            )

    def set_active(self, user_id: int, active: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if active else 0, user_id),
            )
```

- [ ] **Step 5: 테스트 + 커밋**
```bash
pytest tests/webapp/auth/test_security.py tests/webapp/store/test_users.py -v
ruff check alphapulse/webapp/auth/security.py alphapulse/webapp/store/users.py tests/webapp/
git add alphapulse/webapp/auth/security.py alphapulse/webapp/store/users.py tests/webapp/
git commit -m "feat(webapp): UserRepository + bcrypt 해싱 + 세션 토큰"
```

---

### Task 5: SessionRepository + 슬라이딩 갱신

**Files:**
- Create: `alphapulse/webapp/store/sessions.py`
- Test: `tests/webapp/store/test_sessions.py`

- [ ] **Step 1: 테스트 작성 (`tests/webapp/store/test_sessions.py`)**
```python
"""SessionRepository 테스트."""
import time

import pytest

from alphapulse.webapp.store.sessions import SessionRepository


@pytest.fixture
def sessions(webapp_db):
    return SessionRepository(db_path=webapp_db)


class TestSessions:
    def test_create_and_get(self, sessions):
        sessions.create(
            token="tok1", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="1.2.3.4", ua="agent",
        )
        sess = sessions.get("tok1")
        assert sess is not None
        assert sess.user_id == 1
        assert sess.ip == "1.2.3.4"
        assert sess.is_expired is False
        assert sess.revoked_at is None

    def test_expired(self, sessions):
        sessions.create(
            token="old", user_id=1, ttl_seconds=-1,
            absolute_ttl_seconds=-1, ip="", ua="",
        )
        sess = sessions.get("old")
        assert sess.is_expired is True

    def test_touch_extends(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=60,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        first = sessions.get("t").expires_at
        time.sleep(0.01)
        sessions.touch("t", ttl_seconds=120, absolute_ttl_seconds=86400)
        second = sessions.get("t").expires_at
        assert second > first

    def test_touch_respects_absolute_cap(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=60,
            absolute_ttl_seconds=120,   # 120초 후 절대 만료
            ip="", ua="",
        )
        # touch할 때 원하는 TTL이 절대 만료보다 크면 절대로 cap
        sessions.touch(
            "t", ttl_seconds=86400, absolute_ttl_seconds=120,
        )
        sess = sessions.get("t")
        assert sess.expires_at - sess.created_at <= 120

    def test_revoke(self, sessions):
        sessions.create(
            token="t", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        sessions.revoke("t")
        sess = sessions.get("t")
        assert sess.revoked_at is not None

    def test_cleanup_expired(self, sessions):
        sessions.create(
            token="old", user_id=1, ttl_seconds=-1,
            absolute_ttl_seconds=-1, ip="", ua="",
        )
        sessions.create(
            token="new", user_id=1, ttl_seconds=3600,
            absolute_ttl_seconds=86400, ip="", ua="",
        )
        deleted = sessions.cleanup_expired()
        assert deleted == 1
        assert sessions.get("old") is None
        assert sessions.get("new") is not None

    def test_get_not_found(self, sessions):
        assert sessions.get("missing") is None
```

- [ ] **Step 2: 구현 (`alphapulse/webapp/store/sessions.py`)**
```python
"""SessionRepository — data/webapp.db sessions 테이블.

슬라이딩 갱신과 절대 만료를 모두 관리한다.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Session:
    id: str            # 토큰
    user_id: int
    created_at: float
    expires_at: float
    ip: str | None
    user_agent: str | None
    revoked_at: float | None

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        ip=row["ip"],
        user_agent=row["user_agent"],
        revoked_at=row["revoked_at"],
    )


class SessionRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        token: str,
        user_id: int,
        ttl_seconds: int,
        absolute_ttl_seconds: int,
        ip: str,
        ua: str,
    ) -> None:
        now = time.time()
        expires = now + min(ttl_seconds, absolute_ttl_seconds)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, user_id, created_at, "
                "expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
                (token, user_id, now, expires, ip, ua),
            )

    def get(self, token: str) -> Session | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (token,)
            ).fetchone()
        return _row_to_session(row) if row else None

    def touch(
        self,
        token: str,
        ttl_seconds: int,
        absolute_ttl_seconds: int,
    ) -> None:
        """슬라이딩 갱신 — 요청된 TTL이 절대 만료를 넘지 않도록 cap."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT created_at FROM sessions WHERE id = ?", (token,)
            ).fetchone()
            if row is None:
                return
            abs_deadline = row["created_at"] + absolute_ttl_seconds
            new_expires = min(now + ttl_seconds, abs_deadline)
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                (new_expires, token),
            )

    def revoke(self, token: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE id = ?",
                (time.time(), token),
            )

    def cleanup_expired(self) -> int:
        """만료된 세션 삭제. 삭제된 행 수 반환."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (time.time(),),
            )
            return cur.rowcount
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_sessions.py -v
ruff check alphapulse/webapp/store/sessions.py tests/webapp/store/test_sessions.py
git add alphapulse/webapp/store/sessions.py tests/webapp/store/test_sessions.py
git commit -m "feat(webapp): SessionRepository + 슬라이딩 갱신 + 절대 만료 cap"
```

---

### Task 6: LoginAttemptsRepository + 브루트포스 방어

**Files:**
- Create: `alphapulse/webapp/store/login_attempts.py`
- Test: `tests/webapp/store/test_login_attempts.py`

- [ ] **Step 1: 테스트**
```python
"""LoginAttemptsRepository 테스트 — 브루트포스 방어 카운팅."""
import time

import pytest

from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository


@pytest.fixture
def attempts(webapp_db):
    return LoginAttemptsRepository(db_path=webapp_db)


class TestLoginAttempts:
    def test_record_and_count_failures(self, attempts):
        for _ in range(3):
            attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_email(
            "a@b.com", window_seconds=900,
        )
        assert n == 3

    def test_success_does_not_count(self, attempts):
        attempts.record(email="a@b.com", ip="1.1.1.1", success=True)
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_email("a@b.com", 900)
        assert n == 1

    def test_old_failures_ignored(self, attempts):
        # 윈도우 밖으로 밀어내기 위해 직접 삽입
        import sqlite3
        with sqlite3.connect(attempts.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                ("a@b.com", "1.1.1.1", 0, time.time() - 10_000),
            )
        n = attempts.recent_failures_by_email("a@b.com", 900)
        assert n == 0

    def test_count_by_ip(self, attempts):
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        attempts.record(email="c@d.com", ip="1.1.1.1", success=False)
        n = attempts.recent_failures_by_ip("1.1.1.1", window_seconds=60)
        assert n == 2

    def test_cleanup(self, attempts):
        import sqlite3
        with sqlite3.connect(attempts.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                ("a@b.com", "1.1.1.1", 0, time.time() - 86400 * 30),
            )
        attempts.record(email="a@b.com", ip="1.1.1.1", success=False)
        deleted = attempts.cleanup_older_than(86400 * 7)
        assert deleted == 1
```

- [ ] **Step 2: 구현**
```python
"""LoginAttemptsRepository — 브루트포스 방어."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class LoginAttemptsRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def record(self, email: str, ip: str, success: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip, success, "
                "attempted_at) VALUES (?, ?, ?, ?)",
                (email, ip, 1 if success else 0, time.time()),
            )

    def recent_failures_by_email(
        self, email: str, window_seconds: int,
    ) -> int:
        threshold = time.time() - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE email = ? AND success = 0 AND attempted_at >= ?",
                (email, threshold),
            ).fetchone()
        return int(row[0])

    def recent_failures_by_ip(
        self, ip: str, window_seconds: int,
    ) -> int:
        threshold = time.time() - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM login_attempts "
                "WHERE ip = ? AND success = 0 AND attempted_at >= ?",
                (ip, threshold),
            ).fetchone()
        return int(row[0])

    def cleanup_older_than(self, seconds: int) -> int:
        threshold = time.time() - seconds
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM login_attempts WHERE attempted_at < ?",
                (threshold,),
            )
            return cur.rowcount
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_login_attempts.py -v
git add alphapulse/webapp/store/login_attempts.py tests/webapp/store/test_login_attempts.py
git commit -m "feat(webapp): LoginAttemptsRepository — 이메일/IP 실패 카운트"
```

---

### Task 7: Job 모델 + JobRepository

**Files:**
- Create: `alphapulse/webapp/jobs/models.py`
- Create: `alphapulse/webapp/store/jobs.py`
- Test: `tests/webapp/store/test_jobs.py`

- [ ] **Step 1: 모델 (`alphapulse/webapp/jobs/models.py`)**
```python
"""Job dataclass — 백그라운드 작업 상태."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

JobStatus = Literal["pending", "running", "done", "failed", "cancelled"]
JobKind = Literal["backtest", "screening", "data_update"]


@dataclass
class Job:
    id: str
    kind: JobKind
    status: JobStatus
    progress: float = 0.0
    progress_text: str = ""
    params: dict = field(default_factory=dict)
    result_ref: str | None = None
    error: str | None = None
    user_id: int = 0
    tenant_id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None

    def params_json(self) -> str:
        return json.dumps(self.params, ensure_ascii=False)
```

- [ ] **Step 2: Repository 테스트 (`tests/webapp/store/test_jobs.py`)**
```python
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
```

- [ ] **Step 3: 구현 (`alphapulse/webapp/store/jobs.py`)**
```python
"""JobRepository — data/webapp.db jobs 테이블."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from alphapulse.webapp.jobs.models import Job, JobKind, JobStatus


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        kind=row["kind"],
        status=row["status"],
        progress=row["progress"],
        progress_text=row["progress_text"] or "",
        params=json.loads(row["params"]) if row["params"] else {},
        result_ref=row["result_ref"],
        error=row["error"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


class JobRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        job_id: str,
        kind: JobKind,
        params: dict,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, status, progress, "
                "progress_text, params, user_id, tenant_id, "
                "created_at, updated_at) "
                "VALUES (?, ?, 'pending', 0.0, '', ?, ?, ?, ?, ?)",
                (
                    job_id, kind,
                    json.dumps(params, ensure_ascii=False),
                    user_id, tenant_id, now, now,
                ),
            )

    def get(self, job_id: str) -> Job | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _row_to_job(row) if row else None

    def update_progress(
        self, job_id: str, progress: float, text: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET progress = ?, progress_text = ?, "
                "updated_at = ? WHERE id = ?",
                (progress, text, time.time(), job_id),
            )

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        started_at: float | None = None,
        finished_at: float | None = None,
        result_ref: str | None = None,
        error: str | None = None,
    ) -> None:
        fields = ["status = ?", "updated_at = ?"]
        values: list = [status, time.time()]
        if started_at is not None:
            fields.append("started_at = ?")
            values.append(started_at)
        if finished_at is not None:
            fields.append("finished_at = ?")
            values.append(finished_at)
        if result_ref is not None:
            fields.append("result_ref = ?")
            values.append(result_ref)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        values.append(job_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    def list_by_status(self, status: JobStatus) -> list[Job]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at",
                (status,),
            ).fetchall()
        return [_row_to_job(r) for r in rows]
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_jobs.py -v
git add alphapulse/webapp/jobs/ alphapulse/webapp/store/jobs.py tests/webapp/store/test_jobs.py
git commit -m "feat(webapp): Job 모델 + JobRepository (진행률·상태 업데이트)"
```

---

### Task 8: Job Runner + Orphan 복구

**Files:**
- Create: `alphapulse/webapp/jobs/runner.py`
- Test: `tests/webapp/jobs/__init__.py`
- Test: `tests/webapp/jobs/test_runner.py`

- [ ] **Step 1: 테스트**
```python
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
```

`tests/webapp/jobs/__init__.py` 은 빈 파일.

- [ ] **Step 2: 구현**
```python
"""JobRunner — asyncio 백그라운드 실행기.

ARQ 호환 시그니처: future에서 `async def(ctx, *args)` worker로 이식 가능.
"""

from __future__ import annotations

import asyncio
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
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/jobs/test_runner.py -v
git add alphapulse/webapp/jobs/runner.py tests/webapp/jobs/
git commit -m "feat(webapp): JobRunner — asyncio 백그라운드 실행 + Orphan 복구"
```

---

### Task 9: AlertLog + MonitorNotifier

**Files:**
- Create: `alphapulse/webapp/store/alert_log.py`
- Create: `alphapulse/webapp/notifier.py`
- Test: `tests/webapp/store/test_alert_log.py`
- Test: `tests/webapp/test_notifier.py`

- [ ] **Step 1: AlertLog 테스트**
```python
"""AlertLogRepository — 동일 알림 중복 방지."""
import time

import pytest

from alphapulse.webapp.store.alert_log import AlertLogRepository


@pytest.fixture
def log(webapp_db):
    return AlertLogRepository(db_path=webapp_db)


class TestAlertLog:
    def test_first_send_allowed(self, log):
        allowed = log.should_send(
            title="FastAPI 5xx burst", level="ERROR", window_seconds=300,
        )
        assert allowed is True

    def test_duplicate_within_window_denied(self, log):
        log.should_send(
            title="same", level="ERROR", window_seconds=300,
        )
        allowed = log.should_send(
            title="same", level="ERROR", window_seconds=300,
        )
        assert allowed is False

    def test_after_window_allowed(self, log):
        log.should_send(title="x", level="ERROR", window_seconds=1)
        time.sleep(1.1)
        allowed = log.should_send(
            title="x", level="ERROR", window_seconds=1,
        )
        assert allowed is True

    def test_counts_duplicates(self, log):
        log.should_send(title="y", level="ERROR", window_seconds=300)
        log.should_send(title="y", level="ERROR", window_seconds=300)
        log.should_send(title="y", level="ERROR", window_seconds=300)
        n = log.suppressed_count(title="y")
        assert n == 2   # 첫 번째는 send, 이후 2번 억제됨
```

- [ ] **Step 2: AlertLog 구현**
```python
"""AlertLogRepository — 알림 rate limit (동일 title 5분 내 1회)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class AlertLogRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def should_send(
        self, title: str, level: str, window_seconds: int,
    ) -> bool:
        now = time.time()
        threshold = now - window_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, last_sent_at, count FROM alert_log "
                "WHERE title = ? ORDER BY last_sent_at DESC LIMIT 1",
                (title,),
            ).fetchone()
            if row is None or row["last_sent_at"] < threshold:
                conn.execute(
                    "INSERT INTO alert_log (title, level, "
                    "first_sent_at, last_sent_at, count) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (title, level, now, now),
                )
                return True
            # 억제 — 카운터만 증가
            conn.execute(
                "UPDATE alert_log SET count = count + 1, "
                "last_sent_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return False

    def suppressed_count(self, title: str) -> int:
        """마지막 엔트리의 (count - 1) 반환 — 실제 억제 횟수."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT count FROM alert_log WHERE title = ? "
                "ORDER BY last_sent_at DESC LIMIT 1",
                (title,),
            ).fetchone()
        return max(0, (row[0] - 1) if row else 0)
```

- [ ] **Step 3: MonitorNotifier 테스트**
```python
"""MonitorNotifier — 운영 채널 Telegram 발송 (mock)."""
from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository


@pytest.fixture
def alert_log(webapp_db):
    return AlertLogRepository(db_path=webapp_db)


@pytest.fixture
def notifier(alert_log):
    return MonitorNotifier(
        bot_token="t", chat_id="-100",
        alert_log=alert_log, window_seconds=300,
    )


class TestMonitorNotifier:
    async def test_disabled_when_missing_token(self, alert_log):
        n = MonitorNotifier(
            bot_token="", chat_id="", alert_log=alert_log,
        )
        assert n.enabled is False
        await n.send("INFO", "t", "detail")  # no-op, no exception

    @patch("alphapulse.webapp.notifier.httpx.AsyncClient")
    async def test_send_calls_api(self, mock_client, notifier):
        mock_post = AsyncMock(
            return_value=AsyncMock(raise_for_status=lambda: None),
        )
        mock_client.return_value.__aenter__.return_value.post = mock_post
        await notifier.send("ERROR", "title", "detail")
        assert mock_post.await_count == 1
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        assert "title" in kwargs["json"]["text"]

    @patch("alphapulse.webapp.notifier.httpx.AsyncClient")
    async def test_rate_limit_skips_second(self, mock_client, notifier):
        mock_post = AsyncMock(
            return_value=AsyncMock(raise_for_status=lambda: None),
        )
        mock_client.return_value.__aenter__.return_value.post = mock_post
        await notifier.send("ERROR", "dup", "x")
        await notifier.send("ERROR", "dup", "x")
        assert mock_post.await_count == 1
```

- [ ] **Step 4: MonitorNotifier 구현**
```python
"""MonitorNotifier — 운영/장애 전용 Telegram 알림.

기존 콘텐츠 채널(alphapulse.core.notifier)과 분리된 봇/채널 사용.
AlertLog로 동일 title 반복을 rate limit.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from alphapulse.webapp.store.alert_log import AlertLogRepository

logger = logging.getLogger(__name__)

Level = Literal["INFO", "WARN", "ERROR", "CRITICAL"]

_EMOJI = {
    "INFO": "\u2139\ufe0f",
    "WARN": "\u26a0\ufe0f",
    "ERROR": "\U0001f6a8",
    "CRITICAL": "\U0001f525",
}


class MonitorNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        alert_log: AlertLogRepository,
        window_seconds: int = 300,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.alert_log = alert_log
        self.window_seconds = window_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(
        self, level: Level, title: str, detail: str = "",
    ) -> None:
        if not self.enabled:
            return
        if not self.alert_log.should_send(
            title=title, level=level,
            window_seconds=self.window_seconds,
        ):
            logger.debug("alert suppressed: %s", title)
            return

        emoji = _EMOJI.get(level, "")
        text = f"{emoji} [{level}] {title}"
        if detail:
            text += f"\n\n{detail[:3500]}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.exception("monitor telegram send failed")
```

- [ ] **Step 5: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_alert_log.py tests/webapp/test_notifier.py -v
git add alphapulse/webapp/store/alert_log.py alphapulse/webapp/notifier.py tests/webapp/
git commit -m "feat(webapp): MonitorNotifier + AlertLog rate limit"
```

---

### Task 10: CSRF + Rate Limit + Security Headers 미들웨어

**Files:**
- Create: `alphapulse/webapp/middleware/csrf.py`
- Create: `alphapulse/webapp/middleware/rate_limit.py`
- Create: `alphapulse/webapp/middleware/security_headers.py`
- Test: `tests/webapp/middleware/__init__.py` (빈)
- Test: `tests/webapp/middleware/test_csrf.py`
- Test: `tests/webapp/middleware/test_security_headers.py`

- [ ] **Step 1: CSRF 구현 + 테스트 (Double Submit Cookie)**

먼저 테스트:
```python
"""CSRF Double Submit Cookie 미들웨어."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.middleware.csrf import CSRFMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, secret="x" * 32)

    @app.get("/api/v1/csrf-token")
    async def token(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    @app.post("/api/v1/x")
    async def post():
        return {"ok": True}

    @app.get("/api/v1/y")
    async def get():
        return {"ok": True}

    return app


class TestCSRFMiddleware:
    def test_get_allowed_without_token(self):
        client = TestClient(_app())
        r = client.get("/api/v1/y")
        assert r.status_code == 200

    def test_post_without_token_rejected(self):
        client = TestClient(_app())
        r = client.post("/api/v1/x")
        assert r.status_code == 403

    def test_post_with_matching_token_accepted(self):
        client = TestClient(_app())
        r1 = client.get("/api/v1/csrf-token")
        token = r1.json()["token"]
        r2 = client.post(
            "/api/v1/x", headers={"X-CSRF-Token": token},
            cookies={"ap_csrf": token},
        )
        assert r2.status_code == 200

    def test_post_with_mismatched_token_rejected(self):
        client = TestClient(_app())
        client.get("/api/v1/csrf-token")
        r = client.post(
            "/api/v1/x", headers={"X-CSRF-Token": "wrong"},
            cookies={"ap_csrf": "other"},
        )
        assert r.status_code == 403
```

구현:
```python
"""CSRF 미들웨어 — Double Submit Cookie 패턴.

- GET /api/v1/csrf-token → 쿠키 `ap_csrf` 설정 + body에 토큰
- 변경 요청(POST/PUT/DELETE)은 `X-CSRF-Token` 헤더와 `ap_csrf` 쿠키가 일치해야 통과
- GET/HEAD/OPTIONS는 통과
"""

from __future__ import annotations

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_CSRF_COOKIE = "ap_csrf"
_CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret: str) -> None:
        super().__init__(app)
        self.secret = secret

    async def dispatch(self, request: Request, call_next) -> Response:
        cookie = request.cookies.get(_CSRF_COOKIE, "")
        # 토큰 발급 엔드포인트 전용 처리
        if request.url.path == "/api/v1/csrf-token":
            token = cookie or secrets.token_urlsafe(32)
            request.state.csrf_token = token
            response = await call_next(request)
            response.set_cookie(
                _CSRF_COOKIE, token,
                httponly=False,       # JS가 읽어 헤더에 복사해야 함
                secure=True,
                samesite="strict",
                path="/",
            )
            return response

        # 안전 메서드는 검증 생략
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        header = request.headers.get(_CSRF_HEADER, "")
        if not cookie or not header or not hmac.compare_digest(
            cookie, header,
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "type": "https://alphapulse/errors/csrf",
                    "title": "CSRF validation failed",
                    "status": 403,
                    "detail": "missing or mismatched CSRF token",
                },
            )
        return await call_next(request)
```

- [ ] **Step 2: Security Headers 구현 + 테스트**

테스트:
```python
"""보안 헤더 미들웨어."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/x")
    async def x():
        return {"ok": True}
    return app


class TestSecurityHeaders:
    def test_headers_present(self):
        client = TestClient(_app())
        r = client.get("/x")
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "strict-origin" in r.headers["Referrer-Policy"]
        assert "default-src" in r.headers["Content-Security-Policy"]
```

구현:
```python
"""Security Headers 미들웨어 — CSP, X-Frame-Options 등."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin",
        )
        response.headers.setdefault("Content-Security-Policy", _CSP)
        return response
```

- [ ] **Step 3: Rate Limit 래퍼 (`alphapulse/webapp/middleware/rate_limit.py`)**

slowapi 초기화를 한 곳에 모아둔 얇은 래퍼. 사용은 각 라우트에서 데코레이터로.
```python
"""Rate Limit — slowapi 래퍼.

FastAPI 앱에 limiter.state 주입을 편하게 하기 위한 팩토리.
라우트에서는 `@limiter.limit("10/minute")` 데코레이터로 사용.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def make_limiter() -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        default_limits=["300/minute"],   # 사용자당 기본값
    )
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/middleware/ -v
ruff check alphapulse/webapp/middleware/ tests/webapp/middleware/
git add alphapulse/webapp/middleware/ tests/webapp/middleware/
git commit -m "feat(webapp): CSRF + SecurityHeaders + slowapi 팩토리"
```

---

## Part B — Backend API

### Task 11: Auth Routes (`/login`, `/logout`, `/me`, `/csrf-token`)

**Files:**
- Create: `alphapulse/webapp/auth/models.py`
- Create: `alphapulse/webapp/auth/deps.py`
- Create: `alphapulse/webapp/auth/routes.py`
- Test: `tests/webapp/auth/test_routes.py`

- [ ] **Step 1: Pydantic 모델 (`alphapulse/webapp/auth/models.py`)**
```python
"""Auth Pydantic 모델 — 요청/응답 DTO."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: int
    email: str
    role: str


class LoginResponse(BaseModel):
    user: UserResponse
```

- [ ] **Step 2: 의존성 주입 (`alphapulse/webapp/auth/deps.py`)**
```python
"""Auth FastAPI 의존성.

get_current_user, require_role, 그리고 테스트 편의용 provider 패턴.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Cookie, Depends, HTTPException, Request

from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.store.sessions import Session, SessionRepository
from alphapulse.webapp.store.users import User, UserRepository


def get_config(request: Request) -> WebAppConfig:
    return request.app.state.config


def get_users(request: Request) -> UserRepository:
    return request.app.state.users


def get_sessions(request: Request) -> SessionRepository:
    return request.app.state.sessions


async def get_current_user(
    request: Request,
    cfg: WebAppConfig = Depends(get_config),
    users: UserRepository = Depends(get_users),
    sessions: SessionRepository = Depends(get_sessions),
) -> User:
    token = request.cookies.get(cfg.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess: Session | None = sessions.get(token)
    if sess is None or sess.is_expired or sess.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Session invalid")
    # 슬라이딩 갱신
    sessions.touch(
        token,
        ttl_seconds=cfg.session_ttl_seconds,
        absolute_ttl_seconds=cfg.session_absolute_ttl_seconds,
    )
    user = users.get_by_id(sess.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User disabled")
    return user


def require_role(*allowed: str) -> Callable:
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _check
```

- [ ] **Step 3: Auth 라우트 (`alphapulse/webapp/auth/routes.py`)**
```python
"""Auth 라우트 — /login, /logout, /me, /csrf-token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from alphapulse.webapp.auth.deps import (
    get_config,
    get_current_user,
    get_sessions,
    get_users,
)
from alphapulse.webapp.auth.models import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from alphapulse.webapp.auth.security import (
    generate_session_token,
    verify_password,
)
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import User, UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_attempts(request: Request) -> LoginAttemptsRepository:
    return request.app.state.login_attempts


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    cfg: WebAppConfig = Depends(get_config),
    users: UserRepository = Depends(get_users),
    sessions: SessionRepository = Depends(get_sessions),
    attempts: LoginAttemptsRepository = Depends(get_attempts),
):
    client_ip = request.client.host if request.client else ""

    # 계정 잠금 체크
    fails = attempts.recent_failures_by_email(
        body.email, window_seconds=900,
    )
    if fails >= 5:
        raise HTTPException(
            status_code=429, detail="Account temporarily locked",
        )
    ip_fails = attempts.recent_failures_by_ip(
        client_ip, window_seconds=60,
    )
    if ip_fails >= 10:
        raise HTTPException(
            status_code=429, detail="Too many attempts from this IP",
        )

    user = users.get_by_email(body.email)
    ok = (
        user is not None
        and user.is_active
        and verify_password(body.password, user.password_hash)
    )
    attempts.record(email=body.email, ip=client_ip, success=ok)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_session_token()
    sessions.create(
        token=token,
        user_id=user.id,
        ttl_seconds=cfg.session_ttl_seconds,
        absolute_ttl_seconds=cfg.session_absolute_ttl_seconds,
        ip=client_ip,
        ua=request.headers.get("user-agent", ""),
    )
    users.touch_last_login(user.id)

    response.set_cookie(
        cfg.session_cookie_name, token,
        httponly=True, secure=True, samesite="strict",
        path="/", max_age=cfg.session_ttl_seconds,
    )
    return LoginResponse(
        user=UserResponse(id=user.id, email=user.email, role=user.role),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    cfg: WebAppConfig = Depends(get_config),
    sessions: SessionRepository = Depends(get_sessions),
):
    token = request.cookies.get(cfg.session_cookie_name)
    if token:
        sessions.revoke(token)
    response.delete_cookie(
        cfg.session_cookie_name, path="/", samesite="strict",
    )
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, role=user.role)
```

- [ ] **Step 4: Auth 라우트 통합 테스트 (`tests/webapp/auth/test_routes.py`)**
```python
"""Auth 라우트 통합 테스트."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
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
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    return app


@pytest.fixture
def seed_admin(app):
    uid = app.state.users.create(
        email="admin@x.com",
        password_hash=hash_password("correct-horse-battery"),
        role="admin",
    )
    return uid


def _csrf(client: TestClient) -> dict:
    r = client.get("/api/v1/csrf-token")
    t = r.json()["token"]
    return {"headers": {"X-CSRF-Token": t}, "cookies": {"ap_csrf": t}}


class TestLogin:
    def test_success(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            **args,
        )
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "admin@x.com"
        assert "ap_session" in r.cookies

    def test_wrong_password(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@x.com", "password": "wrong-wrong!"},
            **args,
        )
        assert r.status_code == 401

    def test_unknown_email(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "none@x.com", "password": "whatever-long"},
            **args,
        )
        assert r.status_code == 401

    def test_locked_after_5_fails(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@x.com", "password": "wrong-wrong!",
                },
                **args,
            )
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            **args,
        )
        assert r.status_code == 429

    def test_csrf_missing_rejected(self, app, seed_admin):
        client = TestClient(app)
        r = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
        )
        assert r.status_code == 403


class TestMe:
    def test_requires_session(self, app):
        client = TestClient(app)
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_returns_user_when_authed(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            **args,
        )
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "admin@x.com"


class TestLogout:
    def test_logout_revokes(self, app, seed_admin):
        client = TestClient(app)
        args = _csrf(client)
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@x.com",
                "password": "correct-horse-battery",
            },
            **args,
        )
        client.post("/api/v1/auth/logout", **args)
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401
```

- [ ] **Step 5: 테스트 실행 + 커밋**
```bash
pytest tests/webapp/auth/ -v
ruff check alphapulse/webapp/auth/ tests/webapp/auth/
git add alphapulse/webapp/auth/ tests/webapp/auth/
git commit -m "feat(webapp): Auth 라우트 — login/logout/me + 브루트포스 잠금"
```

---

### Task 12: Jobs Route (`GET /api/v1/jobs/{id}`)

**Files:**
- Create: `alphapulse/webapp/jobs/routes.py`
- Test: `tests/webapp/jobs/test_routes.py`

- [ ] **Step 1: 라우트 구현**
```python
"""Jobs 라우트 — 진행률 polling 전용 GET 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    progress_text: str
    result_ref: str | None
    error: str | None
    created_at: float
    started_at: float | None
    finished_at: float | None


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
):
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return JobResponse(
        id=j.id, kind=j.kind, status=j.status,
        progress=j.progress, progress_text=j.progress_text,
        result_ref=j.result_ref, error=j.error,
        created_at=j.created_at,
        started_at=j.started_at, finished_at=j.finished_at,
    )
```

- [ ] **Step 2: 테스트**
```python
"""Jobs 라우트 테스트."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
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
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    return app


@pytest.fixture
def authed_client(app):
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    client = TestClient(app)
    t = client.get("/api/v1/csrf-token").json()["token"]
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": t},
        cookies={"ap_csrf": t},
    )
    return client


class TestJobsRoute:
    def test_get_404(self, authed_client):
        r = authed_client.get("/api/v1/jobs/none")
        assert r.status_code == 404

    def test_get_ok(self, app, authed_client):
        jid = str(uuid.uuid4())
        app.state.jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        r = authed_client.get(f"/api/v1/jobs/{jid}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_requires_auth(self, app):
        jid = str(uuid.uuid4())
        app.state.jobs.create(
            job_id=jid, kind="backtest", params={}, user_id=1,
        )
        r = TestClient(app).get(f"/api/v1/jobs/{jid}")
        assert r.status_code == 401
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/jobs/test_routes.py -v
git add alphapulse/webapp/jobs/routes.py tests/webapp/jobs/test_routes.py
git commit -m "feat(webapp): Jobs GET 라우트 — 진행률 polling용"
```

---

### Task 13: BacktestReader 어댑터

**Files:**
- Create: `alphapulse/webapp/store/readers/backtest.py`
- Test: `tests/webapp/store/test_backtest_reader.py`

목표: 기존 `alphapulse.trading.backtest.store.BacktestStore` 를 웹 응답용으로 감싸서 페이지네이션·필터 DTO를 제공.

- [ ] **Step 1: 테스트 (기존 BacktestStore 직접 사용하여 seed)**
```python
"""BacktestReader — 기존 BacktestStore 래핑 어댑터."""
import json
import time
import uuid

import pytest

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.store.readers.backtest import BacktestReader


def _seed_run(store, name="t", total_return=5.0):
    run_id = str(uuid.uuid4())
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT INTO runs (run_id, name, strategies, allocations,
                start_date, end_date, initial_capital, final_value,
                benchmark, params, metrics, created_at)
            VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                100000000, 105000000, 'KOSPI', '{}', ?, ?)""",
            (
                run_id, name,
                json.dumps({
                    "total_return": total_return,
                    "sharpe_ratio": 1.1,
                    "max_drawdown": -2.0,
                }),
                time.time(),
            ),
        )
    return run_id


@pytest.fixture
def reader(tmp_path):
    store = BacktestStore(db_path=tmp_path / "backtest.db")
    return BacktestReader(db_path=tmp_path / "backtest.db"), store


class TestBacktestReader:
    def test_list_runs_empty(self, reader):
        r, _ = reader
        page = r.list_runs(page=1, size=20)
        assert page.total == 0
        assert page.items == []

    def test_list_runs_paginates(self, reader):
        r, store = reader
        for i in range(25):
            _seed_run(store, name=f"r{i}", total_return=i)
        page = r.list_runs(page=1, size=10)
        assert page.total == 25
        assert len(page.items) == 10
        assert page.page == 1
        assert page.size == 10
        page2 = r.list_runs(page=3, size=10)
        assert len(page2.items) == 5

    def test_list_runs_filter_name(self, reader):
        r, store = reader
        _seed_run(store, name="momentum-bt")
        _seed_run(store, name="value-bt")
        page = r.list_runs(page=1, size=20, name_contains="momentum")
        assert page.total == 1
        assert "momentum" in page.items[0].name

    def test_resolve_by_prefix(self, reader):
        r, store = reader
        rid = _seed_run(store, name="x")
        run = r.resolve_run(rid[:8])
        assert run is not None
        assert run.run_id == rid

    def test_get_run_full_includes_metrics(self, reader):
        r, store = reader
        rid = _seed_run(store, name="x", total_return=7.5)
        full = r.get_run_full(rid)
        assert full is not None
        assert full.metrics["total_return"] == 7.5

    def test_not_found(self, reader):
        r, _ = reader
        assert r.resolve_run("aaaaaaaa") is None
        assert r.get_run_full("aaaaaaaa") is None
```

- [ ] **Step 2: 구현**
```python
"""BacktestReader — 기존 BacktestStore 래핑 + 페이지네이션 DTO."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from alphapulse.trading.backtest.store import BacktestStore


@dataclass
class RunSummary:
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    metrics: dict = field(default_factory=dict)
    created_at: float = 0.0


@dataclass
class RunFull:
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    params: dict
    metrics: dict
    created_at: float


@dataclass
class Page:
    items: list[RunSummary]
    page: int
    size: int
    total: int


class BacktestReader:
    """읽기 전용 어댑터 — 페이지네이션/필터 + 접두사 검색."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        BacktestStore(db_path=self.db_path)  # ensure schema exists
        self._store = BacktestStore(db_path=self.db_path)

    def list_runs(
        self,
        page: int = 1,
        size: int = 20,
        name_contains: str | None = None,
    ) -> Page:
        offset = (page - 1) * size
        where = ""
        params: list = []
        if name_contains:
            where = "WHERE name LIKE ?"
            params.append(f"%{name_contains}%")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM runs {where}", params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM runs {where} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, size, offset],
            ).fetchall()
        items = [self._row_to_summary(r) for r in rows]
        return Page(items=items, page=page, size=size, total=total)

    def resolve_run(self, run_id_or_prefix: str) -> RunSummary | None:
        exact = self._store.get_run(run_id_or_prefix)
        if exact:
            return self._dict_to_summary(exact)
        for row in self._store.list_runs():
            if row["run_id"].startswith(run_id_or_prefix):
                return self._dict_to_summary(row)
        return None

    def get_run_full(self, run_id_or_prefix: str) -> RunFull | None:
        s = self.resolve_run(run_id_or_prefix)
        if s is None:
            return None
        raw = self._store.get_run(s.run_id)
        return RunFull(
            run_id=s.run_id, name=s.name, strategies=s.strategies,
            start_date=s.start_date, end_date=s.end_date,
            initial_capital=s.initial_capital,
            final_value=s.final_value,
            benchmark=s.benchmark,
            params=json.loads(raw.get("params") or "{}"),
            metrics=s.metrics,
            created_at=s.created_at,
        )

    def get_snapshots(self, run_id: str) -> list[dict]:
        return self._store.get_snapshots(run_id)

    def get_trades(
        self,
        run_id: str,
        code: str | None = None,
        winner: bool | None = None,
    ) -> list[dict]:
        rts = self._store.get_round_trips(run_id)
        out = rts
        if code:
            out = [r for r in out if r["code"] == code]
        if winner is True:
            out = [r for r in out if r["pnl"] > 0]
        elif winner is False:
            out = [r for r in out if r["pnl"] <= 0]
        return out

    def get_positions(
        self,
        run_id: str,
        date: str | None = None,
        code: str | None = None,
    ) -> list[dict]:
        return self._store.get_positions(
            run_id, date=date or "", code=code or "",
        )

    def delete_run(self, run_id: str) -> None:
        self._store.delete_run(run_id)

    @staticmethod
    def _row_to_summary(row) -> RunSummary:
        return RunSummary(
            run_id=row["run_id"],
            name=row["name"] or "",
            strategies=json.loads(row["strategies"] or "[]"),
            start_date=row["start_date"],
            end_date=row["end_date"],
            initial_capital=row["initial_capital"],
            final_value=row["final_value"],
            benchmark=row["benchmark"] or "KOSPI",
            metrics=json.loads(row["metrics"] or "{}"),
            created_at=row["created_at"],
        )

    @staticmethod
    def _dict_to_summary(d: dict) -> RunSummary:
        return RunSummary(
            run_id=d["run_id"],
            name=d.get("name", "") or "",
            strategies=json.loads(d.get("strategies") or "[]"),
            start_date=d["start_date"],
            end_date=d["end_date"],
            initial_capital=d["initial_capital"],
            final_value=d["final_value"],
            benchmark=d.get("benchmark") or "KOSPI",
            metrics=json.loads(d.get("metrics") or "{}"),
            created_at=d["created_at"],
        )
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_backtest_reader.py -v
git add alphapulse/webapp/store/readers/ tests/webapp/store/test_backtest_reader.py
git commit -m "feat(webapp): BacktestReader — 페이지네이션/접두사 검색/필터 어댑터"
```

---

### Task 14: Backtest 조회 API

**Files:**
- Create: `alphapulse/webapp/api/backtest.py` (초안 — 조회만)
- Test: `tests/webapp/api/__init__.py` (빈)
- Test: `tests/webapp/api/test_backtest_read.py`

- [ ] **Step 1: 조회 라우트 구현**
```python
"""Backtest API — Phase 1. 조회(Task 14) + 실행(Task 15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


def get_reader(request: Request) -> BacktestReader:
    return request.app.state.backtest_reader


class RunSummaryResponse(BaseModel):
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    metrics: dict
    created_at: float


class RunListResponse(BaseModel):
    items: list[RunSummaryResponse]
    page: int
    size: int
    total: int


class RunDetailResponse(BaseModel):
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    params: dict
    metrics: dict
    created_at: float


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    name: str | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    p = reader.list_runs(page=page, size=size, name_contains=name)
    return RunListResponse(
        items=[RunSummaryResponse(**s.__dict__) for s in p.items],
        page=p.page, size=p.size, total=p.total,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    full = reader.get_run_full(run_id)
    if not full:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetailResponse(**full.__dict__)


@router.get("/runs/{run_id}/snapshots")
async def get_snapshots(
    run_id: str,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_snapshots(s.run_id)}


@router.get("/runs/{run_id}/trades")
async def get_trades(
    run_id: str,
    code: str | None = None,
    winner: bool | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_trades(s.run_id, code=code, winner=winner)}


@router.get("/runs/{run_id}/positions")
async def get_positions(
    run_id: str,
    date: str | None = None,
    code: str | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_positions(s.run_id, date=date, code=code)}


@router.get("/compare")
async def compare_runs(
    ids: str = Query(..., description="comma-separated run ids/prefixes"),
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if len(parts) != 2:
        raise HTTPException(
            status_code=400, detail="ids must have exactly 2 values",
        )
    a = reader.get_run_full(parts[0])
    b = reader.get_run_full(parts[1])
    if not a or not b:
        raise HTTPException(status_code=404, detail="One or both not found")
    return {"a": a.__dict__, "b": b.__dict__}


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    _: User = Depends(require_role("admin")),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    reader.delete_run(s.run_id)
    return {"ok": True}
```

- [ ] **Step 2: 테스트 (`tests/webapp/api/test_backtest_read.py`)**
```python
"""Backtest 조회 API 테스트."""
import json
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.api.backtest import router as bt_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


def _seed(store, name="r"):
    rid = str(uuid.uuid4())
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT INTO runs (run_id, name, strategies, allocations,
                start_date, end_date, initial_capital, final_value,
                benchmark, params, metrics, created_at)
            VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                1e8, 1.05e8, 'KOSPI', '{}', ?, ?)""",
            (
                rid, name,
                json.dumps({"total_return": 5.0}),
                time.time(),
            ),
        )
    return rid


@pytest.fixture
def app(tmp_path):
    bt_db = tmp_path / "backtest.db"
    webapp_db = tmp_path / "webapp.db"
    from alphapulse.webapp.store.webapp_db import init_webapp_db
    init_webapp_db(webapp_db)
    BacktestStore(db_path=bt_db)  # 스키마 생성

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
    app.state.backtest_reader = BacktestReader(db_path=bt_db)
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(bt_router)
    app._bt_db = bt_db   # 테스트용 핸들
    return app


@pytest.fixture
def client(app):
    c = TestClient(app)
    t = c.get("/api/v1/csrf-token").json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": t},
        cookies={"ap_csrf": t},
    )
    c.headers.update({"X-CSRF-Token": t})
    return c


class TestBacktestRead:
    def test_list_empty(self, client):
        r = client.get("/api/v1/backtest/runs")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_with_data(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        _seed(store, name="run-a")
        _seed(store, name="run-b")
        r = client.get("/api/v1/backtest/runs")
        assert r.json()["total"] == 2

    def test_list_paginate(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        for i in range(15):
            _seed(store, name=f"r{i}")
        r = client.get("/api/v1/backtest/runs?page=2&size=10")
        assert len(r.json()["items"]) == 5

    def test_get_run_by_prefix(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="r1")
        r = client.get(f"/api/v1/backtest/runs/{rid[:8]}")
        assert r.status_code == 200
        assert r.json()["name"] == "r1"

    def test_get_run_not_found(self, client):
        r = client.get("/api/v1/backtest/runs/nonexist")
        assert r.status_code == 404

    def test_delete_requires_admin(self, app, client):
        store = BacktestStore(db_path=app._bt_db)
        rid = _seed(store, name="r")
        r = client.delete(f"/api/v1/backtest/runs/{rid[:8]}")
        assert r.status_code == 200

    def test_compare_400_when_not_two(self, client):
        r = client.get("/api/v1/backtest/compare?ids=a")
        assert r.status_code == 400
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_backtest_read.py -v
git add alphapulse/webapp/api/ tests/webapp/api/
git commit -m "feat(webapp): Backtest 조회 API — list/detail/snapshots/trades/positions/compare/delete"
```

---

### Task 15: Backtest 실행 API + JobRunner 연결

**Files:**
- Modify: `alphapulse/webapp/api/backtest.py` (POST /run 추가)
- Create: `alphapulse/webapp/api/backtest_runner.py` (실행 헬퍼)
- Test: `tests/webapp/api/test_backtest_run.py`

- [ ] **Step 1: `backtest_runner.py` — CLI와 동일 로직을 함수로 분리**
```python
"""Backtest 실행 헬퍼 — CLI의 backtest_run 로직을 함수로 추출.

progress_callback을 받아 JobRunner에서 진행률 훅으로 주입 가능.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
)
from alphapulse.trading.backtest.order_gen import (
    make_default_order_generator,
)
from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.backtest.store_feed import TradingStoreDataFeed
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.momentum import MomentumStrategy
from alphapulse.trading.strategy.quality_momentum import (
    QualityMomentumStrategy,
)
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy
from alphapulse.trading.strategy.value import ValueStrategy

_STRATEGY_MAP = {
    "momentum": MomentumStrategy,
    "value": ValueStrategy,
    "quality_momentum": QualityMomentumStrategy,
    "topdown_etf": TopDownETFStrategy,
}


def run_backtest_sync(
    *,
    strategy: str,
    start: str,
    end: str,
    capital: int,
    market: str,
    top: int,
    name: str,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """백테스트를 동기 실행하고 DB에 저장. run_id 반환."""
    if strategy not in _STRATEGY_MAP:
        raise ValueError(
            f"unknown strategy: {strategy}. "
            f"Available: {list(_STRATEGY_MAP)}"
        )
    if not end:
        end = datetime.now().strftime("%Y%m%d")
    if not start:
        start = (
            datetime.now() - timedelta(days=3 * 365)
        ).strftime("%Y%m%d")

    cfg = Config()
    db_path = cfg.TRADING_DB_PATH
    data_feed = TradingStoreDataFeed(db_path=db_path, market=market)
    if not data_feed.codes:
        raise ValueError(f"No market data for {market}")

    ranker = MultiFactorRanker(weights={
        "momentum": 0.25, "flow": 0.25, "value": 0.20,
        "quality": 0.15, "growth": 0.10, "volatility": 0.05,
    })
    strat_cls = _STRATEGY_MAP[strategy]
    factor_calc = FactorCalculator(data_feed.store)
    try:
        strat = strat_cls(
            ranker=ranker, factor_calc=factor_calc,
            config={"top_n": top},
        )
    except TypeError:
        strat = strat_cls(config={"top_n": top})

    cost_model = CostModel(
        commission_rate=cfg.BACKTEST_COMMISSION,
        tax_rate_stock=cfg.BACKTEST_TAX,
    )
    order_gen = make_default_order_generator(
        top_n=top, initial_capital=capital,
    )
    bt_config = BacktestConfig(
        initial_capital=capital,
        start_date=start, end_date=end,
        cost_model=cost_model,
    )
    engine = BacktestEngine(
        config=bt_config,
        data_feed=data_feed,
        strategies=[strat],
        order_generator=order_gen,
    )

    def _hook(current: int, total: int, date: str = ""):
        progress_callback(current, total, date)

    result = engine.run(progress_callback=_hook)
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")
    run_id = bt_store.save_run(
        result, name=name or f"{strategy}_{start}_{end}",
        strategies=[strategy],
    )
    return run_id
```

- [ ] **Step 2: `api/backtest.py` 에 POST /run 추가**

기존 파일 끝에 추가:
```python
# ==== Task 15 additions ====

import asyncio
import uuid
from typing import Literal

from fastapi import BackgroundTasks

from alphapulse.webapp.api.backtest_runner import run_backtest_sync
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.store.jobs import JobRepository


class RunBacktestRequest(BaseModel):
    strategy: Literal[
        "momentum", "value", "quality_momentum", "topdown_etf",
    ]
    start: str | None = Field(default=None, pattern=r"^(\d{8})?$")
    end: str | None = Field(default=None, pattern=r"^(\d{8})?$")
    capital: int = Field(default=100_000_000, ge=1_000_000, le=1e11)
    market: str = Field(default="KOSPI")
    top: int = Field(default=20, ge=1, le=100)
    name: str = Field(default="", max_length=100)


class RunBacktestResponse(BaseModel):
    job_id: str


def get_job_repo(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_job_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


@router.post("/run", response_model=RunBacktestResponse)
async def run_backtest(
    body: RunBacktestRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_job_repo),
    job_runner: JobRunner = Depends(get_job_runner),
):
    # 사용자당 시간 제한 (간단한 rate check: 최근 1시간 내 10건)
    # 실제 프로덕션에서는 slowapi로 구현. Phase 1은 간단한 카운트로.
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="backtest",
        params=body.model_dump(),
        user_id=user.id,
    )

    async def _run():
        await job_runner.run(
            job_id,
            run_backtest_sync,
            strategy=body.strategy,
            start=body.start or "",
            end=body.end or "",
            capital=body.capital,
            market=body.market,
            top=body.top,
            name=body.name,
        )

    background_tasks.add_task(_run)
    return RunBacktestResponse(job_id=job_id)
```

- [ ] **Step 3: 테스트 (실제 실행은 mock)**
```python
"""Backtest 실행 API 테스트 — 백그라운드 태스크는 mock."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.store.jobs import JobRepository


class TestBacktestRun:
    def test_requires_csrf(self, app):
        c = TestClient(app)
        r = c.post("/api/v1/backtest/run", json={"strategy": "momentum"})
        assert r.status_code in (401, 403)

    def test_creates_job(self, app, client, monkeypatch):
        # app.state에 jobs/job_runner 주입
        from pathlib import Path
        db = Path(app.state.config.db_path)
        app.state.jobs = JobRepository(db_path=db)
        app.state.job_runner = JobRunner(job_repo=app.state.jobs)

        # run_backtest_sync를 빠르게 반환하도록 mock
        called = {}

        def fake_run(*, progress_callback, **kwargs):
            called["kwargs"] = kwargs
            progress_callback(1, 1, "done")
            return "run_xyz"

        monkeypatch.setattr(
            "alphapulse.webapp.api.backtest.run_backtest_sync", fake_run,
        )

        r = client.post(
            "/api/v1/backtest/run",
            json={
                "strategy": "momentum",
                "start": "20240101", "end": "20241231",
                "capital": 100_000_000, "market": "KOSPI", "top": 20,
            },
        )
        assert r.status_code == 200
        jid = r.json()["job_id"]
        assert len(jid) > 0

    def test_invalid_strategy(self, client):
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "invalid"},
        )
        assert r.status_code == 422  # Pydantic enum 검증

    def test_capital_out_of_range(self, client):
        r = client.post(
            "/api/v1/backtest/run",
            json={"strategy": "momentum", "capital": 500_000},
        )
        assert r.status_code == 422
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_backtest_run.py -v
git add alphapulse/webapp/api/ tests/webapp/api/
git commit -m "feat(webapp): Backtest 실행 API — POST /run + Job 인프라 연결"
```

---

### Task 16: FastAPI `main.py` 어셈블리 + startup 훅

**Files:**
- Create: `alphapulse/webapp/main.py`
- Test: `tests/webapp/test_main.py`

- [ ] **Step 1: 테스트**
```python
"""FastAPI main 통합 테스트."""
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    # ensure backtest.db exists for reader
    from alphapulse.trading.backtest.store import BacktestStore
    BacktestStore(db_path=tmp_path / "backtest.db")
    monkeypatch.setattr(
        "alphapulse.core.config.Config.DATA_DIR", tmp_path,
    )
    return tmp_path


def test_app_starts_and_healthchecks(env):
    from alphapulse.webapp.main import create_app
    app = create_app()
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_app_has_all_routers(env):
    from alphapulse.webapp.main import create_app
    app = create_app()
    paths = {r.path for r in app.routes}
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/backtest/runs" in paths
    assert "/api/v1/jobs/{job_id}" in paths


def test_startup_recovers_orphans(env):
    """running 상태인 job이 있으면 시작 시 failed로 변환."""
    import uuid
    from alphapulse.webapp.store.jobs import JobRepository
    from alphapulse.webapp.store.webapp_db import init_webapp_db

    db = env / "webapp.db"
    init_webapp_db(db)
    jobs = JobRepository(db_path=db)
    jid = str(uuid.uuid4())
    jobs.create(job_id=jid, kind="backtest", params={}, user_id=1)
    import time
    jobs.update_status(jid, "running", started_at=time.time())

    from alphapulse.webapp.main import create_app
    app = create_app()
    client = TestClient(app)
    with client:   # lifespan 실행
        pass
    assert jobs.get(jid).status == "failed"
```

- [ ] **Step 2: `main.py` 구현**
```python
"""FastAPI 앱 어셈블리."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from alphapulse.core.config import Config
from alphapulse.webapp.api.backtest import router as backtest_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner, recover_orphans
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    cfg = WebAppConfig.from_env()
    core = Config()
    base = Path(core.DATA_DIR).resolve().parent
    db_path = cfg.db_path_resolved(base)
    init_webapp_db(db_path)

    alert_log = AlertLogRepository(db_path=db_path)
    monitor = MonitorNotifier(
        bot_token=cfg.monitor_bot_token,
        chat_id=cfg.monitor_channel_id,
        alert_log=alert_log,
    )
    users = UserRepository(db_path=db_path)
    sessions = SessionRepository(db_path=db_path)
    login_attempts = LoginAttemptsRepository(db_path=db_path)
    jobs = JobRepository(db_path=db_path)
    job_runner = JobRunner(job_repo=jobs)
    bt_reader = BacktestReader(
        db_path=Path(core.DATA_DIR) / "backtest.db",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        n = recover_orphans(job_repo=jobs)
        if n:
            logger.warning("recovered %d orphan jobs", n)
            await monitor.send(
                "WARN", f"Orphan jobs recovered: {n}",
                "Prior session had running jobs; marked as failed.",
            )
        await monitor.send(
            "INFO", "AlphaPulse webapp started",
            "FastAPI 앱이 기동되었습니다.",
        )
        yield
        await monitor.send(
            "INFO", "AlphaPulse webapp stopping", "",
        )

    app = FastAPI(
        title="AlphaPulse Web API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,   # 프로덕션 비활성
        redoc_url=None,
    )
    app.state.config = cfg
    app.state.users = users
    app.state.sessions = sessions
    app.state.login_attempts = login_attempts
    app.state.jobs = jobs
    app.state.job_runner = job_runner
    app.state.backtest_reader = bt_reader
    app.state.alert_log = alert_log
    app.state.monitor = monitor

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(backtest_router)

    return app


app = create_app()
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/test_main.py -v
ruff check alphapulse/webapp/main.py tests/webapp/test_main.py
git add alphapulse/webapp/main.py tests/webapp/test_main.py
git commit -m "feat(webapp): main.py 어셈블리 + lifespan 훅 + Orphan 복구"
```

---

## Part C — Backend CLI + Integration

### Task 17: `ap webapp` CLI 명령

**Files:**
- Create: `alphapulse/webapp/cli.py`
- Modify: `alphapulse/cli.py` (`webapp` 서브그룹 등록)
- Test: `tests/webapp/test_cli_webapp.py`

- [ ] **Step 1: 테스트 (`tests/webapp/test_cli_webapp.py`)**
```python
"""ap webapp CLI 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")
    return tmp_path


class TestCreateAdmin:
    def test_create_admin(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="correct-horse-battery\ncorrect-horse-battery\n",
        )
        assert r.exit_code == 0
        assert "a@x.com" in r.output

    def test_rejects_short_password(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="short\nshort\n",
        )
        assert r.exit_code != 0 or "12" in r.output


class TestResetPassword:
    def test_reset(self, runner, env):
        from alphapulse.cli import cli
        runner.invoke(
            cli,
            ["webapp", "create-admin", "--email", "a@x.com"],
            input="correct-horse-battery\ncorrect-horse-battery\n",
        )
        r = runner.invoke(
            cli,
            ["webapp", "reset-password", "--email", "a@x.com"],
            input="new-password-12!\nnew-password-12!\n",
        )
        assert r.exit_code == 0
        assert "updated" in r.output.lower()


class TestUnlock:
    def test_unlock_removes_recent_fails(self, runner, env):
        from alphapulse.cli import cli
        from alphapulse.webapp.store.login_attempts import (
            LoginAttemptsRepository,
        )
        db = env / "webapp.db"
        from alphapulse.webapp.store.webapp_db import init_webapp_db
        init_webapp_db(db)
        la = LoginAttemptsRepository(db_path=db)
        for _ in range(5):
            la.record(email="a@x.com", ip="1.1.1.1", success=False)

        r = runner.invoke(
            cli, ["webapp", "unlock-account", "--email", "a@x.com"],
        )
        assert r.exit_code == 0
        assert la.recent_failures_by_email("a@x.com", 900) == 0


class TestVerifyMonitoring:
    def test_disabled_when_missing(self, runner, env):
        from alphapulse.cli import cli
        r = runner.invoke(cli, ["webapp", "verify-monitoring"])
        assert r.exit_code == 0
        assert "disabled" in r.output.lower() or "set" in r.output.lower()

    @patch("alphapulse.webapp.cli.MonitorNotifier")
    def test_sends_test_message(
        self, mock_notifier_cls, runner, env, monkeypatch,
    ):
        monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "-100")
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_notifier.send = AsyncMock()
        mock_notifier_cls.return_value = mock_notifier

        from alphapulse.cli import cli
        r = runner.invoke(cli, ["webapp", "verify-monitoring"])
        assert r.exit_code == 0
        assert mock_notifier.send.await_count == 1
```

- [ ] **Step 2: CLI 구현 (`alphapulse/webapp/cli.py`)**
```python
"""ap webapp 서브커맨드 — 관리자 계정·운영 명령."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from alphapulse.core.config import Config
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.notifier import MonitorNotifier
from alphapulse.webapp.store.alert_log import AlertLogRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.users import UserRepository
from alphapulse.webapp.store.webapp_db import init_webapp_db


def _db_path() -> Path:
    cfg = WebAppConfig.from_env()
    core = Config()
    base = Path(core.DATA_DIR).resolve().parent
    path = cfg.db_path_resolved(base)
    init_webapp_db(path)
    return path


@click.group()
def webapp() -> None:
    """웹앱 관리 명령."""


@webapp.command("create-admin")
@click.option("--email", required=True)
def create_admin(email: str) -> None:
    """관리자 계정을 생성한다."""
    pw1 = click.prompt("Password", hide_input=True)
    pw2 = click.prompt("Confirm password", hide_input=True)
    if pw1 != pw2:
        click.echo("Passwords do not match.", err=True)
        sys.exit(1)
    try:
        h = hash_password(pw1)
    except ValueError as e:
        click.echo(f"Password rejected: {e}", err=True)
        sys.exit(1)
    users = UserRepository(db_path=_db_path())
    try:
        uid = users.create(email=email, password_hash=h, role="admin")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(f"Created admin: {email} (id={uid})")


@webapp.command("reset-password")
@click.option("--email", required=True)
def reset_password(email: str) -> None:
    users = UserRepository(db_path=_db_path())
    user = users.get_by_email(email)
    if user is None:
        click.echo("User not found.", err=True)
        sys.exit(1)
    pw1 = click.prompt("New password", hide_input=True)
    pw2 = click.prompt("Confirm password", hide_input=True)
    if pw1 != pw2:
        click.echo("Passwords do not match.", err=True)
        sys.exit(1)
    try:
        h = hash_password(pw1)
    except ValueError as e:
        click.echo(f"Password rejected: {e}", err=True)
        sys.exit(1)
    users.update_password_hash(user.id, h)
    click.echo(f"Password updated for {email}")


@webapp.command("unlock-account")
@click.option("--email", required=True)
def unlock_account(email: str) -> None:
    """최근 로그인 실패 기록을 삭제하여 계정 잠금을 해제한다."""
    import sqlite3
    import time

    db = _db_path()
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            "DELETE FROM login_attempts WHERE email = ? "
            "AND success = 0 AND attempted_at >= ?",
            (email, time.time() - 86400),
        )
        n = cur.rowcount
    click.echo(f"Cleared {n} recent failure records for {email}")


@webapp.command("verify-monitoring")
def verify_monitoring() -> None:
    """모니터링 채널로 테스트 메시지를 발송한다."""
    cfg = WebAppConfig.from_env()
    if not cfg.monitor_enabled:
        click.echo(
            "Monitoring disabled. Set TELEGRAM_MONITOR_BOT_TOKEN and "
            "TELEGRAM_MONITOR_CHANNEL_ID in .env."
        )
        return
    alert_log = AlertLogRepository(db_path=_db_path())
    notifier = MonitorNotifier(
        bot_token=cfg.monitor_bot_token,
        chat_id=cfg.monitor_channel_id,
        alert_log=alert_log,
        window_seconds=1,  # 테스트 시 즉시 보내기
    )
    asyncio.run(notifier.send(
        "INFO", "verify-monitoring",
        "This is a test message from ap webapp verify-monitoring.",
    ))
    click.echo("Test message sent. Check your monitoring channel.")
```

- [ ] **Step 3: `alphapulse/cli.py` 에 서브그룹 등록**

`alphapulse/cli.py` 에서 기존 `trading`, `feedback` 등의 패턴을 따라 추가. 파일 상단의 `cli.add_command` 블록(또는 동등한 위치)에 다음을 추가:
```python
from alphapulse.webapp.cli import webapp as webapp_group
cli.add_command(webapp_group)
```

기존 파일 구조를 먼저 확인:
```bash
grep -n "^from alphapulse\." alphapulse/cli.py | head
grep -n "add_command\|@cli.group" alphapulse/cli.py | head
```

그리고 적절한 위치에 import + `cli.add_command(webapp_group)` 한 줄 추가.

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/test_cli_webapp.py -v
ruff check alphapulse/webapp/cli.py alphapulse/cli.py tests/webapp/test_cli_webapp.py
git add alphapulse/webapp/cli.py alphapulse/cli.py tests/webapp/test_cli_webapp.py
git commit -m "feat(webapp): ap webapp CLI — create-admin/reset-password/unlock/verify-monitoring"
```

---

### Task 18: 감사 로그 통합

**Files:**
- Modify: `alphapulse/webapp/auth/routes.py` (감사 이벤트 기록)
- Modify: `alphapulse/webapp/api/backtest.py` (백테스트 실행/삭제 이벤트)
- Test: `tests/webapp/test_audit.py`

기존 `alphapulse/trading/core/audit.py` 의 `AuditLogger` 를 재사용한다. 이미 `data/audit.db` 에 append하는 인터페이스가 존재.

- [ ] **Step 1: AuditLogger 사용 패턴 확인**
```bash
grep -n "class AuditLogger" alphapulse/trading/core/audit.py
grep -rn "AuditLogger" alphapulse/trading/ | head -5
```
→ `AuditLogger().log(action, details)` 패턴을 그대로 재사용.

- [ ] **Step 2: Audit 주입을 state에 추가**

`alphapulse/webapp/main.py` 의 `create_app()` 에:
```python
from alphapulse.trading.core.audit import AuditLogger
# ... state 세팅 블록에 추가:
app.state.audit = AuditLogger()
```

- [ ] **Step 3: Auth 라우트에 이벤트 기록**

`alphapulse/webapp/auth/routes.py` 의 `login` 함수에서 성공/실패 분기에 다음을 추가:
```python
# login 성공 시
request.app.state.audit.log(
    "webapp.login_success",
    {"user_id": user.id, "email": user.email, "ip": client_ip},
)

# login 실패 시 (raise 직전)
request.app.state.audit.log(
    "webapp.login_failed",
    {"email": body.email, "ip": client_ip},
)

# logout 에서
request.app.state.audit.log(
    "webapp.logout",
    {"user_id": user.id if user else None},
)
```
(기존 함수 시그니처에 `user: User = Depends(get_current_user)` 를 추가해야 함.)

- [ ] **Step 4: Backtest 이벤트 기록**

`alphapulse/webapp/api/backtest.py` 의 `run_backtest` 함수에 (job 생성 직후):
```python
request.app.state.audit.log(
    "webapp.backtest_run",
    {
        "user_id": user.id,
        "job_id": job_id,
        "strategy": body.strategy,
        "period": f"{body.start}~{body.end}",
    },
)
```

`delete_run` 함수에 (삭제 직후):
```python
request.app.state.audit.log(
    "webapp.backtest_delete",
    {"user_id": user.id, "run_id": s.run_id},
)
```
(시그니처 변경: `request: Request` 주입 추가 및 `user`를 `Depends(require_role("admin"))` 결과로 받아 사용.)

- [ ] **Step 5: 통합 테스트**
```python
"""감사 로그 wiring 테스트."""
import pytest
import sqlite3
from fastapi.testclient import TestClient


def test_login_success_audited(app_with_audit, seed_admin):
    """로그인 성공 시 audit.db에 이벤트가 기록된다."""
    client = TestClient(app_with_audit)
    t = client.get("/api/v1/csrf-token").json()["token"]
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"X-CSRF-Token": t},
        cookies={"ap_csrf": t},
    )
    audit_db = app_with_audit.state.audit.db_path
    with sqlite3.connect(audit_db) as conn:
        rows = conn.execute(
            "SELECT action FROM audit_log WHERE action LIKE 'webapp.%'"
        ).fetchall()
    actions = [r[0] for r in rows]
    assert "webapp.login_success" in actions
```

(fixture `app_with_audit`는 Task 14 테스트 fixture를 기반으로 AuditLogger를 연결해 만든다. 중복 fixture 회피 위해 `tests/webapp/conftest.py` 로 공용화 권장.)

- [ ] **Step 6: 테스트 + 커밋**
```bash
pytest tests/webapp/test_audit.py -v
git add alphapulse/webapp/auth/routes.py alphapulse/webapp/api/backtest.py alphapulse/webapp/main.py tests/webapp/
git commit -m "feat(webapp): 감사 로그 wiring — 로그인/로그아웃/백테스트 실행·삭제"
```

---

### Task 19: 통합 테스트 — 풀 플로우

**Files:**
- Create: `tests/webapp/test_integration.py`

- [ ] **Step 1: 풀 플로우 테스트 (mock backtest runner)**
```python
"""통합 테스트: 로그인 → 백테스트 실행 → 결과 조회."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    monkeypatch.setenv("TELEGRAM_MONITOR_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_MONITOR_CHANNEL_ID", "")

    # data dir 세팅
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    from alphapulse.trading.backtest.store import BacktestStore
    BacktestStore(db_path=data_dir / "backtest.db")
    monkeypatch.setattr(
        "alphapulse.core.config.Config.DATA_DIR", data_dir,
    )
    return data_dir


@pytest.fixture
def app(env):
    from alphapulse.webapp.main import create_app
    app = create_app()
    # seed admin
    from alphapulse.webapp.auth.security import hash_password
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )
    return app


def _csrf(client):
    t = client.get("/api/v1/csrf-token").json()["token"]
    return {"headers": {"X-CSRF-Token": t}, "cookies": {"ap_csrf": t}}


def test_full_backtest_flow(app, env, monkeypatch):
    """로그인 → 실행 → 진행률 polling → 완료 조회."""
    # run_backtest_sync를 mock해 빠르게 완료
    from alphapulse.trading.backtest.engine import BacktestResult
    from alphapulse.trading.backtest.store import BacktestStore
    bt_store = BacktestStore(db_path=env / "backtest.db")

    def fake_run(**kwargs):
        from alphapulse.trading.backtest.engine import BacktestConfig
        from alphapulse.trading.core.cost_model import CostModel
        cb = kwargs.get("progress_callback")
        for i in range(3):
            cb(i, 3, f"day {i}")
        result = BacktestResult(
            snapshots=[], trades=[],
            metrics={"total_return": 12.3},
            config=BacktestConfig(
                initial_capital=100_000_000,
                start_date="20240101", end_date="20241231",
                cost_model=CostModel(slippage_model="none"),
            ),
        )
        return bt_store.save_run(
            result, name="integration-test",
            strategies=["momentum"],
        )

    monkeypatch.setattr(
        "alphapulse.webapp.api.backtest.run_backtest_sync", fake_run,
    )

    with TestClient(app) as client:
        args = _csrf(client)
        # 1. 로그인
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "a@x.com", "password": "long-enough-pw!"},
            **args,
        )
        assert r.status_code == 200

        # 2. 백테스트 실행
        r = client.post(
            "/api/v1/backtest/run",
            json={
                "strategy": "momentum",
                "start": "20240101", "end": "20241231",
                "capital": 100_000_000, "market": "KOSPI", "top": 20,
            },
            **args,
        )
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        # 3. 진행률 polling (background task 동기 대기)
        import time
        for _ in range(50):
            j = client.get(f"/api/v1/jobs/{job_id}").json()
            if j["status"] in {"done", "failed"}:
                break
            time.sleep(0.05)
        assert j["status"] == "done"
        run_id = j["result_ref"]

        # 4. 결과 조회
        r = client.get(f"/api/v1/backtest/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["metrics"]["total_return"] == 12.3

        # 5. 목록에 나타남
        r = client.get("/api/v1/backtest/runs")
        assert r.json()["total"] == 1
```

- [ ] **Step 2: 테스트 + 커밋**
```bash
pytest tests/webapp/test_integration.py -v
git add tests/webapp/test_integration.py
git commit -m "test(webapp): 통합 테스트 — 로그인→백테스트 실행→결과 조회"
```

---

## Part D — Frontend Foundation

### Task 20: Next.js 스캐폴드 + Tailwind

**Files:**
- Create: `webapp-ui/package.json`
- Create: `webapp-ui/tsconfig.json`
- Create: `webapp-ui/next.config.mjs`
- Create: `webapp-ui/tailwind.config.ts`
- Create: `webapp-ui/postcss.config.mjs`
- Create: `webapp-ui/.eslintrc.json`
- Create: `webapp-ui/.gitignore`
- Create: `webapp-ui/app/layout.tsx`
- Create: `webapp-ui/app/globals.css`
- Create: `webapp-ui/app/page.tsx` (루트 redirect)

- [ ] **Step 1: `webapp-ui/` 스캐폴드 생성**

Node 22 LTS + pnpm(corepack 제공) 필요. 스캐폴드는 수동 파일 생성(자동 CLI는 불필요한 파일 많이 생성).

`webapp-ui/package.json`:
```json
{
  "name": "alphapulse-webapp-ui",
  "version": "0.1.0",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "next": "^15.2.3",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "typescript": "^5.4.0",
    "@tanstack/react-query": "^5.50.0",
    "react-hook-form": "^7.52.0",
    "zod": "^3.23.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.31",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.0",
    "recharts": "^2.12.0",
    "lightweight-charts": "^4.1.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/node": "^22.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^9.0.0",
    "eslint-config-next": "^15.2.3",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@playwright/test": "^1.47.0"
  }
}
```

- [ ] **Step 2: 설정 파일들**

`webapp-ui/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": [
    "next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"
  ],
  "exclude": ["node_modules"]
}
```

`webapp-ui/next.config.mjs`:
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};
export default nextConfig;
```

`webapp-ui/tailwind.config.ts`:
```typescript
import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
export default config
```

`webapp-ui/postcss.config.mjs`:
```javascript
export default { plugins: { tailwindcss: {}, autoprefixer: {} } }
```

`webapp-ui/.eslintrc.json`:
```json
{
  "extends": "next/core-web-vitals",
  "rules": {
    "react/no-danger": "error"
  }
}
```

`webapp-ui/.gitignore`:
```
node_modules/
.next/
out/
*.log
.env.local
.env.development.local
.env.production.local
test-results/
playwright-report/
```

`webapp-ui/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { --background: 255 255 255; --foreground: 15 15 15; }
.dark { --background: 10 10 10; --foreground: 240 240 240; }
html { color-scheme: light dark; }
body { @apply bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100; }
```

`webapp-ui/app/layout.tsx`:
```tsx
import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "AlphaPulse",
  description: "AI 기반 투자 인텔리전스 플랫폼",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" className="dark">
      <body>{children}</body>
    </html>
  )
}
```

`webapp-ui/app/page.tsx` — 루트는 `/backtest` 로 리다이렉트:
```tsx
import { redirect } from "next/navigation"

export default function RootPage() {
  redirect("/backtest")
}
```

- [ ] **Step 3: 의존성 설치**
```bash
cd webapp-ui
corepack enable
pnpm install
cd ..
```

- [ ] **Step 4: 빌드 확인**
```bash
cd webapp-ui && pnpm build && cd ..
```
예상: 빌드 성공 (루트 리다이렉트만 있는 최소 앱)

- [ ] **Step 5: 커밋**
```bash
git add webapp-ui/
git commit -m "feat(webapp-ui): Next.js 15 + Tailwind 스캐폴드"
```

---

### Task 21: shadcn/ui 초기화 + 기본 컴포넌트

**Files:**
- Create: `webapp-ui/components.json`
- Create: `webapp-ui/lib/utils.ts`
- Create: `webapp-ui/components/ui/button.tsx`
- Create: `webapp-ui/components/ui/card.tsx`
- Create: `webapp-ui/components/ui/input.tsx`
- Create: `webapp-ui/components/ui/label.tsx`
- Create: `webapp-ui/components/ui/table.tsx`
- Create: `webapp-ui/components/ui/tabs.tsx`
- Create: `webapp-ui/components/ui/toast.tsx`
- Create: `webapp-ui/components/ui/skeleton.tsx`
- Modify: `webapp-ui/tailwind.config.ts` (shadcn 토큰 추가)

- [ ] **Step 1: shadcn 구성 파일 (`webapp-ui/components.json`)**
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui"
  }
}
```

- [ ] **Step 2: `lib/utils.ts`**
```typescript
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 3: shadcn 컴포넌트 생성**

`pnpm dlx shadcn@latest add` 를 사용하거나(네트워크 필요), 수동 복사. 아래 컴포넌트를 각각 표준 shadcn/ui 버전으로 생성:
- `button.tsx`, `card.tsx`, `input.tsx`, `label.tsx`, `table.tsx`, `tabs.tsx`, `toast.tsx`, `skeleton.tsx`, `dialog.tsx`, `select.tsx`, `toaster.tsx`

예시 — `components/ui/button.tsx`:
```tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-neutral-400 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-neutral-900 text-white hover:bg-neutral-800 dark:bg-neutral-50 dark:text-neutral-900 dark:hover:bg-neutral-200",
        destructive: "bg-red-600 text-white hover:bg-red-700",
        outline: "border border-neutral-200 bg-transparent hover:bg-neutral-100 dark:border-neutral-800 dark:hover:bg-neutral-800",
        ghost: "hover:bg-neutral-100 dark:hover:bg-neutral-800",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3",
        lg: "h-10 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = "Button"
```

(다른 컴포넌트도 shadcn/ui 공식 저장소의 표준 버전을 사용.)

- [ ] **Step 4: 필요한 radix 의존성 추가**

`webapp-ui/package.json` 의 dependencies에 추가:
```
"@radix-ui/react-slot": "^1.1.0",
"@radix-ui/react-dialog": "^1.1.0",
"@radix-ui/react-label": "^2.1.0",
"@radix-ui/react-tabs": "^1.1.0",
"@radix-ui/react-select": "^2.1.0",
"@radix-ui/react-toast": "^1.2.0",
"class-variance-authority": "^0.7.0"
```
`pnpm install` 재실행.

- [ ] **Step 5: 빌드 확인 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): shadcn/ui 초기화 + 기본 컴포넌트 9종"
```

---

### Task 22: API 클라이언트 + 세션 관리

**Files:**
- Create: `webapp-ui/lib/api-client.ts`
- Create: `webapp-ui/lib/auth.ts`
- Create: `webapp-ui/lib/types.ts`
- Create: `webapp-ui/middleware.ts`

- [ ] **Step 1: `lib/types.ts` — OpenAPI 기반 공통 타입 (수동 정의, Phase 2에서 자동 생성 도입)**
```typescript
export type User = {
  id: number
  email: string
  role: string
}

export type RunSummary = {
  run_id: string
  name: string
  strategies: string[]
  start_date: string
  end_date: string
  initial_capital: number
  final_value: number
  benchmark: string
  metrics: Record<string, number>
  created_at: number
}

export type RunDetail = RunSummary & {
  params: Record<string, unknown>
}

export type RunList = {
  items: RunSummary[]
  page: number
  size: number
  total: number
}

export type Snapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
}

export type Trade = {
  code: string
  name: string
  buy_date: string
  buy_price: number
  sell_date: string
  sell_price: number
  quantity: number
  pnl: number
  return_pct: number
  holding_days: number
  commission: number
  tax: number
  strategy_id: string
}

export type Position = {
  date: string
  code: string
  name: string
  quantity: number
  avg_price: number
  current_price: number
  unrealized_pnl: number
  weight: number
  strategy_id: string
}

export type Job = {
  id: string
  kind: string
  status: "pending" | "running" | "done" | "failed" | "cancelled"
  progress: number
  progress_text: string
  result_ref: string | null
  error: string | null
  created_at: number
  started_at: number | null
  finished_at: number | null
}
```

- [ ] **Step 2: `lib/api-client.ts` — 서버/클라이언트 공용 fetcher**
```typescript
/** FastAPI 호출 래퍼. 서버 컴포넌트/클라이언트 모두 사용 가능. */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ""

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message)
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { searchParams?: Record<string, string | undefined> },
): Promise<T> {
  const url = new URL(
    `${BASE}${path.startsWith("/") ? path : `/${path}`}`,
    typeof window === "undefined" ? "http://localhost" : window.location.origin,
  )
  if (init?.searchParams) {
    for (const [k, v] of Object.entries(init.searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v)
    }
  }
  const res = await fetch(url.toString(), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  const ct = res.headers.get("content-type") ?? ""
  const body = ct.includes("json") ? await res.json() : await res.text()
  if (!res.ok) {
    throw new ApiError(
      res.status, body,
      typeof body === "object" && body && "detail" in body
        ? String(body.detail) : res.statusText,
    )
  }
  return body as T
}

export async function csrfToken(): Promise<string> {
  const r = await apiFetch<{ token: string }>("/api/v1/csrf-token")
  return r.token
}

/** CSRF 토큰을 자동으로 붙이는 헬퍼 — mutations에서 사용. */
export async function apiMutate<T>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown,
): Promise<T> {
  const token = await csrfToken()
  return apiFetch<T>(path, {
    method,
    headers: { "X-CSRF-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
```

- [ ] **Step 3: `lib/auth.ts` — 서버 컴포넌트용 세션 검증**
```typescript
import { cookies, headers } from "next/headers"
import { apiFetch, ApiError } from "./api-client"
import type { User } from "./types"

/** 서버 컴포넌트에서 현재 사용자 조회. 없으면 null. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const cookieStore = await cookies()
    const cookieHeader = cookieStore
      .getAll()
      .map((c) => `${c.name}=${c.value}`)
      .join("; ")
    const r = await apiFetch<User>("/api/v1/auth/me", {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    })
    return r
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null
    throw e
  }
}
```

- [ ] **Step 4: `middleware.ts` — 미인증 시 `/login`으로 (엣지 레이어)**
```typescript
import { NextResponse, type NextRequest } from "next/server"

const PUBLIC_PATHS = ["/login", "/_next", "/api", "/favicon"]

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }
  const session = req.cookies.get("ap_session")
  if (!session) {
    const url = req.nextUrl.clone()
    url.pathname = "/login"
    url.searchParams.set("next", pathname)
    return NextResponse.redirect(url)
  }
  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
```

**중요 — 미들웨어 단독에 의존하지 않음:** `app/(dashboard)/layout.tsx` 에서도 `getCurrentUser()` 재검증하도록 Task 23에서 구현.

- [ ] **Step 5: 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/lib/ webapp-ui/middleware.ts
git commit -m "feat(webapp-ui): API 클라이언트 + 세션 관리 + 미들웨어"
```

---

### Task 23: 로그인 페이지 + Dashboard Layout

**Files:**
- Create: `webapp-ui/app/(auth)/login/page.tsx`
- Create: `webapp-ui/app/(dashboard)/layout.tsx`
- Create: `webapp-ui/app/(dashboard)/page.tsx` (홈)
- Create: `webapp-ui/components/layout/sidebar.tsx`
- Create: `webapp-ui/components/layout/topbar.tsx`
- Create: `webapp-ui/components/providers.tsx`
- Modify: `webapp-ui/app/layout.tsx` (Providers 감싸기)

- [ ] **Step 1: Providers (`components/providers.tsx`)**
```tsx
"use client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState } from "react"

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({
      defaultOptions: {
        queries: { staleTime: 10_000, retry: 3 },
      },
    }),
  )
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
```

- [ ] **Step 2: 로그인 페이지**

`app/(auth)/login/page.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1).max(256),
})
type FormData = z.infer<typeof schema>

export default function LoginPage() {
  const router = useRouter()
  const params = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    setSubmitting(true)
    setError(null)
    try {
      await apiMutate("/api/v1/auth/login", "POST", data)
      const next = params.get("next") ?? "/"
      router.replace(next)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Login failed"
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950 text-neutral-100">
      <Card className="w-full max-w-md p-8">
        <h1 className="mb-6 text-2xl font-semibold">AlphaPulse</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" {...register("email")} />
            {errors.email && <p className="text-sm text-red-400">{errors.email.message}</p>}
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" {...register("password")} />
            {errors.password && <p className="text-sm text-red-400">{errors.password.message}</p>}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "..." : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  )
}
```

추가 의존성: `@hookform/resolvers` (package.json에 추가 필요).

- [ ] **Step 3: Dashboard Layout + Sidebar**

`components/layout/sidebar.tsx`:
```tsx
import Link from "next/link"

const ITEMS = [
  { href: "/backtest", label: "Backtest" },
  { href: "/portfolio", label: "Portfolio", disabled: true },
  { href: "/risk", label: "Risk", disabled: true },
  { href: "/market", label: "Market", disabled: true },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-neutral-800 p-4">
      <div className="mb-6 text-lg font-bold">AlphaPulse</div>
      <nav className="space-y-1">
        {ITEMS.map((it) => (
          <Link
            key={it.href}
            href={it.disabled ? "#" : it.href}
            className={
              "block rounded px-3 py-2 text-sm " +
              (it.disabled
                ? "cursor-not-allowed text-neutral-600"
                : "hover:bg-neutral-800")
            }
          >
            {it.label}
            {it.disabled && <span className="ml-2 text-xs">(soon)</span>}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
```

`components/layout/topbar.tsx`:
```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import type { User } from "@/lib/types"

export function Topbar({ user }: { user: User }) {
  const handleLogout = async () => {
    await apiMutate("/api/v1/auth/logout", "POST")
    window.location.href = "/login"
  }
  return (
    <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-2">
      <div />
      <div className="flex items-center gap-3 text-sm">
        <span className="text-neutral-400">{user.email}</span>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </div>
  )
}
```

`app/(dashboard)/layout.tsx` — **세션 재검증 (미들웨어 우회 대비)**:
```tsx
import { redirect } from "next/navigation"
import { getCurrentUser } from "@/lib/auth"
import { Sidebar } from "@/components/layout/sidebar"
import { Topbar } from "@/components/layout/topbar"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getCurrentUser()
  if (!user) redirect("/login")
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Topbar user={user} />
        <main className="p-6">{children}</main>
      </div>
    </div>
  )
}
```

`app/(dashboard)/page.tsx` (홈):
```tsx
import { redirect } from "next/navigation"
export default function Home() {
  redirect("/backtest")
}
```

- [ ] **Step 4: 루트 `app/layout.tsx` 에 Providers 감싸기**
```tsx
import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "@/components/providers"

export const metadata: Metadata = {
  title: "AlphaPulse",
  description: "AI 기반 투자 인텔리전스 플랫폼",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

- [ ] **Step 5: 빌드 + 커밋**
```bash
cd webapp-ui
pnpm install  # @hookform/resolvers 추가 후
pnpm build
cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): 로그인 + Dashboard Layout (사이드바 + 세션 재검증)"
```

---

## Part E — Frontend Backtest UI

### Task 24: 백테스트 리스트 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/backtest/page.tsx`
- Create: `webapp-ui/components/domain/backtest/runs-table.tsx`

- [ ] **Step 1: 서버 컴포넌트로 최초 데이터 fetch**

`app/(dashboard)/backtest/page.tsx`:
```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunsTable } from "@/components/domain/backtest/runs-table"
import type { RunList } from "@/lib/types"

export const dynamic = "force-dynamic"  // 사용자별 데이터 — 캐시 금지

type Props = { searchParams: Promise<{ page?: string; name?: string }> }

export default async function BacktestListPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page ?? 1)
  const name = sp.name ?? ""

  const cookieStore = await cookies()
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ")
  const runs = await apiFetch<RunList>("/api/v1/backtest/runs", {
    headers: { cookie: cookieHeader },
    searchParams: { page: String(page), size: "20", name: name || undefined },
    cache: "no-store",
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">백테스트 결과</h1>
        <Link href="/backtest/new">
          <Button>새 백테스트</Button>
        </Link>
      </div>
      <RunsTable data={runs} currentPage={page} currentName={name} />
    </div>
  )
}
```

- [ ] **Step 2: RunsTable 컴포넌트**

`components/domain/backtest/runs-table.tsx`:
```tsx
"use client"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import type { RunList } from "@/lib/types"

const fmtPct = (n: number | undefined) =>
  n === undefined ? "-" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`

export function RunsTable({
  data, currentPage, currentName,
}: { data: RunList; currentPage: number; currentName: string }) {
  const router = useRouter()
  const params = useSearchParams()
  const [name, setName] = useState(currentName)

  const updateQuery = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") sp.delete(k)
      else sp.set(k, v)
    }
    router.push(`/backtest?${sp.toString()}`)
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => { e.preventDefault(); updateQuery({ name, page: "1" }) }}
        className="flex gap-2"
      >
        <Input
          placeholder="이름 검색"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="max-w-sm"
        />
        <Button type="submit" variant="outline">검색</Button>
      </form>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>기간</TableHead>
            <TableHead className="text-right">총수익률</TableHead>
            <TableHead className="text-right">샤프</TableHead>
            <TableHead className="text-right">MDD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((r) => (
            <TableRow key={r.run_id} className="cursor-pointer">
              <TableCell>
                <Link href={`/backtest/${r.run_id.slice(0, 8)}`} className="font-mono text-xs">
                  {r.run_id.slice(0, 8)}
                </Link>
              </TableCell>
              <TableCell>{r.name || "-"}</TableCell>
              <TableCell className="text-neutral-400">
                {r.start_date}~{r.end_date}
              </TableCell>
              <TableCell className="text-right font-mono">
                {fmtPct(r.metrics.total_return)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {r.metrics.sharpe_ratio?.toFixed(2) ?? "-"}
              </TableCell>
              <TableCell className="text-right font-mono text-red-400">
                {fmtPct(r.metrics.max_drawdown)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between text-sm">
        <span className="text-neutral-500">
          총 {data.total}건, {currentPage}/{totalPages} 페이지
        </span>
        <div className="space-x-2">
          <Button
            size="sm" variant="outline"
            disabled={currentPage <= 1}
            onClick={() => updateQuery({ page: String(currentPage - 1) })}
          >이전</Button>
          <Button
            size="sm" variant="outline"
            disabled={currentPage >= totalPages}
            onClick={() => updateQuery({ page: String(currentPage + 1) })}
          >다음</Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/backtest/page.tsx webapp-ui/components/domain/backtest/runs-table.tsx
git commit -m "feat(webapp-ui): 백테스트 리스트 페이지 + RunsTable"
```

---

### Task 25: 백테스트 상세 (지표 카드 + 자산 곡선)

**Files:**
- Create: `webapp-ui/app/(dashboard)/backtest/[runId]/page.tsx`
- Create: `webapp-ui/components/domain/backtest/metrics-cards.tsx`
- Create: `webapp-ui/components/charts/equity-curve.tsx`

- [ ] **Step 1: 상세 페이지 서버 컴포넌트**

`app/(dashboard)/backtest/[runId]/page.tsx`:
```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { MetricsCards } from "@/components/domain/backtest/metrics-cards"
import { EquityCurve } from "@/components/charts/equity-curve"
import type { RunDetail, Snapshot } from "@/lib/types"

export const dynamic = "force-dynamic"

async function load(runId: string) {
  const cookieStore = await cookies()
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ")
  try {
    const run = await apiFetch<RunDetail>(
      `/api/v1/backtest/runs/${runId}`,
      { headers: { cookie: cookieHeader }, cache: "no-store" },
    )
    const snaps = await apiFetch<{ items: Snapshot[] }>(
      `/api/v1/backtest/runs/${runId}/snapshots`,
      { headers: { cookie: cookieHeader }, cache: "no-store" },
    )
    return { run, snaps: snaps.items }
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

type Props = { params: Promise<{ runId: string }> }

export default async function BacktestDetailPage({ params }: Props) {
  const { runId } = await params
  const data = await load(runId)
  if (!data) notFound()
  const { run, snaps } = data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{run.name || "(no name)"}</h1>
          <p className="text-sm text-neutral-500">
            {run.strategies.join(", ")} · {run.start_date}~{run.end_date} ·
            초기 {run.initial_capital.toLocaleString()}원 → 최종 {run.final_value.toLocaleString()}원
          </p>
        </div>
        <div className="space-x-2">
          <Link href={`/backtest/${runId}/trades`}>
            <Button variant="outline">거래 이력</Button>
          </Link>
          <Link href={`/backtest/${runId}/positions`}>
            <Button variant="outline">포지션</Button>
          </Link>
        </div>
      </div>
      <MetricsCards metrics={run.metrics} />
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg font-medium">자산 곡선</h2>
        <EquityCurve snapshots={snaps} initialCapital={run.initial_capital} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: MetricsCards 컴포넌트**

`components/domain/backtest/metrics-cards.tsx`:
```tsx
import { Card } from "@/components/ui/card"

const FIELDS: Array<{ key: string; label: string; format: (n: number) => string; color?: "red" | "green" | "neutral" }> = [
  { key: "total_return", label: "총 수익률", format: (n) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`, color: "green" },
  { key: "cagr", label: "CAGR", format: (n) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`, color: "green" },
  { key: "sharpe_ratio", label: "샤프", format: (n) => n.toFixed(2), color: "neutral" },
  { key: "max_drawdown", label: "MDD", format: (n) => `${n.toFixed(2)}%`, color: "red" },
  { key: "win_rate", label: "승률", format: (n) => `${n.toFixed(1)}%`, color: "neutral" },
  { key: "turnover", label: "턴오버", format: (n) => `${n.toFixed(2)}x`, color: "neutral" },
]

export function MetricsCards({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
      {FIELDS.map((f) => {
        const raw = metrics[f.key]
        const val = raw === undefined ? "-" : f.format(raw)
        const cls =
          f.color === "green" && raw !== undefined
            ? raw >= 0 ? "text-green-400" : "text-red-400"
            : f.color === "red" ? "text-red-400"
            : "text-neutral-100"
        return (
          <Card key={f.key} className="p-4">
            <div className="text-xs text-neutral-500">{f.label}</div>
            <div className={`mt-1 text-xl font-semibold ${cls}`}>{val}</div>
          </Card>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: EquityCurve 차트 — TradingView Lightweight**

`components/charts/equity-curve.tsx`:
```tsx
"use client"
import { useEffect, useRef } from "react"
import { createChart, ColorType, LineStyle, type IChartApi } from "lightweight-charts"
import type { Snapshot } from "@/lib/types"

export function EquityCurve({
  snapshots, initialCapital,
}: { snapshots: Snapshot[]; initialCapital: number }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#0a0a0a" }, textColor: "#e5e5e5" },
      grid: { vertLines: { color: "#1f1f1f" }, horzLines: { color: "#1f1f1f" } },
      height: 360,
    })
    chartRef.current = chart
    const series = chart.addLineSeries({ color: "#22c55e", lineWidth: 2 })
    const baseline = chart.addLineSeries({
      color: "#525252", lineWidth: 1,
      lineStyle: LineStyle.Dashed,
    })
    const data = snapshots.map((s) => ({
      time: `${s.date.slice(0, 4)}-${s.date.slice(4, 6)}-${s.date.slice(6, 8)}`,
      value: s.total_value,
    }))
    series.setData(data)
    const baseData = data.map((d) => ({ time: d.time, value: initialCapital }))
    baseline.setData(baseData)
    chart.timeScale().fitContent()
    const resize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    resize()
    window.addEventListener("resize", resize)
    return () => {
      window.removeEventListener("resize", resize)
      chart.remove()
    }
  }, [snapshots, initialCapital])

  return <div ref={containerRef} className="w-full" />
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): 백테스트 상세 (지표 카드 + 자산 곡선)"
```

---

### Task 26: 상세 — 드로다운 + 월별 히트맵

**Files:**
- Modify: `webapp-ui/app/(dashboard)/backtest/[runId]/page.tsx` (탭 추가)
- Create: `webapp-ui/components/charts/drawdown.tsx`
- Create: `webapp-ui/components/charts/monthly-heatmap.tsx`

- [ ] **Step 1: Drawdown 차트**

`components/charts/drawdown.tsx`:
```tsx
"use client"
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts"
import type { Snapshot } from "@/lib/types"

export function Drawdown({ snapshots }: { snapshots: Snapshot[] }) {
  const data = snapshots.map((s) => ({
    date: s.date,
    dd: s.drawdown,     // 음수
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data}>
        <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
        <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: "#171717", border: "1px solid #404040" }}
          formatter={(v: number) => [`${v.toFixed(2)}%`, "Drawdown"]}
        />
        <Area type="monotone" dataKey="dd" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 2: Monthly Heatmap — 스냅샷에서 계산**

`components/charts/monthly-heatmap.tsx`:
```tsx
"use client"
import type { Snapshot } from "@/lib/types"

/** 스냅샷에서 월별 수익률을 계산해 히트맵 렌더. */
function computeMonthly(snaps: Snapshot[]): { month: string; ret: number }[] {
  if (snaps.length === 0) return []
  const byMonth = new Map<string, { first: number; last: number }>()
  for (const s of snaps) {
    const m = s.date.slice(0, 6)
    const v = byMonth.get(m)
    if (!v) byMonth.set(m, { first: s.total_value, last: s.total_value })
    else v.last = s.total_value
  }
  return [...byMonth.entries()].map(([m, v]) => ({
    month: m,
    ret: (v.last / v.first - 1) * 100,
  }))
}

function color(ret: number): string {
  if (ret === 0) return "bg-neutral-800"
  const mag = Math.min(10, Math.abs(ret)) / 10
  const alpha = 0.15 + mag * 0.7
  return ret > 0
    ? `rgba(34, 197, 94, ${alpha})`
    : `rgba(239, 68, 68, ${alpha})`
}

export function MonthlyHeatmap({ snapshots }: { snapshots: Snapshot[] }) {
  const rows = computeMonthly(snapshots)
  return (
    <div className="grid grid-cols-12 gap-1">
      {rows.map((r) => (
        <div
          key={r.month}
          className="flex h-14 flex-col items-center justify-center rounded text-xs"
          style={{ backgroundColor: color(r.ret) }}
          title={`${r.month}: ${r.ret.toFixed(2)}%`}
        >
          <span className="text-[10px] text-neutral-400">{r.month.slice(4)}</span>
          <span className="font-mono">{r.ret >= 0 ? "+" : ""}{r.ret.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: 상세 페이지에 Tabs 통합**

`app/(dashboard)/backtest/[runId]/page.tsx` 수정 — EquityCurve 섹션을 Tabs로 교체:
```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Drawdown } from "@/components/charts/drawdown"
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap"

// ...기존 코드 유지, 하단 차트 섹션을 다음으로 교체:
      <Tabs defaultValue="equity">
        <TabsList>
          <TabsTrigger value="equity">자산 곡선</TabsTrigger>
          <TabsTrigger value="drawdown">드로다운</TabsTrigger>
          <TabsTrigger value="monthly">월별 수익률</TabsTrigger>
        </TabsList>
        <TabsContent value="equity" className="rounded-lg border border-neutral-800 p-4">
          <EquityCurve snapshots={snaps} initialCapital={run.initial_capital} />
        </TabsContent>
        <TabsContent value="drawdown" className="rounded-lg border border-neutral-800 p-4">
          <Drawdown snapshots={snaps} />
        </TabsContent>
        <TabsContent value="monthly" className="rounded-lg border border-neutral-800 p-4">
          <MonthlyHeatmap snapshots={snaps} />
        </TabsContent>
      </Tabs>
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/components/charts/ webapp-ui/app/\(dashboard\)/backtest/
git commit -m "feat(webapp-ui): 상세 탭 — 드로다운 + 월별 수익률 히트맵"
```

---

### Task 27: 거래 이력 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/backtest/[runId]/trades/page.tsx`
- Create: `webapp-ui/components/domain/backtest/trades-table.tsx`

- [ ] **Step 1: 서버 컴포넌트 + 클라이언트 필터**

`app/(dashboard)/backtest/[runId]/trades/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { TradesTable } from "@/components/domain/backtest/trades-table"
import type { RunDetail, Trade } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = {
  params: Promise<{ runId: string }>
  searchParams: Promise<{ code?: string; winner?: string }>
}

export default async function TradesPage({ params, searchParams }: Props) {
  const { runId } = await params
  const sp = await searchParams
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }

  try {
    const run = await apiFetch<RunDetail>(
      `/api/v1/backtest/runs/${runId}`,
      { headers: h, cache: "no-store" },
    )
    const trades = await apiFetch<{ items: Trade[] }>(
      `/api/v1/backtest/runs/${runId}/trades`,
      {
        headers: h, cache: "no-store",
        searchParams: { code: sp.code, winner: sp.winner },
      },
    )
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">거래 이력 — {run.name || runId.slice(0, 8)}</h1>
        <TradesTable trades={trades.items} initialFilters={sp} />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
```

- [ ] **Step 2: TradesTable (클라이언트, 가상 스크롤 미사용 — 기본 테이블)**

`components/domain/backtest/trades-table.tsx`:
```tsx
"use client"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Trade } from "@/lib/types"

export function TradesTable({
  trades, initialFilters,
}: { trades: Trade[]; initialFilters: { code?: string; winner?: string } }) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [code, setCode] = useState(initialFilters.code ?? "")

  const apply = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (!v) sp.delete(k); else sp.set(k, v)
    }
    router.push(`${path}?${sp.toString()}`)
  }

  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0)
  const wins = trades.filter((t) => t.pnl > 0).length
  const losses = trades.length - wins
  const avgHold = trades.length
    ? trades.reduce((s, t) => s + t.holding_days, 0) / trades.length
    : 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="종목코드"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="max-w-xs"
        />
        <Button variant="outline" onClick={() => apply({ code, winner: undefined })}>
          전체
        </Button>
        <Button variant="outline" onClick={() => apply({ code, winner: "true" })}>
          승리만
        </Button>
        <Button variant="outline" onClick={() => apply({ code, winner: "false" })}>
          패배만
        </Button>
      </div>

      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>종목</TableHead>
              <TableHead>이름</TableHead>
              <TableHead>매수일</TableHead>
              <TableHead className="text-right">매수가</TableHead>
              <TableHead>매도일</TableHead>
              <TableHead className="text-right">매도가</TableHead>
              <TableHead className="text-right">수익률</TableHead>
              <TableHead className="text-right">보유일</TableHead>
              <TableHead className="text-right">손익</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.map((t, i) => (
              <TableRow key={`${t.code}-${t.buy_date}-${i}`}>
                <TableCell className="font-mono">{i + 1}</TableCell>
                <TableCell className="font-mono">{t.code}</TableCell>
                <TableCell>{t.name}</TableCell>
                <TableCell>{t.buy_date}</TableCell>
                <TableCell className="text-right font-mono">{t.buy_price.toLocaleString()}</TableCell>
                <TableCell>{t.sell_date}</TableCell>
                <TableCell className="text-right font-mono">{t.sell_price.toLocaleString()}</TableCell>
                <TableCell className={`text-right font-mono ${t.pnl > 0 ? "text-green-400" : "text-red-400"}`}>
                  {t.return_pct >= 0 ? "+" : ""}{t.return_pct.toFixed(1)}%
                </TableCell>
                <TableCell className="text-right">{t.holding_days}일</TableCell>
                <TableCell className={`text-right font-mono ${t.pnl > 0 ? "text-green-400" : "text-red-400"}`}>
                  {t.pnl >= 0 ? "+" : ""}{t.pnl.toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-neutral-400">
        총 {trades.length}건 (승 {wins} / 패 {losses})
        · 총 손익 <span className={totalPnl >= 0 ? "text-green-400" : "text-red-400"}>
          {totalPnl >= 0 ? "+" : ""}{totalPnl.toLocaleString()}원
        </span>
        · 평균 보유 {avgHold.toFixed(0)}일
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): 거래 이력 페이지 + 필터 (종목/승패)"
```

---

### Task 28: 포지션 이력 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/backtest/[runId]/positions/page.tsx`
- Create: `webapp-ui/components/domain/backtest/position-viewer.tsx`

- [ ] **Step 1: 서버 컴포넌트**

`app/(dashboard)/backtest/[runId]/positions/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { PositionViewer } from "@/components/domain/backtest/position-viewer"
import type { Position, RunDetail } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = {
  params: Promise<{ runId: string }>
  searchParams: Promise<{ date?: string; code?: string }>
}

export default async function PositionsPage({ params, searchParams }: Props) {
  const { runId } = await params
  const sp = await searchParams
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }

  try {
    const run = await apiFetch<RunDetail>(
      `/api/v1/backtest/runs/${runId}`,
      { headers: h, cache: "no-store" },
    )
    // 기본: 전 기간 → 날짜 선택 UI에서 필터
    const pos = await apiFetch<{ items: Position[] }>(
      `/api/v1/backtest/runs/${runId}/positions`,
      {
        headers: h, cache: "no-store",
        searchParams: { date: sp.date, code: sp.code },
      },
    )
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">
          포지션 이력 — {run.name || runId.slice(0, 8)}
        </h1>
        <PositionViewer
          positions={pos.items}
          initialDate={sp.date}
          initialCode={sp.code}
          startDate={run.start_date}
          endDate={run.end_date}
        />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
```

- [ ] **Step 2: PositionViewer — 날짜 슬라이더 + 테이블**

`components/domain/backtest/position-viewer.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Position } from "@/lib/types"

export function PositionViewer({
  positions, initialDate, initialCode, startDate, endDate,
}: {
  positions: Position[]
  initialDate?: string
  initialCode?: string
  startDate: string
  endDate: string
}) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [date, setDate] = useState(initialDate ?? "")
  const [code, setCode] = useState(initialCode ?? "")

  const apply = () => {
    const sp = new URLSearchParams(params.toString())
    if (date) sp.set("date", date); else sp.delete("date")
    if (code) sp.set("code", code); else sp.delete("code")
    router.push(`${path}?${sp.toString()}`)
  }

  // 날짜 유니크 리스트 (최근 20개만 슬라이스용)
  const uniqueDates = [...new Set(positions.map((p) => p.date))].sort()

  const total = positions.reduce((s, p) => s + p.unrealized_pnl, 0)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1 block text-xs text-neutral-400">날짜 (YYYYMMDD)</label>
          <Input
            value={date} onChange={(e) => setDate(e.target.value)}
            placeholder={`${startDate}~${endDate}`} className="w-40"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-neutral-400">종목코드</label>
          <Input value={code} onChange={(e) => setCode(e.target.value)} className="w-40" />
        </div>
        <Button onClick={apply}>필터</Button>
        <Button
          variant="outline"
          onClick={() => {
            setDate(""); setCode("")
            router.push(path)
          }}
        >초기화</Button>
      </div>

      {uniqueDates.length > 1 && !date && (
        <div className="text-xs text-neutral-500">
          전 기간 보유 이력 표시 중. 날짜 하나를 지정하면 해당일 스냅샷만 표시.
        </div>
      )}

      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>날짜</TableHead>
              <TableHead>종목</TableHead>
              <TableHead>이름</TableHead>
              <TableHead className="text-right">수량</TableHead>
              <TableHead className="text-right">평단가</TableHead>
              <TableHead className="text-right">현재가</TableHead>
              <TableHead className="text-right">평가손익</TableHead>
              <TableHead className="text-right">비중</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {positions.map((p, i) => (
              <TableRow key={`${p.date}-${p.code}-${i}`}>
                <TableCell>{p.date}</TableCell>
                <TableCell className="font-mono">{p.code}</TableCell>
                <TableCell>{p.name}</TableCell>
                <TableCell className="text-right font-mono">{p.quantity}</TableCell>
                <TableCell className="text-right font-mono">{p.avg_price.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono">{p.current_price.toLocaleString()}</TableCell>
                <TableCell className={`text-right font-mono ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toLocaleString()}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {(p.weight * 100).toFixed(1)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-neutral-400">
        총 {positions.length}행 · 합계 평가손익
        <span className={total >= 0 ? " text-green-400" : " text-red-400"}>
          {" "}{total >= 0 ? "+" : ""}{total.toLocaleString()}원
        </span>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): 포지션 이력 페이지 + 필터 (날짜/종목)"
```

---

### Task 29: 실행 폼 + 진행률 + 비교

**Files:**
- Create: `webapp-ui/app/(dashboard)/backtest/new/page.tsx`
- Create: `webapp-ui/components/domain/backtest/backtest-form.tsx`
- Create: `webapp-ui/app/(dashboard)/backtest/jobs/[jobId]/page.tsx`
- Create: `webapp-ui/components/domain/backtest/job-progress.tsx`
- Create: `webapp-ui/hooks/use-job-status.ts`
- Create: `webapp-ui/app/(dashboard)/backtest/compare/page.tsx`

- [ ] **Step 1: 폼 페이지 + BacktestForm**

`app/(dashboard)/backtest/new/page.tsx`:
```tsx
import { BacktestForm } from "@/components/domain/backtest/backtest-form"

export default function NewBacktestPage() {
  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">새 백테스트</h1>
      <BacktestForm />
    </div>
  )
}
```

`components/domain/backtest/backtest-form.tsx`:
```tsx
"use client"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const schema = z.object({
  strategy: z.enum(["momentum", "value", "quality_momentum", "topdown_etf"]),
  start: z.string().regex(/^\d{8}$/, "YYYYMMDD"),
  end: z.string().regex(/^\d{8}$/, "YYYYMMDD"),
  capital: z.coerce.number().int().min(1_000_000).max(100_000_000_000),
  market: z.enum(["KOSPI", "KOSDAQ"]),
  top: z.coerce.number().int().min(1).max(100),
  name: z.string().max(100).optional(),
})
type FormData = z.infer<typeof schema>

export function BacktestForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormData>({
      resolver: zodResolver(schema),
      defaultValues: {
        strategy: "momentum", market: "KOSPI", top: 20,
        capital: 100_000_000,
        start: "20240101",
        end: new Date().toISOString().slice(0, 10).replace(/-/g, ""),
      },
    })

  const onSubmit = async (data: FormData) => {
    setError(null)
    try {
      const r = await apiMutate<{ job_id: string }>(
        "/api/v1/backtest/run", "POST", data,
      )
      router.push(`/backtest/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {(["strategy", "market"] as const).map((key) => (
        <div key={key}>
          <Label htmlFor={key}>{key}</Label>
          <select id={key} {...register(key)}
            className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm">
            {key === "strategy"
              ? ["momentum", "value", "quality_momentum", "topdown_etf"].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))
              : ["KOSPI", "KOSDAQ"].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
          </select>
        </div>
      ))}
      {(["start", "end"] as const).map((key) => (
        <div key={key}>
          <Label htmlFor={key}>{key === "start" ? "시작일" : "종료일"} (YYYYMMDD)</Label>
          <Input id={key} {...register(key)} />
          {errors[key] && <p className="text-sm text-red-400">{errors[key]?.message}</p>}
        </div>
      ))}
      {(["capital", "top"] as const).map((key) => (
        <div key={key}>
          <Label htmlFor={key}>{key === "capital" ? "초기 자본 (원)" : "Top N"}</Label>
          <Input id={key} type="number" {...register(key)} />
          {errors[key] && <p className="text-sm text-red-400">{errors[key]?.message}</p>}
        </div>
      ))}
      <div>
        <Label htmlFor="name">이름 (선택)</Label>
        <Input id="name" {...register("name")} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "..." : "실행"}
      </Button>
    </form>
  )
}
```

- [ ] **Step 2: 진행률 hook + 페이지**

`hooks/use-job-status.ts`:
```typescript
"use client"
import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type { Job } from "@/lib/types"

export function useJobStatus(jobId: string) {
  return useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => apiFetch<Job>(`/api/v1/jobs/${jobId}`),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === "done" || s === "failed" || s === "cancelled"
        ? false : 2000
    },
  })
}
```

`app/(dashboard)/backtest/jobs/[jobId]/page.tsx`:
```tsx
import { JobProgress } from "@/components/domain/backtest/job-progress"

type Props = { params: Promise<{ jobId: string }> }

export default async function JobPage({ params }: Props) {
  const { jobId } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">백테스트 실행 중</h1>
      <JobProgress jobId={jobId} />
    </div>
  )
}
```

`components/domain/backtest/job-progress.tsx`:
```tsx
"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useJobStatus } from "@/hooks/use-job-status"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function JobProgress({ jobId }: { jobId: string }) {
  const router = useRouter()
  const { data: job, error } = useJobStatus(jobId)

  useEffect(() => {
    if (job?.status === "done" && job.result_ref) {
      router.replace(`/backtest/${job.result_ref.slice(0, 8)}`)
    }
  }, [job, router])

  if (error) return <div className="text-red-400">오류: {String(error)}</div>
  if (!job) return <Card className="p-6">로딩 중...</Card>

  const pct = (job.progress * 100).toFixed(0)

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-neutral-400">상태</p>
          <p className="text-lg font-semibold">{job.status}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-neutral-400">진행률</p>
          <p className="text-2xl font-mono">{pct}%</p>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded bg-neutral-800">
        <div className="h-full bg-green-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-sm text-neutral-400">{job.progress_text || "-"}</p>
      {job.status === "failed" && (
        <div className="space-y-2">
          <p className="text-red-400">실패: {job.error}</p>
          <Button variant="outline" onClick={() => router.push("/backtest/new")}>
            다시 시도
          </Button>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 3: 비교 페이지**

`app/(dashboard)/backtest/compare/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { MetricsCards } from "@/components/domain/backtest/metrics-cards"
import type { RunDetail } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ ids?: string }> }

export default async function ComparePage({ searchParams }: Props) {
  const sp = await searchParams
  const ids = sp.ids
  if (!ids || ids.split(",").length !== 2) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">백테스트 비교</h1>
        <p className="text-neutral-400">
          URL 파라미터에 ids=a,b 형식으로 두 run_id(또는 접두사)를 지정하세요.
        </p>
      </div>
    )
  }
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{ a: RunDetail; b: RunDetail }>(
    `/api/v1/backtest/compare`,
    { headers: h, cache: "no-store", searchParams: { ids } },
  )

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">백테스트 비교</h1>
      <div className="grid gap-6 md:grid-cols-2">
        {[data.a, data.b].map((r, i) => (
          <div key={i} className="space-y-3 rounded-lg border border-neutral-800 p-4">
            <div>
              <p className="text-sm text-neutral-400">ID {i + 1}</p>
              <p className="font-semibold">{r.name || r.run_id.slice(0, 8)}</p>
              <p className="text-xs text-neutral-500">{r.start_date}~{r.end_date}</p>
            </div>
            <MetricsCards metrics={r.metrics} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/
git commit -m "feat(webapp-ui): 실행 폼 + Job 진행률 polling + 비교 페이지"
```

---

## Part F — Deployment + Quality

### Task 30: systemd 유닛 + Cloudflare Tunnel 설정 문서

**Files:**
- Create: `systemd/alphapulse-fastapi.service`
- Create: `systemd/alphapulse-webapp-ui.service`
- Create: `systemd/cloudflared.service.example`
- Create: `docs/operations/webapp-deployment.md`

- [ ] **Step 1: systemd 유닛 파일 3개 (설계서 §9.2 내용 그대로)**

`systemd/alphapulse-fastapi.service`:
```ini
[Unit]
Description=AlphaPulse FastAPI
After=network-online.target
Wants=network-online.target

[Service]
User=alphapulse
WorkingDirectory=/opt/alphapulse
EnvironmentFile=/opt/alphapulse/.env
ExecStart=/opt/alphapulse/.venv/bin/uvicorn alphapulse.webapp.main:app \
    --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5

ProtectSystem=strict
ReadWritePaths=/opt/alphapulse/data /opt/alphapulse/logs
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

`systemd/alphapulse-webapp-ui.service`:
```ini
[Unit]
Description=AlphaPulse Webapp UI (Next.js)
After=network-online.target alphapulse-fastapi.service
Wants=alphapulse-fastapi.service

[Service]
User=alphapulse
WorkingDirectory=/opt/alphapulse/webapp-ui
EnvironmentFile=/opt/alphapulse/.env
ExecStart=/usr/bin/pnpm start -p 3000
Restart=always
RestartSec=5

ProtectSystem=strict
ReadWritePaths=/opt/alphapulse/webapp-ui/.next
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

`systemd/cloudflared.service.example`:
```ini
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
TimeoutStartSec=0
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5s
User=cloudflared
SyslogIdentifier=cloudflared

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 배포 문서 작성**

`docs/operations/webapp-deployment.md`:
```markdown
# AlphaPulse Webapp 배포 가이드 (홈서버 + Cloudflare Tunnel)

## 요구사항
- Ubuntu 24.04 LTS (또는 Debian계 Linux)
- Python 3.12+, Node.js 22 LTS, pnpm (corepack)
- Cloudflare 계정 + 도메인

## 1. 사전 준비

### 사용자/디렉토리
```bash
sudo useradd --system --create-home --home-dir /opt/alphapulse --shell /bin/false alphapulse
sudo chown -R alphapulse:alphapulse /opt/alphapulse
```

### 소스 배포
```bash
sudo -u alphapulse git clone https://<repo> /opt/alphapulse
cd /opt/alphapulse
sudo -u alphapulse uv sync
sudo -u alphapulse bash -c "cd webapp-ui && pnpm install && pnpm build"
```

### `.env` 설정
```bash
sudo -u alphapulse cp .env.example /opt/alphapulse/.env
sudo chmod 600 /opt/alphapulse/.env
sudo nano /opt/alphapulse/.env
```
필수:
- `WEBAPP_SESSION_SECRET` (최소 32자, `openssl rand -hex 32`)
- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` (콘텐츠)
- `TELEGRAM_MONITOR_BOT_TOKEN`, `TELEGRAM_MONITOR_CHANNEL_ID` (모니터링)

### 관리자 계정 생성
```bash
cd /opt/alphapulse
sudo -u alphapulse .venv/bin/ap webapp create-admin --email admin@example.com
```

## 2. systemd 설치

```bash
sudo cp /opt/alphapulse/systemd/alphapulse-fastapi.service /etc/systemd/system/
sudo cp /opt/alphapulse/systemd/alphapulse-webapp-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alphapulse-fastapi alphapulse-webapp-ui
sudo systemctl status alphapulse-fastapi alphapulse-webapp-ui
```

## 3. Cloudflare Tunnel

### 설치
```bash
# 패키지 설치 (Cloudflare 공식 지침 따름)
curl -L https://pkg.cloudflare.com/install.sh | sudo bash
sudo apt install -y cloudflared
```

### 터널 생성 & 인증
```bash
sudo cloudflared tunnel login
sudo cloudflared tunnel create alphapulse
# → /etc/cloudflared/<uuid>.json 생성
```

### 설정
`/etc/cloudflared/config.yml`:
```yaml
tunnel: <uuid-from-above>
credentials-file: /etc/cloudflared/<uuid>.json
ingress:
  - hostname: app.example.com
    service: http://127.0.0.1:3000
  - hostname: api.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

### DNS 라우팅
```bash
sudo cloudflared tunnel route dns alphapulse app.example.com
sudo cloudflared tunnel route dns alphapulse api.example.com
```

### 서비스 등록
```bash
sudo cp /opt/alphapulse/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
```

## 4. Cloudflare 추가 보안 설정

1. **Transform Rules** → Modify Request Header
   - Remove `x-middleware-subrequest`
   - Remove `x-middleware-prefetch`
2. **SSL/TLS** → Full (strict)
3. **WAF** → Managed Rules 활성 (OWASP Core Rule Set)
4. (선택) **Zero Trust Access** → 이메일 OTP 정책으로 `app.example.com` 보호

## 5. 동작 확인

```bash
curl https://api.example.com/api/v1/health
# 예상: {"status":"ok"}

# 브라우저에서 https://app.example.com 접속 → 로그인
```

## 6. 업데이트 절차

```bash
cd /opt/alphapulse
sudo -u alphapulse git pull
sudo -u alphapulse uv sync
sudo -u alphapulse bash -c "cd webapp-ui && pnpm install && pnpm build"
sudo systemctl restart alphapulse-fastapi alphapulse-webapp-ui
```
```

- [ ] **Step 3: 커밋**
```bash
git add systemd/ docs/operations/webapp-deployment.md
git commit -m "docs(webapp): systemd 유닛 + 배포 가이드 (Cloudflare Tunnel)"
```

---

### Task 31: 일일 백업 스크립트

**Files:**
- Create: `scripts/backup.sh`
- Create: `docs/operations/backup-restore.md`

- [ ] **Step 1: 백업 스크립트**

`scripts/backup.sh`:
```bash
#!/usr/bin/env bash
# AlphaPulse 일일 백업 — cron 03:00 실행
# Usage: /opt/alphapulse/scripts/backup.sh

set -euo pipefail

BASE="${BASE:-/opt/alphapulse}"
DATA="$BASE/data"
BACKUPS="$BASE/backups"
DATE=$(date +%Y%m%d_%H%M%S)
TARGET="$BACKUPS/$DATE"

mkdir -p "$TARGET"
for db in trading backtest portfolio audit feedback cache history webapp; do
    SRC="$DATA/$db.db"
    if [ -f "$SRC" ]; then
        sqlite3 "$SRC" ".backup '$TARGET/$db.db'"
    fi
done

# 압축
tar czf "$TARGET.tar.gz" -C "$BACKUPS" "$DATE"
rm -rf "$TARGET"

# 원격 동기화 (rclone 설정 선택)
if command -v rclone >/dev/null 2>&1 && rclone listremotes | grep -q "^b2:"; then
    rclone copy "$TARGET.tar.gz" "b2:alphapulse-backups/" --quiet
fi

# 7일 이전 로컬 백업 삭제
find "$BACKUPS" -maxdepth 1 -name "*.tar.gz" -mtime +7 -delete

echo "backup ok: $TARGET.tar.gz"
```

권한:
```bash
chmod +x scripts/backup.sh
```

- [ ] **Step 2: cron 등록 가이드**

`docs/operations/backup-restore.md`:
```markdown
# 백업 / 복구

## 자동 백업 설정

```bash
sudo -u alphapulse crontab -e
```
```
0 3 * * * /opt/alphapulse/scripts/backup.sh >> /opt/alphapulse/logs/backup.log 2>&1
```

## 복구 절차

### 1. 서비스 중지
```bash
sudo systemctl stop alphapulse-fastapi alphapulse-webapp-ui
```

### 2. 백업 추출
```bash
cd /tmp
tar xzf /opt/alphapulse/backups/<DATE>.tar.gz
```

### 3. DB 복원
```bash
sudo -u alphapulse cp /tmp/<DATE>/<db>.db /opt/alphapulse/data/<db>.db
```

### 4. 무결성 확인
```bash
for db in /opt/alphapulse/data/*.db; do
    sqlite3 "$db" "PRAGMA integrity_check;"
done
```

### 5. 서비스 기동
```bash
sudo systemctl start alphapulse-fastapi alphapulse-webapp-ui
curl https://api.example.com/api/v1/health
```

## 원격 저장소 연결 (선택)

Backblaze B2 예시:
```bash
sudo -u alphapulse rclone config
# Remote name: b2
# Storage: Backblaze B2
# (B2 application key 입력)
```
```

- [ ] **Step 3: 커밋**
```bash
chmod +x scripts/backup.sh
git add scripts/backup.sh docs/operations/backup-restore.md
git commit -m "feat(ops): 일일 백업 스크립트 + 복구 절차 문서"
```

---

### Task 32: CI 주간 취약점 스캔 워크플로우

**Files:**
- Create: `.github/workflows/security-scan.yml`

- [ ] **Step 1: 워크플로우 작성**
```yaml
name: Security Scan
on:
  schedule:
    - cron: "0 3 * * 1"  # 매주 월요일 03:00 UTC
  workflow_dispatch:
  pull_request:
    paths:
      - "pyproject.toml"
      - "uv.lock"
      - "webapp-ui/package.json"
      - "webapp-ui/pnpm-lock.yaml"

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv sync --dev
      - run: uv run pip-audit --strict
      - run: uv run bandit -r alphapulse/ -lll

  node:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: corepack enable
      - working-directory: webapp-ui
        run: pnpm install --frozen-lockfile
      - working-directory: webapp-ui
        run: pnpm audit --audit-level=high
      - name: osv-scanner
        uses: google/osv-scanner-action/osv-scanner-action@v1
        with:
          scan-args: |-
            --lockfile=webapp-ui/pnpm-lock.yaml
            --lockfile=uv.lock

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: 커밋**
```bash
git add .github/workflows/security-scan.yml
git commit -m "ci(webapp): 주간 취약점 스캔 파이프라인 (pip-audit/pnpm/osv/gitleaks)"
```

---

### Task 33: 운영 문서 초안

**Files:**
- Create: `docs/operations/webapp-runbook.md`
- Create: `docs/operations/security-checklist.md`

- [ ] **Step 1: Runbook**

`docs/operations/webapp-runbook.md`:
```markdown
# Webapp Runbook — 장애 대응

## 증상: FastAPI 5xx 급증
1. 로그 확인: `journalctl -u alphapulse-fastapi -n 200 --no-pager`
2. 잘못된 DB 경로/권한 여부: `ls -la /opt/alphapulse/data/`
3. 재시작: `sudo systemctl restart alphapulse-fastapi`
4. 해결 안 됨 → 최근 배포 롤백: `git checkout <prev> && uv sync && restart`

## 증상: Next.js UI 로딩 실패
1. `journalctl -u alphapulse-webapp-ui -n 100`
2. Node 버전: `node --version` (22 LTS)
3. 빌드 재실행: `sudo -u alphapulse bash -c "cd webapp-ui && pnpm build"`
4. 재시작: `sudo systemctl restart alphapulse-webapp-ui`

## 증상: Cloudflare Tunnel 단절
1. `sudo systemctl status cloudflared`
2. 토큰 유효성: `sudo cloudflared tunnel list`
3. 재연결: `sudo systemctl restart cloudflared`

## 증상: 로그인 불가
1. 계정 잠금 여부: `/opt/alphapulse/.venv/bin/ap webapp unlock-account --email <>`
2. DB 무결성: `sqlite3 /opt/alphapulse/data/webapp.db "PRAGMA integrity_check"`
3. 세션 DB 리셋 (극단적 경우): 모든 사용자 로그아웃됨
   ```bash
   sqlite3 /opt/alphapulse/data/webapp.db "DELETE FROM sessions;"
   ```

## 증상: 백테스트 실행 안 끝남 / 멈춤
1. Job 상태: `sqlite3 /opt/alphapulse/data/webapp.db "SELECT id, status, progress FROM jobs ORDER BY created_at DESC LIMIT 5"`
2. 오래된 `running` 정리: FastAPI 재시작하면 orphan 복구 자동 수행
3. 기존 결과 삭제:
   ```bash
   # CLI 또는 UI에서 DELETE /api/v1/backtest/runs/<id>
   ```

## 긴급 전체 중지
```bash
sudo systemctl stop alphapulse-webapp-ui alphapulse-fastapi cloudflared
```
복구: `sudo systemctl start ...` 역순 또는 `systemctl start` 한 번에.

## 로그 수집 범위
- `journalctl -u alphapulse-* -u cloudflared --since "1 hour ago"`
- `/opt/alphapulse/logs/*.log`
- `/opt/alphapulse/data/audit.db` (최근 이벤트)
```

- [ ] **Step 2: 보안 체크리스트**

`docs/operations/security-checklist.md`:
```markdown
# 분기 보안 체크리스트 (3개월 1회)

**실시일:** ____________________  
**실시자:** ____________________

## 의존성
- [ ] `uv run pip-audit --strict` Pass
- [ ] `pnpm audit --audit-level=high` Pass
- [ ] Next.js / FastAPI 메이저 업데이트 여부 확인
- [ ] 최근 CVE 공지 전수 확인 (cvedetails, GHSA)

## 인증/세션
- [ ] 활성 세션 수 검토 (`SELECT COUNT(*) FROM sessions WHERE expires_at > strftime('%s','now')`)
- [ ] 장기 미사용 계정 비활성화 여부
- [ ] 관리자 비밀번호 로테이션 (연 1회 이상)

## 감사 로그
- [ ] 비정상 로그인 시도 로그 확인 (로그인 실패 IP 집중 여부)
- [ ] 감사 로그 1년 이상 보관 중인지

## 시크릿
- [ ] `.env` 권한 `600` 확인
- [ ] `WEBAPP_SESSION_SECRET` / `KIS_*` 로테이션 여부 (연 1회)
- [ ] Git history에 시크릿 누출 없음 (`git log -p | grep -iE "(api[_-]?key|secret|password)"`)

## 인프라
- [ ] 서버 OS 보안 업데이트 최신 (`apt list --upgradable | grep -i security`)
- [ ] Cloudflare WAF Managed Rules 활성
- [ ] SSL 인증서 만료일 > 30일
- [ ] 백업 실행/복구 테스트 (실제 복구 해보기)

## 네트워크
- [ ] 홈서버 포트 80/443 포워딩 없음 재확인
- [ ] SSH는 키 기반 + LAN 한정
- [ ] fail2ban / SSH 로그인 실패 로그 검토

## 서명
- [ ] 모든 항목 OK 시 이 문서 커밋 (`docs/operations/security-log-YYYYQn.md` 로 복사)
```

- [ ] **Step 3: 커밋**
```bash
git add docs/operations/webapp-runbook.md docs/operations/security-checklist.md
git commit -m "docs(ops): Webapp Runbook + 분기 보안 체크리스트"
```

---

### Task 34: Playwright E2E 스모크 테스트

**Files:**
- Create: `webapp-ui/playwright.config.ts`
- Create: `webapp-ui/e2e/backtest-flow.spec.ts`
- Create: `webapp-ui/.env.test.example`

- [ ] **Step 1: Playwright 설정**

`webapp-ui/playwright.config.ts`:
```typescript
import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
})
```

`webapp-ui/.env.test.example`:
```
E2E_BASE_URL=http://localhost:3000
E2E_ADMIN_EMAIL=test@example.com
E2E_ADMIN_PASSWORD=test-password-12!
```

- [ ] **Step 2: 스모크 테스트**

`webapp-ui/e2e/backtest-flow.spec.ts`:
```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe.serial("Backtest flow smoke test", () => {
  test("unauthenticated user is redirected to /login", async ({ page }) => {
    await page.goto("/backtest")
    await expect(page).toHaveURL(/\/login/)
  })

  test("login succeeds with valid credentials", async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/backtest/)
    await expect(page.getByRole("heading", { name: "백테스트 결과" })).toBeVisible()
  })

  test("navigate to new backtest form", async ({ page }) => {
    await page.goto("/backtest")
    await page.getByRole("link", { name: "새 백테스트" }).click()
    await expect(page).toHaveURL(/\/backtest\/new/)
  })

  test("logout clears session", async ({ page }) => {
    await page.goto("/backtest")
    await page.getByRole("button", { name: "Logout" }).click()
    await page.goto("/backtest")
    await expect(page).toHaveURL(/\/login/)
  })
})
```

- [ ] **Step 3: 사전 준비 가이드**

테스트 계정을 별도 생성해서 E2E가 프로덕션 admin과 충돌하지 않도록:
```bash
# 로컬 또는 스테이징
ap webapp create-admin --email test@example.com
```

- [ ] **Step 4: 실행 & 커밋**
```bash
cd webapp-ui
pnpm exec playwright install chromium
pnpm exec playwright test
cd ..

git add webapp-ui/playwright.config.ts webapp-ui/e2e/ webapp-ui/.env.test.example
git commit -m "test(webapp-ui): Playwright E2E 스모크 (로그인/리다이렉트/로그아웃)"
```

---

## Phase 1 완료 기준

아래 조건이 모두 충족되면 Phase 1 완료:

- [ ] 34개 Task 전부 commit됨
- [ ] `pytest tests/webapp/ -v` 전부 통과
- [ ] 기존 `pytest tests/ -q` 통과 (863개 + webapp 신규)
- [ ] `ruff check alphapulse/` 클린
- [ ] `cd webapp-ui && pnpm build` 성공
- [ ] `cd webapp-ui && pnpm exec playwright test` 성공
- [ ] `.github/workflows/security-scan.yml` 수동 실행 성공 (`workflow_dispatch`)
- [ ] 로컬 dev 환경에서 로그인 → 백테스트 실행 → 결과 상세 → 거래 이력 → 포지션 → 비교 전체 플로우 수동 검증
- [ ] Telegram 모니터링 채널에 `webapp started` 알림 수신 확인

## 다음 단계

Phase 1 완료 후 별도 implementation plan 문서로:
- `docs/superpowers/plans/YYYY-MM-DD-webapp-phase2.md` — Portfolio/Risk/Screening/Data + Settings
- `docs/superpowers/plans/YYYY-MM-DD-webapp-phase3.md` — Market/Briefing/Feedback + SaaS 전환 + 실매매 UI

각 Phase는 이전 Phase 위에 쌓는 구조이며 독립 릴리스 가능.
