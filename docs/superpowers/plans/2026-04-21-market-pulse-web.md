# Market Pulse Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AlphaPulse 웹앱에 Market Pulse 도메인을 추가해 CLI `ap market pulse/investor/...` 을 웹에서 대체한다.

**Architecture:** `PulseHistory` 재사용 (테이블 스키마 무변경, JSON 본문에 `indicator_descriptions` 확장) + 신규 FastAPI 라우터 `alphapulse/webapp/api/market.py` + 기존 JobRunner 재사용 + Next.js 3-페이지 (`/market/pulse`, `/market/pulse/[date]`, `/market/pulse/jobs/[id]`). 재활용: `/api/v1/jobs/{id}` 폴링 엔드포인트는 기존 것을 그대로 사용 (spec 4.1 에서 언급한 전용 경로는 중복).

**Tech Stack:** FastAPI, Pydantic, Next.js 15 App Router, recharts, SQLite. Market 도메인은 sync only(CLAUDE.md 규칙) — API `async def` 에서 `asyncio.to_thread` 로 SignalEngine 호출.

**Spec 참조:** `docs/superpowers/specs/2026-04-21-market-pulse-web-design.md`

---

## 파일 구조 (최종)

**신규 (백엔드):**
- `alphapulse/webapp/api/market.py` — FastAPI 라우터 (4 엔드포인트: GET /latest, /history, /{date}, POST /run)
- `alphapulse/webapp/services/market_runner.py` — `run_market_pulse_sync` Job 함수
- `tests/webapp/api/test_market.py` — API 테스트
- `tests/webapp/services/test_market_runner.py` — Runner 테스트

**신규 (프론트엔드):**
- `webapp-ui/lib/market-labels.ts` — 11개 지표 한글명 + 시그널 색상 스타일
- `webapp-ui/components/domain/market/score-hero-card.tsx`
- `webapp-ui/components/domain/market/indicator-card.tsx`
- `webapp-ui/components/domain/market/indicator-grid.tsx`
- `webapp-ui/components/domain/market/pulse-history-chart.tsx`
- `webapp-ui/components/domain/market/run-confirm-modal.tsx`
- `webapp-ui/components/domain/market/no-pulse-snapshot.tsx`
- `webapp-ui/components/domain/market/date-picker-inline.tsx`
- `webapp-ui/app/(dashboard)/market/pulse/page.tsx`
- `webapp-ui/app/(dashboard)/market/pulse/[date]/page.tsx`
- `webapp-ui/app/(dashboard)/market/pulse/jobs/[id]/page.tsx`
- `webapp-ui/e2e/market-pulse.spec.ts`

**수정:**
- `alphapulse/webapp/jobs/models.py` — JobKind literal 에 `"market_pulse"` 추가
- `alphapulse/market/engine/signal_engine.py` — `history.save` payload 에 `indicator_descriptions` 추가
- `alphapulse/webapp/store/jobs.py` — `find_running_by_kind_and_date(kind, date)` 헬퍼 추가
- `alphapulse/webapp/main.py` — PulseHistory 생성 후 `app.state.pulse_history` 주입 + `market_router` include
- `webapp-ui/components/layout/sidebar.tsx` — `"시황"` 항목 추가

---

## Task 1: JobKind 확장 + SignalEngine 저장 payload 확장

**Files:**
- Modify: `alphapulse/webapp/jobs/models.py:10`
- Modify: `alphapulse/market/engine/signal_engine.py:320-330`
- Test: `tests/market/engine/test_signal_engine_save.py` (신규)

- [ ] **Step 1: Write failing test for extraction helper**

Create `tests/market/engine/test_signal_engine_save.py`:
```python
"""SignalEngine — indicator_descriptions 추출 헬퍼 검증."""
from alphapulse.market.engine.signal_engine import (
    extract_indicator_descriptions,
)


def test_extracts_details_strings_from_analyzer_results():
    """각 analyzer 결과 dict 에서 'details' 문자열만 추출."""
    analyzer_results = {
        "investor_flow": {"score": 50, "details": "외국인 +580억"},
        "vkospi": {"score": -30, "details": "V-KOSPI 22.5 (위험)"},
    }
    assert extract_indicator_descriptions(analyzer_results) == {
        "investor_flow": "외국인 +580억",
        "vkospi": "V-KOSPI 22.5 (위험)",
    }


def test_returns_none_when_details_key_missing():
    analyzer_results = {"bad": {"score": 0}}  # details 키 없음
    assert extract_indicator_descriptions(analyzer_results) == {"bad": None}


def test_returns_none_for_non_dict_value():
    analyzer_results = {"broken": None, "other": "string_not_dict"}
    assert extract_indicator_descriptions(analyzer_results) == {
        "broken": None, "other": None,
    }


def test_empty_input_returns_empty_dict():
    assert extract_indicator_descriptions({}) == {}
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest tests/market/engine/test_signal_engine_save.py -v`
Expected: FAIL with `ImportError: cannot import name 'extract_indicator_descriptions'`

- [ ] **Step 3: Extend JobKind literal**

Edit `alphapulse/webapp/jobs/models.py` line 10:
```python
# before
JobKind = Literal["backtest", "screening", "data_update"]

# after
JobKind = Literal["backtest", "screening", "data_update", "market_pulse"]
```

- [ ] **Step 4: Add extraction helper and use it in SignalEngine.run**

Edit `alphapulse/market/engine/signal_engine.py`:

Add this module-level helper after the `logger = logging.getLogger(__name__)` line (near the top of the file):
```python
def extract_indicator_descriptions(
    analyzer_results: dict,
) -> dict[str, str | None]:
    """analyzer 반환 dict 들에서 'details' 문자열만 추출.

    각 값이 dict 가 아니거나 'details' 키가 없으면 None.
    DataFrame 등 직렬화 불가 필드는 제외되므로 JSON 안전.
    """
    return {
        k: (v.get("details") if isinstance(v, dict) else None)
        for k, v in analyzer_results.items()
    }
```

Then update the `self.history.save(...)` call (around line 320-330):

```python
# 기존
self.history.save(target_date, final_score, signal, {
    "indicator_scores": serializable_scores,
    "period": period,
})

# 변경 후
self.history.save(target_date, final_score, signal, {
    "indicator_scores": serializable_scores,
    "indicator_descriptions": extract_indicator_descriptions(details),
    "period": period,
})
```

