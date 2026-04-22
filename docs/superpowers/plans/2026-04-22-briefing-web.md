# Daily Briefing Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AlphaPulse 웹앱에 Briefing 도메인 추가 — `BriefingOrchestrator.run_async` 결과를 `briefings.db` 에 영속화하고 웹에서 리스트/상세 뷰 + Job 기반 수동 실행 제공.

**Architecture:** 신규 `BriefingStore` (SQLite, `briefings` 단일 테이블, date PK + payload JSON) + 기존 `BriefingOrchestrator.run_async` 말미에 save 호출 주입 + FastAPI 라우터 + 기존 JobRunner (Content 작업에서 coroutine 지원 추가됨) + Next.js 3-page (`/briefings`, `/briefings/[date]`, `/briefings/jobs/[id]`).

**Tech Stack:** FastAPI, Pydantic, SQLite, Next.js 15 App Router. 마크다운 렌더는 Content 에서 설치한 `react-markdown + remark-gfm + @tailwindcss/typography` 재사용. 의존성 추가 없음.

**Spec 참조:** `docs/superpowers/specs/2026-04-21-briefing-web-design.md`

---

## 파일 구조 (최종)

**신규 (백엔드):**
- `alphapulse/core/storage/briefings.py` — `BriefingStore(db_path)`
- `alphapulse/webapp/api/briefing.py` — FastAPI 라우터 (4 엔드포인트)
- `alphapulse/webapp/services/briefing_runner.py` — Job 어댑터
- `tests/core/storage/test_briefings.py`
- `tests/webapp/api/test_briefing.py`
- `tests/webapp/services/test_briefing_runner.py`
- `tests/briefing/test_orchestrator_save.py`

**신규 (프론트엔드):**
- `webapp-ui/app/(dashboard)/briefings/page.tsx`
- `webapp-ui/app/(dashboard)/briefings/[date]/page.tsx`
- `webapp-ui/app/(dashboard)/briefings/jobs/[id]/page.tsx`
- `webapp-ui/components/domain/briefing/briefings-table.tsx`
- `webapp-ui/components/domain/briefing/briefing-summary-row.tsx`
- `webapp-ui/components/domain/briefing/briefing-hero-card.tsx`
- `webapp-ui/components/domain/briefing/briefing-synthesis-section.tsx`
- `webapp-ui/components/domain/briefing/briefing-commentary-section.tsx`
- `webapp-ui/components/domain/briefing/briefing-news-section.tsx`
- `webapp-ui/components/domain/briefing/briefing-post-analysis-section.tsx`
- `webapp-ui/components/domain/briefing/briefing-feedback-section.tsx`
- `webapp-ui/components/domain/briefing/briefing-raw-messages.tsx`
- `webapp-ui/components/domain/briefing/run-briefing-button.tsx`
- `webapp-ui/components/domain/briefing/briefing-job-progress.tsx`
- `webapp-ui/components/domain/briefing/no-briefings.tsx`
- `webapp-ui/e2e/briefings.spec.ts`

**수정:**
- `alphapulse/core/config.py` — `BRIEFINGS_DB` 상수
- `alphapulse/core/storage/__init__.py` — `BriefingStore` 재수출
- `alphapulse/briefing/orchestrator.py` — `run_async` 말미에 `BriefingStore.save` 호출 추가
- `alphapulse/webapp/jobs/models.py` — `JobKind` Literal 에 `"briefing"` 추가
- `alphapulse/webapp/main.py` — `briefing_store` state + `briefing_router` 등록
- `webapp-ui/components/layout/sidebar.tsx` — "브리핑" 진입점 추가

---

## Task 1: `BriefingStore` 스토리지 + Config 상수

**Files:**
- Modify: `alphapulse/core/config.py` — add `BRIEFINGS_DB`
- Create: `alphapulse/core/storage/briefings.py`
- Modify: `alphapulse/core/storage/__init__.py` — re-export `BriefingStore`
- Create: `tests/core/storage/test_briefings.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/storage/test_briefings.py`:
```python
"""BriefingStore — briefings.db 테이블 스토리지."""
import pytest

from alphapulse.core.storage.briefings import BriefingStore


@pytest.fixture
def store(tmp_path):
    return BriefingStore(db_path=tmp_path / "briefings.db")


def test_get_returns_none_when_empty(store):
    assert store.get("20260421") is None


def test_save_then_get_roundtrip(store):
    payload = {
        "pulse_result": {"date": "20260421", "score": 42.0, "signal": "moderately_bullish"},
        "synthesis": "요약 테스트",
        "news": {"articles": [{"title": "기사 1"}]},
    }
    store.save("20260421", payload)
    got = store.get("20260421")
    assert got is not None
    assert got["date"] == "20260421"
    assert got["payload"] == payload
    assert got["created_at"] > 0


def test_save_upsert_overwrites(store):
    store.save("20260421", {"v": 1})
    store.save("20260421", {"v": 2})
    got = store.get("20260421")
    assert got["payload"] == {"v": 2}


def test_get_recent_sorted_date_desc(store):
    store.save("20260419", {"i": 1})
    store.save("20260421", {"i": 3})
    store.save("20260420", {"i": 2})
    items = store.get_recent(days=30)
    assert [x["date"] for x in items] == ["20260421", "20260420", "20260419"]


def test_get_recent_limits_to_days(store):
    for i in range(5):
        store.save(f"2026041{i}", {"i": i})
    items = store.get_recent(days=3)
    assert len(items) == 3


def test_save_sanitizes_numpy_scalars(store):
    """numpy float 같은 비-JSON 타입도 sanitize 되어야 함."""
    class FakeNpFloat:
        def __float__(self) -> float:
            return 42.5
    payload = {"score": FakeNpFloat()}
    store.save("20260421", payload)
    got = store.get("20260421")
    # Round-trip 후 float 로 변환됨
    assert got["payload"]["score"] == 42.5


def test_save_sanitizes_unknown_objects_to_str(store):
    class Obj:
        def __repr__(self) -> str:
            return "custom-obj"
    payload = {"weird": Obj()}
    store.save("20260421", payload)
    got = store.get("20260421")
    assert got["payload"]["weird"] == "custom-obj"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/storage/test_briefings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.core.storage.briefings'`

- [ ] **Step 3: Add `BRIEFINGS_DB` to Config**

Edit `alphapulse/core/config.py`. Find the line `self.HISTORY_DB = self.DATA_DIR / "history.db"` (around line 23) and add a new line right after it:

```python
        self.BRIEFINGS_DB = self.DATA_DIR / "briefings.db"
```

- [ ] **Step 4: Implement `BriefingStore`**

