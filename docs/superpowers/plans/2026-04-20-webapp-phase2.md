# AlphaPulse Web Frontend — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1(Auth + Backtest) 위에 Portfolio / Risk / Screening / Data / Settings / Audit 6개 도메인 + 홈 대시보드를 구현한다.

**Architecture:** Phase 1 FastAPI + Next.js 인프라 재사용. 설정은 Fernet DB + `.env` fallback hybrid. Risk는 스냅샷 해시 캐싱. Screening/Data는 기존 Job 인프라로 영속 실행. 모드(paper/live/backtest)는 URL searchParam 전역 셀렉터.

**Tech Stack:** Phase 1 스택 (FastAPI · Pydantic v2 · Next.js 15 · shadcn/ui · TanStack Query) + `cryptography.fernet` (설정 암호화).

**Reference:** `docs/superpowers/specs/2026-04-20-webapp-phase2-design.md`

---

## File Structure

### Backend (Python) — 추가분

```
alphapulse/webapp/
├── api/                              # Phase 2 도메인 라우터
│   ├── dashboard.py                  # 홈 aggregate
│   ├── portfolio.py
│   ├── risk.py
│   ├── screening.py
│   ├── data.py
│   ├── settings.py
│   └── audit.py
├── store/
│   ├── settings.py                   # SettingsRepository (Fernet)
│   ├── risk_cache.py                 # risk_report_cache 테이블
│   ├── screening.py                  # screening_runs 테이블
│   └── readers/
│       ├── portfolio.py              # PortfolioStore 래핑
│       ├── risk.py                   # RiskManager 호출 어댑터
│       ├── data_status.py            # BulkCollector.status 어댑터
│       └── audit.py                  # AuditLogger 조회 어댑터
└── services/
    ├── settings_service.py           # DB → .env fallback, load_env_overrides
    ├── screening_runner.py           # CLI screen 로직 추출 (Job용)
    └── data_jobs.py                  # update / collect-* Job wrapper
```

### Frontend (Next.js) — 추가분

```
webapp-ui/
├── app/(dashboard)/
│   ├── page.tsx                      # 홈 대시보드 (Phase 1 redirect 교체)
│   ├── portfolio/
│   │   ├── page.tsx
│   │   ├── history/page.tsx
│   │   └── attribution/page.tsx
│   ├── risk/
│   │   ├── page.tsx
│   │   ├── stress/page.tsx
│   │   └── limits/page.tsx
│   ├── screening/
│   │   ├── page.tsx
│   │   ├── new/page.tsx
│   │   ├── [runId]/page.tsx
│   │   └── jobs/[jobId]/page.tsx
│   ├── data/
│   │   ├── page.tsx
│   │   └── jobs/[jobId]/page.tsx
│   ├── settings/
│   │   ├── page.tsx                  # 탭 쉘 (redirect to /settings/api-keys)
│   │   ├── api-keys/page.tsx
│   │   ├── risk-limits/page.tsx
│   │   ├── notifications/page.tsx
│   │   └── backtest-defaults/page.tsx
│   └── audit/page.tsx
├── components/
│   ├── layout/
│   │   ├── mode-selector.tsx         # topbar dropdown
│   │   └── sidebar.tsx               # 활성 항목 업데이트 (기존)
│   └── domain/
│       ├── home/                     # 5 위젯
│       ├── portfolio/
│       ├── risk/
│       ├── screening/
│       ├── data/
│       ├── settings/
│       └── audit/
├── hooks/
│   ├── use-mode.ts
│   ├── use-portfolio.ts
│   └── use-data-status.ts
└── lib/
    ├── market-hours.ts
    └── format.ts
```

### Infrastructure

```
docs/operations/
└── webapp-phase2.md                  # Phase 2 운영 절차 (Settings 관리, Fernet 키 등)
```

### Tests

```
tests/webapp/
├── store/
│   ├── test_settings.py
│   ├── test_risk_cache.py
│   └── test_screening.py
├── services/
│   ├── test_settings_service.py
│   ├── test_screening_runner.py
│   └── test_data_jobs.py
├── api/
│   ├── test_portfolio.py
│   ├── test_risk.py
│   ├── test_screening.py
│   ├── test_data.py
│   ├── test_settings.py
│   ├── test_audit.py
│   └── test_dashboard.py
└── test_cli_webapp_settings.py       # init-encrypt-key / import-env

webapp-ui/e2e/
└── phase2-flow.spec.ts               # 모드 전환, 설정 변경, data job 실행
```

---

## Task Index

### Part A — Backend Foundation (Tasks 1-6)
1. SettingsRepository (Fernet 암호화)
2. SettingsService (DB → .env fallback + load_env_overrides)
3. RiskReportCacheRepository (스냅샷 해시 캐싱)
4. ScreeningRepository (screening_runs CRUD)
5. ScreeningRunner 서비스 (기존 screen CLI 로직 추출)
6. Data Jobs 서비스 (update / collect-financials / wisereport / short)

### Part B — Backend API (Tasks 7-14)
7. Portfolio API (summary / history / attribution, mode param)
8. Risk API (report / stress / limits, 캐시 연동)
9. Custom Stress API (캐시 skip, 시나리오 입력)
10. Screening API (조회 / 실행 / 삭제)
11. Data API (status / scheduler / 4 Job)
12. Settings API (category 조회 / 수정, 비밀번호 재확인)
13. Audit API (이벤트 조회, 필터)
14. Dashboard home API (aggregate)

### Part C — Backend CLI & Migration (Tasks 15-16)
15. `ap webapp init-encrypt-key` / `rotate-encrypt-key` / `set` / `list`
16. `ap webapp import-env` + 감사 로그 wiring

### Part D — Frontend Common (Tasks 17-18)
17. `useMode` hook + `ModeSelector` 컴포넌트 + topbar 통합
18. `useMarketHours` + `lib/format.ts`

### Part E — Frontend Home + Portfolio (Tasks 19-22)
19. Home 대시보드 (Layout A, 5 위젯)
20. Portfolio summary 페이지
21. Portfolio history
22. Portfolio attribution

### Part F — Frontend Risk + Screening (Tasks 23-29)
23. Risk overview
24. Risk stress (기본 5 시나리오)
25. Custom stress 폼
26. Risk limits (읽기 전용)
27. Screening list + form
28. Screening detail
29. Screening job progress 연결

### Part G — Frontend Data + Settings + Audit (Tasks 30-36)
30. Data status 대시보드
31. Data action buttons (+ collect_all 비활성)
32. Data job progress
33. Settings 탭 쉘 + API keys 탭
34. Settings 리스크 리밋 탭
35. Settings 알림 + 백테스트 기본값 탭
36. Audit viewer

### Part H — Integration (Tasks 37-38)
37. Sidebar 업데이트 (disabled 해제, 활성 항목 재배치)
38. Playwright E2E 확장 (Phase 2 플로우)

---

## Part A — Backend Foundation

### Task 1: SettingsRepository (Fernet 암호화)

**Files:**
- Create: `alphapulse/webapp/store/settings.py`
- Modify: `alphapulse/webapp/store/webapp_db.py` (settings 테이블 스키마 추가)
- Test: `tests/webapp/store/test_settings.py`
- Modify: `pyproject.toml` (cryptography 의존성 확인/추가)

- [ ] **Step 1: `pyproject.toml`에 cryptography 확인/추가**

`[project.dependencies]`에 `"cryptography>=43"`가 있는지 확인. 없으면 추가하고:
```bash
uv sync
uv run python -c "from cryptography.fernet import Fernet; print('ok')"
```

- [ ] **Step 2: `webapp_db.py`에 settings 테이블 추가**

`_SCHEMA` 문자열에 아래 추가:
```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_encrypted TEXT NOT NULL,
    is_secret INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,
    tenant_id INTEGER,
    updated_at REAL NOT NULL,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);
```

- [ ] **Step 3: 테스트 작성 — `tests/webapp/store/test_settings.py`**

```python
"""SettingsRepository — Fernet 암호화 저장/조회."""
import sqlite3

import pytest
from cryptography.fernet import Fernet

from alphapulse.webapp.store.settings import SettingsRepository


@pytest.fixture
def fernet_key():
    return Fernet.generate_key()


@pytest.fixture
def repo(webapp_db, fernet_key):
    return SettingsRepository(db_path=webapp_db, fernet_key=fernet_key)


class TestSettingsRepository:
    def test_set_and_get_roundtrip(self, repo):
        repo.set(
            key="KIS_APP_KEY", value="secret-value-12345",
            is_secret=True, category="api_key", user_id=1,
        )
        assert repo.get("KIS_APP_KEY") == "secret-value-12345"

    def test_get_missing_returns_none(self, repo):
        assert repo.get("NOT_EXIST") is None

    def test_encryption_at_rest(self, repo, webapp_db):
        repo.set(
            key="KIS_APP_KEY", value="plaintext",
            is_secret=True, category="api_key", user_id=1,
        )
        with sqlite3.connect(webapp_db) as conn:
            row = conn.execute(
                "SELECT value_encrypted FROM settings WHERE key=?",
                ("KIS_APP_KEY",),
            ).fetchone()
        assert row is not None
        assert "plaintext" not in row[0]

    def test_set_updates_existing(self, repo):
        repo.set(
            key="K", value="v1", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K", value="v2", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert repo.get("K") == "v2"

    def test_list_by_category(self, repo):
        repo.set(
            key="K1", value="v1", is_secret=True,
            category="api_key", user_id=1,
        )
        repo.set(
            key="K2", value="v2", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K3", value="v3", is_secret=True,
            category="api_key", user_id=1,
        )
        api_keys = repo.list_by_category("api_key")
        assert {e.key for e in api_keys} == {"K1", "K3"}

    def test_list_all(self, repo):
        repo.set(
            key="K1", value="v1", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.set(
            key="K2", value="v2", is_secret=True,
            category="api_key", user_id=1,
        )
        assert len(repo.list_all()) == 2

    def test_delete(self, repo):
        repo.set(
            key="K", value="v", is_secret=False,
            category="risk_limit", user_id=1,
        )
        repo.delete("K")
        assert repo.get("K") is None

    def test_key_mismatch_raises(self, webapp_db):
        k1 = Fernet.generate_key()
        k2 = Fernet.generate_key()
        r1 = SettingsRepository(db_path=webapp_db, fernet_key=k1)
        r1.set(
            key="K", value="v", is_secret=True,
            category="api_key", user_id=1,
        )
        r2 = SettingsRepository(db_path=webapp_db, fernet_key=k2)
        with pytest.raises(Exception):
            r2.get("K")

    def test_entry_fields(self, repo):
        repo.set(
            key="K", value="v", is_secret=True,
            category="api_key", user_id=42,
        )
        entries = repo.list_all()
        e = entries[0]
        assert e.key == "K"
        assert e.is_secret is True
        assert e.category == "api_key"
        assert e.updated_by == 42
        assert e.updated_at > 0
```

- [ ] **Step 4: 테스트 실행 (FAIL)**
```bash
pytest tests/webapp/store/test_settings.py -v
```
예상: `ModuleNotFoundError`

- [ ] **Step 5: 구현 — `alphapulse/webapp/store/settings.py`**

```python
"""SettingsRepository — data/webapp.db settings 테이블 (Fernet 암호화)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet


@dataclass
class SettingEntry:
    key: str
    is_secret: bool
    category: str
    tenant_id: int | None
    updated_at: float
    updated_by: int | None


def _row_to_entry(row: sqlite3.Row) -> SettingEntry:
    return SettingEntry(
        key=row["key"],
        is_secret=bool(row["is_secret"]),
        category=row["category"],
        tenant_id=row["tenant_id"],
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
    )


class SettingsRepository:
    def __init__(self, db_path: str | Path, fernet_key: bytes) -> None:
        self.db_path = Path(db_path)
        self.fernet = Fernet(fernet_key)

    def get(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value_encrypted FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return self.fernet.decrypt(row[0].encode("utf-8")).decode("utf-8")

    def set(
        self,
        key: str,
        value: str,
        is_secret: bool,
        category: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        encrypted = self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO settings (key, value_encrypted, is_secret, "
                "category, tenant_id, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value_encrypted = excluded.value_encrypted, "
                "is_secret = excluded.is_secret, "
                "category = excluded.category, "
                "updated_at = excluded.updated_at, "
                "updated_by = excluded.updated_by",
                (
                    key, encrypted, 1 if is_secret else 0, category,
                    tenant_id, time.time(), user_id,
                ),
            )

    def delete(self, key: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    def list_by_category(self, category: str) -> list[SettingEntry]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM settings WHERE category = ? ORDER BY key",
                (category,),
            ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def list_all(self) -> list[SettingEntry]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM settings ORDER BY category, key"
            ).fetchall()
        return [_row_to_entry(r) for r in rows]
```

- [ ] **Step 6: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_settings.py -v
ruff check alphapulse/webapp/store/settings.py tests/webapp/store/test_settings.py
git add alphapulse/webapp/store/settings.py alphapulse/webapp/store/webapp_db.py tests/webapp/store/test_settings.py pyproject.toml uv.lock
git commit -m "feat(webapp): SettingsRepository + settings 테이블 + Fernet 암호화"
```

---

### Task 2: SettingsService (hybrid)

**Files:**
- Create: `alphapulse/webapp/services/__init__.py` (빈)
- Create: `alphapulse/webapp/services/settings_service.py`
- Test: `tests/webapp/services/__init__.py` (빈)
- Test: `tests/webapp/services/test_settings_service.py`

- [ ] **Step 1: 테스트 작성**

```python
"""SettingsService — DB → .env fallback + load_env_overrides."""
import os

import pytest
from cryptography.fernet import Fernet

from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.settings import SettingsRepository


@pytest.fixture
def fernet_key():
    return Fernet.generate_key()


@pytest.fixture
def svc(webapp_db, fernet_key):
    repo = SettingsRepository(db_path=webapp_db, fernet_key=fernet_key)
    return SettingsService(repo=repo)


class TestGetFallback:
    def test_db_has_value(self, svc):
        svc.repo.set(
            key="K", value="from_db", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get("K") == "from_db"

    def test_db_missing_env_has(self, svc, monkeypatch):
        monkeypatch.setenv("K", "from_env")
        assert svc.get("K") == "from_env"

    def test_db_takes_priority_over_env(self, svc, monkeypatch):
        monkeypatch.setenv("K", "from_env")
        svc.repo.set(
            key="K", value="from_db", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get("K") == "from_db"

    def test_both_missing(self, svc):
        assert svc.get("NOT_EXIST_AT_ALL") is None


class TestTypedGet:
    def test_int(self, svc):
        svc.repo.set(
            key="N", value="42", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get_int("N", default=0) == 42
        assert svc.get_int("MISSING", default=99) == 99

    def test_float(self, svc):
        svc.repo.set(
            key="R", value="0.25", is_secret=False,
            category="risk_limit", user_id=1,
        )
        assert svc.get_float("R", default=1.0) == 0.25

    def test_bool_truthy(self, svc):
        svc.repo.set(
            key="B", value="true", is_secret=False,
            category="notification", user_id=1,
        )
        assert svc.get_bool("B", default=False) is True

    def test_bool_falsy(self, svc):
        svc.repo.set(
            key="B", value="0", is_secret=False,
            category="notification", user_id=1,
        )
        assert svc.get_bool("B", default=True) is False


class TestMask:
    def test_masks_long_secret(self):
        assert SettingsService.mask("sk-abcdefghij1234") == "sk-a****1234"

    def test_masks_short_secret(self):
        assert SettingsService.mask("short") == "****"

    def test_none(self):
        assert SettingsService.mask(None) == ""


class TestLoadEnvOverrides:
    def test_overrides_os_environ(self, svc, monkeypatch):
        monkeypatch.delenv("KIS_APP_KEY", raising=False)
        svc.repo.set(
            key="KIS_APP_KEY", value="db_val",
            is_secret=True, category="api_key", user_id=1,
        )
        svc.load_env_overrides()
        assert os.environ.get("KIS_APP_KEY") == "db_val"
```

- [ ] **Step 2: 테스트 실행 (FAIL)**
```bash
pytest tests/webapp/services/test_settings_service.py -v
```

- [ ] **Step 3: 구현**

```python
"""SettingsService — 런타임 설정 중앙 접근.

우선순위: DB (Fernet 복호화) → os.environ → default.
"""

from __future__ import annotations

import os

from alphapulse.webapp.store.settings import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository) -> None:
        self.repo = repo

    def get(self, key: str) -> str | None:
        val = self.repo.get(key)
        if val is not None:
            return val
        return os.environ.get(key)

    def get_int(self, key: str, default: int) -> int:
        v = self.get(key)
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float) -> float:
        v = self.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool) -> bool:
        v = self.get(key)
        if v is None:
            return default
        return v.strip().lower() in {"1", "true", "yes", "on"}

    def load_env_overrides(self) -> None:
        """DB의 모든 설정을 os.environ에 덮어쓰기.
        FastAPI startup 훅에서 1회 호출. Phase 2 한정 방식.
        """
        for entry in self.repo.list_all():
            val = self.repo.get(entry.key)
            if val is not None:
                os.environ[entry.key] = val

    @staticmethod
    def mask(value: str | None) -> str:
        """Secret 값 마스킹."""
        if value is None:
            return ""
        if len(value) < 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/services/ -v
ruff check alphapulse/webapp/services/ tests/webapp/services/
git add alphapulse/webapp/services/ tests/webapp/services/
git commit -m "feat(webapp): SettingsService — DB→.env fallback + env override 로더"
```

---

### Task 3: RiskReportCacheRepository

**Files:**
- Create: `alphapulse/webapp/store/risk_cache.py`
- Modify: `alphapulse/webapp/store/webapp_db.py` (risk_report_cache 테이블)
- Test: `tests/webapp/store/test_risk_cache.py`

- [ ] **Step 1: `webapp_db.py`에 테이블 추가**

`_SCHEMA`에 추가:
```sql
CREATE TABLE IF NOT EXISTS risk_report_cache (
    snapshot_key TEXT PRIMARY KEY,
    report_json TEXT NOT NULL,
    stress_json TEXT,
    computed_at REAL NOT NULL,
    tenant_id INTEGER
);
```

- [ ] **Step 2: 테스트 작성**

```python
"""RiskReportCacheRepository."""
import json
import time

import pytest

from alphapulse.webapp.store.risk_cache import (
    CachedRiskReport,
    RiskReportCacheRepository,
)


@pytest.fixture
def cache(webapp_db):
    return RiskReportCacheRepository(db_path=webapp_db)


