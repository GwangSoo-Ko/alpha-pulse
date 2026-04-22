# Feedback Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AlphaPulse 웹앱에 Feedback 도메인 추가 — 기존 `FeedbackStore` + `FeedbackEvaluator` 를 조회 전용 API 로 노출하고, 적중률 카드 / 지표별 차트 / 이력 테이블 / 날짜 상세를 웹에서 제공.

**Architecture:** 새 저장소/Job 없음. 기존 sync `FeedbackStore` / `FeedbackEvaluator` 를 `app.state` 주입 → FastAPI async 라우터가 바로 호출 → 프론트 SSR 대시보드(/feedback) + 날짜 상세(/feedback/[date]).

**Tech Stack:** FastAPI, Pydantic, Next.js 15, recharts (기존). 신규 의존성 0개. `ReportMarkdownView`, `INDICATOR_LABELS`, `signalStyle` 모두 재사용.

**Spec 참조:** `docs/superpowers/specs/2026-04-22-feedback-web-design.md`

---

## 파일 구조 (최종)

**신규 (백엔드):**
- `alphapulse/webapp/api/feedback.py` — 3 엔드포인트 (summary/history/detail) + Pydantic 스키마
- `tests/webapp/api/test_feedback.py`

**신규 (프론트엔드):**
- `webapp-ui/app/(dashboard)/feedback/page.tsx`
- `webapp-ui/app/(dashboard)/feedback/[date]/page.tsx`
- `webapp-ui/components/domain/feedback/hit-rate-cards.tsx`
- `webapp-ui/components/domain/feedback/correlation-card.tsx`
- `webapp-ui/components/domain/feedback/indicator-accuracy-chart.tsx`
- `webapp-ui/components/domain/feedback/signal-history-table.tsx`
- `webapp-ui/components/domain/feedback/feedback-detail-card.tsx`
- `webapp-ui/components/domain/feedback/post-analysis-section.tsx`
- `webapp-ui/components/domain/feedback/news-summary-section.tsx`
- `webapp-ui/components/domain/feedback/period-toggle.tsx`
- `webapp-ui/components/domain/feedback/no-feedback.tsx`
- `webapp-ui/e2e/feedback.spec.ts`

**수정:**
- `alphapulse/core/config.py` — `FEEDBACK_DB` 상수
- `alphapulse/webapp/main.py` — feedback_store/_evaluator state + router
- `webapp-ui/components/layout/sidebar.tsx` — "피드백" 항목

---

## Task 1: Config.FEEDBACK_DB 상수 + Feedback API (3 엔드포인트)

**Files:**
- Modify: `alphapulse/core/config.py` — add `FEEDBACK_DB`
- Create: `alphapulse/webapp/api/feedback.py`
- Create: `tests/webapp/api/test_feedback.py`

- [ ] **Step 1: Write failing tests**