Create `alphapulse/core/storage/briefings.py`:
```python
"""Briefing 결과 영속 저장소.

BriefingOrchestrator.run_async() 반환 dict 를 date 별로 JSON 으로 저장한다.
CLI daemon 과 웹 Job 둘 다 같은 테이블에 기록.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def _to_json_safe(value: Any) -> str:
    """payload dict 를 JSON 문자열로 직렬화 (numpy 타입 fallback 포함)."""
    return json.dumps(
        value,
        ensure_ascii=False,
        default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
    )


class BriefingStore:
    """Briefing 결과 영속 저장소 (`briefings` 테이블)."""

    def __init__(self, db_path: Path | str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS briefings (
                    date TEXT PRIMARY KEY,
                    payload TEXT,
                    created_at REAL
                )
                """
            )

    def save(self, date: str, payload: dict) -> None:
        """UPSERT. payload 안의 numpy/비직렬화 타입은 sanitize 된다."""
        # Round-trip 으로 sanitize 보장 (저장값과 읽은값이 동일하도록)
        safe_text = _to_json_safe(payload)
        safe_payload = json.loads(safe_text)
        final_text = json.dumps(safe_payload, ensure_ascii=False)
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO briefings (date, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (date, final_text, now),
            )

    def get(self, date: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT date, payload, created_at FROM briefings WHERE date = ?",
                (date,),
            ).fetchone()
        if row is None:
            return None
        return {
            "date": row["date"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def get_recent(self, days: int = 30) -> list[dict]:
        """날짜 DESC 정렬, 최대 days 건."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT date, payload, created_at FROM briefings "
                "ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        return [
            {
                "date": r["date"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
```

- [ ] **Step 5: Re-export from `alphapulse.core.storage`**

Edit `alphapulse/core/storage/__init__.py`:
```python
"""스토리지 계층 - 캐시 및 이력 관리"""

from .briefings import BriefingStore
from .cache import DataCache
from .history import PulseHistory

__all__ = ["BriefingStore", "DataCache", "PulseHistory"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/core/storage/test_briefings.py -v`
Expected: PASS (7 tests)

Also confirm no regression in other storage tests:
Run: `pytest tests/core/storage/ -q`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add alphapulse/core/config.py alphapulse/core/storage/briefings.py alphapulse/core/storage/__init__.py tests/core/storage/test_briefings.py
git commit -m "feat(storage): BriefingStore — briefings.db + Config.BRIEFINGS_DB"
```

---

## Task 2: `JobKind` 확장 + BriefingOrchestrator save 주입

**Files:**
- Modify: `alphapulse/webapp/jobs/models.py` — add `"briefing"` to JobKind
- Modify: `alphapulse/briefing/orchestrator.py` — call `BriefingStore.save` after `run_async`
- Create: `tests/briefing/test_orchestrator_save.py`

- [ ] **Step 1: Write failing test**

Create `tests/briefing/test_orchestrator_save.py`:
```python
"""BriefingOrchestrator — run_async 완료 후 BriefingStore.save 호출 검증."""
from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.briefing.orchestrator import BriefingOrchestrator


@pytest.mark.asyncio
async def test_run_async_saves_to_briefing_store(tmp_path, monkeypatch):
    """run_async 정상 완료 시 BriefingStore.save 가 호출되어야 한다."""
    monkeypatch.setenv("FEEDBACK_ENABLED", "false")

    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 42.0, "signal": "moderately_bullish",
        "indicator_scores": {}, "details": {},
    }

    with patch.object(orch, "run_quantitative", return_value=fake_pulse), \
         patch("alphapulse.briefing.orchestrator.TelegramNotifier") as notifier, \
         patch("alphapulse.agents.commentary.MarketCommentaryAgent") as cm_cls, \
         patch("alphapulse.agents.synthesis.SeniorSynthesisAgent") as synth_cls:
        notifier.return_value._send_message = AsyncMock()
        cm_cls.return_value.generate = AsyncMock(return_value="comm-text")
        synth_cls.return_value.synthesize = AsyncMock(return_value="synth-text")

        with patch(
            "alphapulse.briefing.orchestrator.BriefingStore",
        ) as store_cls:
            store_instance = store_cls.return_value
            result = await orch.run_async(date="20260421", send_telegram=False)

    # Store 생성 + save 호출 확인
    assert store_cls.called
    assert store_instance.save.called
    save_args = store_instance.save.call_args
    assert save_args.args[0] == "20260421"   # date
    saved_payload = save_args.args[1]
    assert saved_payload["pulse_result"] == fake_pulse
    assert "commentary" in saved_payload
    assert "synthesis" in saved_payload
    # run_async 자체는 정상 완료 (기존 반환값 유지)
    assert result["pulse_result"] == fake_pulse


@pytest.mark.asyncio
async def test_run_async_tolerates_save_failure(tmp_path, monkeypatch):
    """Store.save 가 예외 내도 run_async 는 완료돼야 한다 (기존 흐름 보호)."""
    monkeypatch.setenv("FEEDBACK_ENABLED", "false")

    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 42.0, "signal": "neutral",
        "indicator_scores": {}, "details": {},
    }
    with patch.object(orch, "run_quantitative", return_value=fake_pulse), \
         patch("alphapulse.briefing.orchestrator.TelegramNotifier") as notifier, \
         patch("alphapulse.agents.commentary.MarketCommentaryAgent") as cm_cls, \
         patch("alphapulse.agents.synthesis.SeniorSynthesisAgent") as synth_cls:
        notifier.return_value._send_message = AsyncMock()
        cm_cls.return_value.generate = AsyncMock(return_value="c")
        synth_cls.return_value.synthesize = AsyncMock(return_value="s")
        with patch(
            "alphapulse.briefing.orchestrator.BriefingStore",
        ) as store_cls:
            store_cls.return_value.save.side_effect = RuntimeError("disk full")
            # 예외 bubble 되지 않아야 함
            result = await orch.run_async(date="20260421", send_telegram=False)
    assert result is not None
    assert result["pulse_result"]["date"] == "20260421"