- [ ] **Step 5: Run test to confirm it passes**

Run: `pytest tests/market/engine/test_signal_engine_save.py -v`
Expected: PASS (4개 테스트)

- [ ] **Step 6: Run full market tests to confirm no regression**

Run: `pytest tests/market/ -q`
Expected: 모든 기존 테스트 그린. 기존 테스트가 `indicator_scores` / `period` 키만 assert 하면 영향 없음.

- [ ] **Step 7: Commit**

```bash
git add alphapulse/webapp/jobs/models.py alphapulse/market/engine/signal_engine.py tests/market/engine/test_signal_engine_save.py
git commit -m "feat(market): PulseHistory details 에 indicator_descriptions 저장 + JobKind market_pulse 추가"
```

---

## Task 2: JobRepository 중복 실행 감지 헬퍼

**Files:**
- Modify: `alphapulse/webapp/store/jobs.py` (신규 메서드 추가)
- Test: `tests/webapp/store/test_jobs_find_running.py` (신규)

- [ ] **Step 1: Write failing test**

Create `tests/webapp/store/test_jobs_find_running.py`:
```python
"""JobRepository.find_running_by_kind_and_date 테스트."""
import json

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/store/test_jobs_find_running.py -v`
Expected: FAIL with `AttributeError: 'JobRepository' object has no attribute 'find_running_by_kind_and_date'`

- [ ] **Step 3: Implement the method**

Add to `alphapulse/webapp/store/jobs.py` (at end of `JobRepository` class, after `list_by_status`):

```python
    def find_running_by_kind_and_date(
        self, kind: str, date: str,
    ) -> Job | None:
        """kind 와 params.date 가 일치하는 pending/running Job 을 1건 반환.

        중복 실행 요청 방지용. 동일 날짜의 다른 Job 이 진행 중이면 그걸 재사용.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE kind = ? "
                "AND status IN ('pending', 'running') "
                "AND json_extract(params, '$.date') = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (kind, date),
            ).fetchone()
        return _row_to_job(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/webapp/store/test_jobs_find_running.py -v`
Expected: PASS (6개 테스트 모두)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/store/jobs.py tests/webapp/store/test_jobs_find_running.py
git commit -m "feat(webapp): JobRepository.find_running_by_kind_and_date — Market Pulse 중복 실행 감지"
```

---

## Task 3: MarketRunner 서비스 — `run_market_pulse_sync`

**Files:**
- Create: `alphapulse/webapp/services/market_runner.py`
- Test: `tests/webapp/services/test_market_runner.py`

- [ ] **Step 1: Write failing test**

Create `tests/webapp/services/test_market_runner.py`:
```python
"""run_market_pulse_sync 테스트 — SignalEngine 모킹."""
from unittest.mock import MagicMock, patch


def test_runs_engine_and_returns_date():
    """SignalEngine.run 을 호출하고 저장된 date 를 반환한다."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260420",
        "score": 42.0,
        "signal": "moderately_bullish",
        "indicator_scores": {"investor_flow": 50.0},
        "details": {},
    }

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        result_date = run_market_pulse_sync(
            date="20260420",
            progress_callback=on_progress,
        )

    assert result_date == "20260420"
    mock_engine.run.assert_called_once_with(date="20260420")
    assert progress_calls[0] == (0, 1, "시황 분석 실행 중")
    assert progress_calls[-1] == (1, 1, "완료")


def test_passes_none_date_to_engine():
    """date=None 이면 SignalEngine 이 직전 거래일을 자동 선택한다."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260420", "score": 10.0, "signal": "neutral",
        "indicator_scores": {}, "details": {},
    }
    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        run_market_pulse_sync(date=None, progress_callback=lambda *_: None)

    mock_engine.run.assert_called_once_with(date=None)


def test_propagates_engine_exception():
    """SignalEngine.run 예외 그대로 raise (JobRunner 가 failed 로 마킹)."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.side_effect = RuntimeError("fetch failed")

    import pytest
    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        with pytest.raises(RuntimeError, match="fetch failed"):
            run_market_pulse_sync(date="20260420", progress_callback=lambda *_: None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/services/test_market_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alphapulse.webapp.services.market_runner'`

- [ ] **Step 3: Implement runner**

Create `alphapulse/webapp/services/market_runner.py`:
```python
"""MarketRunner — Job 에서 호출되는 Market Pulse 실행 헬퍼.

SignalEngine.run() 을 sync 로 호출하고 progress_callback 으로 Job 진행률을 기록.
저장은 SignalEngine 내부의 PulseHistory.save 가 담당 → 여기선 저장된 date 만 반환.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.market.engine.signal_engine import SignalEngine