Create `tests/webapp/api/test_feedback.py`:
```python
"""Feedback API — summary/history/detail GET endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.api.feedback import router as feedback_router
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
def feedback_store(tmp_path):
    return FeedbackStore(db_path=tmp_path / "feedback.db")


@pytest.fixture
def feedback_evaluator(feedback_store):
    return FeedbackEvaluator(store=feedback_store)


@pytest.fixture
def app(webapp_db, feedback_store, feedback_evaluator):
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
    app.state.feedback_store = feedback_store
    app.state.feedback_evaluator = feedback_evaluator
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)

    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(feedback_router)
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


def _save_full(store, date: str, *,
               score: float = 40.0, signal: str = "moderately_bullish",
               indicator_scores: dict | None = None,
               kospi_change: float = 0.8,
               return_1d: float | None = 0.8, hit_1d: int | None = 1,
               return_3d: float | None = -0.3, hit_3d: int | None = 0,
               return_5d: float | None = 1.5, hit_5d: int | None = 1,
               post_analysis: str | None = None,
               news_summary: str | None = None,
               blind_spots: str | None = None) -> None:
    """헬퍼 — 완전한 feedback row 삽입 (평가 완료 상태)."""
    store.save_signal(date, score, signal, indicator_scores or {"investor_flow": 60.0})
    store.update_result(
        date,
        kospi_close=2700.0, kospi_change_pct=kospi_change,
        kosdaq_close=850.0, kosdaq_change_pct=0.5,
    )
    store.update_returns(
        date,
        return_1d=return_1d, return_3d=return_3d, return_5d=return_5d,
        hit_1d=hit_1d, hit_3d=hit_3d, hit_5d=hit_5d,
    )
    if post_analysis or news_summary or blind_spots:
        store.update_analysis(
            date,
            post_analysis=post_analysis or "",
            news_summary=news_summary or "",
            blind_spots=blind_spots or "",
        )


def test_summary_empty_db(client):
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30
    assert body["hit_rates"]["total_evaluated"] == 0
    assert body["hit_rates"]["count_1d"] == 0
    assert body["correlation"] is None
    assert body["indicator_accuracy"] == []
    assert body["recent_history"] == []


def test_summary_returns_rates_and_accuracy(client, feedback_store):
    _save_full(feedback_store, "20260420", score=70.0, hit_1d=1, hit_3d=1, hit_5d=1,
               indicator_scores={"investor_flow": 60.0, "vkospi": 55.0})
    _save_full(feedback_store, "20260421", score=-70.0, hit_1d=1, hit_3d=0, hit_5d=1,
               indicator_scores={"investor_flow": -60.0, "vkospi": 10.0})
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["hit_rates"]["total_evaluated"] == 2
    assert body["hit_rates"]["hit_rate_1d"] == 1.0
    assert body["hit_rates"]["count_1d"] == 2
    # indicator_accuracy: investor_flow 둘 다 극단값 → count=2, accuracy=1.0; vkospi 하나만
    keys = [i["key"] for i in body["indicator_accuracy"]]
    assert "investor_flow" in keys
    # 정렬: accuracy 내림차순
    accs = [i["accuracy"] for i in body["indicator_accuracy"]]
    assert accs == sorted(accs, reverse=True)


def test_summary_excludes_zero_count_indicators(client, feedback_store):
    """모든 지표가 threshold 미만이면 제외."""
    _save_full(feedback_store, "20260421", score=10.0,
               indicator_scores={"investor_flow": 5.0})  # 극단값 아님
    r = client.get("/api/v1/feedback/summary?days=30")
    assert r.json()["indicator_accuracy"] == []


def test_summary_recent_history_has_10_max(client, feedback_store):
    """recent_history 는 최근 10건으로 제한."""
    for i in range(15):
        _save_full(feedback_store, f"202604{i+1:02d}")
    r = client.get("/api/v1/feedback/summary?days=30")
    body = r.json()
    assert len(body["recent_history"]) <= 10


def test_summary_days_out_of_range(client):
    r = client.get("/api/v1/feedback/summary?days=0")
    assert r.status_code == 422
    r = client.get("/api/v1/feedback/summary?days=500")
    assert r.status_code == 422


def test_history_returns_paginated(client, feedback_store):
    for i in range(25):
        _save_full(feedback_store, f"202604{i+1:02d}")
    r = client.get("/api/v1/feedback/history?days=60&page=1&size=10")
    body = r.json()
    assert body["total"] == 25
    assert body["page"] == 1
    assert body["size"] == 10
    assert len(body["items"]) == 10


def test_history_returns_bool_hit_flags(client, feedback_store):
    """DB 의 INTEGER 0/1/NULL 이 bool/None 으로 변환된다."""
    _save_full(feedback_store, "20260421", hit_1d=1, hit_3d=0, hit_5d=None)
    r = client.get("/api/v1/feedback/history?days=30")
    item = r.json()["items"][0]
    assert item["hit_1d"] is True
    assert item["hit_3d"] is False
    assert item["hit_5d"] is None


def test_history_size_out_of_range(client):
    r = client.get("/api/v1/feedback/history?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/feedback/history?size=500")
    assert r.status_code == 422


def test_detail_returns_full_row(client, feedback_store):
    _save_full(feedback_store, "20260421",
               post_analysis="종합분석", news_summary="뉴스요약", blind_spots="사각지대")
    r = client.get("/api/v1/feedback/20260421")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260421"
    assert body["score"] == 40.0
    assert body["kospi_change_pct"] == 0.8
    assert body["return_1d"] == 0.8
    assert body["hit_1d"] is True
    assert body["post_analysis"] == "종합분석"
    assert body["news_summary"] == "뉴스요약"
    assert body["blind_spots"] == "사각지대"
    assert isinstance(body["indicator_scores"], dict)


def test_detail_404_missing(client):
    r = client.get("/api/v1/feedback/19000101")
    assert r.status_code == 404


def test_detail_rejects_invalid_date_format(client):
    r = client.get("/api/v1/feedback/not-a-date")
    assert r.status_code == 422


def test_summary_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/feedback/summary")
    assert r.status_code == 401


def test_detail_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/feedback/20260421")
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_feedback.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.api.feedback'`

- [ ] **Step 3: Add FEEDBACK_DB to Config**

Edit `alphapulse/core/config.py`. Find `self.HISTORY_DB = ...` or `self.BRIEFINGS_DB = ...` line and add right after:

```python
        self.FEEDBACK_DB = self.DATA_DIR / "feedback.db"
```

- [ ] **Step 4: Implement feedback API**