```

Check if `tests/briefing/__init__.py` exists — if not, create empty file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/briefing/test_orchestrator_save.py -v`
Expected: FAIL — `store_cls.called` is False (orchestrator doesn't use BriefingStore yet), OR `BriefingStore` import target doesn't exist in orchestrator module namespace.

- [ ] **Step 3: Extend `JobKind` literal**

Edit `alphapulse/webapp/jobs/models.py` line 10:
```python
# before
JobKind = Literal["backtest", "screening", "data_update", "market_pulse", "content_monitor"]

# after
JobKind = Literal["backtest", "screening", "data_update", "market_pulse", "content_monitor", "briefing"]
```

- [ ] **Step 4: Wire `BriefingStore.save` in `run_async`**

Edit `alphapulse/briefing/orchestrator.py`.

Add import at top (after existing imports):
```python
from alphapulse.core.storage.briefings import BriefingStore
```

In `run_async`, find the line `return {` that begins the final return statement (around line 202). Insert the following block right BEFORE the `return`:

```python
        # [8] Briefing payload 영속화 — 실패해도 메인 흐름 중단 금지
        payload = {
            "pulse_result": pulse_result,
            "content_summaries": content_summaries,
            "commentary": commentary,
            "synthesis": synthesis,
            "quant_msg": quant_msg,
            "synth_msg": synth_msg,
            "feedback_context": feedback_context,
            "daily_result_msg": daily_result_msg,
            "news": news,
            "post_analysis": post_analysis,
            "generated_at": datetime.now().isoformat(),
        }
        try:
            store = BriefingStore(self.config.BRIEFINGS_DB)
            await asyncio.to_thread(store.save, pulse_result["date"], payload)
            logger.info(f"Briefing 저장 완료: {pulse_result['date']}")
        except Exception as e:
            logger.warning(f"Briefing 저장 실패: {e}")
```

The existing `return { ... "pulse_result": pulse_result, ... "generated_at": datetime.now().isoformat(), }` block still remains below — replace it with `return payload` (since we already built the exact same dict). Verify the final block looks like:

```python
        # [8] Briefing payload 영속화 — 실패해도 메인 흐름 중단 금지
        payload = {
            "pulse_result": pulse_result,
            "content_summaries": content_summaries,
            "commentary": commentary,
            "synthesis": synthesis,
            "quant_msg": quant_msg,
            "synth_msg": synth_msg,
            "feedback_context": feedback_context,
            "daily_result_msg": daily_result_msg,
            "news": news,
            "post_analysis": post_analysis,
            "generated_at": datetime.now().isoformat(),
        }
        try:
            store = BriefingStore(self.config.BRIEFINGS_DB)
            await asyncio.to_thread(store.save, pulse_result["date"], payload)
            logger.info(f"Briefing 저장 완료: {pulse_result['date']}")
        except Exception as e:
            logger.warning(f"Briefing 저장 실패: {e}")

        return payload
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/briefing/test_orchestrator_save.py -v`
Expected: PASS (2 tests)

Also run existing briefing tests to confirm no regression:
Run: `pytest tests/briefing/ -q`
Expected: all PASS (may include existing integration tests). If any existing test asserts exact equality on `run_async` return dict keys/order, it still passes because `payload` has same keys as the old return.

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/jobs/models.py alphapulse/briefing/orchestrator.py tests/briefing/test_orchestrator_save.py tests/briefing/__init__.py
git commit -m "feat(briefing): run_async 완료 후 BriefingStore.save 호출 + JobKind briefing"
```

If `tests/briefing/__init__.py` already exists, exclude it from `git add`.

---

## Task 3: `briefing_runner.py` Job 어댑터

**Files:**
- Create: `alphapulse/webapp/services/briefing_runner.py`
- Create: `tests/webapp/services/test_briefing_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/webapp/services/test_briefing_runner.py`:
```python
"""BriefingRunner — Job 어댑터 테스트."""
import asyncio
from unittest.mock import AsyncMock, patch


def test_runs_orchestrator_and_returns_saved_date():
    """run_briefing_async 가 orchestrator 호출 + pulse_result.date 반환."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.return_value = {
        "pulse_result": {"date": "20260421", "score": 42.0, "signal": "neutral"},
        "synthesis": "요약",
    }

    progress_calls: list[tuple[int, int, str]] = []
    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        result = asyncio.run(
            run_briefing_async(date="20260421", progress_callback=on_progress),
        )

    mock_orch.run_async.assert_awaited_once_with(date="20260421", send_telegram=False)
    assert result == "20260421"
    assert progress_calls[0] == (0, 1, "브리핑 실행 중 (3~10분 소요, 브라우저 닫아도 계속)")
    assert progress_calls[-1][0] == 1 and progress_calls[-1][1] == 1
    assert "20260421" in progress_calls[-1][2]


def test_passes_none_date_to_orchestrator():
    """date=None 이면 orchestrator 가 오늘 날짜로 처리."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.return_value = {
        "pulse_result": {"date": "20260422", "score": 10.0, "signal": "neutral"},
    }
    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        result = asyncio.run(
            run_briefing_async(date=None, progress_callback=lambda *_: None),
        )
    mock_orch.run_async.assert_awaited_once_with(date=None, send_telegram=False)
    assert result == "20260422"


def test_propagates_exception():
    """orchestrator 예외는 그대로 raise (JobRunner 가 failed 마킹)."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.side_effect = RuntimeError("gemini unavailable")

    import pytest
    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        with pytest.raises(RuntimeError, match="gemini unavailable"):
            asyncio.run(
                run_briefing_async(date="20260421", progress_callback=lambda *_: None),
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/services/test_briefing_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.services.briefing_runner'`

- [ ] **Step 3: Implement briefing_runner**

Create `alphapulse/webapp/services/briefing_runner.py`:
```python
"""BriefingRunner — Job 에서 호출되는 BriefingOrchestrator 실행 async 헬퍼.

BriefingOrchestrator.run_async() 는 coroutine function — JobRunner 의
iscoroutinefunction 분기로 직접 await 된다 (Content 작업에서 추가됨).
웹 Job 은 텔레그램 발송 off — 디버깅/재확인 시 스팸 방지.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.briefing.orchestrator import BriefingOrchestrator