def run_market_pulse_sync(
    *,
    date: str | None,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """SignalEngine 을 실행하고 저장된 날짜를 반환한다.

    Args:
        date: YYYYMMDD 또는 None(= 직전 거래일).
        progress_callback: Job 진행률 훅. (current, total, text).

    Returns:
        실제 저장된 날짜 (YYYYMMDD).
    """
    progress_callback(0, 1, "시황 분석 실행 중")
    engine = SignalEngine()
    result = engine.run(date=date)
    progress_callback(1, 1, "완료")
    return result["date"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/webapp/services/test_market_runner.py -v`
Expected: PASS (3개 테스트)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/services/market_runner.py tests/webapp/services/test_market_runner.py
git commit -m "feat(webapp): run_market_pulse_sync — Job 어댑터 for SignalEngine"
```

---

## Task 4: Market API — GET /latest, /history, /{date}

**Files:**
- Create: `alphapulse/webapp/api/market.py` (부분 — GET 엔드포인트만)
- Test: `tests/webapp/api/test_market.py` (신규)

- [ ] **Step 1: Write failing tests for GET endpoints**

Create `tests/webapp/api/test_market.py`:
```python
"""Market Pulse API 테스트 — GET endpoints."""
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.core.storage import PulseHistory
from alphapulse.webapp.api.market import router as market_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


@pytest.fixture
def pulse_history(tmp_path):
    return PulseHistory(db_path=tmp_path / "history.db")


@pytest.fixture
def app(webapp_db, pulse_history):
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
    app.state.pulse_history = pulse_history
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(market_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app)
    r = c.get("/api/v1/csrf-token")
    token = r.json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"x-csrf-token": token},
    )
    return c


def test_latest_returns_null_when_empty(client):
    r = client.get("/api/v1/market/pulse/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_latest_returns_most_recent(client, pulse_history):
    pulse_history.save(
        "20260419", 10.0, "neutral",
        {"indicator_scores": {"investor_flow": 5}, "period": "daily",
         "indicator_descriptions": {"investor_flow": "외국인 +100억"}},
    )
    pulse_history.save(
        "20260420", 42.0, "moderately_bullish",
        {"indicator_scores": {"investor_flow": 60}, "period": "daily",
         "indicator_descriptions": {"investor_flow": "외국인 +580억"}},
    )
    r = client.get("/api/v1/market/pulse/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260420"
    assert body["score"] == 42.0
    assert body["signal"] == "moderately_bullish"
    assert body["indicator_scores"]["investor_flow"] == 60
    assert body["indicator_descriptions"]["investor_flow"] == "외국인 +580억"
    assert body["period"] == "daily"


def test_history_returns_empty_when_no_data(client):
    r = client.get("/api/v1/market/pulse/history?days=30")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_history_returns_ascending_order(client, pulse_history):
    pulse_history.save("20260420", 42.0, "moderately_bullish",
                       {"indicator_scores": {}, "period": "daily"})
    pulse_history.save("20260418", 10.0, "neutral",
                       {"indicator_scores": {}, "period": "daily"})
    pulse_history.save("20260419", 20.0, "moderately_bullish",
                       {"indicator_scores": {}, "period": "daily"})
    r = client.get("/api/v1/market/pulse/history?days=10")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [x["date"] for x in items] == ["20260418", "20260419", "20260420"]


def test_pulse_detail_returns_404_when_missing(client):
    r = client.get("/api/v1/market/pulse/19000101")
    assert r.status_code == 404


def test_pulse_detail_returns_all_fields(client, pulse_history):
    pulse_history.save(
        "20260420", 42.0, "moderately_bullish",
        {
            "indicator_scores": {"investor_flow": 60, "vkospi": None},
            "indicator_descriptions": {"investor_flow": "외국인 +580억", "vkospi": None},
            "period": "daily",
        },
    )
    r = client.get("/api/v1/market/pulse/20260420")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260420"
    assert body["indicator_scores"]["vkospi"] is None
    assert body["indicator_descriptions"]["vkospi"] is None


def test_pulse_detail_handles_legacy_row_without_descriptions(client, pulse_history):
    """과거 저장분 (indicator_descriptions 키 없음) → null 로 응답."""
    pulse_history.save(
        "20260315", 15.0, "neutral",
        {"indicator_scores": {"investor_flow": 15}, "period": "daily"},
    )
    r = client.get("/api/v1/market/pulse/20260315")
    assert r.status_code == 200
    body = r.json()
    assert body["indicator_descriptions"] == {"investor_flow": None}


def test_latest_requires_auth(app):
    c = TestClient(app)
    r = c.get("/api/v1/market/pulse/latest")
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_market.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alphapulse.webapp.api.market'`

- [ ] **Step 3: Implement GET endpoints**

Create `alphapulse/webapp/api/market.py`:
```python
"""Market Pulse API — 이력 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage import PulseHistory
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class PulseSnapshot(BaseModel):
    date: str
    score: float
    signal: str
    indicator_scores: dict[str, float | None]
    indicator_descriptions: dict[str, str | None]
    period: str
    created_at: float


class HistoryItem(BaseModel):
    date: str
    score: float
    signal: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


class RunPulseRequest(BaseModel):
    date: str | None = None


class RunPulseResponse(BaseModel):
    job_id: str
    reused: bool


def get_pulse_history(request: Request) -> PulseHistory:
    return request.app.state.pulse_history


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def _row_to_snapshot(row: dict) -> PulseSnapshot:
    """PulseHistory.get 결과 dict 를 API 응답 모델로 변환.

    과거 저장분은 indicator_descriptions 키가 없으므로
    indicator_scores 키셋에 맞춰 None 으로 채운다.
    """
    details = row.get("details") or {}
    scores = details.get("indicator_scores") or {}
    descriptions_raw = details.get("indicator_descriptions") or {}
    # 모든 score 키에 대해 description 기본 None
    descriptions = {k: descriptions_raw.get(k) for k in scores.keys()}
    return PulseSnapshot(
        date=row["date"],
        score=row["score"],
        signal=row["signal"],
        indicator_scores=scores,
        indicator_descriptions=descriptions,
        period=details.get("period", "daily"),
        created_at=row["created_at"],
    )


@router.get("/pulse/latest", response_model=PulseSnapshot | None)
async def get_latest(
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    rows = history.get_recent(days=1)
    if not rows:
        return None
    return _row_to_snapshot(rows[0])


@router.get("/pulse/history", response_model=HistoryResponse)
async def get_history(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    rows = history.get_recent(days=days)
    rows_asc = sorted(rows, key=lambda r: r["date"])
    return HistoryResponse(
        items=[
            HistoryItem(date=r["date"], score=r["score"], signal=r["signal"])
            for r in rows_asc
        ]
    )


@router.get("/pulse/{date}", response_model=PulseSnapshot)
async def get_pulse(
    date: str,
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    row = history.get(date)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pulse history not found for {date}",
        )
    return _row_to_snapshot(row)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/api/test_market.py -v`
Expected: PASS (7개 GET 테스트 + auth 테스트)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/api/market.py tests/webapp/api/test_market.py
git commit -m "feat(webapp): Market Pulse API GET endpoints (latest/history/{date})"
```

---

## Task 5: Market API — POST /run (Job + 중복 감지)

**Files:**
- Modify: `alphapulse/webapp/api/market.py` (POST 추가)
- Modify: `tests/webapp/api/test_market.py` (POST 테스트 추가)

- [ ] **Step 1: Write failing tests for POST /run**

Append to `tests/webapp/api/test_market.py`:
```python
def test_run_creates_job_and_returns_id(client, monkeypatch):
    """POST /run → BackgroundTasks 로 스케줄, reused=false."""
    called: dict = {}

    async def fake_runner_run(self, job_id, func, **kwargs):
        called["job_id"] = job_id
        called["kwargs"] = kwargs

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is False
    assert "job_id" in body


def test_run_reuses_existing_job(client, app, monkeypatch):
    """같은 date 의 running Job 있으면 그 id 반환, reused=true."""
    # 기존 Job 수동 생성
    app.state.jobs.create(
        job_id="existing-job", kind="market_pulse",
        params={"date": "20260420"}, user_id=1,
    )
    app.state.jobs.update_status("existing-job", "running")

    async def fake_runner_run(self, job_id, func, **kwargs):
        raise AssertionError("should not be called for reused job")

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "existing-job"
    assert body["reused"] is True


def test_run_with_null_date_resolves_via_helper(client, app, monkeypatch):
    """date=None → _resolve_target_date 호출, 결과가 Job params.date 에 저장."""
    monkeypatch.setattr(
        "alphapulse.webapp.api.market._resolve_target_date",
        lambda d: "20260420",
    )

    async def noop(self, *a, **kw):
        pass

    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )

    r = client.post("/api/v1/market/pulse/run", json={})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # DB 에서 직접 params 확인
    saved = app.state.jobs.get(job_id)
    assert saved is not None
    assert saved.params.get("date") == "20260420"


def test_run_audit_log(client, app, monkeypatch):
    """POST /run 시 audit.log 호출."""
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )

    r = client.post("/api/v1/market/pulse/run", json={"date": "20260420"})
    assert r.status_code == 200
    assert app.state.audit.log.called
    call_args = app.state.audit.log.call_args
    assert call_args.args[0] == "webapp.market.pulse.run"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_market.py -v -k "run"`
Expected: FAIL — POST 엔드포인트 없음

- [ ] **Step 3: Implement POST /run**

Add to `alphapulse/webapp/api/market.py`:

```python
import uuid