Create `alphapulse/webapp/api/feedback.py`:
```python
"""Feedback API — 시그널 적중률 / 지표별 정확도 / 이력 조회 (read-only)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class HitRates(BaseModel):
    total_evaluated: int
    hit_rate_1d: float | None
    hit_rate_3d: float | None
    hit_rate_5d: float | None
    count_1d: int
    count_3d: int
    count_5d: int


class IndicatorAccuracy(BaseModel):
    key: str
    accuracy: float
    count: int


class SignalHistoryItem(BaseModel):
    date: str
    score: float
    signal: str
    kospi_change_pct: float | None
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    hit_1d: bool | None
    hit_3d: bool | None
    hit_5d: bool | None


class FeedbackSummaryResponse(BaseModel):
    days: int
    hit_rates: HitRates
    correlation: float | None
    indicator_accuracy: list[IndicatorAccuracy]
    recent_history: list[SignalHistoryItem]


class FeedbackHistoryResponse(BaseModel):
    items: list[SignalHistoryItem]
    page: int
    size: int
    total: int


class FeedbackDetail(BaseModel):
    date: str
    score: float
    signal: str
    indicator_scores: dict[str, float | None]
    kospi_close: float | None
    kospi_change_pct: float | None
    kosdaq_close: float | None
    kosdaq_change_pct: float | None
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    hit_1d: bool | None
    hit_3d: bool | None
    hit_5d: bool | None
    post_analysis: str | None
    news_summary: str | None
    blind_spots: str | None
    evaluated_at: float | None
    created_at: float


def get_feedback_store(request: Request) -> FeedbackStore:
    return request.app.state.feedback_store


def get_feedback_evaluator(request: Request) -> FeedbackEvaluator:
    return request.app.state.feedback_evaluator


def _int_to_bool(v: int | None) -> bool | None:
    if v is None:
        return None
    return bool(v)


def _parse_indicator_scores(raw) -> dict[str, float | None]:
    """DB 에서 온 indicator_scores 는 JSON 문자열 또는 이미 dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _row_to_history_item(row: dict) -> SignalHistoryItem:
    return SignalHistoryItem(
        date=row["date"],
        score=float(row["score"] or 0.0),
        signal=str(row["signal"] or ""),
        kospi_change_pct=row.get("kospi_change_pct"),
        return_1d=row.get("return_1d"),
        return_3d=row.get("return_3d"),
        return_5d=row.get("return_5d"),
        hit_1d=_int_to_bool(row.get("hit_1d")),
        hit_3d=_int_to_bool(row.get("hit_3d")),
        hit_5d=_int_to_bool(row.get("hit_5d")),
    )


def _row_to_detail(row: dict) -> FeedbackDetail:
    return FeedbackDetail(
        date=row["date"],
        score=float(row["score"] or 0.0),
        signal=str(row["signal"] or ""),
        indicator_scores=_parse_indicator_scores(row.get("indicator_scores")),
        kospi_close=row.get("kospi_close"),
        kospi_change_pct=row.get("kospi_change_pct"),
        kosdaq_close=row.get("kosdaq_close"),
        kosdaq_change_pct=row.get("kosdaq_change_pct"),
        return_1d=row.get("return_1d"),
        return_3d=row.get("return_3d"),
        return_5d=row.get("return_5d"),
        hit_1d=_int_to_bool(row.get("hit_1d")),
        hit_3d=_int_to_bool(row.get("hit_3d")),
        hit_5d=_int_to_bool(row.get("hit_5d")),
        post_analysis=row.get("post_analysis"),
        news_summary=row.get("news_summary"),
        blind_spots=row.get("blind_spots"),
        evaluated_at=row.get("evaluated_at"),
        created_at=row["created_at"],
    )


def _indicator_accuracy_list(raw: dict) -> list[IndicatorAccuracy]:
    """Evaluator dict → 정렬된 list. count=0 은 제외."""
    items = [
        IndicatorAccuracy(
            key=k,
            accuracy=v.get("accuracy") or 0.0,
            count=v.get("total") or 0,
        )
        for k, v in raw.items()
        if (v.get("total") or 0) > 0
    ]
    items.sort(key=lambda x: x.accuracy, reverse=True)
    return items


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_summary(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
    store: FeedbackStore = Depends(get_feedback_store),
):
    rates_raw = evaluator.get_hit_rates(days)
    correlation = evaluator.get_correlation(days)
    accuracy_raw = evaluator.get_indicator_accuracy(days)
    recent = store.get_recent(days=10)

    # 빈 데이터: hit_rate_* 는 evaluator 가 0.0 반환하지만 spec 는 null 선호
    total = rates_raw.get("total_evaluated", 0)
    hit_rates = HitRates(
        total_evaluated=total,
        hit_rate_1d=rates_raw.get("hit_rate_1d") if total > 0 else None,
        hit_rate_3d=rates_raw.get("hit_rate_3d") if total > 0 else None,
        hit_rate_5d=rates_raw.get("hit_rate_5d") if total > 0 else None,
        count_1d=rates_raw.get("count_1d", 0),
        count_3d=rates_raw.get("count_3d", 0),
        count_5d=rates_raw.get("count_5d", 0),
    )

    return FeedbackSummaryResponse(
        days=days,
        hit_rates=hit_rates,
        correlation=correlation,
        indicator_accuracy=_indicator_accuracy_list(accuracy_raw),
        recent_history=[_row_to_history_item(r) for r in recent],
    )


@router.get("/history", response_model=FeedbackHistoryResponse)
async def get_history(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    rows = store.get_recent(days=days)
    total = len(rows)
    start = (page - 1) * size
    sliced = rows[start:start + size]
    return FeedbackHistoryResponse(
        items=[_row_to_history_item(r) for r in sliced],
        page=page,
        size=size,
        total=total,
    )


@router.get("/{date}", response_model=FeedbackDetail)
async def get_detail(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    row = store.get(date)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Feedback not found for {date}",
        )
    return _row_to_detail(row)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/webapp/api/test_feedback.py -v`