class TestRiskCache:
    def test_miss_returns_none(self, cache):
        assert cache.get("20260420|paper|100000000") is None

    def test_put_and_get(self, cache):
        cache.put(
            key="20260420|paper|100000000",
            report={"var_95": -2.5, "cvar_95": -3.1, "drawdown_status": "NORMAL"},
            stress={"2020_covid": -10.5, "flash_crash": -15.0},
        )
        got = cache.get("20260420|paper|100000000")
        assert got is not None
        assert got.report["var_95"] == -2.5
        assert got.stress["2020_covid"] == -10.5

    def test_put_overwrites(self, cache):
        cache.put(
            key="K", report={"var_95": -1.0}, stress={},
        )
        cache.put(
            key="K", report={"var_95": -2.0}, stress={},
        )
        got = cache.get("K")
        assert got.report["var_95"] == -2.0

    def test_computed_at_recent(self, cache):
        cache.put(key="K", report={}, stress={})
        got = cache.get("K")
        assert time.time() - got.computed_at < 2

    def test_snapshot_key_helper(self):
        key = RiskReportCacheRepository.snapshot_key(
            date="20260420", mode="paper", total_value=100_000_000.5,
        )
        assert key == "20260420|paper|100000000"
```

- [ ] **Step 3: 구현**

```python
"""RiskReportCacheRepository — 스냅샷 해시 기반 리스크 리포트 캐시."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CachedRiskReport:
    snapshot_key: str
    report: dict
    stress: dict
    computed_at: float


class RiskReportCacheRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @staticmethod
    def snapshot_key(date: str, mode: str, total_value: float) -> str:
        return f"{date}|{mode}|{int(total_value)}"

    def get(self, key: str) -> CachedRiskReport | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM risk_report_cache WHERE snapshot_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CachedRiskReport(
            snapshot_key=row["snapshot_key"],
            report=json.loads(row["report_json"]),
            stress=json.loads(row["stress_json"] or "{}"),
            computed_at=row["computed_at"],
        )

    def put(self, key: str, report: dict, stress: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO risk_report_cache "
                "(snapshot_key, report_json, stress_json, computed_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(snapshot_key) DO UPDATE SET "
                "report_json = excluded.report_json, "
                "stress_json = excluded.stress_json, "
                "computed_at = excluded.computed_at",
                (
                    key,
                    json.dumps(report, ensure_ascii=False),
                    json.dumps(stress, ensure_ascii=False),
                    time.time(),
                ),
            )
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_risk_cache.py -v
git add alphapulse/webapp/store/risk_cache.py alphapulse/webapp/store/webapp_db.py tests/webapp/store/test_risk_cache.py
git commit -m "feat(webapp): RiskReportCache — 스냅샷 해시 기반 리스크 리포트 캐시"
```

---

### Task 4: ScreeningRepository

**Files:**
- Create: `alphapulse/webapp/store/screening.py`
- Modify: `alphapulse/webapp/store/webapp_db.py` (screening_runs 테이블)
- Test: `tests/webapp/store/test_screening.py`

- [ ] **Step 1: `webapp_db.py`에 테이블 추가**
```sql
CREATE TABLE IF NOT EXISTS screening_runs (
    run_id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    market TEXT NOT NULL,
    strategy TEXT NOT NULL,
    factor_weights TEXT NOT NULL,
    top_n INTEGER NOT NULL,
    market_context TEXT DEFAULT '{}',
    results TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_screening_user
    ON screening_runs(user_id, created_at DESC);
```

- [ ] **Step 2: 테스트**

```python
"""ScreeningRepository."""
import uuid

import pytest

from alphapulse.webapp.store.screening import ScreeningRepository


@pytest.fixture
def repo(webapp_db):
    return ScreeningRepository(db_path=webapp_db)


class TestScreening:
    def test_save_and_get(self, repo):
        rid = repo.save(
            name="test", market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 0.5, "value": 0.5},
            top_n=10, market_context={"pulse_signal": "moderately_bullish"},
            results=[{"code": "005930", "name": "삼성전자", "score": 85.0}],
            user_id=1,
        )
        run = repo.get(rid)
        assert run is not None
        assert run.market == "KOSPI"
        assert run.strategy == "momentum"
        assert run.top_n == 10
        assert run.factor_weights["momentum"] == 0.5
        assert len(run.results) == 1
        assert run.results[0]["code"] == "005930"

    def test_list_for_user(self, repo):
        rid1 = repo.save(
            name="r1", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        rid2 = repo.save(
            name="r2", market="KOSDAQ", strategy="value",
            factor_weights={}, top_n=20, market_context={},
            results=[], user_id=1,
        )
        rid3 = repo.save(
            name="other_user", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=2,
        )
        runs = repo.list_for_user(user_id=1, page=1, size=20)
        assert runs.total == 2
        assert {r.run_id for r in runs.items} == {rid1, rid2}

    def test_delete(self, repo):
        rid = repo.save(
            name="r", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        repo.delete(rid)
        assert repo.get(rid) is None

    def test_get_missing(self, repo):
        assert repo.get("missing") is None

    def test_pagination(self, repo):
        for i in range(25):
            repo.save(
                name=f"r{i}", market="KOSPI", strategy="momentum",
                factor_weights={}, top_n=10, market_context={},
                results=[], user_id=1,
            )
        p1 = repo.list_for_user(user_id=1, page=1, size=10)
        p3 = repo.list_for_user(user_id=1, page=3, size=10)
        assert p1.total == 25
        assert len(p1.items) == 10
        assert len(p3.items) == 5
```

- [ ] **Step 3: 구현**

```python
"""ScreeningRepository — webapp.db screening_runs CRUD."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScreeningRun:
    run_id: str
    name: str
    market: str
    strategy: str
    factor_weights: dict
    top_n: int
    market_context: dict
    results: list
    user_id: int
    tenant_id: int | None
    created_at: float


@dataclass
class Page:
    items: list[ScreeningRun] = field(default_factory=list)
    page: int = 1
    size: int = 20
    total: int = 0


def _row_to_run(row: sqlite3.Row) -> ScreeningRun:
    return ScreeningRun(
        run_id=row["run_id"],
        name=row["name"] or "",
        market=row["market"],
        strategy=row["strategy"],
        factor_weights=json.loads(row["factor_weights"]),
        top_n=row["top_n"],
        market_context=json.loads(row["market_context"] or "{}"),
        results=json.loads(row["results"]),
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
    )


class ScreeningRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def save(
        self,
        *,
        name: str,
        market: str,
        strategy: str,
        factor_weights: dict,
        top_n: int,
        market_context: dict,
        results: list,
        user_id: int,
        tenant_id: int | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO screening_runs "
                "(run_id, name, market, strategy, factor_weights, "
                "top_n, market_context, results, user_id, tenant_id, "
                "created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, name, market, strategy,
                    json.dumps(factor_weights, ensure_ascii=False),
                    top_n,
                    json.dumps(market_context, ensure_ascii=False),
                    json.dumps(results, ensure_ascii=False),
                    user_id, tenant_id, time.time(),
                ),
            )
        return run_id

    def get(self, run_id: str) -> ScreeningRun | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM screening_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row_to_run(row) if row else None

    def list_for_user(
        self, user_id: int, page: int = 1, size: int = 20,
    ) -> Page:
        offset = (page - 1) * size
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                "SELECT COUNT(*) FROM screening_runs WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM screening_runs WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, size, offset),
            ).fetchall()
        return Page(
            items=[_row_to_run(r) for r in rows],
            page=page, size=size, total=total,
        )

    def delete(self, run_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM screening_runs WHERE run_id = ?", (run_id,),
            )
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/store/test_screening.py -v
git add alphapulse/webapp/store/screening.py alphapulse/webapp/store/webapp_db.py tests/webapp/store/test_screening.py
git commit -m "feat(webapp): ScreeningRepository + screening_runs 테이블"
```

---

### Task 5: ScreeningRunner 서비스

**Files:**
- Create: `alphapulse/webapp/services/screening_runner.py`
- Test: `tests/webapp/services/test_screening_runner.py`

- [ ] **Step 1: 테스트 (Mock 기반 — 실제 스크리닝 실행 없음)**

```python
"""ScreeningRunner — CLI screen 로직 추출."""
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.webapp.services.screening_runner import run_screening_sync
from alphapulse.webapp.store.screening import ScreeningRepository


@pytest.fixture
def repo(webapp_db):
    return ScreeningRepository(db_path=webapp_db)


class TestScreeningRunner:
    @patch("alphapulse.webapp.services.screening_runner.TradingStore")
    @patch("alphapulse.webapp.services.screening_runner.FactorCalculator")
    @patch("alphapulse.webapp.services.screening_runner.MultiFactorRanker")
    @patch("alphapulse.webapp.services.screening_runner._load_universe")
    def test_runs_end_to_end(
        self, mock_load, mock_ranker_cls, mock_calc_cls, mock_store_cls,
        repo,
    ):
        from alphapulse.trading.core.models import Signal, Stock
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        mock_load.return_value = [stock]
        mock_calc = MagicMock()
        mock_calc.momentum.return_value = 50
        mock_calc.value.return_value = 30
        mock_calc.quality.return_value = 40
        mock_calc.growth.return_value = 50
        mock_calc.flow.return_value = 20
        mock_calc.volatility.return_value = 10
        mock_calc_cls.return_value = mock_calc
        mock_ranker = MagicMock()
        mock_ranker.rank.return_value = [
            Signal(
                stock=stock, score=80.0,
                factors={"momentum": 50}, strategy_id="momentum",
            ),
        ]
        mock_ranker_cls.return_value = mock_ranker

        progress = []
        def cb(cur, total, text=""):
            progress.append((cur, total, text))

        run_id = run_screening_sync(
            market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 0.5, "value": 0.5},
            top_n=10, name="test",
            screening_repo=repo, user_id=1,
            progress_callback=cb,
        )

        run = repo.get(run_id)
        assert run is not None
        assert run.market == "KOSPI"
        assert run.strategy == "momentum"
        assert len(run.results) == 1
        assert run.results[0]["code"] == "005930"
        assert run.results[0]["score"] == 80.0
        assert len(progress) >= 2

    def test_unknown_market_raises(self, repo):
        with pytest.raises(ValueError, match="market"):
            run_screening_sync(
                market="INVALID", strategy="momentum",
                factor_weights={}, top_n=10, name="",
                screening_repo=repo, user_id=1,
                progress_callback=lambda *a, **kw: None,
            )
```

- [ ] **Step 2: 구현**

```python
"""ScreeningRunner — Job에서 호출되는 스크리닝 실행 헬퍼.

기존 `ap trading screen` CLI 로직 추출. progress_callback으로 Job 연동.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.webapp.store.screening import ScreeningRepository


def _load_universe(market: str, store: TradingStore) -> list[Stock]:
    stocks = store.get_all_stocks()
    if market == "ALL":
        filtered = [s for s in stocks if s["market"] in ("KOSPI", "KOSDAQ")]
    elif market in ("KOSPI", "KOSDAQ"):
        filtered = [s for s in stocks if s["market"] == market]
    else:
        raise ValueError(f"unknown market: {market}")
    return [
        Stock(code=s["code"], name=s["name"], market=s["market"])
        for s in filtered
    ]


def run_screening_sync(
    *,
    market: str,
    strategy: str,
    factor_weights: dict[str, float],
    top_n: int,
    name: str,
    screening_repo: ScreeningRepository,
    user_id: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    store = TradingStore(db_path=cfg.TRADING_DB_PATH)

    progress_callback(0, 4, "유니버스 로드")
    universe = _load_universe(market, store)

    progress_callback(1, 4, "팩터 계산")
    calc = FactorCalculator(store)
    factor_data: dict[str, dict[str, float]] = {}
    for s in universe:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "growth": calc.growth(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    progress_callback(2, 4, "랭킹")
    ranker = MultiFactorRanker(weights=factor_weights)
    ranked = ranker.rank(universe, factor_data, strategy_id=strategy)
    top = ranked[:top_n]

    progress_callback(3, 4, "저장")
    market_context = _get_market_context()
    results = [
        {
            "code": sig.stock.code,
            "name": sig.stock.name,
            "market": sig.stock.market,
            "score": round(sig.score, 2),
            "factors": sig.factors,
        }
        for sig in top
    ]
    run_id = screening_repo.save(
        name=name or f"{market}_{strategy}",
        market=market, strategy=strategy,
        factor_weights=factor_weights, top_n=top_n,
        market_context=market_context, results=results,
        user_id=user_id,
    )

    progress_callback(4, 4, "완료")
    return run_id


def _get_market_context() -> dict:
    """Market Pulse 스냅샷 획득. 실패 시 빈 dict."""
    try:
        from alphapulse.market.engine.signal_engine import SignalEngine
        from alphapulse.trading.core.adapters import PulseResultAdapter
        engine = SignalEngine()
        pulse = engine.run()
        return PulseResultAdapter.to_market_context(pulse)
    except Exception:
        return {}
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/services/test_screening_runner.py -v
git add alphapulse/webapp/services/screening_runner.py tests/webapp/services/test_screening_runner.py
git commit -m "feat(webapp): ScreeningRunner — Job용 screen 실행 헬퍼"
```

---

### Task 6: Data Jobs 서비스

**Files:**
- Create: `alphapulse/webapp/services/data_jobs.py`
- Test: `tests/webapp/services/test_data_jobs.py`

- [ ] **Step 1: 테스트 (Mock 기반)**

```python
"""Data Jobs — update/collect-* Job wrappers."""
from unittest.mock import MagicMock, patch

import pytest

from alphapulse.webapp.services.data_jobs import (
    run_data_collect_financials,
    run_data_collect_short,
    run_data_collect_wisereport,
    run_data_update,
)


class TestDataJobs:
    @patch("alphapulse.webapp.services.data_jobs.BulkCollector")
    def test_update_calls_bulk_collector(self, mock_cls):
        inst = MagicMock()
        result = MagicMock()
        result.__dict__ = {
            "market": "KOSPI", "ohlcv_count": 10,
            "fundamentals_count": 0, "flow_count": 0,
            "wisereport_count": 0, "skipped": 0, "elapsed_seconds": 1.2,
        }
        inst.update.return_value = [result]
        mock_cls.return_value = inst

        cb = MagicMock()
        result_json = run_data_update(
            markets=["KOSPI"], progress_callback=cb,
        )
        assert inst.update.called
        assert "KOSPI" in result_json

    @patch("alphapulse.webapp.services.data_jobs.FundamentalCollector")
    def test_collect_financials(self, mock_cls):
        inst = MagicMock()
        inst.collect.return_value = {"collected": 50, "skipped": 2}
        mock_cls.return_value = inst
        cb = MagicMock()
        out = run_data_collect_financials(
            market="KOSPI", top=100, progress_callback=cb,
        )
        assert inst.collect.called
        assert "KOSPI" in out or "50" in out

    @patch("alphapulse.webapp.services.data_jobs.WisereportCollector")
    def test_collect_wisereport(self, mock_cls):
        inst = MagicMock()
        inst.collect_static_batch.return_value = ["005930", "000660"]
        mock_cls.return_value = inst
        cb = MagicMock()
        out = run_data_collect_wisereport(
            market="KOSPI", top=100, progress_callback=cb,
        )
        assert inst.collect_static_batch.called

    @patch("alphapulse.webapp.services.data_jobs.ShortCollector")
    def test_collect_short(self, mock_cls):
        inst = MagicMock()
        inst.collect.return_value = {"collected": 10}
        mock_cls.return_value = inst
        cb = MagicMock()
        run_data_collect_short(
            market="KOSPI", top=100, progress_callback=cb,
        )
        assert inst.collect.called
```

- [ ] **Step 2: 구현**

```python
"""Data Jobs — 기존 데이터 수집 모듈의 Job wrapper.

collect_all은 제공하지 않는다 (리소스 보호). CLI(`ap trading data collect`)에서만.
"""

from __future__ import annotations

import json
from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.data.bulk_collector import BulkCollector
from alphapulse.trading.data.fundamental_collector import FundamentalCollector
from alphapulse.trading.data.short_collector import ShortCollector
from alphapulse.trading.data.wisereport_collector import WisereportCollector


def run_data_update(
    *,
    markets: list[str],
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    collector = BulkCollector(db_path=cfg.TRADING_DB_PATH)
    progress_callback(0, 1, "증분 업데이트 시작")
    # BulkCollector는 progress_callback을 내부 print로 사용하므로
    # 여기서는 거친 단계만 콜백
    results = collector.update(markets=markets)
    progress_callback(1, 1, "완료")
    payload = [
        {
            "market": r.market,
            "ohlcv_count": r.ohlcv_count,
            "fundamentals_count": r.fundamentals_count,
            "flow_count": r.flow_count,
            "wisereport_count": r.wisereport_count,
            "skipped": r.skipped,
            "elapsed_seconds": r.elapsed_seconds,
        }
        for r in results
    ]
    return json.dumps(payload, ensure_ascii=False)


def run_data_collect_financials(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    collector = FundamentalCollector(db_path=cfg.TRADING_DB_PATH)
    progress_callback(0, 1, "재무제표 수집 중")
    today = _today()
    result = collector.collect(date=today, market=market)
    progress_callback(1, 1, "완료")
    return json.dumps({"market": market, **result}, ensure_ascii=False)


def run_data_collect_wisereport(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    from alphapulse.trading.data.store import TradingStore
    store = TradingStore(db_path=cfg.TRADING_DB_PATH)
    stocks = store.get_all_stocks()
    codes = [s["code"] for s in stocks if s["market"] == market][:top]
    collector = WisereportCollector(db_path=cfg.TRADING_DB_PATH)
    progress_callback(0, 1, f"wisereport {len(codes)}종목 수집 중")
    today = _today()
    results = collector.collect_static_batch(codes, today)
    progress_callback(1, 1, "완료")
    return json.dumps(
        {"market": market, "collected": len(results)}, ensure_ascii=False,
    )


def run_data_collect_short(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    collector = ShortCollector(db_path=cfg.TRADING_DB_PATH)
    progress_callback(0, 1, "공매도 수집 중")
    result = collector.collect(market=market, top=top)
    progress_callback(1, 1, "완료")
    return json.dumps({"market": market, **result}, ensure_ascii=False)


def _today() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d")
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/services/test_data_jobs.py -v
git add alphapulse/webapp/services/data_jobs.py tests/webapp/services/test_data_jobs.py
git commit -m "feat(webapp): DataJobs 서비스 — update / collect-financials / wisereport / short"
```

---

## Part B — Backend API

### Task 7: Portfolio API

**Files:**
- Create: `alphapulse/webapp/store/readers/portfolio.py`
- Create: `alphapulse/webapp/api/portfolio.py`
- Test: `tests/webapp/api/test_portfolio.py`

- [ ] **Step 1: PortfolioReader 어댑터 구현**

`alphapulse/webapp/store/readers/portfolio.py`:
```python
"""PortfolioStore 래핑 어댑터 — 웹 응답용 DTO."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from alphapulse.trading.portfolio.store import PortfolioStore