async def run_briefing_async(
    *,
    date: str | None,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """BriefingOrchestrator.run_async(date, send_telegram=False) 실행.

    Args:
        date: YYYYMMDD 또는 None (None 이면 오늘).
        progress_callback: (current, total, text) 진행률 훅.

    Returns:
        저장된 date (YYYYMMDD) — Job.result_ref 로 저장되어 프론트 redirect 에 사용.
    """
    progress_callback(0, 1, "브리핑 실행 중 (3~10분 소요, 브라우저 닫아도 계속)")
    orch = BriefingOrchestrator()
    result = await orch.run_async(date=date, send_telegram=False)
    saved_date = result["pulse_result"]["date"]
    progress_callback(1, 1, f"완료 ({saved_date})")
    return saved_date
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/services/test_briefing_runner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/services/briefing_runner.py tests/webapp/services/test_briefing_runner.py
git commit -m "feat(webapp): run_briefing_async — Job 어댑터 for BriefingOrchestrator"
```

---

## Task 4: Briefing API — GET endpoints

**Files:**
- Create: `alphapulse/webapp/api/briefing.py` (list + latest + detail)
- Create: `tests/webapp/api/test_briefing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/webapp/api/test_briefing.py`:
```python
"""Briefing API — GET endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.webapp.api.briefing import router as briefing_router
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
def briefing_store(tmp_path):
    return BriefingStore(db_path=tmp_path / "briefings.db")


@pytest.fixture
def app(webapp_db, briefing_store):
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
    app.state.briefing_store = briefing_store
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
    app.include_router(briefing_router)
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


def _minimal_payload(date: str, score: float = 10.0, signal: str = "neutral",
                     synthesis: str | None = "syn", commentary: str | None = "comm") -> dict:
    return {
        "pulse_result": {"date": date, "score": score, "signal": signal,
                         "indicator_scores": {}, "details": {}},
        "content_summaries": [],
        "commentary": commentary,
        "synthesis": synthesis,
        "quant_msg": "q",
        "synth_msg": "s",
        "feedback_context": None,
        "daily_result_msg": "",
        "news": {"articles": []},
        "post_analysis": None,
        "generated_at": "2026-04-21T10:00:00",
    }


def test_list_empty(client):
    r = client.get("/api/v1/briefings")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["size"] == 20


def test_list_returns_items(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", score=42.0))
    briefing_store.save("20260420", _minimal_payload("20260420", score=10.0))
    r = client.get("/api/v1/briefings")
    body = r.json()
    assert body["total"] == 2
    assert [i["date"] for i in body["items"]] == ["20260421", "20260420"]
    assert body["items"][0]["score"] == 42.0
    assert body["items"][0]["has_synthesis"] is True


def test_list_has_synthesis_false_when_null(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", synthesis=None))
    r = client.get("/api/v1/briefings")
    assert r.json()["items"][0]["has_synthesis"] is False


def test_latest_returns_null_when_empty(client):
    r = client.get("/api/v1/briefings/latest")
    assert r.status_code == 200
    assert r.json() is None


def test_latest_returns_most_recent(client, briefing_store):
    briefing_store.save("20260419", _minimal_payload("20260419"))
    briefing_store.save("20260421", _minimal_payload("20260421", score=50.0))
    r = client.get("/api/v1/briefings/latest")
    body = r.json()
    assert body["date"] == "20260421"
    assert body["pulse_result"]["score"] == 50.0


def test_detail_returns_full_payload(client, briefing_store):
    briefing_store.save("20260421", _minimal_payload("20260421", score=42.0,
                                                     synthesis="종합", commentary="해설"))
    r = client.get("/api/v1/briefings/20260421")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20260421"
    assert body["synthesis"] == "종합"
    assert body["commentary"] == "해설"
    assert body["pulse_result"]["score"] == 42.0


def test_detail_404_when_missing(client):
    r = client.get("/api/v1/briefings/19000101")
    assert r.status_code == 404


def test_detail_rejects_invalid_date_format(client):
    r = client.get("/api/v1/briefings/not-a-date")
    assert r.status_code == 422


def test_list_size_out_of_range(client):
    r = client.get("/api/v1/briefings?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/briefings?size=500")
    assert r.status_code == 422


def test_list_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/briefings")
    assert r.status_code == 401


def test_detail_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/briefings/20260421")
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_briefing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.api.briefing'`

- [ ] **Step 3: Implement GET endpoints**

Create `alphapulse/webapp/api/briefing.py`:
```python
"""Briefing API — 저장된 브리핑 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/briefings", tags=["briefings"])


class BriefingSummary(BaseModel):
    date: str
    score: float
    signal: str
    has_synthesis: bool
    has_commentary: bool
    created_at: float


class BriefingListResponse(BaseModel):
    items: list[BriefingSummary]
    page: int
    size: int
    total: int


class BriefingDetail(BaseModel):
    date: str
    created_at: float
    pulse_result: dict
    content_summaries: list[str]
    commentary: str | None
    synthesis: str | None
    quant_msg: str
    synth_msg: str
    feedback_context: dict | None
    daily_result_msg: str
    news: dict
    post_analysis: dict | None
    generated_at: str


class RunBriefingRequest(BaseModel):
    date: str | None = None


class RunBriefingResponse(BaseModel):
    job_id: str
    reused: bool


def get_briefing_store(request: Request) -> BriefingStore:
    return request.app.state.briefing_store


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def _row_to_summary(row: dict) -> BriefingSummary:
    payload = row["payload"] or {}
    pulse = payload.get("pulse_result") or {}
    return BriefingSummary(
        date=row["date"],
        score=float(pulse.get("score") or 0.0),
        signal=str(pulse.get("signal") or ""),
        has_synthesis=bool(payload.get("synthesis")),
        has_commentary=bool(payload.get("commentary")),
        created_at=row["created_at"],
    )


def _row_to_detail(row: dict) -> BriefingDetail:
    payload = row["payload"] or {}
    return BriefingDetail(
        date=row["date"],
        created_at=row["created_at"],
        pulse_result=payload.get("pulse_result") or {},
        content_summaries=payload.get("content_summaries") or [],
        commentary=payload.get("commentary"),
        synthesis=payload.get("synthesis"),
        quant_msg=payload.get("quant_msg") or "",
        synth_msg=payload.get("synth_msg") or "",
        feedback_context=payload.get("feedback_context"),
        daily_result_msg=payload.get("daily_result_msg") or "",
        news=payload.get("news") or {"articles": []},
        post_analysis=payload.get("post_analysis"),
        generated_at=payload.get("generated_at") or "",
    )


@router.get("/latest", response_model=BriefingDetail | None)
async def get_latest(
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    rows = store.get_recent(days=1)
    if not rows:
        return None
    return _row_to_detail(rows[0])


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    rows = store.get_recent(days=days)
    total = len(rows)
    start = (page - 1) * size
    sliced = rows[start:start + size]
    return BriefingListResponse(
        items=[_row_to_summary(r) for r in sliced],
        page=page,
        size=size,
        total=total,
    )


@router.get("/{date}", response_model=BriefingDetail)
async def get_briefing(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    row = store.get(date)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Briefing not found for {date}")
    return _row_to_detail(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/api/test_briefing.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/api/briefing.py tests/webapp/api/test_briefing.py
git commit -m "feat(webapp): Briefing API GET endpoints (latest/list/detail)"
```

---

## Task 5: Briefing API — POST `/run` + 중복 감지

**Files:**
- Modify: `alphapulse/webapp/api/briefing.py` — add POST endpoint
- Modify: `tests/webapp/api/test_briefing.py` — add POST tests

- [ ] **Step 1: Write failing tests**

Append to `tests/webapp/api/test_briefing.py`:
```python
def test_run_creates_job_and_returns_id(client, monkeypatch):
    """POST /run → BackgroundTasks 스케줄, reused=false."""
    async def fake_run(self, job_id, func, **kwargs):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_run,
    )
    r = client.post("/api/v1/briefings/run", json={"date": "20260421"})
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is False
    assert "job_id" in body


def test_run_reuses_existing_job(client, app, monkeypatch):
    """같은 date 의 running Job 있으면 그 id 반환."""
    app.state.jobs.create(
        job_id="existing", kind="briefing",
        params={"date": "20260421"}, user_id=1,
    )
    app.state.jobs.update_status("existing", "running")

    async def fake_run(self, job_id, func, **kwargs):
        raise AssertionError("should not be called")
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_run,
    )
    r = client.post("/api/v1/briefings/run", json={"date": "20260421"})
    body = r.json()
    assert body["job_id"] == "existing"
    assert body["reused"] is True


def test_run_with_null_date_resolves_via_helper(client, app, monkeypatch):
    """date=None → _resolve_target_date 호출, params.date 에 저장."""
    monkeypatch.setattr(
        "alphapulse.webapp.api.briefing._resolve_target_date",
        lambda d: "20260422",
    )
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )
    r = client.post("/api/v1/briefings/run", json={})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    saved = app.state.jobs.get(job_id)
    assert saved is not None
    assert saved.params.get("date") == "20260422"


def test_run_rejects_invalid_date_with_422(client):
    """잘못된 date 입력은 422 반환 (not 500)."""
    r = client.post("/api/v1/briefings/run", json={"date": "not-a-date"})
    assert r.status_code == 422


def test_run_audit_log(client, app, monkeypatch):
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )
    r = client.post("/api/v1/briefings/run", json={"date": "20260421"})
    assert r.status_code == 200
    assert app.state.audit.log.called
    call = app.state.audit.log.call_args
    assert call.args[0] == "webapp.briefing.run"
    data = call.kwargs.get("data", {})
    assert "user_id" in data
    assert "job_id" in data
    assert data.get("date") == "20260421"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/webapp/api/test_briefing.py -v -k "run"`
Expected: FAIL — POST endpoint not registered

- [ ] **Step 3: Implement POST endpoint + _resolve_target_date**

Edit `alphapulse/webapp/api/briefing.py`. Add imports near top:

```python
import uuid