Expected: PASS (13 tests)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/core/config.py alphapulse/webapp/api/feedback.py tests/webapp/api/test_feedback.py
git commit -m "feat(webapp): Feedback API — summary/history/{date} + Config.FEEDBACK_DB"
```

## Context

Working directory: `/Users/gwangsoo/alpha-pulse`
Branch: `webapp/phase3-feedback`

Spec 참조: `docs/superpowers/specs/2026-04-22-feedback-web-design.md`

`FeedbackEvaluator.get_indicator_accuracy` 실제 반환 shape:
```python
{"investor_flow": {"hits": 35, "total": 45, "accuracy": 0.78}, ...}
```

`FeedbackEvaluator.get_hit_rates` 실제 반환 shape:
```python
{
    "hit_rate_1d": 0.65, "hit_rate_3d": 0.58, "hit_rate_5d": 0.53,
    "total_evaluated": 20,
    "count_1d": 20, "count_3d": 18, "count_5d": 15,
}
```

`FeedbackStore.get_recent(days)` 반환: `list[dict]` where dict keys are:
`date, score, signal, indicator_scores(JSON str 또는 dict), kospi_close, kospi_change_pct, kosdaq_close, kosdaq_change_pct, return_1d, return_3d, return_5d, hit_1d, hit_3d, hit_5d, post_analysis, news_summary, blind_spots, evaluated_at, created_at`

---

## Task 2: main.py — feedback state + router

**Files:**
- Modify: `alphapulse/webapp/main.py`
- Modify: `tests/webapp/test_main.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/webapp/test_main.py`:
```python
def test_feedback_router_registered():
    """create_app 후 feedback 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/feedback/summary" in routes
    assert "/api/v1/feedback/history" in routes
    assert "/api/v1/feedback/{date}" in routes


def test_feedback_store_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "feedback_store")
    assert app.state.feedback_store is not None


def test_feedback_evaluator_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "feedback_evaluator")
    assert app.state.feedback_evaluator is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/test_main.py -v -k "feedback"`
Expected: FAIL — routes 없음 + state 없음

- [ ] **Step 3: Wire feedback router + state**

Edit `alphapulse/webapp/main.py`:

Add imports next to other `api.*` imports (e.g. after `briefing_router`):
```python
from alphapulse.webapp.api.feedback import router as feedback_router
```

Add near other storage imports (after `BriefingStore` import):
```python
from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator
```

In `create_app()`, after `briefing_store = BriefingStore(db_path=core.BRIEFINGS_DB)` line, add:
```python
    feedback_store = FeedbackStore(db_path=core.FEEDBACK_DB)
    feedback_evaluator = FeedbackEvaluator(store=feedback_store)
```

After `app.state.briefing_store = briefing_store`, add:
```python
    app.state.feedback_store = feedback_store
    app.state.feedback_evaluator = feedback_evaluator
```

After `app.include_router(briefing_router)`, add:
```python
    app.include_router(feedback_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/test_main.py -v`
Expected: PASS (existing + 3 new)

- [ ] **Step 5: Full webapp regression**

Run: `pytest tests/webapp/ -q --tb=short`
Expected: PASS (1 pre-existing unrelated failure `test_settings_router_absent_without_encrypt_key` acceptable)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/main.py tests/webapp/test_main.py
git commit -m "feat(webapp): main.py 에 feedback router + FeedbackStore/Evaluator 상태 주입"
```

---

## Task 3: Frontend — `hit-rate-cards.tsx` + `correlation-card.tsx`

**Files:**
- Create: `webapp-ui/components/domain/feedback/hit-rate-cards.tsx`
- Create: `webapp-ui/components/domain/feedback/correlation-card.tsx`

- [ ] **Step 1: Create HitRateCards**

Create `webapp-ui/components/domain/feedback/hit-rate-cards.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"

export type HitRates = {
  total_evaluated: number
  hit_rate_1d: number | null
  hit_rate_3d: number | null
  hit_rate_5d: number | null
  count_1d: number
  count_3d: number
  count_5d: number
}

function pct(rate: number | null): string {
  if (rate === null) return "-"
  return `${(rate * 100).toFixed(0)}%`
}

function colorClass(rate: number | null): string {
  if (rate === null) return "text-neutral-500"
  if (rate >= 0.6) return "text-green-400"
  if (rate >= 0.5) return "text-yellow-400"
  return "text-red-400"
}

function Cell({ label, rate, count }: { label: string; rate: number | null; count: number }) {
  return (
    <Card className="p-4 space-y-1">
      <p className="text-xs text-neutral-400">{label}</p>
      <p className={`text-3xl font-bold font-mono ${colorClass(rate)}`}>
        {pct(rate)}
      </p>
      <p className="text-xs text-neutral-500">{count}건 평가</p>
    </Card>
  )
}

export function HitRateCards({ rates }: { rates: HitRates }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <Cell label="1일 적중률" rate={rates.hit_rate_1d} count={rates.count_1d} />
      <Cell label="3일 적중률" rate={rates.hit_rate_3d} count={rates.count_3d} />
      <Cell label="5일 적중률" rate={rates.hit_rate_5d} count={rates.count_5d} />
    </div>
  )
}
```

- [ ] **Step 2: Create CorrelationCard**

Create `webapp-ui/components/domain/feedback/correlation-card.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"

function describeCorrelation(r: number): string {
  const a = Math.abs(r)
  const dir = r > 0 ? "양" : "음"
  if (a < 0.1) return "상관관계 거의 없음"
  if (a < 0.3) return `약한 ${dir}의 상관`
  if (a < 0.5) return `중간 ${dir}의 상관`
  if (a < 0.7) return `상당한 ${dir}의 상관`
  return `강한 ${dir}의 상관`
}

export function CorrelationCard({ correlation }: { correlation: number | null }) {
  if (correlation === null) {
    return (
      <Card className="p-4 space-y-1">
        <p className="text-xs text-neutral-400">Score ↔ 1일 수익률 상관</p>
        <p className="text-3xl font-bold font-mono text-neutral-500">-</p>
        <p className="text-xs text-neutral-500">데이터 부족</p>
      </Card>
    )
  }
  return (
    <Card className="p-4 space-y-1">
      <p className="text-xs text-neutral-400">Score ↔ 1일 수익률 상관</p>
      <p className="text-3xl font-bold font-mono">{correlation.toFixed(2)}</p>
      <p className="text-xs text-neutral-500">{describeCorrelation(correlation)}</p>
    </Card>
  )
}
```

- [ ] **Step 3: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/feedback/hit-rate-cards.tsx webapp-ui/components/domain/feedback/correlation-card.tsx
git commit -m "feat(webapp-ui): HitRateCards + CorrelationCard"
```

---

## Task 4: Frontend — `indicator-accuracy-chart.tsx`

**Files:**
- Create: `webapp-ui/components/domain/feedback/indicator-accuracy-chart.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/components/domain/feedback/indicator-accuracy-chart.tsx`:
```tsx
"use client"
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell as BarCell,
} from "recharts"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS } from "@/lib/market-labels"

export type IndicatorAccuracy = {
  key: string
  accuracy: number
  count: number
}

function color(accuracy: number, count: number): string {
  if (count < 5) return "#737373"          // neutral-500, 데이터 부족
  if (accuracy >= 0.70) return "#22c55e"   // green-500
  if (accuracy >= 0.50) return "#eab308"   // yellow-500
  return "#ef4444"                          // red-500
}

function fmtTick(v: number): string {
  return `${(v * 100).toFixed(0)}%`
}

export function IndicatorAccuracyChart({
  items,
}: {
  items: IndicatorAccuracy[]
}) {
  if (items.length === 0) {
    return (
      <Card className="p-6 text-sm text-neutral-500">
        지표별 적중률 데이터 없음 (극단값 시그널 누적 필요)
      </Card>
    )
  }

  const data = items.map((i) => ({
    label: INDICATOR_LABELS[i.key] ?? i.key,
    accuracy: i.accuracy,
    count: i.count,
    color: color(i.accuracy, i.count),
  }))

  return (
    <Card className="p-4">
      <h2 className="text-sm text-neutral-300 mb-4">지표별 적중률 (극단값 기준)</h2>
      <div style={{ height: Math.max(220, data.length * 28) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
            <XAxis
              type="number" domain={[0, 1]}
              tickFormatter={fmtTick}
              stroke="#888" fontSize={11}
            />
            <YAxis
              type="category" dataKey="label" width={100}
              stroke="#888" fontSize={11}
            />
            <Tooltip
              contentStyle={{
                background: "#1f1f1f", border: "1px solid #333", fontSize: 12,
              }}
              formatter={(v: number, _name, ctx) => [
                `${(v * 100).toFixed(0)}% · ${ctx.payload.count}건`,
                "정확도",
              ]}
            />
            <Bar dataKey="accuracy">
              {data.map((d, i) => (
                <BarCell key={i} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/feedback/indicator-accuracy-chart.tsx
git commit -m "feat(webapp-ui): IndicatorAccuracyChart — 지표별 적중률 가로 bar"
```

---

## Task 5: Frontend — `signal-history-table.tsx`

**Files:**
- Create: `webapp-ui/components/domain/feedback/signal-history-table.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/components/domain/feedback/signal-history-table.tsx`:
```tsx
"use client"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { signalStyle } from "@/lib/market-labels"

export type SignalHistoryItem = {
  date: string
  score: number
  signal: string
  kospi_change_pct: number | null
  return_1d: number | null
  return_3d: number | null
  return_5d: number | null
  hit_1d: boolean | null
  hit_3d: boolean | null
  hit_5d: boolean | null
}

type ListData = {
  items: SignalHistoryItem[]
  page: number
  size: number
  total: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatPct(v: number | null): string {
  if (v === null) return "-"
  const sign = v >= 0 ? "+" : ""
  return `${sign}${v.toFixed(2)}%`
}

function hitIcon(hit: boolean | null): string {
  if (hit === null) return "-"
  return hit ? "✓" : "✗"
}

function hitClass(hit: boolean | null): string {
  if (hit === null) return "text-neutral-500"
  return hit ? "text-green-400" : "text-red-400"
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/feedback?${next}`
}

export function SignalHistoryTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))
  const sign = (v: number) => (v >= 0 ? "+" : "")

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">
        전체 {data.total}건 · 페이지 {data.page}/{totalPages}
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2">날짜</th>
            <th className="px-3 py-2">시그널</th>
            <th className="px-3 py-2">점수</th>
            <th className="px-3 py-2">KOSPI</th>
            <th className="px-3 py-2">1D</th>
            <th className="px-3 py-2">3D</th>
            <th className="px-3 py-2">5D</th>
            <th className="px-3 py-2">적중 1/3/5</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => {
            const style = signalStyle(i.signal)
            return (
              <tr key={i.date} className="border-t border-neutral-800 hover:bg-neutral-900">
                <td className="px-3 py-2">
                  <Link
                    href={`/feedback/${i.date}`}
                    className="text-blue-400 hover:underline font-mono"
                  >
                    {formatDate(i.date)}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono tabular-nums">
                  {sign(i.score)}{i.score.toFixed(1)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs text-neutral-400">
                  {formatPct(i.kospi_change_pct)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_1d)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_3d)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_5d)}
                </td>
                <td className="px-3 py-2 text-xs">
                  <span className={hitClass(i.hit_1d)}>{hitIcon(i.hit_1d)}</span>
                  <span className="mx-1 text-neutral-600">/</span>
                  <span className={hitClass(i.hit_3d)}>{hitIcon(i.hit_3d)}</span>
                  <span className="mx-1 text-neutral-600">/</span>
                  <span className={hitClass(i.hit_5d)}>{hitIcon(i.hit_5d)}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex justify-center gap-1">
          {data.page > 1 ? (
            <Link href={pageHref(spParams, data.page - 1)}>
              <Button size="sm" variant="outline">← 이전</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>← 이전</Button>
          )}
          <span className="px-3 py-1 text-sm">{data.page} / {totalPages}</span>
          {data.page < totalPages ? (
            <Link href={pageHref(spParams, data.page + 1)}>
              <Button size="sm" variant="outline">다음 →</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>다음 →</Button>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/feedback/signal-history-table.tsx
git commit -m "feat(webapp-ui): SignalHistoryTable — 시그널 vs 결과 + 적중 표시"
```

---

## Task 6: Frontend — `period-toggle.tsx` + `no-feedback.tsx`

**Files:**
- Create: `webapp-ui/components/domain/feedback/period-toggle.tsx`
- Create: `webapp-ui/components/domain/feedback/no-feedback.tsx`

- [ ] **Step 1: PeriodToggle**

Create `webapp-ui/components/domain/feedback/period-toggle.tsx`:
```tsx
"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"

const OPTIONS = [30, 60, 90]

export function PeriodToggle({ current }: { current: number }) {
  const router = useRouter()
  const sp = useSearchParams()

  const pick = (days: number) => {
    const next = new URLSearchParams(sp?.toString() ?? "")
    next.set("days", String(days))
    next.delete("page")
    router.push(`/feedback?${next}`)
  }

  return (
    <div className="flex gap-1">
      {OPTIONS.map((d) => (
        <Button
          key={d} size="sm"
          variant={current === d ? "default" : "outline"}
          onClick={() => pick(d)}
        >
          {d}일
        </Button>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: NoFeedback**

Create `webapp-ui/components/domain/feedback/no-feedback.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"

export function NoFeedback() {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">평가된 시그널이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        브리핑 발행 이후 시장 결과가 채워지기까지 최소 1영업일 필요합니다.<br />
        매일 브리핑 실행 시 자동으로 피드백이 축적됩니다.
      </p>
      <p className="text-xs text-neutral-500">
        수동 평가: <code className="px-1 bg-neutral-800 rounded">ap feedback evaluate</code>
      </p>
    </Card>
  )
}
```

- [ ] **Step 3: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/feedback/period-toggle.tsx webapp-ui/components/domain/feedback/no-feedback.tsx
git commit -m "feat(webapp-ui): PeriodToggle + NoFeedback"
```

---

## Task 7: Frontend — Detail 페이지용 섹션 컴포넌트 3종

**Files:**
- Create: `webapp-ui/components/domain/feedback/feedback-detail-card.tsx`
- Create: `webapp-ui/components/domain/feedback/news-summary-section.tsx`
- Create: `webapp-ui/components/domain/feedback/post-analysis-section.tsx`

- [ ] **Step 1: FeedbackDetailCard**

Create `webapp-ui/components/domain/feedback/feedback-detail-card.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type FeedbackDetail = {
  date: string
  score: number
  signal: string
  indicator_scores: Record<string, number | null>
  kospi_close: number | null
  kospi_change_pct: number | null
  kosdaq_close: number | null
  kosdaq_change_pct: number | null
  return_1d: number | null
  return_3d: number | null
  return_5d: number | null
  hit_1d: boolean | null
  hit_3d: boolean | null
  hit_5d: boolean | null
  post_analysis: string | null
  news_summary: string | null
  blind_spots: string | null
  evaluated_at: number | null
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatPct(v: number | null): string {
  if (v === null) return "-"
  const sign = v >= 0 ? "+" : ""
  return `${sign}${v.toFixed(2)}%`
}

function HitBadge({ hit }: { hit: boolean | null }) {
  if (hit === null) return <span className="text-neutral-500">-</span>
  return hit
    ? <span className="text-green-400">✓</span>
    : <span className="text-red-400">✗</span>
}

export function FeedbackDetailCard({ detail }: { detail: FeedbackDetail }) {
  const style = signalStyle(detail.signal)
  const sign = detail.score >= 0 ? "+" : ""

  return (
    <Card className="p-6 space-y-4">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          피드백 · {formatDate(detail.date)}
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{detail.score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-neutral-800 pt-3">
        <div>
          <p className="text-xs text-neutral-400 mb-1">KOSPI</p>
          <p className="text-sm font-mono tabular-nums">
            {detail.kospi_close?.toFixed(2) ?? "-"} ({formatPct(detail.kospi_change_pct)})
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">KOSDAQ</p>
          <p className="text-sm font-mono tabular-nums">
            {detail.kosdaq_close?.toFixed(2) ?? "-"} ({formatPct(detail.kosdaq_change_pct)})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 border-t border-neutral-800 pt-3">
        <div>
          <p className="text-xs text-neutral-400 mb-1">1일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_1d)} <HitBadge hit={detail.hit_1d} />
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">3일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_3d)} <HitBadge hit={detail.hit_3d} />
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">5일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_5d)} <HitBadge hit={detail.hit_5d} />
          </p>
        </div>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: NewsSummarySection**

Create `webapp-ui/components/domain/feedback/news-summary-section.tsx`:
```tsx
"use client"

export function NewsSummarySection({
  newsSummary,
}: {
  newsSummary: string | null
}) {
  if (!newsSummary) return null
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">장 후 뉴스 요약</h2>
      <pre className="text-sm text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
        {newsSummary}
      </pre>
    </section>
  )
}
```

- [ ] **Step 3: PostAnalysisSection**

Create `webapp-ui/components/domain/feedback/post-analysis-section.tsx`:
```tsx
"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function PostAnalysisSection({
  postAnalysis,
  blindSpots,
}: {
  postAnalysis: string | null
  blindSpots: string | null
}) {
  const hasAny = !!(postAnalysis || blindSpots)
  if (!hasAny) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">사후 분석</h2>
        <p className="text-sm text-neutral-500">아직 생성되지 않음</p>
      </section>
    )
  }
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">사후 분석</h2>
      {postAnalysis && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">종합</h3>
          <ReportMarkdownView body={postAnalysis} />
        </div>
      )}
      {blindSpots && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">사각지대</h3>
          <ReportMarkdownView body={blindSpots} />
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add webapp-ui/components/domain/feedback/feedback-detail-card.tsx webapp-ui/components/domain/feedback/news-summary-section.tsx webapp-ui/components/domain/feedback/post-analysis-section.tsx
git commit -m "feat(webapp-ui): Feedback 상세 섹션 3종 (DetailCard + NewsSummary + PostAnalysis)"
```

---

## Task 8: Frontend — `/feedback` 메인 페이지 + 사이드바

**Files:**
- Modify: `webapp-ui/components/layout/sidebar.tsx`
- Create: `webapp-ui/app/(dashboard)/feedback/page.tsx`

- [ ] **Step 1: Add sidebar entry**

Edit `webapp-ui/components/layout/sidebar.tsx`. ITEMS 배열에 "브리핑" 다음 삽입:
```tsx
const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/market/pulse", label: "시황" },
  { href: "/content", label: "콘텐츠" },
  { href: "/briefings", label: "브리핑" },
  { href: "/feedback", label: "피드백" },
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/risk", label: "리스크" },
  { href: "/screening", label: "스크리닝" },
  { href: "/backtest", label: "백테스트" },
  { href: "/data", label: "데이터" },
  { href: "/settings", label: "설정" },
  { href: "/audit", label: "감사" },
]
```

- [ ] **Step 2: Create SSR page**

Create `webapp-ui/app/(dashboard)/feedback/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { HitRateCards, type HitRates } from "@/components/domain/feedback/hit-rate-cards"
import { CorrelationCard } from "@/components/domain/feedback/correlation-card"
import {
  IndicatorAccuracyChart,
  type IndicatorAccuracy,
} from "@/components/domain/feedback/indicator-accuracy-chart"
import {
  SignalHistoryTable,
  type SignalHistoryItem,
} from "@/components/domain/feedback/signal-history-table"
import { PeriodToggle } from "@/components/domain/feedback/period-toggle"
import { NoFeedback } from "@/components/domain/feedback/no-feedback"

export const dynamic = "force-dynamic"

type Props = {
  searchParams: Promise<{ days?: string; page?: string }>
}

type SummaryResponse = {
  days: number
  hit_rates: HitRates
  correlation: number | null
  indicator_accuracy: IndicatorAccuracy[]
  recent_history: SignalHistoryItem[]
}

type HistoryResponse = {
  items: SignalHistoryItem[]
  page: number
  size: number
  total: number
}

export default async function FeedbackPage({ searchParams }: Props) {
  const sp = await searchParams
  const days = Math.min(365, Math.max(1, Number(sp.days || 30)))
  const page = Math.max(1, Number(sp.page || 1))

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const [summary, history] = await Promise.all([
    apiFetch<SummaryResponse>(
      `/api/v1/feedback/summary?days=${days}`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<HistoryResponse>(
      `/api/v1/feedback/history?days=${days}&page=${page}&size=20`,
      { headers: h, cache: "no-store" },
    ),
  ])

  const empty = summary.hit_rates.total_evaluated === 0

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">피드백</h1>
        <PeriodToggle current={days} />
      </div>
      {empty ? (
        <NoFeedback />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-1">
              <CorrelationCard correlation={summary.correlation} />
            </div>
            <div className="md:col-span-1"></div>
          </div>
          <HitRateCards rates={summary.hit_rates} />
          <IndicatorAccuracyChart items={summary.indicator_accuracy} />
          <SignalHistoryTable data={history} />
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/layout/sidebar.tsx 'webapp-ui/app/(dashboard)/feedback/page.tsx'
git commit -m "feat(webapp-ui): 피드백 메인 대시보드 + 사이드바 진입점"
```

---

## Task 9: Frontend — `/feedback/[date]` 상세 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/feedback/[date]/page.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/app/(dashboard)/feedback/[date]/page.tsx`:
```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import {
  FeedbackDetailCard,
  type FeedbackDetail,
} from "@/components/domain/feedback/feedback-detail-card"
import { NewsSummarySection } from "@/components/domain/feedback/news-summary-section"
import { PostAnalysisSection } from "@/components/domain/feedback/post-analysis-section"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function FeedbackDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<FeedbackDetail>(
      `/api/v1/feedback/${date}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-6">
        <Link href="/feedback">
          <Button variant="outline" size="sm">← 피드백 대시보드로</Button>
        </Link>
        <FeedbackDetailCard detail={detail} />
        <NewsSummarySection newsSummary={detail.news_summary} />
        <PostAnalysisSection
          postAnalysis={detail.post_analysis}
          blindSpots={detail.blind_spots}
        />
        <div className="pt-4 border-t border-neutral-800">
          <Link href={`/briefings/${date}`}>
            <Button variant="outline" size="sm">
              → 이 날짜 브리핑 전체 보기
            </Button>
          </Link>
        </div>
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add 'webapp-ui/app/(dashboard)/feedback/[date]/page.tsx'
git commit -m "feat(webapp-ui): 피드백 날짜 상세 페이지 + Briefing 링크"
```

---

## Task 10: E2E 스모크 테스트

**Files:**
- Create: `webapp-ui/e2e/feedback.spec.ts`

- [ ] **Step 1: Implement**

Create `webapp-ui/e2e/feedback.spec.ts`:
```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Feedback", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 피드백 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/feedback']")).toBeVisible()
  })

  test("/feedback 로드 → 대시보드 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/feedback")
    const heading = page.locator("h1", { hasText: "피드백" })
    const empty = page.locator("text=/평가된 시그널이 없습니다/")
    const toggle = page.locator("button", { hasText: /30일/ })
    await expect(heading).toBeVisible()
    await expect(empty.or(toggle)).toBeVisible()
  })

  test("기간 토글 버튼 렌더", async ({ page }) => {
    await page.goto("/feedback")
    for (const d of [30, 60, 90]) {
      await expect(
        page.locator("button", { hasText: new RegExp(`${d}일`) }),
      ).toBeVisible()
    }
  })
})
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/e2e/feedback.spec.ts
git commit -m "test(webapp-ui): 피드백 E2E 스모크 — 진입점 + 대시보드 + 토글"
```

---

## Task 11: 최종 회귀 + CLAUDE.md 링크

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 전체 pytest**

Run: `pytest tests/ -q --tb=short`
Expected: 신규 ~15개 PASS + 기존 PASS (1 pre-existing 무관 실패 허용)

- [ ] **Step 2: Ruff**

Run: `ruff check alphapulse/`
Expected: PASS

- [ ] **Step 3: Frontend build**

Run: `cd webapp-ui && pnpm build`
Expected: Next.js build 성공, 새 2개 라우트 (`/feedback`, `/feedback/[date]`) 생성

- [ ] **Step 4: Add spec link to CLAUDE.md**

Read `/Users/gwangsoo/alpha-pulse/CLAUDE.md`. "## Detailed Docs" 섹션에 Briefing 링크 다음 추가:

```markdown
- Feedback 웹 대시보드 설계: `docs/superpowers/specs/2026-04-22-feedback-web-design.md`
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — Feedback 웹 spec 링크 추가"
```

---

## 완료 기준 (Definition of Done)

- [ ] `tests/webapp/api/test_feedback.py` — 13 tests PASS
- [ ] `tests/webapp/test_main.py` — feedback state + router 3 tests PASS
- [ ] `pytest tests/ -q` — 전체 그린 (1 pre-existing 무관 허용)
- [ ] `ruff check alphapulse/` — 통과
- [ ] `cd webapp-ui && pnpm build` — 성공, 2개 라우트 (`/feedback`, `/feedback/[date]`) 생성
- [ ] 사이드바 "피드백" 노출 → 클릭 시 `/feedback`
- [ ] 데이터 있을 때 HitRateCards + CorrelationCard + IndicatorAccuracyChart + SignalHistoryTable 렌더
- [ ] 데이터 없을 때 NoFeedback 렌더
- [ ] 기간 토글 30/60/90 → URL `?days=N` 업데이트 + SSR 재조회
- [ ] `/feedback/[date]` 상세 — DetailCard + 섹션들 + "브리핑 보기" 링크
- [ ] CLAUDE.md 에 spec 링크 추가