@dataclass
class SnapshotDTO:
    date: str
    cash: float
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions: list


@dataclass
class AttributionDTO:
    date: str
    strategy_returns: dict
    factor_returns: dict
    sector_returns: dict


class PortfolioReader:
    def __init__(self, db_path: str | Path) -> None:
        self.store = PortfolioStore(db_path=str(db_path))

    def get_latest(self, mode: str) -> SnapshotDTO | None:
        raw = self.store.get_latest_snapshot(mode=mode)
        if raw is None:
            return None
        return self._to_dto(raw)

    def get_history(
        self, mode: str, days: int,
    ) -> list[SnapshotDTO]:
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y%m%d")
        start = (
            datetime.now() - timedelta(days=days)
        ).strftime("%Y%m%d")
        rows = self.store.get_snapshots(start=start, end=end, mode=mode)
        return [self._to_dto(r) for r in rows]

    def get_attribution(self, mode: str, date: str) -> AttributionDTO | None:
        raw = self.store.get_attribution(date=date, mode=mode)
        if not raw:
            return None
        return AttributionDTO(
            date=raw["date"],
            strategy_returns=self._parse_json(raw.get("strategy_returns")),
            factor_returns=self._parse_json(raw.get("factor_returns")),
            sector_returns=self._parse_json(raw.get("sector_returns")),
        )

    @staticmethod
    def _parse_json(val) -> dict:
        if val is None:
            return {}
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return val

    @staticmethod
    def _to_dto(raw: dict) -> SnapshotDTO:
        positions = raw.get("positions", "[]")
        if isinstance(positions, str):
            try:
                positions = json.loads(positions)
            except json.JSONDecodeError:
                positions = []
        return SnapshotDTO(
            date=raw["date"],
            cash=raw["cash"],
            total_value=raw["total_value"],
            daily_return=raw["daily_return"],
            cumulative_return=raw["cumulative_return"],
            drawdown=raw["drawdown"],
            positions=positions or [],
        )
```

- [ ] **Step 2: Portfolio API 구현**

`alphapulse/webapp/api/portfolio.py`:
```python
"""Portfolio API — summary / history / attribution."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.users import User


router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


Mode = Literal["paper", "live", "backtest"]


class SnapshotResponse(BaseModel):
    date: str
    cash: float
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions: list


class HistoryResponse(BaseModel):
    items: list[SnapshotResponse]


class AttributionResponse(BaseModel):
    date: str
    strategy_returns: dict
    factor_returns: dict
    sector_returns: dict


def get_reader(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


@router.get("", response_model=SnapshotResponse | None)
async def get_portfolio(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    dto = reader.get_latest(mode=mode)
    if dto is None:
        return None
    return SnapshotResponse(**dto.__dict__)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    mode: Mode = "paper",
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    items = reader.get_history(mode=mode, days=days)
    return HistoryResponse(
        items=[SnapshotResponse(**d.__dict__) for d in items],
    )


@router.get("/attribution", response_model=AttributionResponse | None)
async def get_attribution(
    mode: Mode = "paper",
    date: str | None = None,
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    if not date:
        date = datetime.now().strftime("%Y%m%d")
    dto = reader.get_attribution(mode=mode, date=date)
    if dto is None:
        return None
    return AttributionResponse(**dto.__dict__)
```

- [ ] **Step 3: 테스트**

```python
"""Portfolio API 테스트."""
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.trading.portfolio.store import PortfolioStore
from alphapulse.webapp.api.portfolio import router as portfolio_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    portfolio_db = tmp_path / "portfolio.db"
    PortfolioStore(db_path=str(portfolio_db))

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
    app.state.portfolio_reader = PortfolioReader(db_path=portfolio_db)
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf_token(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(portfolio_router)
    app._portfolio_db = portfolio_db
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


def _seed_snapshot(db_path, date, total_value, mode="paper"):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots "
            "(date, mode, run_id, cash, total_value, positions, "
            "daily_return, cumulative_return, drawdown, created_at) "
            "VALUES (?, ?, '', ?, ?, '[]', 0.5, 2.0, 0.0, ?)",
            (date, mode, total_value * 0.1, total_value, time.time()),
        )


class TestPortfolio:
    def test_get_none_when_empty(self, client):
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200
        assert r.json() is None

    def test_get_latest(self, app, client):
        _seed_snapshot(app._portfolio_db, "20260420", 100_000_000)
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["total_value"] == 100_000_000

    def test_mode_filter(self, app, client):
        _seed_snapshot(app._portfolio_db, "20260420", 100_000_000, mode="paper")
        _seed_snapshot(app._portfolio_db, "20260420", 200_000_000, mode="live")
        r1 = client.get("/api/v1/portfolio?mode=paper")
        r2 = client.get("/api/v1/portfolio?mode=live")
        assert r1.json()["total_value"] == 100_000_000
        assert r2.json()["total_value"] == 200_000_000

    def test_history(self, app, client):
        for i, d in enumerate(["20260418", "20260419", "20260420"]):
            _seed_snapshot(app._portfolio_db, d, 100_000_000 + i * 1_000_000)
        r = client.get("/api/v1/portfolio/history?days=30")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/portfolio"
        )
        assert r.status_code == 401
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_portfolio.py -v
git add alphapulse/webapp/store/readers/portfolio.py alphapulse/webapp/api/portfolio.py tests/webapp/api/test_portfolio.py
git commit -m "feat(webapp): Portfolio API — summary / history / attribution (mode 지원)"
```

---

### Task 8: Risk API (report / stress / limits)

**Files:**
- Create: `alphapulse/webapp/store/readers/risk.py`
- Create: `alphapulse/webapp/api/risk.py`
- Test: `tests/webapp/api/test_risk.py`

- [ ] **Step 1: RiskReader 어댑터**

`alphapulse/webapp/store/readers/risk.py`:
```python
"""Risk 어댑터 — 캐싱 포함. RiskManager/StressTest 호출."""

from __future__ import annotations

from alphapulse.core.config import Config
from alphapulse.trading.core.models import PortfolioSnapshot
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.stress_test import StressTest
from alphapulse.trading.risk.var import VaRCalculator
from alphapulse.webapp.store.readers.portfolio import (
    PortfolioReader, SnapshotDTO,
)
from alphapulse.webapp.store.risk_cache import (
    CachedRiskReport, RiskReportCacheRepository,
)


class RiskReader:
    def __init__(
        self,
        portfolio_reader: PortfolioReader,
        cache: RiskReportCacheRepository,
    ) -> None:
        self.portfolio_reader = portfolio_reader
        self.cache = cache

    def get_report(self, mode: str) -> dict | None:
        snap = self.portfolio_reader.get_latest(mode=mode)
        if snap is None:
            return None
        key = self.cache.snapshot_key(
            date=snap.date, mode=mode, total_value=snap.total_value,
        )
        cached = self.cache.get(key)
        if cached:
            return {
                "report": cached.report, "stress": cached.stress,
                "computed_at": cached.computed_at, "cached": True,
            }
        cfg = Config()
        limits = RiskLimits(
            max_position_weight=cfg.MAX_POSITION_WEIGHT,
            max_drawdown_soft=cfg.MAX_DRAWDOWN_SOFT,
            max_drawdown_hard=cfg.MAX_DRAWDOWN_HARD,
        )
        mgr = RiskManager(
            limits=limits,
            var_calc=VaRCalculator(),
            drawdown_mgr=DrawdownManager(limits=limits),
        )
        snap_obj = self._to_snapshot(snap)
        report = mgr.daily_report(snap_obj)
        stress = StressTest().run_all(snap_obj)
        report_dict = {
            "drawdown_status": report.drawdown_status,
            "var_95": report.var_95,
            "cvar_95": report.cvar_95,
            "alerts": [
                {"level": a.level, "message": a.message}
                for a in (report.alerts or [])
            ],
        }
        self.cache.put(key=key, report=report_dict, stress=stress)
        return {
            "report": report_dict, "stress": stress,
            "cached": False,
        }

    def get_limits(self) -> dict:
        cfg = Config()
        return {
            "max_position_weight": cfg.MAX_POSITION_WEIGHT,
            "max_drawdown_soft": cfg.MAX_DRAWDOWN_SOFT,
            "max_drawdown_hard": cfg.MAX_DRAWDOWN_HARD,
            "max_daily_orders": cfg.MAX_DAILY_ORDERS,
            "max_daily_amount": cfg.MAX_DAILY_AMOUNT,
        }

    def run_custom_stress(self, mode: str, shocks: dict[str, float]) -> dict:
        snap = self.portfolio_reader.get_latest(mode=mode)
        if snap is None:
            return {}
        snap_obj = self._to_snapshot(snap)
        tester = StressTest()
        tester.add_custom_scenario(name="custom_user", shocks=shocks)
        result = tester.run(scenario="custom_user", snapshot=snap_obj)
        return {"custom_user": result}

    @staticmethod
    def _to_snapshot(dto: SnapshotDTO) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            date=dto.date, cash=dto.cash, positions=[],
            total_value=dto.total_value,
            daily_return=dto.daily_return,
            cumulative_return=dto.cumulative_return,
            drawdown=dto.drawdown,
        )
```

- [ ] **Step 2: Risk API**

`alphapulse/webapp/api/risk.py`:
```python
"""Risk API — report / stress / limits / custom stress."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

Mode = Literal["paper", "live", "backtest"]


class RiskReport(BaseModel):
    report: dict
    stress: dict
    cached: bool = False
    computed_at: float | None = None


class LimitsResponse(BaseModel):
    max_position_weight: float
    max_drawdown_soft: float
    max_drawdown_hard: float
    max_daily_orders: int
    max_daily_amount: int


class CustomStressRequest(BaseModel):
    mode: Mode = "paper"
    shocks: dict[str, float] = Field(
        description="시장별 충격 (예: {'KOSPI': -0.1, 'KOSDAQ': -0.15})",
    )


def get_reader(request: Request) -> RiskReader:
    return request.app.state.risk_reader


@router.get("/report", response_model=RiskReport | None)
async def get_report(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    data = reader.get_report(mode=mode)
    return data


@router.get("/stress", response_model=RiskReport | None)
async def get_stress(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    # 동일 API — 캐시된 stress 부분 포함
    return reader.get_report(mode=mode)


@router.post("/stress/custom")
async def run_custom_stress(
    body: CustomStressRequest,
    request: Request,
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    result = reader.run_custom_stress(mode=body.mode, shocks=body.shocks)
    try:
        request.app.state.audit.log(
            "webapp.risk.custom_stress",
            component="webapp",
            data={"mode": body.mode, "shocks": body.shocks},
            mode="live",
        )
    except AttributeError:
        pass
    return {"results": result}


@router.get("/limits", response_model=LimitsResponse)
async def get_limits(
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    return LimitsResponse(**reader.get_limits())
```

- [ ] **Step 3: 테스트**

```python
"""Risk API 테스트 — mock 기반."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.risk import router as risk_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import SnapshotDTO
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.risk_cache import RiskReportCacheRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    mock_portfolio = MagicMock()
    mock_portfolio.get_latest.return_value = SnapshotDTO(
        date="20260420", cash=10_000_000, total_value=100_000_000,
        daily_return=0.5, cumulative_return=2.0, drawdown=-1.0,
        positions=[],
    )
    cache = RiskReportCacheRepository(db_path=webapp_db)
    risk_reader = RiskReader(portfolio_reader=mock_portfolio, cache=cache)

    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.risk_reader = risk_reader
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(risk_router)
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


class TestRiskAPI:
    def test_report(self, client):
        r = client.get("/api/v1/risk/report?mode=paper")
        assert r.status_code == 200
        body = r.json()
        assert "report" in body
        assert "stress" in body

    def test_limits(self, client):
        r = client.get("/api/v1/risk/limits")
        assert r.status_code == 200
        body = r.json()
        assert body["max_position_weight"] > 0

    def test_custom_stress(self, client):
        r = client.post(
            "/api/v1/risk/stress/custom",
            json={"mode": "paper", "shocks": {"KOSPI": -0.1}},
        )
        assert r.status_code == 200
        assert "results" in r.json()

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/risk/report"
        )
        assert r.status_code == 401
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_risk.py -v
git add alphapulse/webapp/store/readers/risk.py alphapulse/webapp/api/risk.py tests/webapp/api/test_risk.py
git commit -m "feat(webapp): Risk API — report/stress/limits/custom (캐싱 연동)"
```

---

### Task 9: Custom Stress API (이미 Task 8에 포함)

Task 8에서 POST `/api/v1/risk/stress/custom`도 함께 구현됨. 별도 태스크로 분리하지 않고 Task 8에 통합.

**이 태스크는 건너뜀** (Task 8과 합쳐짐). 다음 번호를 Task 10으로 이어간다.

---

### Task 10: Screening API

**Files:**
- Create: `alphapulse/webapp/api/screening.py`
- Test: `tests/webapp/api/test_screening.py`

- [ ] **Step 1: API 구현**

```python
"""Screening API — 조회 / 실행 (Job) / 삭제."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.screening_runner import run_screening_sync
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.screening import ScreeningRepository
from alphapulse.webapp.store.users import User


router = APIRouter(prefix="/api/v1/screening", tags=["screening"])


class ScreeningRunRequest(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = "KOSPI"
    strategy: str = Field(default="momentum", max_length=40)
    factor_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 0.5, "value": 0.0, "quality": 0.0,
            "growth": 0.0, "flow": 0.3, "volatility": 0.2,
        },
    )
    top_n: int = Field(default=20, ge=1, le=100)
    name: str = Field(default="", max_length=100)


class ScreeningRunResponse(BaseModel):
    job_id: str


class RunSummary(BaseModel):
    run_id: str
    name: str
    market: str
    strategy: str
    top_n: int
    created_at: float


class RunListResponse(BaseModel):
    items: list[RunSummary]
    page: int
    size: int
    total: int


class RunDetailResponse(BaseModel):
    run_id: str
    name: str
    market: str
    strategy: str
    factor_weights: dict
    top_n: int
    market_context: dict
    results: list
    created_at: float


def get_repo(request: Request) -> ScreeningRepository:
    return request.app.state.screening_repo


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
):
    p = repo.list_for_user(user_id=user.id, page=page, size=size)
    return RunListResponse(
        items=[
            RunSummary(
                run_id=r.run_id, name=r.name,
                market=r.market, strategy=r.strategy,
                top_n=r.top_n, created_at=r.created_at,
            )
            for r in p.items
        ],
        page=p.page, size=p.size, total=p.total,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
):
    run = repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return RunDetailResponse(
        run_id=run.run_id, name=run.name,
        market=run.market, strategy=run.strategy,
        factor_weights=run.factor_weights, top_n=run.top_n,
        market_context=run.market_context,
        results=run.results, created_at=run.created_at,
    )


@router.post("/run", response_model=ScreeningRunResponse)
async def run_screening(
    body: ScreeningRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="screening",
        params=body.model_dump(),
        user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.screening.run",
            component="webapp",
            data={
                "user_id": user.id, "job_id": job_id,
                "market": body.market, "strategy": body.strategy,
            },
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_screening_sync,
            market=body.market, strategy=body.strategy,
            factor_weights=body.factor_weights,
            top_n=body.top_n, name=body.name,
            screening_repo=repo, user_id=user.id,
        )

    background_tasks.add_task(_run)
    return ScreeningRunResponse(job_id=job_id)


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    request: Request,
    user: User = Depends(require_role("admin")),
    repo: ScreeningRepository = Depends(get_repo),
):
    run = repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    repo.delete(run_id)
    try:
        request.app.state.audit.log(
            "webapp.screening.delete",
            component="webapp",
            data={"user_id": user.id, "run_id": run_id},
            mode="live",
        )
    except AttributeError:
        pass
    return {"ok": True}
```

- [ ] **Step 2: 테스트**

```python
"""Screening API 테스트."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.screening import router as screening_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.screening import ScreeningRepository
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
    app.state.job_runner = JobRunner(job_repo=app.state.jobs)
    app.state.screening_repo = ScreeningRepository(db_path=webapp_db)
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(screening_router)
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


class TestScreeningAPI:
    def test_list_empty(self, client):
        r = client.get("/api/v1/screening/runs")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_run_creates_job(self, app, client, monkeypatch):
        captured = {}

        def fake_run(*, progress_callback, **kwargs):
            captured.update(kwargs)
            progress_callback(1, 1, "done")
            return app.state.screening_repo.save(
                name=kwargs.get("name") or "t",
                market=kwargs["market"],
                strategy=kwargs["strategy"],
                factor_weights=kwargs["factor_weights"],
                top_n=kwargs["top_n"],
                market_context={}, results=[],
                user_id=kwargs["user_id"],
            )

        monkeypatch.setattr(
            "alphapulse.webapp.api.screening.run_screening_sync", fake_run,
        )
        r = client.post(
            "/api/v1/screening/run",
            json={
                "market": "KOSPI", "strategy": "momentum",
                "factor_weights": {"momentum": 1.0},
                "top_n": 10, "name": "test",
            },
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_invalid_market(self, client):
        r = client.post(
            "/api/v1/screening/run",
            json={"market": "INVALID", "strategy": "momentum"},
        )
        assert r.status_code == 422

    def test_delete_requires_admin(self, app, client):
        rid = app.state.screening_repo.save(
            name="t", market="KOSPI", strategy="momentum",
            factor_weights={}, top_n=10, market_context={},
            results=[], user_id=1,
        )
        r = client.delete(f"/api/v1/screening/runs/{rid}")
        assert r.status_code == 200

    def test_get_run(self, app, client):
        rid = app.state.screening_repo.save(
            name="t", market="KOSPI", strategy="momentum",
            factor_weights={"momentum": 1.0}, top_n=10,
            market_context={}, results=[{"code": "005930"}], user_id=1,
        )
        r = client.get(f"/api/v1/screening/runs/{rid}")
        assert r.status_code == 200
        assert r.json()["market"] == "KOSPI"
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_screening.py -v
git add alphapulse/webapp/api/screening.py tests/webapp/api/test_screening.py
git commit -m "feat(webapp): Screening API — list/detail/run(Job)/delete"
```

---

### Task 11: Data API

**Files:**
- Create: `alphapulse/webapp/store/readers/data_status.py`
- Create: `alphapulse/webapp/api/data.py`
- Test: `tests/webapp/api/test_data.py`

- [ ] **Step 1: DataStatusReader**

```python
"""Data 상태 조회 어댑터."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TableStatus:
    name: str
    row_count: int
    latest_date: str | None
    distinct_codes: int


class DataStatusReader:
    def __init__(self, trading_db_path: str | Path) -> None:
        self.db_path = Path(trading_db_path)

    def get_status(self) -> list[TableStatus]:
        targets = [
            ("ohlcv", "date", "code"),
            ("fundamentals_timeseries", "period", "code"),
            ("stock_investor_flow", "date", "code"),
            ("short_interest", "date", "code"),
            ("wisereport_data", "date", "code"),
        ]
        out: list[TableStatus] = []
        with sqlite3.connect(self.db_path) as conn:
            for table, date_col, code_col in targets:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*), MAX({date_col}), "
                        f"COUNT(DISTINCT {code_col}) FROM {table}"
                    ).fetchone()
                except sqlite3.OperationalError:
                    continue
                out.append(TableStatus(
                    name=table, row_count=row[0] or 0,
                    latest_date=row[1], distinct_codes=row[2] or 0,
                ))
        return out

    def detect_gaps(self, days: int = 5) -> list[dict]:
        """최근 N일 내 OHLCV 결측 종목 리스트."""
        from datetime import datetime, timedelta
        threshold = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT code, MAX(date) as max_date FROM ohlcv "
                "GROUP BY code HAVING max_date < ?",
                (threshold,),
            ).fetchall()
        return [{"code": r[0], "last_date": r[1]} for r in rows]