from fastapi import BackgroundTasks

from alphapulse.core.config import Config
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.briefing_runner import run_briefing_async
```

Add helper functions (after `get_jobs`):

```python
def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def _resolve_target_date(date: str | None) -> str:
    """None 이면 오늘, 있으면 Config.parse_date 로 정규화."""
    if date:
        return Config.parse_date(date)
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d")
```

Add endpoint at end of file:

```python
@router.post("/run", response_model=RunBriefingResponse)
async def run_briefing(
    body: RunBriefingRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    try:
        target_date = _resolve_target_date(body.date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 중복 running Job 감지 (Market Pulse 헬퍼 재사용)
    existing = jobs.find_running_by_kind_and_date("briefing", target_date)
    if existing is not None:
        return RunBriefingResponse(job_id=existing.id, reused=True)

    job_id = str(uuid.uuid4())
    jobs.create(
        job_id=job_id, kind="briefing",
        params={"date": target_date}, user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.briefing.run",
            component="webapp",
            data={"user_id": user.id, "job_id": job_id, "date": target_date},
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_briefing_async,
            date=target_date,
        )

    background_tasks.add_task(_run)
    return RunBriefingResponse(job_id=job_id, reused=False)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/api/test_briefing.py -v`
Expected: PASS (all 16 tests — 11 GET + 5 POST)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/api/briefing.py tests/webapp/api/test_briefing.py
git commit -m "feat(webapp): Briefing POST /run + 중복 Job 재사용 + audit"
```

---

## Task 6: `main.py` — briefing_store state + router 등록

**Files:**
- Modify: `alphapulse/webapp/main.py`
- Modify: `tests/webapp/test_main.py`

- [ ] **Step 1: Write failing test**

Append to `tests/webapp/test_main.py`:
```python
def test_briefing_router_registered():
    """create_app 후 briefing 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/briefings" in routes
    assert "/api/v1/briefings/{date}" in routes
    assert "/api/v1/briefings/latest" in routes
    assert "/api/v1/briefings/run" in routes


def test_briefing_store_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "briefing_store")
    assert app.state.briefing_store is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/test_main.py -v -k "briefing"`
Expected: FAIL

- [ ] **Step 3: Wire briefing_router + briefing_store**

Edit `alphapulse/webapp/main.py`:

Add imports next to other API imports:
```python
from alphapulse.webapp.api.briefing import router as briefing_router
```

Near other storage imports:
```python
from alphapulse.core.storage.briefings import BriefingStore
```

In `create_app()`, after `content_reader = ContentReader(...)` (Task 6 of Content plan already in main.py), add:
```python
    briefing_store = BriefingStore(db_path=core.BRIEFINGS_DB)
```

After `app.state.content_reader = content_reader`, add:
```python
    app.state.briefing_store = briefing_store
```

After `app.include_router(content_router)`, add:
```python
    app.include_router(briefing_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/test_main.py -v`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Full webapp regression**

Run: `pytest tests/webapp/ -q --tb=short`
Expected: all PASS (1 pre-existing unrelated failure `test_settings_router_absent_without_encrypt_key` allowed)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/main.py tests/webapp/test_main.py
git commit -m "feat(webapp): main.py 에 briefing router + BriefingStore 상태 주입"
```

---

## Task 7: Frontend — `BriefingsTable` + `BriefingSummaryRow`

**Files:**
- Create: `webapp-ui/components/domain/briefing/briefing-summary-row.tsx`
- Create: `webapp-ui/components/domain/briefing/briefings-table.tsx`

- [ ] **Step 1: Create BriefingSummaryRow**

Create `webapp-ui/components/domain/briefing/briefing-summary-row.tsx`:
```tsx
import Link from "next/link"
import { signalStyle } from "@/lib/market-labels"

export type BriefingSummary = {
  date: string
  score: number
  signal: string
  has_synthesis: boolean
  has_commentary: boolean
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function BriefingSummaryRow({ item }: { item: BriefingSummary }) {
  const style = signalStyle(item.signal)
  const sign = item.score >= 0 ? "+" : ""
  return (
    <tr className="border-t border-neutral-800 hover:bg-neutral-900">
      <td className="px-3 py-2">
        <Link
          href={`/briefings/${item.date}`}
          className="text-blue-400 hover:underline font-mono"
        >
          {formatDate(item.date)}
        </Link>
      </td>
      <td className="px-3 py-2 text-sm font-mono tabular-nums">
        {sign}{item.score.toFixed(1)}
      </td>
      <td className="px-3 py-2">
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
          {style.label}
        </span>
      </td>
      <td className="px-3 py-2 text-sm">
        {item.has_synthesis ? "✓" : "✗"}
      </td>
    </tr>
  )
}
```

- [ ] **Step 2: Create BriefingsTable**

Create `webapp-ui/components/domain/briefing/briefings-table.tsx`:
```tsx
"use client"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { BriefingSummaryRow, type BriefingSummary } from "./briefing-summary-row"
import { Button } from "@/components/ui/button"

type ListData = {
  items: BriefingSummary[]
  page: number
  size: number
  total: number
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/briefings?${next}`
}

export function BriefingsTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">
        전체 {data.total}건 · 페이지 {data.page}/{totalPages}
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2">날짜</th>
            <th className="px-3 py-2">점수</th>
            <th className="px-3 py-2">시그널</th>
            <th className="px-3 py-2">종합</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => (
            <BriefingSummaryRow key={i.date} item={i} />
          ))}
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

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/briefing/briefings-table.tsx webapp-ui/components/domain/briefing/briefing-summary-row.tsx
git commit -m "feat(webapp-ui): BriefingsTable + BriefingSummaryRow"
```

---

## Task 8: Frontend — `BriefingHeroCard`

**Files:**
- Create: `webapp-ui/components/domain/briefing/briefing-hero-card.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/components/domain/briefing/briefing-hero-card.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type BriefingDetail = {
  date: string
  created_at: number
  pulse_result: Record<string, unknown>
  content_summaries: string[]
  commentary: string | null
  synthesis: string | null
  quant_msg: string
  synth_msg: string
  feedback_context: Record<string, unknown> | null
  daily_result_msg: string
  news: { articles: Array<Record<string, unknown>> }
  post_analysis: Record<string, unknown> | null
  generated_at: string
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epoch: number): string {
  const d = new Date(epoch * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function BriefingHeroCard({ detail }: { detail: BriefingDetail }) {
  const pulse = detail.pulse_result as { score?: number; signal?: string }
  const score = typeof pulse.score === "number" ? pulse.score : 0
  const signal = typeof pulse.signal === "string" ? pulse.signal : "neutral"
  const style = signalStyle(signal)
  const sign = score >= 0 ? "+" : ""

  return (
    <Card className="p-6 space-y-3">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          브리핑 · {formatDate(detail.date)} · {formatTime(detail.created_at)} 저장
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>
      {detail.daily_result_msg && (
        <div className="text-sm text-neutral-300 whitespace-pre-line border-t border-neutral-800 pt-3">
          {detail.daily_result_msg}
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/briefing/briefing-hero-card.tsx
git commit -m "feat(webapp-ui): BriefingHeroCard — 날짜/점수/시그널/전일 결과"
```

---

## Task 9: Frontend — 6개 섹션 컴포넌트

**Files:**
- Create: `webapp-ui/components/domain/briefing/briefing-synthesis-section.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-commentary-section.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-news-section.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-post-analysis-section.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-feedback-section.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-raw-messages.tsx`

- [ ] **Step 1: Create synthesis + commentary sections**

Create `webapp-ui/components/domain/briefing/briefing-synthesis-section.tsx`:
```tsx
"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingSynthesisSection({ synthesis }: { synthesis: string | null }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">종합 판단</h2>
      {synthesis ? (
        <ReportMarkdownView body={synthesis} />
      ) : (
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      )}
    </section>
  )
}
```

Create `webapp-ui/components/domain/briefing/briefing-commentary-section.tsx`:
```tsx
"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingCommentarySection({ commentary }: { commentary: string | null }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">AI 해설</h2>
      {commentary ? (
        <ReportMarkdownView body={commentary} />
      ) : (
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      )}
    </section>
  )
}
```

- [ ] **Step 2: Create news section**

Create `webapp-ui/components/domain/briefing/briefing-news-section.tsx`:
```tsx
"use client"

type Article = {
  title?: string
  url?: string
  source?: string
  published_at?: string
  [key: string]: unknown
}

export function BriefingNewsSection({
  news,
}: {
  news: { articles?: Article[] }
}) {
  const articles = news.articles ?? []
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">장 후 뉴스</h2>
      {articles.length === 0 ? (
        <p className="text-sm text-neutral-500">수집된 뉴스 없음</p>
      ) : (
        <ul className="space-y-1.5">
          {articles.map((a, i) => (
            <li key={i} className="text-sm">
              {a.url ? (
                <a
                  href={a.url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-400 hover:underline"
                >
                  {a.title || a.url}
                </a>
              ) : (
                <span>{a.title || "(제목 없음)"}</span>
              )}
              {a.source && (
                <span className="ml-2 text-xs text-neutral-500">· {a.source}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
```

- [ ] **Step 3: Create post-analysis section**

Create `webapp-ui/components/domain/briefing/briefing-post-analysis-section.tsx`:
```tsx
"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingPostAnalysisSection({
  postAnalysis,
}: {
  postAnalysis: Record<string, unknown> | null
}) {
  if (!postAnalysis) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">사후 분석</h2>
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      </section>
    )
  }
  const seniorSynthesis = typeof postAnalysis.senior_synthesis === "string"
    ? postAnalysis.senior_synthesis : ""
  const blindSpots = typeof postAnalysis.blind_spots === "string"
    ? postAnalysis.blind_spots : ""

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">사후 분석</h2>
      {seniorSynthesis && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">종합</h3>
          <ReportMarkdownView body={seniorSynthesis} />
        </div>
      )}
      {blindSpots && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">사각지대</h3>
          <ReportMarkdownView body={blindSpots} />
        </div>
      )}
      {!seniorSynthesis && !blindSpots && (
        <p className="text-sm text-neutral-500">내용 없음</p>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Create feedback section**

Create `webapp-ui/components/domain/briefing/briefing-feedback-section.tsx`:
```tsx
"use client"

export function BriefingFeedbackSection({
  feedbackContext,
  dailyResultMsg,
}: {
  feedbackContext: Record<string, unknown> | null
  dailyResultMsg: string
}) {
  if (!feedbackContext && !dailyResultMsg) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">피드백 컨텍스트</h2>
        <p className="text-sm text-neutral-500">피드백 데이터 없음</p>
      </section>
    )
  }
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">피드백 컨텍스트</h2>
      {dailyResultMsg && (
        <pre className="text-xs text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
          {dailyResultMsg}
        </pre>
      )}
      {feedbackContext && (
        <pre className="text-xs text-neutral-400 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
          {JSON.stringify(feedbackContext, null, 2)}
        </pre>
      )}
    </section>
  )
}
```

- [ ] **Step 5: Create raw-messages section**

Create `webapp-ui/components/domain/briefing/briefing-raw-messages.tsx`:
```tsx
"use client"

export function BriefingRawMessages({
  quantMsg,
  synthMsg,
}: {
  quantMsg: string
  synthMsg: string
}) {
  return (
    <details className="rounded border border-neutral-800 bg-neutral-900 p-3">
      <summary className="text-sm cursor-pointer text-neutral-300">
        텔레그램 메시지 원문
      </summary>
      <div className="mt-3 space-y-3">
        {quantMsg && (
          <div className="space-y-1">
            <p className="text-xs text-neutral-500">정량 메시지</p>
            <pre className="text-xs text-neutral-300 whitespace-pre-wrap">{quantMsg}</pre>
          </div>
        )}
        {synthMsg && (
          <div className="space-y-1">
            <p className="text-xs text-neutral-500">종합 메시지</p>
            <pre className="text-xs text-neutral-300 whitespace-pre-wrap">{synthMsg}</pre>
          </div>
        )}
      </div>
    </details>
  )
}
```

- [ ] **Step 6: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add webapp-ui/components/domain/briefing/briefing-synthesis-section.tsx webapp-ui/components/domain/briefing/briefing-commentary-section.tsx webapp-ui/components/domain/briefing/briefing-news-section.tsx webapp-ui/components/domain/briefing/briefing-post-analysis-section.tsx webapp-ui/components/domain/briefing/briefing-feedback-section.tsx webapp-ui/components/domain/briefing/briefing-raw-messages.tsx
git commit -m "feat(webapp-ui): Briefing 상세 섹션 컴포넌트 6개"
```

---

## Task 10: Frontend — `RunBriefingButton` + `NoBriefings` + `BriefingJobProgress`

**Files:**
- Create: `webapp-ui/components/domain/briefing/run-briefing-button.tsx`
- Create: `webapp-ui/components/domain/briefing/no-briefings.tsx`
- Create: `webapp-ui/components/domain/briefing/briefing-job-progress.tsx`

- [ ] **Step 1: Create RunBriefingButton**

Create `webapp-ui/components/domain/briefing/run-briefing-button.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunConfirmModal } from "@/components/domain/market/run-confirm-modal"
import type { BriefingSummary } from "./briefing-summary-row"

function todayYmd(): string {
  const d = new Date()
  const yyyy = String(d.getFullYear())
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  return `${yyyy}${mm}${dd}`
}

export function RunBriefingButton({
  latestToday,
}: {
  latestToday: BriefingSummary | null
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
        "/api/v1/briefings/run", "POST", {},
      )
      router.push(`/briefings/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패")
      setRunning(false)
    }
  }

  const handleClick = () => {
    if (latestToday && latestToday.date === todayYmd()) {
      setShowConfirm(true)
    } else {
      doRun()
    }
  }

  return (
    <div>
      <Button onClick={handleClick} disabled={running}>
        {running ? "실행 중…" : "지금 실행"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {showConfirm && latestToday && (
        <RunConfirmModal
          existingSavedAt={latestToday.created_at}
          onConfirm={doRun}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create NoBriefings**

Create `webapp-ui/components/domain/briefing/no-briefings.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoBriefings({ onRun }: { onRun?: () => void }) {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">브리핑이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 저장된 브리핑이 없습니다. 지금 바로 실행하거나
        <code className="px-1 mx-1 bg-neutral-800 rounded">ap briefing</code>
        CLI 로 생성할 수 있습니다.
      </p>
      {onRun && (
        <div className="flex justify-center">
          <Button onClick={onRun}>지금 실행</Button>
        </div>
      )}
      <p className="text-xs text-neutral-500">
        Daemon: <code className="px-1 bg-neutral-800 rounded">ap briefing --daemon</code>
      </p>
    </Card>
  )
}
```

- [ ] **Step 3: Create BriefingJobProgress**

Create `webapp-ui/components/domain/briefing/briefing-job-progress.tsx`:
```tsx
"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useJobStatus } from "@/hooks/use-job-status"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function BriefingJobProgress({ jobId }: { jobId: string }) {
  const router = useRouter()
  const { data: job, error } = useJobStatus(jobId)

  useEffect(() => {
    if (job?.status === "done") {
      const dest = job.result_ref && /^\d{8}$/.test(job.result_ref)
        ? `/briefings/${job.result_ref}`
        : "/briefings"
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
      <p className="text-xs text-neutral-500">
        정량분석 + AI Commentary + Senior Synthesis 로 3~10분 소요됩니다.
        브라우저 닫아도 백그라운드에서 계속 실행되며, 완료 후 브리핑 목록에서 확인할 수 있습니다.
      </p>
      {job.status === "failed" && (
        <div className="space-y-2">
          <p className="text-red-400">실패: {job.error}</p>
          <Button variant="outline" onClick={() => router.push("/briefings")}>
            돌아가기
          </Button>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 4: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add webapp-ui/components/domain/briefing/run-briefing-button.tsx webapp-ui/components/domain/briefing/no-briefings.tsx webapp-ui/components/domain/briefing/briefing-job-progress.tsx
git commit -m "feat(webapp-ui): RunBriefingButton + NoBriefings + BriefingJobProgress"
```

---

## Task 11: Frontend — `/briefings` 메인 페이지 + 사이드바

**Files:**
- Modify: `webapp-ui/components/layout/sidebar.tsx`
- Create: `webapp-ui/app/(dashboard)/briefings/page.tsx`

- [ ] **Step 1: Add sidebar entry**

Edit `webapp-ui/components/layout/sidebar.tsx`. Find ITEMS array. Insert `{ href: "/briefings", label: "브리핑" }` right after `{ href: "/content", label: "콘텐츠" }`. Preserve all other items.

Final ITEMS should be:
```tsx
const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/market/pulse", label: "시황" },
  { href: "/content", label: "콘텐츠" },
  { href: "/briefings", label: "브리핑" },
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

Create `webapp-ui/app/(dashboard)/briefings/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { BriefingsTable } from "@/components/domain/briefing/briefings-table"
import { NoBriefings } from "@/components/domain/briefing/no-briefings"
import { RunBriefingButton } from "@/components/domain/briefing/run-briefing-button"
import type { BriefingSummary } from "@/components/domain/briefing/briefing-summary-row"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string }> }

export default async function BriefingsPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  const data = await apiFetch<{
    items: BriefingSummary[]
    page: number
    size: number
    total: number
  }>(`/api/v1/briefings?page=${page}&size=20`, { headers: h, cache: "no-store" })

  // "오늘 이미 저장된 브리핑이 있는지" — RunConfirmModal 트리거 용
  const latestToday = data.items.find((i) => {
    const now = new Date()
    const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
    return i.date === ymd
  }) ?? null

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">브리핑</h1>
        <RunBriefingButton latestToday={latestToday} />
      </div>
      {data.total === 0 ? (
        <NoBriefings />
      ) : (
        <BriefingsTable data={data} />
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
git add webapp-ui/components/layout/sidebar.tsx 'webapp-ui/app/(dashboard)/briefings/page.tsx'
git commit -m "feat(webapp-ui): 브리핑 메인 페이지 + 사이드바 진입점"
```

---

## Task 12: Frontend — `/briefings/[date]` 상세 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/briefings/[date]/page.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/app/(dashboard)/briefings/[date]/page.tsx`:
```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { BriefingHeroCard, type BriefingDetail } from "@/components/domain/briefing/briefing-hero-card"
import { BriefingSynthesisSection } from "@/components/domain/briefing/briefing-synthesis-section"
import { BriefingCommentarySection } from "@/components/domain/briefing/briefing-commentary-section"
import { BriefingNewsSection } from "@/components/domain/briefing/briefing-news-section"
import { BriefingPostAnalysisSection } from "@/components/domain/briefing/briefing-post-analysis-section"
import { BriefingFeedbackSection } from "@/components/domain/briefing/briefing-feedback-section"
import { BriefingRawMessages } from "@/components/domain/briefing/briefing-raw-messages"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function BriefingDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<BriefingDetail>(
      `/api/v1/briefings/${date}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-6">
        <Link href="/briefings">
          <Button variant="outline" size="sm">← 브리핑 목록으로</Button>
        </Link>
        <BriefingHeroCard detail={detail} />
        <BriefingSynthesisSection synthesis={detail.synthesis} />
        <BriefingCommentarySection commentary={detail.commentary} />
        <BriefingNewsSection news={detail.news} />
        <BriefingPostAnalysisSection postAnalysis={detail.post_analysis} />
        <BriefingFeedbackSection
          feedbackContext={detail.feedback_context}
          dailyResultMsg={detail.daily_result_msg}
        />
        <BriefingRawMessages
          quantMsg={detail.quant_msg}
          synthMsg={detail.synth_msg}
        />
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
git add 'webapp-ui/app/(dashboard)/briefings/[date]/page.tsx'
git commit -m "feat(webapp-ui): 브리핑 날짜 상세 페이지 — 7개 섹션 조합"
```

---

## Task 13: Frontend — `/briefings/jobs/[id]` Job 진행 페이지

**Files:**
- Create: `webapp-ui/app/(dashboard)/briefings/jobs/[id]/page.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/app/(dashboard)/briefings/jobs/[id]/page.tsx`:
```tsx
import { BriefingJobProgress } from "@/components/domain/briefing/briefing-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function BriefingJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">브리핑 생성 중</h1>
      <BriefingJobProgress jobId={id} />
    </div>
  )
}
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add 'webapp-ui/app/(dashboard)/briefings/jobs/[id]/page.tsx'
git commit -m "feat(webapp-ui): 브리핑 Job 진행 페이지"
```

---

## Task 14: E2E 스모크 테스트

**Files:**
- Create: `webapp-ui/e2e/briefings.spec.ts`

- [ ] **Step 1: Implement**

Create `webapp-ui/e2e/briefings.spec.ts`:
```typescript
import { test, expect } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Briefings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 브리핑 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/briefings']")).toBeVisible()
  })

  test("/briefings 로드 → 테이블 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/briefings")
    const table = page.locator("text=/날짜/")
    const empty = page.locator("text=/브리핑이 없습니다/")
    await expect(table.or(empty)).toBeVisible()
  })

  test("'지금 실행' 버튼 렌더", async ({ page }) => {
    await page.goto("/briefings")
    await expect(page.locator("button", { hasText: /지금 실행/ })).toBeVisible()
  })
})
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/e2e/briefings.spec.ts
git commit -m "test(webapp-ui): 브리핑 E2E 스모크 — 진입점 + 리스트 + 실행 버튼"
```

---

## Task 15: 최종 회귀 + CLAUDE.md 링크

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 전체 pytest**

Run: `pytest tests/ -q --tb=short`
Expected: 신규 ~25개 PASS + 기존 PASS (1 pre-existing 무관 실패 허용)

- [ ] **Step 2: Ruff**

Run: `ruff check alphapulse/`
Expected: PASS

- [ ] **Step 3: Frontend build**

Run: `cd webapp-ui && pnpm build`
Expected: Next.js build 성공 (새 3개 라우트 포함)

- [ ] **Step 4: Add spec link to CLAUDE.md**

Edit `CLAUDE.md`. Under "## Detailed Docs" section, add this line (after Content link, before anything else):

```markdown
- Briefing 웹 대시보드 설계: `docs/superpowers/specs/2026-04-21-briefing-web-design.md`
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — Briefing 웹 spec 링크 추가"
```

---

## 완료 기준 (Definition of Done)

- [ ] `tests/core/storage/test_briefings.py` — 7 tests PASS
- [ ] `tests/briefing/test_orchestrator_save.py` — 2 tests PASS
- [ ] `tests/webapp/services/test_briefing_runner.py` — 3 tests PASS
- [ ] `tests/webapp/api/test_briefing.py` — 16 tests PASS (11 GET + 5 POST)
- [ ] `tests/webapp/test_main.py` — briefing router + state 테스트 PASS
- [ ] `pytest tests/ -q` — 전체 그린 (1 pre-existing 무관 실패 허용)
- [ ] `ruff check alphapulse/` — 통과
- [ ] `cd webapp-ui && pnpm build` — 성공, 3개 라우트 생성 (`/briefings`, `/briefings/[date]`, `/briefings/jobs/[id]`)
- [ ] 사이드바 "브리핑" 항목 노출 → 클릭 시 `/briefings`
- [ ] 이력 있을 때 BriefingsTable 렌더
- [ ] 이력 없을 때 NoBriefings 렌더
- [ ] 상세 페이지에서 7개 섹션 모두 렌더
- [ ] "지금 실행" 클릭 → 오늘 이력 있으면 RunConfirmModal → Job 페이지
- [ ] Job 완료 시 `/briefings/{date}` redirect
- [ ] CLAUDE.md 에 spec 링크 추가