from fastapi import BackgroundTasks
from alphapulse.core.config import Config
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.market_runner import run_market_pulse_sync


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def _resolve_target_date(date: str | None) -> str:
    """None 이면 Config 의 직전 거래일 규칙으로 결정."""
    if date:
        return Config().parse_date(date)
    return Config().get_prev_trading_day()


@router.post("/pulse/run", response_model=RunPulseResponse)
async def run_pulse(
    body: RunPulseRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    target_date = _resolve_target_date(body.date)

    # 중복 running Job 감지 → 재사용
    existing = jobs.find_running_by_kind_and_date("market_pulse", target_date)
    if existing is not None:
        return RunPulseResponse(job_id=existing.id, reused=True)

    job_id = str(uuid.uuid4())
    jobs.create(
        job_id=job_id, kind="market_pulse",
        params={"date": target_date}, user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.market.pulse.run",
            component="webapp",
            data={"user_id": user.id, "job_id": job_id, "date": target_date},
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_market_pulse_sync,
            date=target_date,
        )

    background_tasks.add_task(_run)
    return RunPulseResponse(job_id=job_id, reused=False)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/api/test_market.py -v`
Expected: PASS (모든 API 테스트)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/api/market.py tests/webapp/api/test_market.py
git commit -m "feat(webapp): Market Pulse POST /run + 중복 Job 재사용"
```

---

## Task 6: main.py — Router 등록 + PulseHistory state 주입

**Files:**
- Modify: `alphapulse/webapp/main.py`
- Test: 전체 앱 부팅 테스트 (기존 `tests/webapp/test_app_boot.py` 있으면 거기에 추가, 없으면 신규)

- [ ] **Step 1: Write failing test**

Create or append to `tests/webapp/test_app_boot.py`:
```python
"""create_app 부팅 — market router 등록 확인."""
from alphapulse.webapp.main import create_app


def test_market_router_registered():
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/market/pulse/latest" in routes
    assert "/api/v1/market/pulse/history" in routes
    assert "/api/v1/market/pulse/{date}" in routes
    assert "/api/v1/market/pulse/run" in routes


def test_pulse_history_on_state():
    app = create_app()
    assert hasattr(app.state, "pulse_history")
    assert app.state.pulse_history is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/test_app_boot.py -v`
Expected: FAIL — routes 없음 / state 속성 없음

- [ ] **Step 3: Wire market router + pulse_history state**

Edit `alphapulse/webapp/main.py`:

Add import near other `api` imports (around line 14):
```python
from alphapulse.webapp.api.market import router as market_router
```

Add PulseHistory import near other storage imports:
```python
from alphapulse.core.storage import PulseHistory
```

In `create_app` function, after existing repo/reader creation (around line 90), add:
```python
    pulse_history = PulseHistory(db_path=core.HISTORY_DB)
```

After `app.state.audit_reader = audit_reader` (around line 152), add:
```python
    app.state.pulse_history = pulse_history
```

After `app.include_router(dashboard_router)` (around line 178), add:
```python
    app.include_router(market_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/test_app_boot.py -v`
Expected: PASS

- [ ] **Step 5: Run full webapp tests to confirm no regression**

Run: `pytest tests/webapp/ -q`
Expected: 모두 그린

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/main.py tests/webapp/test_app_boot.py
git commit -m "feat(webapp): main.py 에 market router + PulseHistory 상태 주입"
```

---

## Task 7: Frontend — 지표 라벨 + 시그널 스타일 유틸

**Files:**
- Create: `webapp-ui/lib/market-labels.ts`

- [ ] **Step 1: Create labels module**

Create `webapp-ui/lib/market-labels.ts`:
```typescript
// 11개 Market Pulse 지표 한글명 + 시그널 색상 매핑
// 기준: alphapulse/market/reporters/terminal.py INDICATOR_NAMES

export const INDICATOR_LABELS: Record<string, string> = {
  investor_flow: "외국인+기관 수급",
  spot_futures_align: "선물 베이시스",
  futures_flow: "선물 수급",
  program_trade: "프로그램 비차익",
  sector_momentum: "업종 모멘텀",
  exchange_rate: "환율 (USD/KRW)",
  vkospi: "V-KOSPI",
  interest_rate_diff: "한미 금리차",
  global_market: "글로벌 시장",
  fund_flow: "증시 자금",
  adr_volume: "ADR + 거래량",
}

export const INDICATOR_ORDER: string[] = [
  "investor_flow", "spot_futures_align", "futures_flow",
  "program_trade", "sector_momentum", "exchange_rate",
  "vkospi", "interest_rate_diff", "global_market",
  "fund_flow", "adr_volume",
]

export type SignalLevel =
  | "strong_bullish" | "moderately_bullish" | "neutral"
  | "moderately_bearish" | "strong_bearish"

export const SIGNAL_STYLE: Record<SignalLevel, {
  bar: string; badge: string; label: string
}> = {
  strong_bullish: {
    bar: "bg-green-500",
    badge: "bg-green-500/20 text-green-300",
    label: "강한 강세",
  },
  moderately_bullish: {
    bar: "bg-emerald-500",
    badge: "bg-emerald-500/20 text-emerald-300",
    label: "중립-강세",
  },
  neutral: {
    bar: "bg-yellow-500",
    badge: "bg-yellow-500/20 text-yellow-300",
    label: "중립",
  },
  moderately_bearish: {
    bar: "bg-orange-500",
    badge: "bg-orange-500/20 text-orange-300",
    label: "중립-약세",
  },
  strong_bearish: {
    bar: "bg-red-500",
    badge: "bg-red-500/20 text-red-300",
    label: "강한 약세",
  },
}

export function scoreToSignal(score: number): SignalLevel {
  if (score >= 60) return "strong_bullish"
  if (score >= 20) return "moderately_bullish"
  if (score >= -19) return "neutral"
  if (score >= -59) return "moderately_bearish"
  return "strong_bearish"
}

export function signalStyle(signal: string) {
  return SIGNAL_STYLE[signal as SignalLevel] ?? SIGNAL_STYLE.neutral
}
```

- [ ] **Step 2: Verify import resolves**

Run: `cd webapp-ui && npx tsc --noEmit lib/market-labels.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/lib/market-labels.ts
git commit -m "feat(webapp-ui): Market Pulse 지표 라벨 + 시그널 스타일 유틸"
```

---

## Task 8: Frontend — ScoreHeroCard

**Files:**
- Create: `webapp-ui/components/domain/market/score-hero-card.tsx`

- [ ] **Step 1: Implement component**

Create `webapp-ui/components/domain/market/score-hero-card.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { signalStyle } from "@/lib/market-labels"

export type PulseSnapshot = {
  date: string
  score: number
  signal: string
  indicator_scores: Record<string, number | null>
  indicator_descriptions: Record<string, string | null>
  period: string
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function ScoreHeroCard({
  snapshot,
  onRun,
  running = false,
}: {
  snapshot: PulseSnapshot
  onRun?: () => void
  running?: boolean
}) {
  const style = signalStyle(snapshot.signal)
  const sign = snapshot.score >= 0 ? "+" : ""

  return (
    <Card className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          K-Market Pulse · {formatDate(snapshot.date)} · {formatTime(snapshot.created_at)} 저장
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-5xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{snapshot.score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>
      {onRun && (
        <Button onClick={onRun} disabled={running}>
          {running ? "실행 중…" : "지금 실행"}
        </Button>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/market/score-hero-card.tsx
git commit -m "feat(webapp-ui): ScoreHeroCard — Market Pulse 최신 스코어 카드"
```

---

## Task 9: Frontend — IndicatorCard + IndicatorGrid

**Files:**
- Create: `webapp-ui/components/domain/market/indicator-card.tsx`
- Create: `webapp-ui/components/domain/market/indicator-grid.tsx`

- [ ] **Step 1: Implement IndicatorCard**

Create `webapp-ui/components/domain/market/indicator-card.tsx`:
```tsx
"use client"
import { useState } from "react"
import { signalStyle, scoreToSignal } from "@/lib/market-labels"

export function IndicatorCard({
  koreanName,
  score,
  description,
  defaultExpanded = false,
}: {
  koreanName: string
  score: number | null
  description: string | null
  defaultExpanded?: boolean
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (score === null) {
    return (
      <div className="rounded border border-neutral-800 bg-neutral-900 p-3">
        <p className="text-sm text-neutral-300">{koreanName}</p>
        <p className="text-xs text-neutral-500 mt-1">데이터 없음</p>
      </div>
    )
  }

  const style = signalStyle(scoreToSignal(score))
  const normalized = Math.max(0, Math.min(1, (score + 100) / 200))
  const sign = score >= 0 ? "+" : ""

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="text-left w-full rounded border border-neutral-800 bg-neutral-900 p-3 hover:border-neutral-600 transition"
    >
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-neutral-300">{koreanName}</p>
        <p className="text-sm font-mono tabular-nums">
          {sign}{score.toFixed(1)}
        </p>
      </div>
      <div className="h-1.5 rounded bg-neutral-800 overflow-hidden">
        <div
          className={`h-full ${style.bar}`}
          style={{ width: `${normalized * 100}%` }}
        />
      </div>
      {expanded && (
        <div className="mt-3 text-xs text-neutral-400 whitespace-pre-line">
          {description ?? "설명 저장 이전 날짜 — '지금 실행' 으로 재계산하세요"}
        </div>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Implement IndicatorGrid**

Create `webapp-ui/components/domain/market/indicator-grid.tsx`:
```tsx
"use client"
import { IndicatorCard } from "./indicator-card"
import { INDICATOR_LABELS, INDICATOR_ORDER } from "@/lib/market-labels"

export function IndicatorGrid({
  scores,
  descriptions,
  expandAll = false,
}: {
  scores: Record<string, number | null>
  descriptions: Record<string, string | null>
  expandAll?: boolean
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {INDICATOR_ORDER.map((key) => (
        <IndicatorCard
          key={key}
          koreanName={INDICATOR_LABELS[key] ?? key}
          score={scores[key] ?? null}
          description={descriptions[key] ?? null}
          defaultExpanded={expandAll}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/market/indicator-card.tsx webapp-ui/components/domain/market/indicator-grid.tsx
git commit -m "feat(webapp-ui): IndicatorCard/IndicatorGrid — 11개 지표 카드"
```

---

## Task 10: Frontend — PulseHistoryChart

**Files:**
- Create: `webapp-ui/components/domain/market/pulse-history-chart.tsx`

- [ ] **Step 1: Implement chart**

Create `webapp-ui/components/domain/market/pulse-history-chart.tsx`:
```tsx
"use client"
import { useState } from "react"
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip,
  ReferenceArea, ReferenceLine,
} from "recharts"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export type HistoryItem = {
  date: string    // YYYYMMDD
  score: number
  signal: string
}

const RANGES: { days: number; label: string }[] = [
  { days: 30, label: "30일" },
  { days: 60, label: "60일" },
  { days: 90, label: "90일" },
]

function formatDateTick(yyyymmdd: string): string {
  return `${yyyymmdd.slice(4, 6)}/${yyyymmdd.slice(6)}`
}

export function PulseHistoryChart({
  items,
  onRangeChange,
  initialRange = 30,
}: {
  items: HistoryItem[]
  onRangeChange?: (days: number) => void
  initialRange?: number
}) {
  const [range, setRange] = useState(initialRange)

  return (
    <Card className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm text-neutral-300">Pulse Score 추이</h2>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <Button
              key={r.days}
              size="sm"
              variant={range === r.days ? "default" : "outline"}
              onClick={() => {
                setRange(r.days)
                onRangeChange?.(r.days)
              }}
            >
              {r.label}
            </Button>
          ))}
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={items}>
            <XAxis
              dataKey="date" tickFormatter={formatDateTick}
              stroke="#888" fontSize={11}
            />
            <YAxis
              domain={[-100, 100]} stroke="#888" fontSize={11}
              ticks={[-100, -60, -20, 20, 60, 100]}
            />
            <ReferenceArea y1={60} y2={100} fill="#22c55e" fillOpacity={0.08} />
            <ReferenceArea y1={20} y2={60} fill="#10b981" fillOpacity={0.06} />
            <ReferenceArea y1={-19} y2={20} fill="#eab308" fillOpacity={0.06} />
            <ReferenceArea y1={-59} y2={-19} fill="#f97316" fillOpacity={0.06} />
            <ReferenceArea y1={-100} y2={-59} fill="#ef4444" fillOpacity={0.08} />
            <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{
                background: "#1f1f1f", border: "1px solid #333",
                fontSize: 12,
              }}
              labelFormatter={formatDateTick}
              formatter={(v: number) => [v.toFixed(1), "Score"]}
            />
            <Line
              type="monotone" dataKey="score" stroke="#60a5fa"
              strokeWidth={2} dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/market/pulse-history-chart.tsx
git commit -m "feat(webapp-ui): PulseHistoryChart — 30/60/90일 스코어 추이 차트"
```

---

## Task 11: Frontend — RunConfirmModal + NoPulseSnapshot

**Files:**
- Create: `webapp-ui/components/domain/market/run-confirm-modal.tsx`
- Create: `webapp-ui/components/domain/market/no-pulse-snapshot.tsx`

- [ ] **Step 1: Implement RunConfirmModal**

Create `webapp-ui/components/domain/market/run-confirm-modal.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

function formatTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function RunConfirmModal({
  existingSavedAt,
  onConfirm,
  onCancel,
}: {
  existingSavedAt: number
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onCancel}
    >
      <Card
        className="p-6 max-w-md w-full m-4 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">재실행 확인</h3>
        <p className="text-sm text-neutral-300">
          오늘 날짜의 Pulse 는 <span className="font-mono">{formatTime(existingSavedAt)}</span>
          에 이미 계산되어 있습니다. 재실행하면 기존 값이 덮어씌워집니다.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>취소</Button>
          <Button onClick={onConfirm}>재실행</Button>
        </div>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Implement NoPulseSnapshot**

Create `webapp-ui/components/domain/market/no-pulse-snapshot.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoPulseSnapshot({ onRun }: { onRun?: () => void }) {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">Pulse 이력이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 K-Market Pulse 가 계산된 적이 없습니다.<br />
        Daily briefing 을 실행하거나 지금 바로 계산해보세요.
      </p>
      <div className="flex justify-center gap-2">
        {onRun && <Button onClick={onRun}>지금 실행</Button>}
      </div>
      <p className="text-xs text-neutral-500">
        CLI: <code className="px-1 bg-neutral-800 rounded">ap market pulse</code> 또는 <code className="px-1 bg-neutral-800 rounded">ap briefing</code>
      </p>
    </Card>
  )
}
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/market/run-confirm-modal.tsx webapp-ui/components/domain/market/no-pulse-snapshot.tsx
git commit -m "feat(webapp-ui): RunConfirmModal + NoPulseSnapshot"
```

---

## Task 12: Frontend — DatePickerInline

**Files:**
- Create: `webapp-ui/components/domain/market/date-picker-inline.tsx`

- [ ] **Step 1: Implement component**

Create `webapp-ui/components/domain/market/date-picker-inline.tsx`:
```tsx
"use client"
import Link from "next/link"
import { Button } from "@/components/ui/button"

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function DatePickerInline({
  currentDate,
  availableDates,
}: {
  currentDate: string
  availableDates: string[]  // 오름차순 YYYYMMDD
}) {
  const idx = availableDates.indexOf(currentDate)
  const prev = idx > 0 ? availableDates[idx - 1] : null
  const next = idx >= 0 && idx < availableDates.length - 1
    ? availableDates[idx + 1] : null

  return (
    <div className="flex items-center gap-2">
      {prev ? (
        <Link href={`/market/pulse/${prev}`}>
          <Button variant="outline" size="sm">← 이전</Button>
        </Link>
      ) : (
        <Button variant="outline" size="sm" disabled>← 이전</Button>
      )}
      <span className="text-lg font-mono px-3">{formatDate(currentDate)}</span>
      {next ? (
        <Link href={`/market/pulse/${next}`}>
          <Button variant="outline" size="sm">다음 →</Button>
        </Link>
      ) : (
        <Button variant="outline" size="sm" disabled>다음 →</Button>
      )}
      <Link href="/market/pulse">
        <Button variant="ghost" size="sm">최신으로</Button>
      </Link>
    </div>
  )
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/market/date-picker-inline.tsx
git commit -m "feat(webapp-ui): DatePickerInline — Pulse 상세 날짜 네비게이션"
```

---

## Task 13: Frontend — Main Page `/market/pulse` + 사이드바

**Files:**
- Create: `webapp-ui/app/(dashboard)/market/pulse/page.tsx`
- Create: `webapp-ui/components/domain/market/pulse-dashboard-client.tsx` (client 상호작용 분리)
- Modify: `webapp-ui/components/layout/sidebar.tsx`

- [ ] **Step 1: Add sidebar entry**

Edit `webapp-ui/components/layout/sidebar.tsx`. Insert new item after `{ href: "/", label: "홈" }`:

```tsx
const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/market/pulse", label: "시황" },   // <- 추가
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/risk", label: "리스크" },
  { href: "/screening", label: "스크리닝" },
  { href: "/backtest", label: "백테스트" },
  { href: "/data", label: "데이터" },
  { href: "/settings", label: "설정" },
  { href: "/audit", label: "감사" },
]
```

- [ ] **Step 2: Create client component for run interaction**

Create `webapp-ui/components/domain/market/pulse-dashboard-client.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { ScoreHeroCard, type PulseSnapshot } from "./score-hero-card"
import { PulseHistoryChart, type HistoryItem } from "./pulse-history-chart"
import { IndicatorGrid } from "./indicator-grid"
import { RunConfirmModal } from "./run-confirm-modal"
import { NoPulseSnapshot } from "./no-pulse-snapshot"

function isToday(yyyymmdd: string): boolean {
  const now = new Date()
  const yyyy = String(now.getFullYear())
  const mm = String(now.getMonth() + 1).padStart(2, "0")
  const dd = String(now.getDate()).padStart(2, "0")
  return yyyymmdd === `${yyyy}${mm}${dd}`
}

export function PulseDashboardClient({
  latest,
  history,
}: {
  latest: PulseSnapshot | null
  history: HistoryItem[]
}) {
  const router = useRouter()
  const [running, setRunning] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doRun = async () => {
    setRunning(true)
    setShowConfirm(false)
    setError(null)
    try {
      const r = await apiMutate<{ job_id: string; reused: boolean }>(
        "/api/v1/market/pulse/run", "POST", {},
      )
      router.push(`/market/pulse/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패")
      setRunning(false)
    }
  }

  const handleRunClick = () => {
    if (latest && isToday(latest.date)) {
      setShowConfirm(true)
    } else {
      doRun()
    }
  }

  if (!latest) {
    return <NoPulseSnapshot onRun={handleRunClick} />
  }

  return (
    <div className="space-y-6">
      <ScoreHeroCard snapshot={latest} onRun={handleRunClick} running={running} />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <PulseHistoryChart items={history} />
      <IndicatorGrid
        scores={latest.indicator_scores}
        descriptions={latest.indicator_descriptions}
      />
      {showConfirm && (
        <RunConfirmModal
          existingSavedAt={latest.created_at}
          onConfirm={doRun}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create SSR page**

Create `webapp-ui/app/(dashboard)/market/pulse/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { PulseDashboardClient } from "@/components/domain/market/pulse-dashboard-client"
import type { PulseSnapshot } from "@/components/domain/market/score-hero-card"
import type { HistoryItem } from "@/components/domain/market/pulse-history-chart"

export const dynamic = "force-dynamic"

export default async function MarketPulsePage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  const [latest, hist] = await Promise.all([
    apiFetch<PulseSnapshot | null>(
      "/api/v1/market/pulse/latest",
      { headers: h, cache: "no-store" },
    ),
    apiFetch<{ items: HistoryItem[] }>(
      "/api/v1/market/pulse/history?days=30",
      { headers: h, cache: "no-store" },
    ),
  ])
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">시황 (Market Pulse)</h1>
      <PulseDashboardClient latest={latest} history={hist.items} />
    </div>
  )
}
```

- [ ] **Step 4: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add webapp-ui/app/\(dashboard\)/market/pulse/page.tsx webapp-ui/components/domain/market/pulse-dashboard-client.tsx webapp-ui/components/layout/sidebar.tsx
git commit -m "feat(webapp-ui): Market Pulse 메인 대시보드 + 사이드바 시황 진입점"
```

---

## Task 14: Frontend — 상세 페이지 `/market/pulse/[date]`

**Files:**
- Create: `webapp-ui/app/(dashboard)/market/pulse/[date]/page.tsx`

- [ ] **Step 1: Implement detail page**

Create `webapp-ui/app/(dashboard)/market/pulse/[date]/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { apiFetch } from "@/lib/api-client"
import { ScoreHeroCard, type PulseSnapshot } from "@/components/domain/market/score-hero-card"
import { IndicatorGrid } from "@/components/domain/market/indicator-grid"
import { DatePickerInline } from "@/components/domain/market/date-picker-inline"
import type { HistoryItem } from "@/components/domain/market/pulse-history-chart"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function PulseDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const [snapshot, hist] = await Promise.all([
      apiFetch<PulseSnapshot>(
        `/api/v1/market/pulse/${date}`,
        { headers: h, cache: "no-store" },
      ),
      apiFetch<{ items: HistoryItem[] }>(
        "/api/v1/market/pulse/history?days=365",
        { headers: h, cache: "no-store" },
      ),
    ])
    const availableDates = hist.items.map((i) => i.date)

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold">시황 상세</h1>
          <DatePickerInline currentDate={date} availableDates={availableDates} />
        </div>
        <ScoreHeroCard snapshot={snapshot} />
        <IndicatorGrid
          scores={snapshot.indicator_scores}
          descriptions={snapshot.indicator_descriptions}
          expandAll
        />
      </div>
    )
  } catch (e) {
    if (e instanceof Error && /404/.test(e.message)) {
      notFound()
    }
    throw e
  }
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/app/\(dashboard\)/market/pulse/\[date\]/page.tsx
git commit -m "feat(webapp-ui): Market Pulse 날짜 상세 페이지"
```

---

## Task 15: Frontend — Job 진행 페이지 + MarketJobProgress

**Files:**
- Create: `webapp-ui/components/domain/market/market-job-progress.tsx`
- Create: `webapp-ui/app/(dashboard)/market/pulse/jobs/[id]/page.tsx`

기존 `JobProgress` (Phase 2 Screening/Backtest 용) 는 완료 시 `result_ref` 를 UUID 로 가정해 `^[a-f0-9-]{8,}$` 매칭 후 slice 한다. Market Pulse 는 `result_ref` 에 YYYYMMDD 8자리 숫자를 저장하므로 기존 컴포넌트를 재사용하지 않고 Market 전용 래퍼를 새로 만든다.

- [ ] **Step 1: Create MarketJobProgress**

Create `webapp-ui/components/domain/market/market-job-progress.tsx`:
```tsx
"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useJobStatus } from "@/hooks/use-job-status"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function MarketJobProgress({ jobId }: { jobId: string }) {
  const router = useRouter()
  const { data: job, error } = useJobStatus(jobId)

  useEffect(() => {
    if (job?.status === "done") {
      const dest = job.result_ref && /^\d{8}$/.test(job.result_ref)
        ? `/market/pulse/${job.result_ref}`
        : "/market/pulse"
      router.replace(dest)
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
      <p className="text-xs text-neutral-500">최대 약 1분 소요됩니다.</p>
      {job.status === "failed" && (
        <div className="space-y-2">
          <p className="text-red-400">실패: {job.error}</p>
          <Button variant="outline" onClick={() => router.push("/market/pulse")}>
            돌아가기
          </Button>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Create the job page**

Create `webapp-ui/app/(dashboard)/market/pulse/jobs/[id]/page.tsx`:
```tsx
import { MarketJobProgress } from "@/components/domain/market/market-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function MarketPulseJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Market Pulse 실행 중</h1>
      <MarketJobProgress jobId={id} />
    </div>
  )
}
```

Background: `run_market_pulse_sync` 는 저장된 date (YYYYMMDD) 를 반환하고, `JobRunner` 는 반환값을 `str(result)` 로 `result_ref` 에 저장한다 (기존 `alphapulse/webapp/jobs/runner.py:38-43`). 따라서 `MarketJobProgress` 의 정규식 `^\d{8}$` 이 매치된다.

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/app/\(dashboard\)/market/pulse/jobs/\[id\]/page.tsx webapp-ui/components/domain/market/market-job-progress.tsx
git commit -m "feat(webapp-ui): Market Pulse Job 진행 페이지 — 완료 시 날짜 상세로 redirect"
```

---

## Task 16: E2E 스모크 테스트

**Files:**
- Create: `webapp-ui/e2e/market-pulse.spec.ts`

- [ ] **Step 1: Write E2E test**

Create `webapp-ui/e2e/market-pulse.spec.ts`:
```typescript
import { test, expect } from "@playwright/test"

// webapp-ui/e2e 의 기존 로그인 helper 를 재사용할 수 있으면 사용.
// 여기서는 직접 로그인 수행.

test.describe("Market Pulse", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill("input[name=email]", process.env.E2E_EMAIL || "a@x.com")
    await page.fill("input[name=password]", process.env.E2E_PASSWORD || "long-enough-pw!")
    await page.click("button[type=submit]")
    await expect(page).toHaveURL("/")
  })

  test("사이드바에 시황 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/market/pulse']")).toBeVisible()
  })

  test("/market/pulse 에서 ScoreHeroCard 또는 NoPulseSnapshot 렌더", async ({ page }) => {
    await page.goto("/market/pulse")
    const hero = page.locator("text=/K-Market Pulse/")
    const empty = page.locator("text=/Pulse 이력이 없습니다/")
    await expect(hero.or(empty)).toBeVisible()
  })

  test("이력 있을 때 지표 카드 11개 렌더", async ({ page }) => {
    await page.goto("/market/pulse")
    const empty = page.locator("text=/Pulse 이력이 없습니다/")
    if (await empty.isVisible()) {
      test.skip(true, "history DB 비어있어 검증 스킵")
    }
    // 한글 라벨 중 하나
    await expect(page.locator("text=/외국인\\+기관 수급/")).toBeVisible()
  })

  test("'지금 실행' 클릭 → 모달 또는 Job 페이지 이동", async ({ page }) => {
    await page.goto("/market/pulse")
    const runButton = page.locator("button", { hasText: /지금 실행/ })
    if (!(await runButton.isVisible())) {
      test.skip(true, "run button 없음 (이력 없음 상태)")
    }
    await runButton.click()
    // 모달 ("재실행 확인") 또는 URL 변경 (/market/pulse/jobs/)
    await expect(
      page.locator("text=/재실행 확인/").or(page.locator("h1", { hasText: /Market Pulse 실행 중/ }))
    ).toBeVisible()
  })
})
```

- [ ] **Step 2: Run E2E (dev server 와 webapp 서버 기동 필요)**

사용자가 별도 터미널에서:
```
# 터미널 1
uvicorn alphapulse.webapp.main:app --port 8000

# 터미널 2
cd webapp-ui && pnpm dev

# 터미널 3
cd webapp-ui && npx playwright test e2e/market-pulse.spec.ts
```
Expected: PASS (history DB 상태에 따라 2~3개 테스트 PASS, 나머지 SKIP)

에이전트가 직접 실행 못하면 step 2 는 수동 확인으로 대체.

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/e2e/market-pulse.spec.ts
git commit -m "test(webapp-ui): Market Pulse E2E 스모크 — 진입점/렌더/실행"
```

---

## Task 17: 전체 회귀 검증 + 최종 문서 링크 갱신

**Files:**
- (문서) `CLAUDE.md` — Detailed Docs 섹션에 spec 경로 추가 (있으면)
- (문서) `.claude/docs/cli-commands.md` — 변경 없음 (CLI 변경 아님)

- [ ] **Step 1: 전체 테스트 실행**

Run:
```bash
pytest tests/ -q --tb=short
```
Expected: 기존 863+ 테스트 + 신규 ~15개 모두 PASS

- [ ] **Step 2: Frontend 빌드 확인**

Run:
```bash
cd webapp-ui && pnpm build
```
Expected: Next.js build 성공, 타입 에러 없음

- [ ] **Step 3: Ruff 린트 확인**

Run:
```bash
ruff check alphapulse/
```
Expected: 통과

- [ ] **Step 4: CLAUDE.md 의 "Detailed Docs" 섹션에 spec 링크 추가 (선택)**

Edit `CLAUDE.md` around Detailed Docs section:
```markdown
## Detailed Docs
...
- Market Pulse 웹 대시보드 설계: `docs/superpowers/specs/2026-04-21-market-pulse-web-design.md`
```

- [ ] **Step 5: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — Market Pulse 웹 spec 링크 추가"
```

---

## 완료 기준 (Definition of Done)

- [ ] 모든 백엔드 엔드포인트 테스트 PASS (`pytest tests/webapp/api/test_market.py`)
- [ ] Frontend `pnpm build` 성공
- [ ] `ruff check alphapulse/` 통과
- [ ] E2E 스모크 테스트 PASS (또는 데이터 없어 SKIP 정상)
- [ ] 사이드바에 "시황" 항목 노출, 클릭 시 `/market/pulse` 로 이동
- [ ] 이력 존재 시 ScoreHeroCard + 차트 + 11개 지표 카드 렌더
- [ ] 이력 없음 시 NoPulseSnapshot 렌더
- [ ] "지금 실행" 클릭 → 모달(오늘 이력 있음) 또는 바로 Job 페이지
- [ ] 완료된 Job 은 `/market/pulse/{date}` 로 redirect
- [ ] 기존 Phase 2 테스트 수 그대로 (no regression)