```

- [ ] **Step 2: Data API**

```python
"""Data API — status / scheduler / update / collect-*."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.data_jobs import (
    run_data_collect_financials,
    run_data_collect_short,
    run_data_collect_wisereport,
    run_data_update,
)
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.users import User


router = APIRouter(prefix="/api/v1/data", tags=["data"])


class UpdateRequest(BaseModel):
    markets: list[Literal["KOSPI", "KOSDAQ"]] = Field(
        default_factory=lambda: ["KOSPI"],
    )


class CollectRequest(BaseModel):
    market: Literal["KOSPI", "KOSDAQ"] = "KOSPI"
    top: int = Field(default=100, ge=1, le=500)


class JobCreatedResponse(BaseModel):
    job_id: str


def get_reader(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def _audit(request, action, data):
    try:
        request.app.state.audit.log(
            action, component="webapp", data=data, mode="live",
        )
    except AttributeError:
        pass


@router.get("/status")
async def get_status(
    gap_days: int = Query(5, ge=1, le=30),
    _: User = Depends(get_current_user),
    reader: DataStatusReader = Depends(get_reader),
):
    return {
        "tables": [t.__dict__ for t in reader.get_status()],
        "gaps": reader.detect_gaps(days=gap_days),
    }


@router.post("/update", response_model=JobCreatedResponse)
async def update(
    body: UpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "update", "markets": body.markets, "job_id": job_id})

    async def _run():
        await runner.run(job_id, run_data_update, markets=body.markets)

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-financials", response_model=JobCreatedResponse)
async def collect_financials(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_financials", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_financials,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-wisereport", response_model=JobCreatedResponse)
async def collect_wisereport(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_wisereport", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_wisereport,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-short", response_model=JobCreatedResponse)
async def collect_short(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_short", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_short,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)
```

- [ ] **Step 3: 테스트 (핵심만)**

```python
"""Data API 테스트."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.data import router as data_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    import sqlite3
    trading_db = tmp_path / "trading.db"
    with sqlite3.connect(trading_db) as conn:
        conn.execute(
            "CREATE TABLE ohlcv (code TEXT, date TEXT, close REAL)"
        )
        conn.execute(
            "INSERT INTO ohlcv VALUES ('005930', '20260420', 70000)"
        )
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
    app.state.data_status_reader = DataStatusReader(trading_db_path=trading_db)
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(data_router)
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


class TestDataAPI:
    def test_status(self, client):
        r = client.get("/api/v1/data/status")
        assert r.status_code == 200
        assert "tables" in r.json()
        assert "gaps" in r.json()

    def test_update_creates_job(self, client, monkeypatch):
        def fake(*, progress_callback, **kwargs):
            progress_callback(1, 1, "done")
            return "{}"
        monkeypatch.setattr(
            "alphapulse.webapp.api.data.run_data_update", fake,
        )
        r = client.post(
            "/api/v1/data/update",
            json={"markets": ["KOSPI"]},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_no_collect_all_endpoint(self, client):
        r = client.post("/api/v1/data/collect_all", json={})
        assert r.status_code == 404
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_data.py -v
git add alphapulse/webapp/store/readers/data_status.py alphapulse/webapp/api/data.py tests/webapp/api/test_data.py
git commit -m "feat(webapp): Data API — status/update/collect-* (collect_all 미제공)"
```

---

### Task 12: Settings API

**Files:**
- Create: `alphapulse/webapp/api/settings.py`
- Test: `tests/webapp/api/test_settings.py`

- [ ] **Step 1: API 구현**

```python
"""Settings API — category 조회 / 개별 수정 (비밀번호 재확인)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.auth.security import verify_password
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.settings import SettingsRepository
from alphapulse.webapp.store.users import User, UserRepository


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


Category = Literal["api_key", "risk_limit", "notification", "backtest"]


class SettingView(BaseModel):
    key: str
    value: str            # 마스킹된 표시용
    is_secret: bool
    category: str
    updated_at: float
    updated_by: int | None


class SettingsListResponse(BaseModel):
    items: list[SettingView]


class UpdateSettingRequest(BaseModel):
    value: str = Field(min_length=1, max_length=10000)
    current_password: str = Field(min_length=1, max_length=256)


def get_repo(request: Request) -> SettingsRepository:
    return request.app.state.settings_repo


def get_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_users(request: Request) -> UserRepository:
    return request.app.state.users


@router.get("", response_model=SettingsListResponse)
async def list_settings(
    category: Category,
    user: User = Depends(require_role("admin")),
    repo: SettingsRepository = Depends(get_repo),
    svc: SettingsService = Depends(get_service),
):
    entries = repo.list_by_category(category)
    items: list[SettingView] = []
    for e in entries:
        raw = repo.get(e.key) or ""
        display = SettingsService.mask(raw) if e.is_secret else raw
        items.append(SettingView(
            key=e.key, value=display,
            is_secret=e.is_secret, category=e.category,
            updated_at=e.updated_at, updated_by=e.updated_by,
        ))
    return SettingsListResponse(items=items)


@router.put("/{key}")
async def update_setting(
    key: str,
    body: UpdateSettingRequest,
    request: Request,
    user: User = Depends(require_role("admin")),
    repo: SettingsRepository = Depends(get_repo),
    users: UserRepository = Depends(get_users),
):
    # 비밀번호 재확인
    current = users.get_by_id(user.id)
    if current is None or not verify_password(
        body.current_password, current.password_hash,
    ):
        raise HTTPException(
            status_code=401, detail="Current password incorrect",
        )
    existing = repo.list_all()
    match = next((e for e in existing if e.key == key), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    old_val = repo.get(key) or ""
    repo.set(
        key=key, value=body.value,
        is_secret=match.is_secret, category=match.category,
        user_id=user.id,
    )
    try:
        import hashlib
        request.app.state.audit.log(
            "webapp.settings.update",
            component="webapp",
            data={
                "key": key, "category": match.category,
                "user_id": user.id,
                "old_hash": hashlib.sha256(
                    old_val.encode("utf-8"),
                ).hexdigest()[:8],
                "new_hash": hashlib.sha256(
                    body.value.encode("utf-8"),
                ).hexdigest()[:8],
            },
            mode="live",
        )
    except AttributeError:
        pass
    return {"ok": True}
```

- [ ] **Step 2: 테스트**

```python
"""Settings API 테스트."""
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.settings import router as settings_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.settings import SettingsRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(webapp_db):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    fkey = Fernet.generate_key()
    repo = SettingsRepository(db_path=webapp_db, fernet_key=fkey)
    svc = SettingsService(repo=repo)
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.settings_repo = repo
    app.state.settings_service = svc
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(settings_router)
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


class TestSettings:
    def test_list_masks_secrets(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="super-secret-12345",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.get("/api/v1/settings?category=api_key")
        assert r.status_code == 200
        items = r.json()["items"]
        assert items[0]["value"] != "super-secret-12345"
        assert "****" in items[0]["value"]

    def test_update_requires_correct_password(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="old",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.put(
            "/api/v1/settings/KIS_APP_KEY",
            json={"value": "new", "current_password": "wrong"},
        )
        assert r.status_code == 401

    def test_update_success(self, app, client):
        app.state.settings_repo.set(
            key="KIS_APP_KEY", value="old",
            is_secret=True, category="api_key", user_id=1,
        )
        r = client.put(
            "/api/v1/settings/KIS_APP_KEY",
            json={
                "value": "new-value", "current_password": "long-enough-pw!",
            },
        )
        assert r.status_code == 200
        assert app.state.settings_repo.get("KIS_APP_KEY") == "new-value"

    def test_update_unknown_key_404(self, client):
        r = client.put(
            "/api/v1/settings/UNKNOWN_KEY",
            json={"value": "x", "current_password": "long-enough-pw!"},
        )
        assert r.status_code == 404
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_settings.py -v
git add alphapulse/webapp/api/settings.py tests/webapp/api/test_settings.py
git commit -m "feat(webapp): Settings API — category 조회 + 개별 수정 (비밀번호 재확인)"
```

---

### Task 13: Audit API

**Files:**
- Create: `alphapulse/webapp/store/readers/audit.py`
- Create: `alphapulse/webapp/api/audit.py`
- Test: `tests/webapp/api/test_audit.py`

- [ ] **Step 1: AuditReader 어댑터**

```python
"""AuditLog 조회 어댑터 (data/audit.db)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuditEvent:
    id: int
    timestamp: float
    event_type: str
    component: str
    data: dict
    mode: str


class AuditReader:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def query(
        self,
        from_ts: float | None = None,
        to_ts: float | None = None,
        actor_email: str | None = None,
        action_prefix: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        where = []
        params: list = []
        if from_ts is not None:
            where.append("timestamp >= ?")
            params.append(from_ts)
        if to_ts is not None:
            where.append("timestamp <= ?")
            params.append(to_ts)
        if action_prefix:
            where.append("event_type LIKE ?")
            params.append(f"{action_prefix}%")
        where_sql = " AND ".join(where) if where else "1=1"
        offset = (page - 1) * size
        if not self.db_path.exists():
            return {"items": [], "page": page, "size": size, "total": 0}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM audit_log WHERE {where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM audit_log WHERE {where_sql} "
                f"ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                [*params, size, offset],
            ).fetchall()
        events = []
        for r in rows:
            data = self._parse_json(r["data"] if "data" in r.keys() else None)
            if actor_email:
                if data.get("email") != actor_email:
                    continue
            events.append(AuditEvent(
                id=r["id"],
                timestamp=r["timestamp"],
                event_type=r["event_type"],
                component=r["component"] if "component" in r.keys() else "",
                data=data,
                mode=r["mode"] if "mode" in r.keys() else "",
            ))
        return {
            "items": events, "page": page, "size": size, "total": total,
        }

    @staticmethod
    def _parse_json(val) -> dict:
        if not val:
            return {}
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return val
```

- [ ] **Step 2: Audit API**

```python
"""Audit API — 감사 로그 조회."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import require_role
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.users import User


router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: int
    timestamp: float
    event_type: str
    component: str
    data: dict
    mode: str


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    page: int
    size: int
    total: int


def get_reader(request: Request) -> AuditReader:
    return request.app.state.audit_reader


@router.get("/events", response_model=AuditListResponse)
async def list_events(
    from_ts: float | None = None,
    to_ts: float | None = None,
    actor: str | None = None,
    action_prefix: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _: User = Depends(require_role("admin")),
    reader: AuditReader = Depends(get_reader),
):
    result = reader.query(
        from_ts=from_ts, to_ts=to_ts,
        actor_email=actor, action_prefix=action_prefix,
        page=page, size=size,
    )
    items = [
        AuditEventResponse(
            id=e.id, timestamp=e.timestamp, event_type=e.event_type,
            component=e.component, data=e.data, mode=e.mode,
        )
        for e in result["items"]
    ]
    return AuditListResponse(
        items=items, page=result["page"],
        size=result["size"], total=result["total"],
    )
```

- [ ] **Step 3: 테스트**

```python
"""Audit API 테스트."""
import sqlite3
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.audit import router as audit_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def app(tmp_path, webapp_db):
    audit_db = tmp_path / "audit.db"
    with sqlite3.connect(audit_db) as conn:
        conn.execute(
            "CREATE TABLE audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "timestamp REAL NOT NULL,"
            "event_type TEXT NOT NULL,"
            "component TEXT,"
            "data TEXT,"
            "mode TEXT)"
        )
        for i, ev in enumerate([
            "webapp.login_success", "webapp.backtest_run",
            "webapp.settings.update",
        ]):
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, component, "
                "data, mode) VALUES (?, ?, ?, ?, ?)",
                (time.time() - i, ev, "webapp", "{}", "live"),
            )

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
    app.state.audit_reader = AuditReader(db_path=audit_db)
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(audit_router)
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


class TestAudit:
    def test_list(self, client):
        r = client.get("/api/v1/audit/events")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_filter_by_action_prefix(self, client):
        r = client.get("/api/v1/audit/events?action_prefix=webapp.settings")
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(
            ev["event_type"].startswith("webapp.settings") for ev in items
        )

    def test_requires_admin(self, app):
        app.state.users.create(
            email="u@x.com",
            password_hash=hash_password("long-enough-pw!"),
            role="user",
        )
        c = TestClient(app, base_url="https://testserver")
        t = c.get("/api/v1/csrf-token").json()["token"]
        c.post(
            "/api/v1/auth/login",
            json={"email": "u@x.com", "password": "long-enough-pw!"},
            headers={"X-CSRF-Token": t},
        )
        r = c.get("/api/v1/audit/events")
        assert r.status_code == 403
```

- [ ] **Step 4: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_audit.py -v
git add alphapulse/webapp/store/readers/audit.py alphapulse/webapp/api/audit.py tests/webapp/api/test_audit.py
git commit -m "feat(webapp): Audit API — 감사 로그 조회 (admin only)"
```

---

### Task 14: Dashboard home API

**Files:**
- Create: `alphapulse/webapp/api/dashboard.py`
- Test: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 1: API 구현**

```python
"""Dashboard home — 여러 도메인 aggregate 1회 호출."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class HomeResponse(BaseModel):
    portfolio: dict | None
    portfolio_history: list
    risk: dict | None
    data_status: dict
    recent_backtests: list
    recent_audits: list


def get_portfolio(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


def get_risk(request: Request) -> RiskReader:
    return request.app.state.risk_reader


def get_data(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_audit(request: Request) -> AuditReader:
    return request.app.state.audit_reader


@router.get("/home", response_model=HomeResponse)
async def home(
    request: Request,
    _: User = Depends(get_current_user),
    portfolio: PortfolioReader = Depends(get_portfolio),
    risk: RiskReader = Depends(get_risk),
    data: DataStatusReader = Depends(get_data),
    audit: AuditReader = Depends(get_audit),
):
    mode = "paper"
    snap = portfolio.get_latest(mode=mode)
    history = portfolio.get_history(mode=mode, days=30)
    risk_data = risk.get_report(mode=mode) if snap else None
    bt_store = request.app.state.backtest_reader
    recent_bt = bt_store.list_runs(page=1, size=3)
    audit_result = audit.query(page=1, size=10)

    return HomeResponse(
        portfolio=snap.__dict__ if snap else None,
        portfolio_history=[s.__dict__ for s in history],
        risk=risk_data,
        data_status={
            "tables": [t.__dict__ for t in data.get_status()],
            "gaps_count": len(data.detect_gaps(days=5)),
        },
        recent_backtests=[s.__dict__ for s in recent_bt.items],
        recent_audits=[e.__dict__ for e in audit_result["items"]],
    )
```

- [ ] **Step 2: 테스트**

```python
"""Dashboard home API — aggregation."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.dashboard import router as dash_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.portfolio import SnapshotDTO
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

    # Readers mocks
    portfolio = MagicMock()
    portfolio.get_latest.return_value = SnapshotDTO(
        date="20260420", cash=10_000_000, total_value=100_000_000,
        daily_return=0.5, cumulative_return=2.0, drawdown=-1.0,
        positions=[],
    )
    portfolio.get_history.return_value = []
    app.state.portfolio_reader = portfolio

    risk = MagicMock()
    risk.get_report.return_value = {
        "report": {"var_95": -2.5}, "stress": {}, "cached": False,
    }
    app.state.risk_reader = risk

    data = MagicMock()
    data.get_status.return_value = []
    data.detect_gaps.return_value = []
    app.state.data_status_reader = data

    audit = MagicMock()
    audit.query.return_value = {
        "items": [], "page": 1, "size": 10, "total": 0,
    }
    app.state.audit_reader = audit

    bt = MagicMock()
    listing = MagicMock()
    listing.items = []
    bt.list_runs.return_value = listing
    app.state.backtest_reader = bt

    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="admin",
    )

    @app.get("/api/v1/csrf-token")
    async def csrf(request):  # noqa: ANN001
        return {"token": request.state.csrf_token}

    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(dash_router)
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


class TestHome:
    def test_aggregates(self, client):
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["portfolio"]["total_value"] == 100_000_000
        assert body["risk"]["report"]["var_95"] == -2.5
        assert "tables" in body["data_status"]

    def test_requires_auth(self, app):
        r = TestClient(app, base_url="https://testserver").get(
            "/api/v1/dashboard/home",
        )
        assert r.status_code == 401
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/api/test_dashboard.py -v
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): Dashboard home API — portfolio/risk/data/backtest/audit aggregate"
```

---

## Part C — Backend CLI & Migration

### Task 15: `ap webapp init-encrypt-key` / `rotate-encrypt-key` / `set` / `list`

**Files:**
- Modify: `alphapulse/webapp/cli.py` (명령 4개 추가)
- Test: `tests/webapp/test_cli_webapp_settings.py`

- [ ] **Step 1: CLI 확장**

`alphapulse/webapp/cli.py` 하단에 명령 추가:
```python
# === Task 15: settings 관련 명령 ===

from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.settings import SettingsRepository


def _get_fernet_key() -> bytes:
    key = os.environ.get("WEBAPP_ENCRYPT_KEY", "").strip()
    if not key:
        click.echo(
            "WEBAPP_ENCRYPT_KEY not set. "
            "Run `ap webapp init-encrypt-key` first.", err=True,
        )
        sys.exit(1)
    return key.encode("utf-8")


@webapp.command("init-encrypt-key")
def init_encrypt_key() -> None:
    """새 Fernet 키 생성 — .env에 수동 추가."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode("utf-8")
    click.echo("Generated WEBAPP_ENCRYPT_KEY:")
    click.echo("")
    click.echo(f"  {key}")
    click.echo("")
    click.echo("다음 줄을 .env에 수동 추가하세요:")
    click.echo(f"WEBAPP_ENCRYPT_KEY={key}")
    click.echo("")
    click.echo("주의: 키 분실 시 DB의 암호화 값 복구 불가.")


@webapp.command("rotate-encrypt-key")
@click.option("--new-key", required=True, help="새 키 (base64)")
def rotate_encrypt_key(new_key: str) -> None:
    """기존 키로 복호화 → 새 키로 재암호화."""
    from cryptography.fernet import Fernet
    old_key = _get_fernet_key()
    db = _db_path()
    old_repo = SettingsRepository(db_path=db, fernet_key=old_key)
    new_repo = SettingsRepository(db_path=db, fernet_key=new_key.encode("utf-8"))
    entries = old_repo.list_all()
    for e in entries:
        plain = old_repo.get(e.key)
        if plain is not None:
            new_repo.set(
                key=e.key, value=plain,
                is_secret=e.is_secret, category=e.category,
                user_id=e.updated_by or 0,
                tenant_id=e.tenant_id,
            )
    click.echo(f"Rotated {len(entries)} settings.")
    click.echo(
        "이제 .env의 WEBAPP_ENCRYPT_KEY를 새 키로 교체하세요.",
    )


@webapp.command("set")
@click.option("--key", required=True)
@click.option("--value", required=True)
@click.option("--category", required=True,
              type=click.Choice(
                  ["api_key", "risk_limit", "notification", "backtest"],
              ))
@click.option("--secret/--plain", default=False)
def set_setting(
    key: str, value: str, category: str, secret: bool,
) -> None:
    """설정 값을 DB에 저장."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    repo.set(
        key=key, value=value,
        is_secret=secret, category=category, user_id=0,
    )
    click.echo(f"Set: {key}")


@webapp.command("list")
@click.option("--category", default=None,
              type=click.Choice(
                  ["api_key", "risk_limit", "notification", "backtest"],
              ))
def list_settings(category: str | None) -> None:
    """DB에 저장된 설정 목록 (secret은 마스킹)."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    entries = repo.list_by_category(category) if category else repo.list_all()
    if not entries:
        click.echo("설정 없음.")
        return
    click.echo(f"{'category':<15} {'key':<30} {'value':<30}")
    click.echo(f"{'-'*15} {'-'*30} {'-'*30}")
    for e in entries:
        val = repo.get(e.key) or ""
        display = SettingsService.mask(val) if e.is_secret else val
        click.echo(f"{e.category:<15} {e.key:<30} {display:<30}")
```

- [ ] **Step 2: 테스트**

```python
"""ap webapp settings CLI."""
import os

from click.testing import CliRunner
from cryptography.fernet import Fernet

from alphapulse.cli import cli


def test_init_encrypt_key_prints_key(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    r = CliRunner().invoke(cli, ["webapp", "init-encrypt-key"])
    assert r.exit_code == 0
    assert "WEBAPP_ENCRYPT_KEY=" in r.output


def test_set_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)

    r1 = CliRunner().invoke(
        cli,
        ["webapp", "set",
         "--key", "KIS_APP_KEY", "--value", "myvalue",
         "--category", "api_key", "--secret"],
    )
    assert r1.exit_code == 0

    r2 = CliRunner().invoke(
        cli, ["webapp", "list", "--category", "api_key"],
    )
    assert r2.exit_code == 0
    assert "KIS_APP_KEY" in r2.output
    assert "myvalue" not in r2.output  # 마스킹


def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)
    r = CliRunner().invoke(cli, ["webapp", "list"])
    assert r.exit_code == 0
    assert "설정 없음" in r.output or "None" in r.output or "설정" in r.output


def test_rotate_encrypt_key(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    old_k = Fernet.generate_key().decode("utf-8")
    new_k = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", old_k)
    # seed
    CliRunner().invoke(cli, [
        "webapp", "set", "--key", "K", "--value", "v",
        "--category", "risk_limit", "--plain",
    ])
    r = CliRunner().invoke(
        cli,
        ["webapp", "rotate-encrypt-key", "--new-key", new_k],
    )
    assert r.exit_code == 0
    assert "Rotated" in r.output
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/test_cli_webapp_settings.py -v
git add alphapulse/webapp/cli.py tests/webapp/test_cli_webapp_settings.py
git commit -m "feat(webapp): ap webapp init/rotate/set/list 명령"
```

---

### Task 16: `ap webapp import-env`

**Files:**
- Modify: `alphapulse/webapp/cli.py` (import-env 명령 추가)
- Test: `tests/webapp/test_cli_webapp_settings.py` (테스트 추가)

- [ ] **Step 1: CLI 명령 추가**

```python
_IMPORT_WHITELIST = {
    # (env key, category, is_secret)
    "KIS_APP_KEY": ("api_key", True),
    "KIS_APP_SECRET": ("api_key", True),
    "KIS_ACCOUNT_NO": ("api_key", True),
    "GEMINI_API_KEY": ("api_key", True),
    "TELEGRAM_BOT_TOKEN": ("notification", True),
    "TELEGRAM_CHANNEL_ID": ("notification", True),
    "TELEGRAM_MONITOR_BOT_TOKEN": ("notification", True),
    "TELEGRAM_MONITOR_CHANNEL_ID": ("notification", True),
    "MAX_POSITION_WEIGHT": ("risk_limit", False),
    "MAX_DRAWDOWN_SOFT": ("risk_limit", False),
    "MAX_DRAWDOWN_HARD": ("risk_limit", False),
    "MAX_DAILY_ORDERS": ("risk_limit", False),
    "MAX_DAILY_AMOUNT": ("risk_limit", False),
    "BACKTEST_COMMISSION": ("backtest", False),
    "BACKTEST_TAX": ("backtest", False),
    "BACKTEST_INITIAL_CAPITAL": ("backtest", False),
    "STRATEGY_ALLOCATIONS": ("backtest", False),
}


@webapp.command("import-env")
@click.option("--dry-run", is_flag=True, help="실제 쓰기 없이 변경 목록만 출력")
def import_env(dry_run: bool) -> None:
    """화이트리스트 키를 .env → DB로 이관. 이미 DB에 있으면 skip."""
    fkey = _get_fernet_key()
    repo = SettingsRepository(db_path=_db_path(), fernet_key=fkey)
    existing_keys = {e.key for e in repo.list_all()}

    to_import: list[tuple[str, str, str, bool]] = []
    for env_key, (category, is_secret) in _IMPORT_WHITELIST.items():
        val = os.environ.get(env_key)
        if val is None or not val.strip():
            continue
        if env_key in existing_keys:
            continue
        to_import.append((env_key, val, category, is_secret))

    if dry_run:
        click.echo(f"[dry-run] {len(to_import)} 키 이관 예정:")
        for k, _, cat, _ in to_import:
            click.echo(f"  {cat:<15} {k}")
        return

    for k, v, cat, secret in to_import:
        repo.set(
            key=k, value=v,
            is_secret=secret, category=cat, user_id=0,
        )

    click.echo(f"Imported {len(to_import)} settings from .env.")
```

- [ ] **Step 2: 테스트 추가**

```python
def test_import_env_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)
    monkeypatch.setenv("KIS_APP_KEY", "fake-key")
    r = CliRunner().invoke(cli, ["webapp", "import-env", "--dry-run"])
    assert r.exit_code == 0
    assert "KIS_APP_KEY" in r.output


def test_import_env_actual(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)
    monkeypatch.setenv("KIS_APP_KEY", "fake-key")
    monkeypatch.setenv("MAX_POSITION_WEIGHT", "0.15")
    r = CliRunner().invoke(cli, ["webapp", "import-env"])
    assert r.exit_code == 0
    # list로 확인
    r2 = CliRunner().invoke(cli, ["webapp", "list"])
    assert "KIS_APP_KEY" in r2.output
    assert "MAX_POSITION_WEIGHT" in r2.output


def test_import_env_skips_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEBAPP_DB_PATH", str(tmp_path / "webapp.db"))
    fk = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("WEBAPP_ENCRYPT_KEY", fk)
    monkeypatch.setenv("KIS_APP_KEY", "from-env")
    # seed DB with different value
    CliRunner().invoke(cli, [
        "webapp", "set", "--key", "KIS_APP_KEY", "--value", "from-db",
        "--category", "api_key", "--secret",
    ])
    CliRunner().invoke(cli, ["webapp", "import-env"])
    # DB 값 유지 확인
    from alphapulse.webapp.store.settings import SettingsRepository
    from cryptography.fernet import Fernet
    repo = SettingsRepository(
        db_path=tmp_path / "webapp.db",
        fernet_key=fk.encode("utf-8"),
    )
    assert repo.get("KIS_APP_KEY") == "from-db"
```

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/test_cli_webapp_settings.py -v
git add alphapulse/webapp/cli.py tests/webapp/test_cli_webapp_settings.py
git commit -m "feat(webapp): ap webapp import-env — 화이트리스트 .env → DB 이관"
```

---

### Task 16.5: main.py 통합 (신규 라우터 + state 주입)

이 태스크는 Part B/C 결과를 main.py에 연결한다. Task 16 직후 실행.

**Files:**
- Modify: `alphapulse/webapp/main.py`

- [ ] **Step 1: main.py의 `create_app()` 수정**

신규 state + 라우터 등록:
```python
# imports 추가
from cryptography.fernet import Fernet
from alphapulse.webapp.api.audit import router as audit_router
from alphapulse.webapp.api.dashboard import router as dashboard_router
from alphapulse.webapp.api.data import router as data_router
from alphapulse.webapp.api.portfolio import router as portfolio_router
from alphapulse.webapp.api.risk import router as risk_router
from alphapulse.webapp.api.screening import router as screening_router
from alphapulse.webapp.api.settings import router as settings_router
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.risk_cache import RiskReportCacheRepository
from alphapulse.webapp.store.screening import ScreeningRepository
from alphapulse.webapp.store.settings import SettingsRepository

# create_app 내부에서 Phase 1 state 뒤에 추가:
fernet_key_raw = os.environ.get("WEBAPP_ENCRYPT_KEY", "")
if fernet_key_raw:
    fernet_key = fernet_key_raw.encode("utf-8")
    settings_repo = SettingsRepository(db_path=db_path, fernet_key=fernet_key)
    settings_service = SettingsService(repo=settings_repo)
    app.state.settings_repo = settings_repo
    app.state.settings_service = settings_service
    # startup에서 load_env_overrides 호출
else:
    logger.warning("WEBAPP_ENCRYPT_KEY not set; settings API disabled")
    app.state.settings_repo = None
    app.state.settings_service = None

app.state.portfolio_reader = PortfolioReader(
    db_path=core.DATA_DIR / "portfolio.db",
)
app.state.risk_cache = RiskReportCacheRepository(db_path=db_path)
app.state.risk_reader = RiskReader(
    portfolio_reader=app.state.portfolio_reader,
    cache=app.state.risk_cache,
)
app.state.screening_repo = ScreeningRepository(db_path=db_path)
app.state.data_status_reader = DataStatusReader(
    trading_db_path=core.DATA_DIR / "trading.db",
)
app.state.audit_reader = AuditReader(db_path=core.DATA_DIR / "audit.db")

# 라우터 등록
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(screening_router)
app.include_router(data_router)
if app.state.settings_service is not None:
    app.include_router(settings_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
```

lifespan 훅 수정 — startup 시 `load_env_overrides` 호출:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    n = recover_orphans(job_repo=jobs)
    if n:
        # ...existing code...
    # Phase 2: DB → os.environ 오버라이드
    if app.state.settings_service is not None:
        try:
            app.state.settings_service.load_env_overrides()
            logger.info("Settings loaded from DB to os.environ")
        except Exception:
            logger.exception("Failed to load settings overrides")
    await monitor.send(
        "INFO", "AlphaPulse webapp started", "FastAPI 앱이 기동되었습니다.",
    )
    yield
    # ...existing shutdown...
```

- [ ] **Step 2: 기존 test_main.py에서 신규 라우터 확인**

기존 `test_app_has_all_routers` 테스트 업데이트. 새 경로 추가 확인:
- `/api/v1/portfolio`
- `/api/v1/risk/report`
- `/api/v1/screening/runs`
- `/api/v1/data/status`
- `/api/v1/audit/events`
- `/api/v1/dashboard/home`

(WEBAPP_ENCRYPT_KEY 없이도 나머지 라우터는 등록되어야 한다.)

- [ ] **Step 3: 테스트 + 커밋**
```bash
pytest tests/webapp/test_main.py -v
git add alphapulse/webapp/main.py tests/webapp/test_main.py
git commit -m "feat(webapp): main.py — Phase 2 라우터 + state + settings startup 훅"
```

---

## Part D — Frontend Common

### Task 17: `useMode` hook + `ModeSelector` + topbar

**Files:**
- Create: `webapp-ui/hooks/use-mode.ts`
- Create: `webapp-ui/components/layout/mode-selector.tsx`
- Modify: `webapp-ui/components/layout/topbar.tsx` (ModeSelector 삽입)
- Modify: `webapp-ui/lib/types.ts` (Mode 타입 추가)

- [ ] **Step 1: `lib/types.ts`에 Mode 타입 추가**

기존 파일 하단에 추가:
```typescript
export type Mode = "paper" | "live" | "backtest"
```

- [ ] **Step 2: `hooks/use-mode.ts`**

```typescript
"use client"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { useCallback } from "react"
import type { Mode } from "@/lib/types"

const MODES: Mode[] = ["paper", "live", "backtest"]

export function useMode(): {
  mode: Mode
  setMode: (m: Mode) => void
} {
  const params = useSearchParams()
  const router = useRouter()
  const path = usePathname()
  const raw = params.get("mode") ?? "paper"
  const mode: Mode = MODES.includes(raw as Mode) ? (raw as Mode) : "paper"

  const setMode = useCallback(
    (m: Mode) => {
      const sp = new URLSearchParams(params.toString())
      sp.set("mode", m)
      router.replace(`${path}?${sp.toString()}`)
    },
    [params, router, path],
  )

  return { mode, setMode }
}
```

- [ ] **Step 3: `components/layout/mode-selector.tsx`**

```tsx
"use client"
import { useMode } from "@/hooks/use-mode"
import type { Mode } from "@/lib/types"

const LABELS: Record<Mode, string> = {
  paper: "Paper",
  live: "Live",
  backtest: "Backtest",
}

const COLORS: Record<Mode, string> = {
  paper: "bg-sky-900/40 text-sky-300",
  live: "bg-red-900/40 text-red-300",
  backtest: "bg-neutral-800 text-neutral-300",
}

export function ModeSelector() {
  const { mode, setMode } = useMode()
  return (
    <select
      value={mode}
      onChange={(e) => setMode(e.target.value as Mode)}
      className={
        "rounded px-2 py-1 text-xs font-medium border-0 focus:ring-1 " +
        COLORS[mode]
      }
      aria-label="Mode selector"
    >
      {(Object.keys(LABELS) as Mode[]).map((m) => (
        <option key={m} value={m}>
          {LABELS[m]}
        </option>
      ))}
    </select>
  )
}
```

- [ ] **Step 4: `topbar.tsx` — ModeSelector 삽입**

기존 Topbar 수정:
```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { ModeSelector } from "@/components/layout/mode-selector"
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
        <span className="text-neutral-400">{user.email}</span>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/hooks/use-mode.ts webapp-ui/components/layout/mode-selector.tsx webapp-ui/components/layout/topbar.tsx webapp-ui/lib/types.ts
git commit -m "feat(webapp-ui): ModeSelector + useMode hook — URL searchParam 동기화"
```

---

### Task 18: `useMarketHours` + `lib/format.ts`

**Files:**
- Create: `webapp-ui/lib/market-hours.ts`
- Create: `webapp-ui/lib/format.ts`

- [ ] **Step 1: `lib/market-hours.ts`**

```typescript
"use client"
import { useEffect, useState } from "react"

/** 한국 시간 기준 장중 여부(평일 09:00~15:30). 주말/휴일 체크 없음. */
export function isMarketHours(now: Date = new Date()): boolean {
  const kst = new Date(
    now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }),
  )
  const day = kst.getDay()  // 0: Sun, 6: Sat
  if (day === 0 || day === 6) return false
  const h = kst.getHours()
  const m = kst.getMinutes()
  const minutes = h * 60 + m
  return minutes >= 9 * 60 && minutes <= 15 * 60 + 30
}

export function useMarketHours(): boolean {
  const [open, setOpen] = useState(() => isMarketHours())
  useEffect(() => {
    const id = setInterval(() => setOpen(isMarketHours()), 60_000)
    return () => clearInterval(id)
  }, [])
  return open
}
```

- [ ] **Step 2: `lib/format.ts`**

```typescript
export function fmtPct(n: number | undefined, digits = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`
}

export function fmtNum(
  n: number | undefined,
  digits = 0,
): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function fmtKrw(n: number | undefined): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`
}

export function fmtDate(yyyymmdd: string | undefined): string {
  if (!yyyymmdd || yyyymmdd.length !== 8) return yyyymmdd ?? "-"
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/lib/market-hours.ts webapp-ui/lib/format.ts
git commit -m "feat(webapp-ui): useMarketHours + 포맷 유틸"
```

---

## Part E — Frontend Home + Portfolio

### Task 19: 홈 대시보드 (Layout A, 5 위젯)

**Files:**
- Modify: `webapp-ui/app/(dashboard)/page.tsx` (redirect 교체)
- Create: `webapp-ui/components/domain/home/portfolio-widget.tsx`
- Create: `webapp-ui/components/domain/home/risk-status-widget.tsx`
- Create: `webapp-ui/components/domain/home/data-status-widget.tsx`
- Create: `webapp-ui/components/domain/home/recent-backtests-widget.tsx`
- Create: `webapp-ui/components/domain/home/recent-audit-widget.tsx`

- [ ] **Step 1: 홈 페이지 (server component)**

`app/(dashboard)/page.tsx` 전체 교체:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { PortfolioWidget } from "@/components/domain/home/portfolio-widget"
import { RiskStatusWidget } from "@/components/domain/home/risk-status-widget"
import { DataStatusWidget } from "@/components/domain/home/data-status-widget"
import { RecentBacktestsWidget } from "@/components/domain/home/recent-backtests-widget"
import { RecentAuditWidget } from "@/components/domain/home/recent-audit-widget"

export const dynamic = "force-dynamic"

type HomeData = {
  portfolio: {
    date: string
    cash: number
    total_value: number
    daily_return: number
    cumulative_return: number
    drawdown: number
    positions: { code: string; name: string; quantity: number; current_price: number }[]
  } | null
  portfolio_history: { date: string; total_value: number }[]
  risk: { report: { var_95?: number; cvar_95?: number; drawdown_status?: string; alerts?: { level: string; message: string }[] } } | null
  data_status: { tables: { name: string; row_count: number; latest_date: string | null }[]; gaps_count: number }
  recent_backtests: { run_id: string; name: string; start_date: string; end_date: string; metrics: Record<string, number> }[]
  recent_audits: { id: number; timestamp: number; event_type: string }[]
}

export default async function HomePage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<HomeData>("/api/v1/dashboard/home", {
    headers: h, cache: "no-store",
  })
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="md:col-span-2">
        <PortfolioWidget
          portfolio={data.portfolio}
          history={data.portfolio_history}
        />
      </div>
      <div className="space-y-4">
        <RiskStatusWidget risk={data.risk} />
        <DataStatusWidget status={data.data_status} />
        <RecentBacktestsWidget items={data.recent_backtests} />
        <RecentAuditWidget items={data.recent_audits} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: `portfolio-widget.tsx`**

```tsx
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtKrw, fmtPct } from "@/lib/format"

type Props = {
  portfolio: {
    date: string
    cash: number
    total_value: number
    daily_return: number
    cumulative_return: number
    drawdown: number
    positions: { code: string; name: string; quantity: number; current_price: number }[]
  } | null
  history: { date: string; total_value: number }[]
}

export function PortfolioWidget({ portfolio, history }: Props) {
  if (!portfolio) {
    return (
      <Card className="p-6 h-full">
        <h2 className="text-lg font-semibold mb-2">포트폴리오</h2>
        <p className="text-sm text-neutral-500">
          포트폴리오 스냅샷 없음. 매매 실행 전 상태.
        </p>
      </Card>
    )
  }
  const top5 = portfolio.positions.slice(0, 5)
  return (
    <Card className="p-6 h-full space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-lg font-semibold">포트폴리오</h2>
          <p className="text-xs text-neutral-500">{portfolio.date}</p>
        </div>
        <Link href="/portfolio" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-neutral-400">총 자산</div>
          <div className="text-xl font-mono font-semibold">{fmtKrw(portfolio.total_value)}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">현금</div>
          <div className="text-lg font-mono">{fmtKrw(portfolio.cash)}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">일간</div>
          <div className={`text-lg font-mono ${portfolio.daily_return >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmtPct(portfolio.daily_return)}
          </div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">누적</div>
          <div className={`text-lg font-mono ${portfolio.cumulative_return >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmtPct(portfolio.cumulative_return)}
          </div>
        </div>
      </div>
      {history.length > 0 && <Sparkline points={history.map((h) => h.total_value)} />}
      <div>
        <h3 className="text-sm font-medium mb-2">상위 5 보유 종목</h3>
        {top5.length === 0 ? (
          <p className="text-xs text-neutral-500">보유 종목 없음.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {top5.map((p) => (
              <li key={p.code} className="flex justify-between">
                <span className="font-mono text-xs">{p.code} {p.name}</span>
                <span className="font-mono">{p.quantity}주 @ {fmtKrw(p.current_price)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length === 0) return null
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const w = 300
  const h = 60
  const step = w / Math.max(1, points.length - 1)
  const d = points
    .map((v, i) => {
      const x = i * step
      const y = h - ((v - min) / range) * h
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-16">
      <path d={d} stroke="#22c55e" strokeWidth="2" fill="none" />
    </svg>
  )
}
```

- [ ] **Step 3: `risk-status-widget.tsx`**

```tsx
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  risk: {
    report: {
      var_95?: number
      cvar_95?: number
      drawdown_status?: string
      alerts?: { level: string; message: string }[]
    }
  } | null
}

export function RiskStatusWidget({ risk }: Props) {
  const r = risk?.report
  const status = r?.drawdown_status ?? "-"
  const statusColor =
    status === "NORMAL" ? "text-green-400"
    : status === "WARN" ? "text-yellow-400"
    : status === "DELEVERAGE" ? "text-red-400"
    : "text-neutral-400"
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">리스크 상태</h3>
        <Link href="/risk" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">DD</span>
        <span className={`font-medium ${statusColor}`}>{status}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">VaR95</span>
        <span className="font-mono">{r?.var_95 !== undefined ? fmtPct(r.var_95) : "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">CVaR95</span>
        <span className="font-mono">{r?.cvar_95 !== undefined ? fmtPct(r.cvar_95) : "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">경고</span>
        <span className="font-mono">{r?.alerts?.length ?? 0}건</span>
      </div>
    </Card>
  )
}
```

- [ ] **Step 4: 나머지 3개 위젯 (정적 JSX 모음)**

`data-status-widget.tsx`:
```tsx
import Link from "next/link"
import { Card } from "@/components/ui/card"

type Props = {
  status: {
    tables: { name: string; row_count: number; latest_date: string | null }[]
    gaps_count: number
  }
}

export function DataStatusWidget({ status }: Props) {
  const ohlcv = status.tables.find((t) => t.name === "ohlcv")
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">데이터</h3>
        <Link href="/data" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">OHLCV 최신</span>
        <span className="font-mono">{ohlcv?.latest_date ?? "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">갭 감지</span>
        <span className={`font-mono ${status.gaps_count > 0 ? "text-yellow-400" : "text-green-400"}`}>
          {status.gaps_count}종목
        </span>
      </div>
    </Card>
  )
}
```

`recent-backtests-widget.tsx`:
```tsx
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  items: {
    run_id: string
    name: string
    start_date: string
    end_date: string
    metrics: Record<string, number>
  }[]
}

export function RecentBacktestsWidget({ items }: Props) {
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">최근 백테스트</h3>
        <Link href="/backtest" className="text-xs text-blue-400 hover:underline">전체 →</Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-500">없음.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {items.slice(0, 3).map((r) => (
            <li key={r.run_id} className="flex justify-between">
              <Link href={`/backtest/${r.run_id.slice(0, 8)}`} className="hover:underline truncate">
                {r.name || r.run_id.slice(0, 8)}
              </Link>
              <span className={`font-mono ${(r.metrics.total_return ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(r.metrics.total_return)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
```

`recent-audit-widget.tsx`:
```tsx
import Link from "next/link"
import { Card } from "@/components/ui/card"

type Props = {
  items: { id: number; timestamp: number; event_type: string }[]
}

export function RecentAuditWidget({ items }: Props) {
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">감사</h3>
        <Link href="/audit" className="text-xs text-blue-400 hover:underline">전체 →</Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-500">없음.</p>
      ) : (
        <ul className="space-y-1 text-xs font-mono text-neutral-400">
          {items.slice(0, 5).map((e) => (
            <li key={e.id} className="truncate">
              {new Date(e.timestamp * 1000).toISOString().slice(11, 19)} {e.event_type}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
```

- [ ] **Step 5: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/page.tsx webapp-ui/components/domain/home/
git commit -m "feat(webapp-ui): 홈 대시보드 — 포트폴리오 + 4 위젯 (Layout A)"
```

---

### Task 20: Portfolio summary 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/portfolio/page.tsx`
- Create: `webapp-ui/components/domain/portfolio/summary-card.tsx`
- Create: `webapp-ui/components/domain/portfolio/holdings-table.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SummaryCard } from "@/components/domain/portfolio/summary-card"
import { HoldingsTable } from "@/components/domain/portfolio/holdings-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function PortfolioPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const snap = await apiFetch<{
    date: string; cash: number; total_value: number
    daily_return: number; cumulative_return: number; drawdown: number
    positions: { code: string; name: string; quantity: number; avg_price: number; current_price: number; unrealized_pnl: number; weight: number }[]
  } | null>(`/api/v1/portfolio?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  if (!snap) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">포트폴리오 ({mode})</h1>
        <p className="text-neutral-500">스냅샷 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">포트폴리오 — {snap.date} ({mode})</h1>
      <SummaryCard snapshot={snap} />
      <HoldingsTable positions={snap.positions} />
    </div>
  )
}
```

- [ ] **Step 2: SummaryCard**

```tsx
import { Card } from "@/components/ui/card"
import { fmtKrw, fmtPct } from "@/lib/format"

type Snapshot = {
  date: string; cash: number; total_value: number
  daily_return: number; cumulative_return: number; drawdown: number
}

export function SummaryCard({ snapshot }: { snapshot: Snapshot }) {
  const items: Array<{ label: string; value: string; color?: string }> = [
    { label: "총 자산", value: fmtKrw(snapshot.total_value) },
    { label: "현금", value: fmtKrw(snapshot.cash) },
    {
      label: "일간 수익률",
      value: fmtPct(snapshot.daily_return),
      color: snapshot.daily_return >= 0 ? "text-green-400" : "text-red-400",
    },
    {
      label: "누적 수익률",
      value: fmtPct(snapshot.cumulative_return),
      color: snapshot.cumulative_return >= 0 ? "text-green-400" : "text-red-400",
    },
    {
      label: "드로다운",
      value: fmtPct(snapshot.drawdown),
      color: "text-red-400",
    },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {items.map((it) => (
        <Card key={it.label} className="p-4">
          <div className="text-xs text-neutral-400">{it.label}</div>
          <div className={`mt-1 text-xl font-semibold font-mono ${it.color ?? "text-neutral-100"}`}>
            {it.value}
          </div>
        </Card>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: HoldingsTable**

```tsx
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { fmtKrw, fmtPct } from "@/lib/format"

type Position = {
  code: string; name: string; quantity: number
  avg_price: number; current_price: number
  unrealized_pnl: number; weight: number
}

export function HoldingsTable({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return <p className="text-sm text-neutral-500">보유 종목 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>종목</TableHead>
            <TableHead>이름</TableHead>
            <TableHead className="text-right">수량</TableHead>
            <TableHead className="text-right">평단</TableHead>
            <TableHead className="text-right">현재가</TableHead>
            <TableHead className="text-right">평가손익</TableHead>
            <TableHead className="text-right">비중</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {positions.map((p) => (
            <TableRow key={p.code}>
              <TableCell className="font-mono">{p.code}</TableCell>
              <TableCell>{p.name}</TableCell>
              <TableCell className="text-right">{p.quantity.toLocaleString()}</TableCell>
              <TableCell className="text-right font-mono">{fmtKrw(p.avg_price)}</TableCell>
              <TableCell className="text-right font-mono">{fmtKrw(p.current_price)}</TableCell>
              <TableCell className={`text-right font-mono ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toLocaleString()}
              </TableCell>
              <TableCell className="text-right font-mono">{fmtPct(p.weight * 100, 1)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/portfolio/page.tsx webapp-ui/components/domain/portfolio/
git commit -m "feat(webapp-ui): Portfolio summary + Holdings 테이블"
```

---

### Task 21: Portfolio history

**Files:**
- Create: `webapp-ui/app/(dashboard)/portfolio/history/page.tsx`
- Create: `webapp-ui/components/domain/portfolio/history-chart.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { HistoryChart } from "@/components/domain/portfolio/history-chart"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string; days?: string }> }

export default async function PortfolioHistoryPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const days = Number(sp.days || 30)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { date: string; total_value: number; daily_return: number }[]
  }>(`/api/v1/portfolio/history?mode=${mode}&days=${days}`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">포트폴리오 이력 ({mode}, {days}일)</h1>
      <HistoryChart snapshots={data.items} />
    </div>
  )
}
```

- [ ] **Step 2: HistoryChart (Recharts)**

```tsx
"use client"
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, BarChart, Bar,
} from "recharts"

type Snapshot = {
  date: string
  total_value: number
  daily_return: number
}

export function HistoryChart({ snapshots }: { snapshots: Snapshot[] }) {
  if (snapshots.length === 0) {
    return <p className="text-sm text-neutral-500">이력 없음.</p>
  }
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">자산 곡선</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={snapshots}>
            <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "M"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
            <Line type="monotone" dataKey="total_value" stroke="#22c55e" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">일별 수익률</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={snapshots}>
            <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <YAxis tickFormatter={(v) => v.toFixed(1) + "%"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
            <Bar dataKey="daily_return" fill="#22c55e" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/portfolio/history/ webapp-ui/components/domain/portfolio/history-chart.tsx
git commit -m "feat(webapp-ui): Portfolio history — 자산 곡선 + 일별 수익률"
```

---

### Task 22: Portfolio attribution

**Files:**
- Create: `webapp-ui/app/(dashboard)/portfolio/attribution/page.tsx`
- Create: `webapp-ui/components/domain/portfolio/attribution-bars.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { AttributionBars } from "@/components/domain/portfolio/attribution-bars"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string; date?: string }> }

export default async function AttributionPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const url = `/api/v1/portfolio/attribution?mode=${mode}${sp.date ? `&date=${sp.date}` : ""}`
  const data = await apiFetch<{
    date: string
    strategy_returns: Record<string, number>
    factor_returns: Record<string, number>
    sector_returns: Record<string, number>
  } | null>(url, { headers: h, cache: "no-store" })
  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">성과 귀속 ({mode})</h1>
        <p className="text-neutral-500">attribution 데이터 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">성과 귀속 — {data.date} ({mode})</h1>
      <AttributionBars title="전략별" data={data.strategy_returns} />
      <AttributionBars title="섹터별" data={data.sector_returns} />
      <AttributionBars title="팩터별" data={data.factor_returns} />
    </div>
  )
}
```

- [ ] **Step 2: AttributionBars**

```tsx
"use client"
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts"

type Props = { title: string; data: Record<string, number> }

export function AttributionBars({ title, data }: Props) {
  const entries = Object.entries(data).map(([name, value]) => ({ name, value }))
  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">{title}</h2>
        <p className="text-sm text-neutral-500">데이터 없음.</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-neutral-800 p-4">
      <h2 className="mb-4 text-lg">{title}</h2>
      <ResponsiveContainer width="100%" height={Math.max(180, entries.length * 30)}>
        <BarChart data={entries} layout="vertical">
          <XAxis type="number" tickFormatter={(v) => v.toFixed(1) + "%"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
          <YAxis dataKey="name" type="category" tick={{ fill: "#a3a3a3", fontSize: 11 }} width={100} />
          <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} formatter={(v: number) => `${v.toFixed(2)}%`} />
          <Bar dataKey="value" fill="#22c55e" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/portfolio/attribution/ webapp-ui/components/domain/portfolio/attribution-bars.tsx
git commit -m "feat(webapp-ui): Portfolio attribution — 전략/섹터/팩터별 기여도 차트"
```

---

## Part F — Frontend Risk + Screening

### Task 23: Risk overview

**Files:**
- Create: `webapp-ui/app/(dashboard)/risk/page.tsx`
- Create: `webapp-ui/components/domain/risk/risk-cards.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { RiskCards } from "@/components/domain/risk/risk-cards"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function RiskPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    report: {
      drawdown_status: string
      var_95: number
      cvar_95: number
      alerts: { level: string; message: string }[]
    }
    stress: Record<string, number>
    cached: boolean
    computed_at?: number
  } | null>(`/api/v1/risk/report?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">리스크 ({mode})</h1>
        <p className="text-neutral-500">스냅샷 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">리스크 ({mode})</h1>
      <RiskCards report={data.report} cached={data.cached} />
      <div>
        <h2 className="text-lg mb-2">경고</h2>
        {data.report.alerts.length === 0 ? (
          <p className="text-sm text-neutral-500">경고 없음.</p>
        ) : (
          <ul className="space-y-1">
            {data.report.alerts.map((a, i) => (
              <li key={i} className="text-sm">
                <span className={`font-mono mr-2 ${a.level === "CRITICAL" ? "text-red-400" : "text-yellow-400"}`}>
                  [{a.level}]
                </span>
                {a.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: RiskCards**

```tsx
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  report: { drawdown_status: string; var_95: number; cvar_95: number; alerts: unknown[] }
  cached: boolean
}

export function RiskCards({ report, cached }: Props) {
  const ddColor =
    report.drawdown_status === "NORMAL" ? "text-green-400"
    : report.drawdown_status === "WARN" ? "text-yellow-400"
    : report.drawdown_status === "DELEVERAGE" ? "text-red-400"
    : "text-neutral-100"
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-neutral-400">드로다운 상태</div>
          <div className={`mt-1 text-xl font-semibold ${ddColor}`}>{report.drawdown_status}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">VaR 95%</div>
          <div className="mt-1 text-xl font-semibold font-mono text-red-400">{fmtPct(report.var_95)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">CVaR 95%</div>
          <div className="mt-1 text-xl font-semibold font-mono text-red-400">{fmtPct(report.cvar_95)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">경고</div>
          <div className="mt-1 text-xl font-semibold font-mono">{report.alerts.length}건</div>
        </Card>
      </div>
      {cached && <p className="text-xs text-neutral-500">캐시된 결과.</p>}
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/risk/page.tsx webapp-ui/components/domain/risk/risk-cards.tsx
git commit -m "feat(webapp-ui): Risk overview — 드로다운/VaR/CVaR/경고 카드"
```

---

### Task 24: Risk stress (기본 시나리오)

**Files:**
- Create: `webapp-ui/app/(dashboard)/risk/stress/page.tsx`
- Create: `webapp-ui/components/domain/risk/stress-table.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { StressTable } from "@/components/domain/risk/stress-table"
import { CustomStressForm } from "@/components/domain/risk/custom-stress-form"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function StressPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    stress: Record<string, number>
  } | null>(`/api/v1/risk/stress?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">스트레스 테스트 ({mode})</h1>
      <StressTable scenarios={data?.stress ?? {}} />
      <CustomStressForm mode={mode} />
    </div>
  )
}
```

- [ ] **Step 2: StressTable**

```tsx
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { fmtPct } from "@/lib/format"

const SCENARIO_LABELS: Record<string, string> = {
  "2020_covid": "2020 코로나",
  "2022_rate_hike": "2022 금리 인상",
  "flash_crash": "Flash Crash",
  "won_crisis": "원화 위기",
  "sector_collapse": "섹터 붕괴",
}

export function StressTable({ scenarios }: { scenarios: Record<string, number> }) {
  const entries = Object.entries(scenarios)
  if (entries.length === 0) {
    return <p className="text-sm text-neutral-500">스트레스 결과 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>시나리오</TableHead>
            <TableHead className="text-right">예상 영향 (%)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([k, v]) => (
            <TableRow key={k}>
              <TableCell>{SCENARIO_LABELS[k] || k}</TableCell>
              <TableCell className={`text-right font-mono ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(v)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/risk/stress/page.tsx webapp-ui/components/domain/risk/stress-table.tsx
git commit -m "feat(webapp-ui): Risk stress — 5 시나리오 표"
```

---

### Task 25: Custom stress 폼

**Files:**
- Create: `webapp-ui/components/domain/risk/custom-stress-form.tsx`

- [ ] **Step 1: 폼 컴포넌트**

```tsx
"use client"
import { useState } from "react"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

export function CustomStressForm({ mode }: { mode: string }) {
  const [kospi, setKospi] = useState("-0.10")
  const [kosdaq, setKosdaq] = useState("-0.15")
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const r = await apiMutate<{ results: Record<string, number> }>(
        "/api/v1/risk/stress/custom", "POST",
        {
          mode,
          shocks: { KOSPI: parseFloat(kospi), KOSDAQ: parseFloat(kosdaq) },
        },
      )
      setResult(r.results)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <h2 className="font-medium">커스텀 시나리오</h2>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="kospi">KOSPI 충격</Label>
          <Input
            id="kospi" type="number" step="0.01"
            value={kospi} onChange={(e) => setKospi(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="kosdaq">KOSDAQ 충격</Label>
          <Input
            id="kosdaq" type="number" step="0.01"
            value={kosdaq} onChange={(e) => setKosdaq(e.target.value)}
          />
        </div>
      </div>
      <Button onClick={handleRun} disabled={loading}>
        {loading ? "계산 중..." : "실행"}
      </Button>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && (
        <div className="text-sm">
          {Object.entries(result).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <span>{k}</span>
              <span className={`font-mono ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/components/domain/risk/custom-stress-form.tsx
git commit -m "feat(webapp-ui): Custom stress form — 사용자 정의 시나리오 실행"
```

---

### Task 26: Risk limits (읽기 전용)

**Files:**
- Create: `webapp-ui/app/(dashboard)/risk/limits/page.tsx`

- [ ] **Step 1: 페이지**

```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

export const dynamic = "force-dynamic"

export default async function LimitsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    max_position_weight: number
    max_drawdown_soft: number
    max_drawdown_hard: number
    max_daily_orders: number
    max_daily_amount: number
  }>("/api/v1/risk/limits", { headers: h, cache: "no-store" })

  const rows: Array<[string, string]> = [
    ["종목당 최대 비중", fmtPct(data.max_position_weight * 100, 1)],
    ["MDD soft 임계값", fmtPct(data.max_drawdown_soft * 100, 1)],
    ["MDD hard 임계값", fmtPct(data.max_drawdown_hard * 100, 1)],
    ["일일 주문 한도", `${data.max_daily_orders}회`],
    ["일일 금액 한도", `${data.max_daily_amount.toLocaleString("ko-KR")}원`],
  ]

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">리스크 리밋</h1>
        <Link href="/settings/risk-limits" className="text-sm text-blue-400 hover:underline">
          Settings에서 수정 →
        </Link>
      </div>
      <Card className="p-6 space-y-3">
        {rows.map(([label, val]) => (
          <div key={label} className="flex justify-between py-2 border-b border-neutral-800 last:border-0">
            <span className="text-neutral-400">{label}</span>
            <span className="font-mono">{val}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/risk/limits/page.tsx
git commit -m "feat(webapp-ui): Risk limits — 읽기 전용 + Settings 링크"
```

---

### Task 27: Screening list + form

**Files:**
- Create: `webapp-ui/app/(dashboard)/screening/page.tsx`
- Create: `webapp-ui/app/(dashboard)/screening/new/page.tsx`
- Create: `webapp-ui/components/domain/screening/runs-table.tsx`
- Create: `webapp-ui/components/domain/screening/screening-form.tsx`

- [ ] **Step 1: List 페이지**

```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunsTable } from "@/components/domain/screening/runs-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string }> }

export default async function ScreeningListPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { run_id: string; name: string; market: string; strategy: string; top_n: number; created_at: number }[]
    page: number; size: number; total: number
  }>(`/api/v1/screening/runs?page=${page}&size=20`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">스크리닝 결과</h1>
        <Link href="/screening/new">
          <Button>새 스크리닝</Button>
        </Link>
      </div>
      <RunsTable data={data} currentPage={page} />
    </div>
  )
}
```

- [ ] **Step 2: RunsTable (클라이언트)**

```tsx
"use client"
import Link from "next/link"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"

type Props = {
  data: {
    items: { run_id: string; name: string; market: string; strategy: string; top_n: number; created_at: number }[]
    page: number; size: number; total: number
  }
  currentPage: number
}

export function RunsTable({ data, currentPage }: Props) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  const go = (page: number) => {
    const sp = new URLSearchParams(params.toString())
    sp.set("page", String(page))
    router.push(`${path}?${sp.toString()}`)
  }
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>이름</TableHead>
              <TableHead>시장</TableHead>
              <TableHead>전략</TableHead>
              <TableHead className="text-right">Top N</TableHead>
              <TableHead>생성 시각</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((r) => (
              <TableRow key={r.run_id}>
                <TableCell className="font-mono">
                  <Link href={`/screening/${r.run_id}`} className="hover:underline">
                    {r.run_id.slice(0, 8)}
                  </Link>
                </TableCell>
                <TableCell>{r.name || "-"}</TableCell>
                <TableCell>{r.market}</TableCell>
                <TableCell>{r.strategy}</TableCell>
                <TableCell className="text-right">{r.top_n}</TableCell>
                <TableCell className="text-neutral-400 text-xs">
                  {new Date(r.created_at * 1000).toISOString().slice(0, 19).replace("T", " ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-between items-center text-sm">
        <span>총 {data.total}건 · {currentPage}/{totalPages}</span>
        <div className="space-x-2">
          <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => go(currentPage - 1)}>이전</Button>
          <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={() => go(currentPage + 1)}>다음</Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: New 폼 페이지 + ScreeningForm**

`app/(dashboard)/screening/new/page.tsx`:
```tsx
import { ScreeningForm } from "@/components/domain/screening/screening-form"

export default function NewScreeningPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">새 스크리닝</h1>
      <ScreeningForm />
    </div>
  )
}
```

`components/domain/screening/screening-form.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const PRESETS: Record<string, Record<string, number>> = {
  momentum: { momentum: 0.5, flow: 0.3, volatility: 0.2 },
  value: { value: 0.4, quality: 0.2, momentum: 0.2, flow: 0.15, volatility: 0.05 },
  quality: { quality: 0.35, growth: 0.2, value: 0.15, momentum: 0.2, flow: 0.1 },
  balanced: { momentum: 0.25, flow: 0.25, value: 0.20, quality: 0.15, growth: 0.10, volatility: 0.05 },
}

export function ScreeningForm() {
  const router = useRouter()
  const [market, setMarket] = useState<"KOSPI" | "KOSDAQ" | "ALL">("KOSPI")
  const [strategy, setStrategy] = useState("momentum")
  const [topN, setTopN] = useState("20")
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handle = async () => {
    setSubmitting(true); setError(null)
    try {
      const r = await apiMutate<{ job_id: string }>(
        "/api/v1/screening/run", "POST",
        {
          market, strategy, top_n: Number(topN), name,
          factor_weights: PRESETS[strategy] || PRESETS.momentum,
        },
      )
      router.push(`/screening/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>시장</Label>
        <select value={market} onChange={(e) => setMarket(e.target.value as typeof market)}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm">
          <option value="KOSPI">KOSPI</option>
          <option value="KOSDAQ">KOSDAQ</option>
          <option value="ALL">ALL</option>
        </select>
      </div>
      <div>
        <Label>전략 preset</Label>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm">
          {Object.keys(PRESETS).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>
      <div>
        <Label>Top N</Label>
        <Input type="number" value={topN} onChange={(e) => setTopN(e.target.value)} />
      </div>
      <div>
        <Label>이름 (선택)</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button onClick={handle} disabled={submitting} className="w-full">
        {submitting ? "실행 중..." : "실행"}
      </Button>
    </div>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/screening/ webapp-ui/components/domain/screening/
git commit -m "feat(webapp-ui): Screening list + new form (preset 4종)"
```

---

### Task 28: Screening detail

**Files:**
- Create: `webapp-ui/app/(dashboard)/screening/[runId]/page.tsx`
- Create: `webapp-ui/components/domain/screening/results-table.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { ResultsTable } from "@/components/domain/screening/results-table"
import { Card } from "@/components/ui/card"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ runId: string }> }

export default async function ScreeningDetailPage({ params }: Props) {
  const { runId } = await params
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  let data: {
    run_id: string; name: string; market: string; strategy: string
    factor_weights: Record<string, number>; top_n: number
    market_context: Record<string, unknown>
    results: { code: string; name: string; market: string; score: number; factors: Record<string, number> }[]
    created_at: number
  }
  try {
    data = await apiFetch(`/api/v1/screening/runs/${runId}`, {
      headers: h, cache: "no-store",
    })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{data.name || data.run_id.slice(0, 8)}</h1>
        <p className="text-sm text-neutral-500">
          {data.market} · {data.strategy} · Top {data.top_n} · {new Date(data.created_at * 1000).toISOString().slice(0, 19).replace("T", " ")}
        </p>
      </div>
      {Object.keys(data.market_context).length > 0 && (
        <Card className="p-4">
          <h2 className="font-medium mb-2">시장 컨텍스트</h2>
          <pre className="text-xs text-neutral-400">
            {JSON.stringify(data.market_context, null, 2)}
          </pre>
        </Card>
      )}
      <ResultsTable results={data.results} />
    </div>
  )
}
```

- [ ] **Step 2: ResultsTable**

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Result = {
  code: string; name: string; market: string
  score: number
  factors: Record<string, number>
}

export function ResultsTable({ results }: { results: Result[] }) {
  if (results.length === 0) {
    return <p className="text-sm text-neutral-500">결과 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>순위</TableHead>
            <TableHead>종목</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>시장</TableHead>
            <TableHead className="text-right">점수</TableHead>
            <TableHead>주요 팩터</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((r, i) => {
            const topFactor = Object.entries(r.factors).sort((a, b) => b[1] - a[1])[0]
            return (
              <TableRow key={`${r.code}-${i}`}>
                <TableCell className="font-mono">{i + 1}</TableCell>
                <TableCell className="font-mono">{r.code}</TableCell>
                <TableCell>{r.name}</TableCell>
                <TableCell>{r.market}</TableCell>
                <TableCell className="text-right font-mono">
                  {r.score >= 0 ? "+" : ""}{r.score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {topFactor ? `${topFactor[0]}(${topFactor[1].toFixed(0)})` : "-"}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/screening/\[runId\] webapp-ui/components/domain/screening/results-table.tsx
git commit -m "feat(webapp-ui): Screening detail — 결과 표 + 시장 컨텍스트"
```

---

### Task 29: Screening job progress 연결

**Files:**
- Create: `webapp-ui/app/(dashboard)/screening/jobs/[jobId]/page.tsx`

- [ ] **Step 1: Phase 1 job-progress 재사용**

```tsx
import { JobProgress } from "@/components/domain/backtest/job-progress"

type Props = { params: Promise<{ jobId: string }> }

export default async function ScreeningJobPage({ params }: Props) {
  const { jobId } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">스크리닝 실행 중</h1>
      <JobProgress jobId={jobId} />
    </div>
  )
}
```

**주의:** 기존 `JobProgress`는 완료 시 `/backtest/{run_id}`로 redirect. 스크리닝용으로는 `/screening/{run_id}`로 가야 하므로 분기 필요. 일단 Phase 1 컴포넌트를 복사해서 스크리닝 전용으로 만들거나, Phase 1 컴포넌트에 `redirectPath` prop 추가.

옵션 A — prop 추가 (권장):
`webapp-ui/components/domain/backtest/job-progress.tsx` 수정:
```tsx
// redirectPath prop 추가
export function JobProgress({
  jobId,
  redirectPath = "/backtest",  // 기본값 유지
}: { jobId: string; redirectPath?: string }) {
  // ...
  useEffect(() => {
    if (job?.status === "done" && job.result_ref) {
      router.replace(`${redirectPath}/${job.result_ref.slice(0, 8)}`)
    }
  }, [job, router, redirectPath])
  // ...
}
```

screening job page에서 `<JobProgress jobId={jobId} redirectPath="/screening" />` 사용.

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/screening/jobs webapp-ui/components/domain/backtest/job-progress.tsx
git commit -m "feat(webapp-ui): Screening job progress — redirectPath prop 재사용"
```

---

## Part G — Frontend Data + Settings + Audit

### Task 30: Data status 대시보드

**Files:**
- Create: `webapp-ui/app/(dashboard)/data/page.tsx`
- Create: `webapp-ui/components/domain/data/status-table.tsx`
- Create: `webapp-ui/components/domain/data/gap-detector.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { StatusTable } from "@/components/domain/data/status-table"
import { GapDetector } from "@/components/domain/data/gap-detector"
import { ActionButtons } from "@/components/domain/data/action-buttons"

export const dynamic = "force-dynamic"

export default async function DataPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    tables: { name: string; row_count: number; latest_date: string | null; distinct_codes: number }[]
    gaps: { code: string; last_date: string }[]
  }>("/api/v1/data/status", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">데이터 수집 현황</h1>
      <StatusTable tables={data.tables} />
      <GapDetector gaps={data.gaps} />
      <ActionButtons />
    </div>
  )
}
```

- [ ] **Step 2: StatusTable**

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type TableStatus = { name: string; row_count: number; latest_date: string | null; distinct_codes: number }

export function StatusTable({ tables }: { tables: TableStatus[] }) {
  if (tables.length === 0) {
    return <p className="text-sm text-neutral-500">데이터 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>테이블</TableHead>
            <TableHead className="text-right">행 수</TableHead>
            <TableHead className="text-right">종목 수</TableHead>
            <TableHead>최신 날짜</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tables.map((t) => (
            <TableRow key={t.name}>
              <TableCell className="font-mono">{t.name}</TableCell>
              <TableCell className="text-right">{t.row_count.toLocaleString()}</TableCell>
              <TableCell className="text-right">{t.distinct_codes.toLocaleString()}</TableCell>
              <TableCell className="font-mono">{t.latest_date || "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 3: GapDetector**

```tsx
import { Card } from "@/components/ui/card"

export function GapDetector({ gaps }: { gaps: { code: string; last_date: string }[] }) {
  return (
    <Card className="p-4">
      <h2 className="font-medium mb-2">갭 감지 (최근 5일 이내 미업데이트)</h2>
      {gaps.length === 0 ? (
        <p className="text-sm text-green-400">갭 없음.</p>
      ) : (
        <div>
          <p className="text-sm text-yellow-400 mb-2">{gaps.length}종목 갭 발견.</p>
          <div className="grid grid-cols-6 gap-1 text-xs font-mono">
            {gaps.slice(0, 60).map((g) => (
              <div key={g.code} className="text-neutral-400">
                {g.code} ({g.last_date})
              </div>
            ))}
          </div>
          {gaps.length > 60 && <p className="text-xs text-neutral-500 mt-2">... +{gaps.length - 60} more</p>}
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/data/page.tsx webapp-ui/components/domain/data/status-table.tsx webapp-ui/components/domain/data/gap-detector.tsx
git commit -m "feat(webapp-ui): Data 대시보드 — 테이블 현황 + 갭 감지"
```

---

### Task 31: Data action buttons (+ collect_all 비활성)

**Files:**
- Create: `webapp-ui/components/domain/data/action-buttons.tsx`

- [ ] **Step 1: ActionButtons**

```tsx
"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

const DISABLED_TOOLTIP = "초기 1회 전종목 수집은 리소스가 큼. CLI `ap trading data collect`에서만 실행 가능. 웹에서는 안전상 차단."

export function ActionButtons() {
  const router = useRouter()
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)

  const trigger = async (
    path: string, body: object, label: string,
  ) => {
    setLoading(label); setErr(null)
    try {
      const r = await apiMutate<{ job_id: string }>(path, "POST", body)
      router.push(`/data/jobs/${r.job_id}`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally {
      setLoading(null)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <h2 className="font-medium">수집 액션</h2>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => trigger(
            "/api/v1/data/update", { markets: ["KOSPI", "KOSDAQ"] },
            "update",
          )}
          disabled={loading !== null}
        >
          {loading === "update" ? "..." : "증분 업데이트"}
        </Button>
        <Button
          variant="outline"
          onClick={() => trigger(
            "/api/v1/data/collect-financials",
            { market: "KOSPI", top: 100 },
            "financials",
          )}
          disabled={loading !== null}
        >
          {loading === "financials" ? "..." : "재무 재수집"}
        </Button>
        <Button
          variant="outline"
          onClick={() => trigger(
            "/api/v1/data/collect-wisereport",
            { market: "KOSPI", top: 100 },
            "wisereport",
          )}
          disabled={loading !== null}
        >
          {loading === "wisereport" ? "..." : "Wisereport 재수집"}
        </Button>
        <Button
          variant="outline"
          onClick={() => trigger(
            "/api/v1/data/collect-short",
            { market: "KOSPI", top: 100 },
            "short",
          )}
          disabled={loading !== null}
        >
          {loading === "short" ? "..." : "공매도 재수집"}
        </Button>
        <Button
          variant="outline"
          disabled
          title={DISABLED_TOOLTIP}
          className="cursor-not-allowed opacity-50"
        >
          전종목 수집 (비활성)
        </Button>
      </div>
      <p className="text-xs text-neutral-500">
        💡 전종목 수집은 CLI <code>ap trading data collect</code>에서만 실행 가능합니다. 리소스 보호 및 실수 방지.
      </p>
      {err && <p className="text-sm text-red-400">{err}</p>}
    </Card>
  )
}
```

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/components/domain/data/action-buttons.tsx
git commit -m "feat(webapp-ui): Data action buttons — update/collect-* + collect_all 비활성 툴팁"
```

---

### Task 32: Data job progress

**Files:**
- Create: `webapp-ui/app/(dashboard)/data/jobs/[jobId]/page.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { JobProgress } from "@/components/domain/backtest/job-progress"

type Props = { params: Promise<{ jobId: string }> }

export default async function DataJobPage({ params }: Props) {
  const { jobId } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">데이터 수집 진행 중</h1>
      <JobProgress jobId={jobId} redirectPath="/data" />
    </div>
  )
}
```

데이터 Job은 결과가 JSON 문자열이어서 run_id로 redirect 안 됨. `JobProgress` 를 복사해서 데이터 전용 버전을 만들거나, `redirectPath`가 빈 문자열이면 리다이렉트 skip하도록 확장:

`webapp-ui/components/domain/backtest/job-progress.tsx` 수정:
```tsx
useEffect(() => {
  if (job?.status === "done" && job.result_ref && redirectPath) {
    // result_ref가 uuid 형태면 slice, JSON이면 skip
    if (/^[a-f0-9-]{8,}$/.test(job.result_ref)) {
      router.replace(`${redirectPath}/${job.result_ref.slice(0, 8)}`)
    }
  }
}, [job, router, redirectPath])
```

또는 data job 전용 컴포넌트를 별도 작성. 이 경우 완료 시 "완료" 메시지 + 결과 JSON 표시 후 /data로 돌아가는 버튼.

간단한 방식: 데이터 Job은 redirect 안 함, 결과만 보여주고 `[데이터로 돌아가기]` 버튼 제공.

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/data/jobs webapp-ui/components/domain/backtest/job-progress.tsx
git commit -m "feat(webapp-ui): Data job progress — redirect skip (JSON 결과)"
```

---

### Task 33: Settings 탭 쉘 + API keys 탭

**Files:**
- Create: `webapp-ui/app/(dashboard)/settings/page.tsx`
- Create: `webapp-ui/app/(dashboard)/settings/api-keys/page.tsx`
- Create: `webapp-ui/components/domain/settings/secret-input.tsx`
- Create: `webapp-ui/components/domain/settings/api-keys-form.tsx`

- [ ] **Step 1: 탭 쉘 + API keys 페이지**

`app/(dashboard)/settings/page.tsx`:
```tsx
import { redirect } from "next/navigation"

export default function SettingsPage() {
  redirect("/settings/api-keys")
}
```

`app/(dashboard)/settings/api-keys/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { ApiKeysForm } from "@/components/domain/settings/api-keys-form"

export const dynamic = "force-dynamic"

export default async function ApiKeysPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=api_key", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="api-keys" />
      <ApiKeysForm items={data.items} />
    </div>
  )
}
```

- [ ] **Step 2: SettingsTabs + SecretInput**

`components/domain/settings/settings-tabs.tsx`:
```tsx
import Link from "next/link"

const TABS: { slug: string; label: string }[] = [
  { slug: "api-keys", label: "API 키" },
  { slug: "risk-limits", label: "리스크 리밋" },
  { slug: "notifications", label: "알림" },
  { slug: "backtest-defaults", label: "백테스트 기본값" },
]

export function SettingsTabs({ active }: { active: string }) {
  return (
    <nav className="flex gap-2 border-b border-neutral-800 pb-2">
      {TABS.map((t) => (
        <Link
          key={t.slug}
          href={`/settings/${t.slug}`}
          className={
            "px-3 py-1 text-sm rounded " +
            (active === t.slug
              ? "bg-neutral-800 text-neutral-100"
              : "text-neutral-400 hover:text-neutral-200")
          }
        >
          {t.label}
        </Link>
      ))}
    </nav>
  )
}
```

`components/domain/settings/secret-input.tsx`:
```tsx
"use client"
import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

type Props = {
  label: string
  displayValue: string         // 이미 마스킹됨
  isSecret: boolean
  onChange: (newValue: string, currentPassword: string) => Promise<void>
}

export function SecretInput({ label, displayValue, isSecret, onChange }: Props) {
  const [editing, setEditing] = useState(false)
  const [newValue, setNewValue] = useState("")
  const [currentPw, setCurrentPw] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true); setErr(null)
    try {
      await onChange(newValue, currentPw)
      setEditing(false); setNewValue(""); setCurrentPw("")
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="py-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-neutral-400">{label}</span>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            수정
          </Button>
        )}
      </div>
      {!editing && (
        <div className="mt-1 font-mono text-sm">{displayValue || "(없음)"}</div>
      )}
      {editing && (
        <div className="mt-2 space-y-2">
          <Input
            type={isSecret ? "password" : "text"}
            placeholder="새 값"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
          />
          <Input
            type="password"
            placeholder="현재 비밀번호 (확인)"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
          {err && <p className="text-sm text-red-400">{err}</p>}
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={saving || !newValue || !currentPw}>
              {saving ? "..." : "저장"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setEditing(false); setNewValue(""); setCurrentPw("") }}>
              취소
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: ApiKeysForm**

```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

const LABELS: Record<string, string> = {
  KIS_APP_KEY: "KIS APP KEY",
  KIS_APP_SECRET: "KIS APP SECRET",
  KIS_ACCOUNT_NO: "KIS 계좌번호",
  GEMINI_API_KEY: "Gemini API Key",
}

export function ApiKeysForm({ items }: { items: Item[] }) {
  const handleUpdate = async (key: string, newValue: string, currentPw: string) => {
    await apiMutate(`/api/v1/settings/${key}`, "PUT", {
      value: newValue, current_password: currentPw,
    })
  }
  const sorted = [...items].sort((a, b) => a.key.localeCompare(b.key))
  if (sorted.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">
          저장된 API 키 없음. <code>ap webapp import-env</code> 또는 CLI <code>ap webapp set</code>으로 초기화하세요.
        </p>
      </Card>
    )
  }
  return (
    <Card className="p-6 space-y-1">
      {sorted.map((item) => (
        <SecretInput
          key={item.key}
          label={LABELS[item.key] || item.key}
          displayValue={item.value}
          isSecret={item.is_secret}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/settings/ webapp-ui/components/domain/settings/
git commit -m "feat(webapp-ui): Settings 탭 쉘 + API 키 편집 (비밀번호 재확인)"
```

---

### Task 34: Settings 리스크 리밋 탭

**Files:**
- Create: `webapp-ui/app/(dashboard)/settings/risk-limits/page.tsx`
- Create: `webapp-ui/components/domain/settings/risk-limits-form.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { RiskLimitsForm } from "@/components/domain/settings/risk-limits-form"

export const dynamic = "force-dynamic"

export default async function RiskLimitsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=risk_limit", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="risk-limits" />
      <RiskLimitsForm items={data.items} />
    </div>
  )
}
```

- [ ] **Step 2: RiskLimitsForm (non-secret, 평문 표시)**

```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

const LABELS: Record<string, string> = {
  MAX_POSITION_WEIGHT: "종목당 최대 비중 (0-1)",
  MAX_DRAWDOWN_SOFT: "MDD soft 임계값 (0-1)",
  MAX_DRAWDOWN_HARD: "MDD hard 임계값 (0-1)",
  MAX_DAILY_ORDERS: "일일 주문 한도 (회)",
  MAX_DAILY_AMOUNT: "일일 금액 한도 (원)",
}

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

export function RiskLimitsForm({ items }: { items: Item[] }) {
  const handleUpdate = async (key: string, newValue: string, currentPw: string) => {
    await apiMutate(`/api/v1/settings/${key}`, "PUT", {
      value: newValue, current_password: currentPw,
    })
  }
  const sorted = [...items].sort((a, b) => a.key.localeCompare(b.key))
  if (sorted.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">
          리스크 리밋 설정 없음. <code>ap webapp import-env</code>로 초기화하세요.
        </p>
      </Card>
    )
  }
  return (
    <Card className="p-6 space-y-1">
      {sorted.map((item) => (
        <SecretInput
          key={item.key}
          label={LABELS[item.key] || item.key}
          displayValue={item.value}
          isSecret={false}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/settings/risk-limits webapp-ui/components/domain/settings/risk-limits-form.tsx
git commit -m "feat(webapp-ui): Settings 리스크 리밋 탭"
```

---

### Task 35: Settings 알림 + 백테스트 기본값 탭

**Files:**
- Create: `webapp-ui/app/(dashboard)/settings/notifications/page.tsx`
- Create: `webapp-ui/app/(dashboard)/settings/backtest-defaults/page.tsx`

- [ ] **Step 1: Notifications 페이지 (SecretInput 재사용)**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { CategorySettingsForm } from "@/components/domain/settings/category-settings-form"

export const dynamic = "force-dynamic"

const LABELS: Record<string, string> = {
  TELEGRAM_BOT_TOKEN: "Telegram Bot Token (콘텐츠)",
  TELEGRAM_CHANNEL_ID: "Telegram Channel ID (콘텐츠)",
  TELEGRAM_MONITOR_BOT_TOKEN: "Telegram Bot Token (모니터링)",
  TELEGRAM_MONITOR_CHANNEL_ID: "Telegram Channel ID (모니터링)",
}

export default async function NotificationsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=notification", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="notifications" />
      <CategorySettingsForm items={data.items} labels={LABELS} />
    </div>
  )
}
```

- [ ] **Step 2: Backtest defaults 페이지 (동일 패턴)**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { CategorySettingsForm } from "@/components/domain/settings/category-settings-form"

export const dynamic = "force-dynamic"

const LABELS: Record<string, string> = {
  BACKTEST_COMMISSION: "수수료율 (0-1)",
  BACKTEST_TAX: "세금율 (0-1)",
  BACKTEST_INITIAL_CAPITAL: "기본 초기 자본 (원)",
  STRATEGY_ALLOCATIONS: "전략 배분 (JSON)",
}

export default async function BacktestDefaultsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=backtest", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="backtest-defaults" />
      <CategorySettingsForm items={data.items} labels={LABELS} />
    </div>
  )
}
```

- [ ] **Step 3: 공용 `CategorySettingsForm`**

`components/domain/settings/category-settings-form.tsx`:
```tsx
"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

export function CategorySettingsForm({
  items, labels,
}: { items: Item[]; labels: Record<string, string> }) {
  const handleUpdate = async (key: string, newValue: string, currentPw: string) => {
    await apiMutate(`/api/v1/settings/${key}`, "PUT", {
      value: newValue, current_password: currentPw,
    })
  }
  const sorted = [...items].sort((a, b) => a.key.localeCompare(b.key))
  if (sorted.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">
          설정 없음. <code>ap webapp import-env</code>로 초기화하세요.
        </p>
      </Card>
    )
  }
  return (
    <Card className="p-6 space-y-1">
      {sorted.map((item) => (
        <SecretInput
          key={item.key}
          label={labels[item.key] || item.key}
          displayValue={item.value}
          isSecret={item.is_secret}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
```

- [ ] **Step 4: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/settings/ webapp-ui/components/domain/settings/category-settings-form.tsx
git commit -m "feat(webapp-ui): Settings 알림 + 백테스트 기본값 탭"
```

---

### Task 36: Audit viewer

**Files:**
- Create: `webapp-ui/app/(dashboard)/audit/page.tsx`
- Create: `webapp-ui/components/domain/audit/audit-table.tsx`

- [ ] **Step 1: 페이지**

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { AuditTable } from "@/components/domain/audit/audit-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string; action_prefix?: string; actor?: string }> }

export default async function AuditPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const qs = new URLSearchParams({ page: String(page), size: "50" })
  if (sp.action_prefix) qs.set("action_prefix", sp.action_prefix)
  if (sp.actor) qs.set("actor", sp.actor)
  const data = await apiFetch<{
    items: { id: number; timestamp: number; event_type: string; component: string; data: Record<string, unknown>; mode: string }[]
    page: number; size: number; total: number
  }>(`/api/v1/audit/events?${qs.toString()}`, { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">감사 로그</h1>
      <AuditTable
        data={data} currentPage={page}
        currentActionPrefix={sp.action_prefix ?? ""}
        currentActor={sp.actor ?? ""}
      />
    </div>
  )
}
```

- [ ] **Step 2: AuditTable**

```tsx
"use client"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Event = {
  id: number; timestamp: number; event_type: string; component: string
  data: Record<string, unknown>; mode: string
}

type Props = {
  data: { items: Event[]; page: number; size: number; total: number }
  currentPage: number
  currentActionPrefix: string
  currentActor: string
}

export function AuditTable({ data, currentPage, currentActionPrefix, currentActor }: Props) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [prefix, setPrefix] = useState(currentActionPrefix)
  const [actor, setActor] = useState(currentActor)

  const apply = () => {
    const sp = new URLSearchParams(params.toString())
    if (prefix) sp.set("action_prefix", prefix); else sp.delete("action_prefix")
    if (actor) sp.set("actor", actor); else sp.delete("actor")
    sp.set("page", "1")
    router.push(`${path}?${sp.toString()}`)
  }
  const go = (p: number) => {
    const sp = new URLSearchParams(params.toString())
    sp.set("page", String(p))
    router.push(`${path}?${sp.toString()}`)
  }
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-end">
        <div>
          <label className="text-xs text-neutral-400 block mb-1">Action prefix</label>
          <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="webapp.settings" />
        </div>
        <div>
          <label className="text-xs text-neutral-400 block mb-1">Actor email</label>
          <Input value={actor} onChange={(e) => setActor(e.target.value)} />
        </div>
        <Button onClick={apply}>필터</Button>
      </div>
      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시각</TableHead>
              <TableHead>이벤트</TableHead>
              <TableHead>모드</TableHead>
              <TableHead>데이터</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="font-mono text-xs">
                  {new Date(e.timestamp * 1000).toISOString().slice(0, 19).replace("T", " ")}
                </TableCell>
                <TableCell className="font-mono">{e.event_type}</TableCell>
                <TableCell>{e.mode}</TableCell>
                <TableCell className="font-mono text-xs truncate max-w-md">
                  {JSON.stringify(e.data)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-between items-center text-sm">
        <span>총 {data.total}건 · {currentPage}/{totalPages}</span>
        <div className="space-x-2">
          <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => go(currentPage - 1)}>이전</Button>
          <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={() => go(currentPage + 1)}>다음</Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/app/\(dashboard\)/audit webapp-ui/components/domain/audit/
git commit -m "feat(webapp-ui): Audit viewer — 감사 로그 조회 + 필터"
```

---

## Part H — Integration

### Task 37: Sidebar 업데이트

**Files:**
- Modify: `webapp-ui/components/layout/sidebar.tsx`

- [ ] **Step 1: Sidebar 항목 확장**

```tsx
import Link from "next/link"

const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/risk", label: "리스크" },
  { href: "/screening", label: "스크리닝" },
  { href: "/backtest", label: "백테스트" },
  { href: "/data", label: "데이터" },
  { href: "/settings", label: "설정" },
  { href: "/audit", label: "감사" },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-neutral-800 p-4">
      <div className="mb-6 text-lg font-bold">AlphaPulse</div>
      <nav className="space-y-1">
        {ITEMS.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className="block rounded px-3 py-2 text-sm hover:bg-neutral-800"
          >
            {it.label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: 빌드 + 커밋**
```bash
cd webapp-ui && pnpm build && cd ..
git add webapp-ui/components/layout/sidebar.tsx
git commit -m "feat(webapp-ui): Sidebar — Phase 2 도메인 활성 (disabled 해제)"
```

---

### Task 38: Playwright E2E 확장

**Files:**
- Create: `webapp-ui/e2e/phase2-flow.spec.ts`

- [ ] **Step 1: E2E 테스트**

```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe.serial("Phase 2 flow smoke", () => {
  test("login", async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("mode selector changes URL", async ({ page }) => {
    await page.goto("/portfolio")
    await page.selectOption('select[aria-label="Mode selector"]', "backtest")
    await expect(page).toHaveURL(/mode=backtest/)
  })

  test("risk page loads", async ({ page }) => {
    await page.goto("/risk")
    await expect(page.getByRole("heading", { name: /리스크/ })).toBeVisible()
  })

  test("screening list loads", async ({ page }) => {
    await page.goto("/screening")
    await expect(page.getByRole("heading", { name: /스크리닝/ })).toBeVisible()
    await expect(page.getByRole("button", { name: "새 스크리닝" })).toBeVisible()
  })

  test("data page shows collect_all disabled", async ({ page }) => {
    await page.goto("/data")
    const disabled = page.getByRole("button", { name: /전종목 수집/ })
    await expect(disabled).toBeVisible()
    await expect(disabled).toBeDisabled()
  })

  test("settings tabs navigate", async ({ page }) => {
    await page.goto("/settings/api-keys")
    await expect(page.getByRole("heading", { name: "설정" })).toBeVisible()
    await page.click('a[href="/settings/risk-limits"]')
    await expect(page).toHaveURL(/risk-limits/)
  })

  test("audit viewer loads", async ({ page }) => {
    await page.goto("/audit")
    await expect(page.getByRole("heading", { name: "감사 로그" })).toBeVisible()
  })
})
```

- [ ] **Step 2: 실행 검증 (서비스 기동 환경에서만)**
```bash
# FastAPI + Next.js 실행 중
cd webapp-ui && pnpm exec playwright test e2e/phase2-flow.spec.ts
```

서비스 미기동 환경에서는 테스트 파일 작성만 하고 실제 실행은 생략 (Phase 1 Task 34와 동일).

- [ ] **Step 3: 커밋**
```bash
git add webapp-ui/e2e/phase2-flow.spec.ts
git commit -m "test(webapp-ui): Phase 2 E2E — 모드 전환 / 각 도메인 페이지 스모크"
```

---

## Phase 2 완료 기준

- [ ] 38개 태스크 전부 commit
- [ ] `pytest tests/webapp/` 통과 (신규 ~50+ 테스트 추가)
- [ ] 기존 `pytest tests/ -q` 회귀 없음 (976개 유지)
- [ ] `ruff check alphapulse/` 클린
- [ ] `cd webapp-ui && pnpm build` 성공
- [ ] 수동 검증:
  - [ ] 홈 대시보드 표시
  - [ ] 모드 전환 (Paper → Backtest)
  - [ ] Portfolio/Risk/Screening/Data 페이지 정상 동작
  - [ ] Settings → API 키 변경 → 감사 로그 기록 확인
  - [ ] Data update Job 실행 → 진행률 표시
  - [ ] collect_all 버튼 비활성 + 툴팁 확인
- [ ] Playwright E2E 통과 (서비스 기동 환경에서)
- [ ] 운영 문서 업데이트 — `docs/operations/webapp-phase2.md` 작성 (Settings 관리, Fernet 키 등)

## 다음 단계

Phase 2 완료 후 별도 plan 문서로:
- `docs/superpowers/plans/YYYY-MM-DD-webapp-phase3.md` — Market/Briefing/Feedback + SaaS 전환 + 실매매 UI

각 Phase 독립 릴리스 가능.
