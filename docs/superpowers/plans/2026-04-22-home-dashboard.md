# Home Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 3 5개 도메인(Briefing / Market Pulse / Content / Feedback) + 기존 Phase 2(Portfolio / Risk / DataHealth)를 통합한 브리핑-중심 홈 대시보드로 재설계한다.

**Architecture:** `/api/v1/dashboard/home` 단일 aggregate 엔드포인트를 확장(섹션 단위 try/except 격리). 상단 Hero는 오늘 브리핑 요약(점수/시그널/지표 badge 3개), 아래 2×3 Balanced Grid에 6개 위젯 배치. 오늘 브리핑 부재 시 어제 데이터 + 상단 배너. 각 위젯은 display-only, 카드 전체 클릭으로 도메인 페이지 드릴다운.

**Tech Stack:** FastAPI + Pydantic (backend), Next.js 15 App Router + shadcn/ui + recharts (frontend), Playwright E2E.

**Branch:** `webapp/phase3-home` (already created)

**Spec:** `docs/superpowers/specs/2026-04-22-home-dashboard-design.md`

---

## File Structure

### Backend
- **Modify:** `alphapulse/webapp/api/dashboard.py`
  - 신규 Pydantic 모델 5개 (`BriefingHeroData`, `PulseWidgetData`, `PulseHistoryPoint`, `PulseLatest`, `FeedbackWidgetData`, `FeedbackIndicator`, `ContentWidgetData`, `ContentRecentItem`)
  - 신규 헬퍼 함수 5개 (`_select_top3_indicators`, `_build_briefing_hero`, `_build_pulse_widget`, `_build_feedback_widget`, `_build_content_widget`)
  - 신규 Depends 4개 (`get_briefing_store`, `get_pulse_history`, `get_feedback_evaluator`, `get_content_reader`)
  - `home()` 함수 재작성 (섹션별 try/except, 새 응답 필드)
  - 기존 필드 제거: `recent_backtests`, `recent_audits`
- **Modify:** `tests/webapp/api/test_dashboard.py`
  - 기존 fixtures 확장 (Phase 3 stores mock 추가)
  - 신규 테스트 케이스 추가 (Phase 3 필드, 섹션 격리, 헬퍼 단위 테스트)

### Frontend
- **Create:** `webapp-ui/components/domain/home/briefing-hero-plus.tsx`
- **Create:** `webapp-ui/components/domain/home/missing-briefing-banner.tsx`
- **Create:** `webapp-ui/components/domain/home/pulse-widget.tsx`
- **Create:** `webapp-ui/components/domain/home/feedback-widget.tsx`
- **Create:** `webapp-ui/components/domain/home/content-widget.tsx`
- **Create:** `webapp-ui/components/domain/home/data-health-widget.tsx`
- **Rewrite:** `webapp-ui/components/domain/home/portfolio-widget.tsx` (홈 축소판)
- **Rewrite:** `webapp-ui/components/domain/home/risk-status-widget.tsx` (홈 축소판)
- **Rewrite:** `webapp-ui/app/(dashboard)/page.tsx`
- **Delete:** `webapp-ui/components/domain/home/recent-backtests-widget.tsx`
- **Delete:** `webapp-ui/components/domain/home/recent-audit-widget.tsx`
- **Delete:** `webapp-ui/components/domain/home/data-status-widget.tsx`

### E2E
- **Create:** `webapp-ui/e2e/home.spec.ts`

---

## Conventions

- 백엔드는 **TDD 엄격**: test first → red → implement → green → commit
- 프런트엔드 컴포넌트: 기존 프로젝트에 Vitest 단위 테스트 없음 (Playwright E2E만 존재). 각 컴포넌트는 lint + tsc + build 로 검증, 최종 E2E 스모크로 통합 검증
- 각 Task 완료마다 `git commit` (세밀한 단위)
- `ruff check alphapulse/` 린트 통과 필수 (backend)
- `pnpm lint` 통과 필수 (frontend, `webapp-ui/` 디렉터리에서 실행)
- 피드백/브리핑 실패가 메인 렌더를 막지 않도록 try/except 격리

---

## Task 1: Pydantic 응답 모델 + `_select_top3_indicators` 헬퍼

**목적:** 신규 응답 모델을 먼저 정의하고, 가장 단순한 pure 헬퍼 함수(지표 TOP3 선택)를 TDD로 구현한다.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 1.1: 테스트 파일 맨 아래에 `TestSelectTop3Indicators` 클래스 추가 (빈 pulse_result, indicators 키 TOP3, indicator_descriptions 우선)**

파일 `tests/webapp/api/test_dashboard.py` 끝에 다음을 추가:

```python
from alphapulse.webapp.api.dashboard import _select_top3_indicators


class TestSelectTop3Indicators:
    def test_returns_empty_when_no_keys(self):
        assert _select_top3_indicators({}) == []

    def test_returns_empty_when_indicators_and_descriptions_missing(self):
        assert _select_top3_indicators({"score": 50, "signal": "positive"}) == []

    def test_picks_top3_by_abs_score_from_indicators(self):
        pulse = {
            "indicators": {
                "RSI": {"score": 80},
                "MA": {"score": -30},
                "VIX": {"score": 60},
                "VOL": {"score": 10},
                "FX": {"score": -70},
            }
        }
        result = _select_top3_indicators(pulse)
        assert len(result) == 3
        assert [r["name"] for r in result] == ["RSI", "FX", "VIX"]

    def test_direction_and_sentiment_signs(self):
        pulse = {"indicators": {"A": {"score": 80}, "B": {"score": -40}, "C": {"score": 0}}}
        result = _select_top3_indicators(pulse)
        by_name = {r["name"]: r for r in result}
        assert by_name["A"]["direction"] == "up"
        assert by_name["A"]["sentiment"] == "positive"
        assert by_name["B"]["direction"] == "down"
        assert by_name["B"]["sentiment"] == "negative"
        assert by_name["C"]["direction"] == "neutral"
        assert by_name["C"]["sentiment"] == "neutral"

    def test_indicator_descriptions_preferred_over_indicators(self):
        pulse = {
            "indicator_descriptions": {"DESC_A": {"score": 90}},
            "indicators": {"IND_A": {"score": 50}, "IND_B": {"score": 60}},
        }
        result = _select_top3_indicators(pulse)
        assert [r["name"] for r in result] == ["DESC_A"]

    def test_accepts_scalar_score_value(self):
        pulse = {"indicators": {"X": 70, "Y": -20, "Z": 55}}
        result = _select_top3_indicators(pulse)
        assert [r["name"] for r in result] == ["X", "Z", "Y"]
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_dashboard.py::TestSelectTop3Indicators -v`
Expected: FAIL — `ImportError: cannot import name '_select_top3_indicators'`

- [ ] **Step 1.3: `dashboard.py` 에 신규 Pydantic 모델과 헬퍼 추가**

파일 `alphapulse/webapp/api/dashboard.py` 에서 기존 `HomeResponse` 정의 앞/뒤에 추가 (기존 `HomeResponse` 는 아직 삭제하지 않는다 — Task 6에서 교체):

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


class HighlightBadge(BaseModel):
    name: str
    direction: str   # up | down | neutral
    sentiment: str   # positive | negative | neutral


class BriefingHeroData(BaseModel):
    date: str                          # YYYYMMDD
    created_at: int                    # epoch seconds
    score: float
    signal: str
    summary_line: str
    highlight_badges: list[HighlightBadge]
    is_today: bool


class PulseLatest(BaseModel):
    date: str
    score: float
    signal: str


class PulseHistoryPoint(BaseModel):
    date: str
    score: float
    signal: str


class PulseWidgetData(BaseModel):
    latest: PulseLatest | None
    history7: list[PulseHistoryPoint]


class FeedbackIndicator(BaseModel):
    name: str
    hit_rate: float


class FeedbackWidgetData(BaseModel):
    hit_rate_7d: float | None
    top_indicators: list[FeedbackIndicator]


class ContentRecentItem(BaseModel):
    date: str
    filename: str
    title: str


class ContentWidgetData(BaseModel):
    recent: list[ContentRecentItem]


class HomeResponse(BaseModel):
    portfolio: dict | None
    portfolio_history: list
    risk: dict | None
    data_status: dict
    recent_backtests: list
    recent_audits: list


def _select_top3_indicators(pulse_result: dict) -> list[dict]:
    """pulse_result 의 지표 목록에서 score 절대값 TOP3 을 반환한다.

    indicator_descriptions 가 있으면 우선 사용, 없으면 indicators 사용.
    각 지표의 value 는 `{score: float}` 또는 scalar 숫자 둘 다 허용.
    """
    source = pulse_result.get("indicator_descriptions") or pulse_result.get("indicators")
    if not isinstance(source, dict) or not source:
        return []

    scored: list[tuple[str, float]] = []
    for name, value in source.items():
        if isinstance(value, dict):
            raw = value.get("score")
        else:
            raw = value
        if raw is None:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        scored.append((name, score))

    scored.sort(key=lambda t: abs(t[1]), reverse=True)
    top = scored[:3]

    result: list[dict] = []
    for name, score in top:
        if score > 0:
            direction, sentiment = "up", "positive"
        elif score < 0:
            direction, sentiment = "down", "negative"
        else:
            direction, sentiment = "neutral", "neutral"
        result.append({"name": name, "direction": direction, "sentiment": sentiment})
    return result


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

(주의: 이 Step 은 **기존 `HomeResponse` 와 `home()` 엔드포인트를 그대로 유지**한 채 새 모델/헬퍼만 추가한다. Task 6 에서 통합 교체한다.)

- [ ] **Step 1.4: 테스트 재실행하여 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py::TestSelectTop3Indicators -v`
Expected: 6 passed

- [ ] **Step 1.5: 린트**

Run: `ruff check alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py`
Expected: `All checks passed!`

- [ ] **Step 1.6: 커밋**

```bash
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): Home API — 응답 모델 + _select_top3_indicators 헬퍼"
```

---

## Task 2: `_build_briefing_hero` 헬퍼

**목적:** `BriefingStore.get_recent(days=1)` 결과를 `BriefingHeroData` 로 변환하는 헬퍼. 오늘/어제 판별(is_today), summary_line 추출, badges 합성.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 2.1: 테스트 추가 (`TestBuildBriefingHero`)**

파일 `tests/webapp/api/test_dashboard.py` 끝에 추가:

```python
from unittest.mock import MagicMock, patch

from alphapulse.webapp.api.dashboard import _build_briefing_hero


class TestBuildBriefingHero:
    def test_returns_none_when_store_empty(self):
        store = MagicMock()
        store.get_recent.return_value = []
        assert _build_briefing_hero(store) is None

    @patch("alphapulse.webapp.api.dashboard.Config.get_today_str", return_value="20260422")
    def test_is_today_true_when_date_matches(self, _today):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1766839200,
            "payload": {
                "pulse_result": {"score": 62.5, "signal": "positive", "indicators": {"RSI": 80}},
                "daily_result_msg": "코스피 강세 흐름.\n외국인 순매수 유입.",
                "commentary": "상세 해설",
            },
        }]
        result = _build_briefing_hero(store)
        assert result is not None
        assert result.is_today is True
        assert result.date == "20260422"
        assert result.score == 62.5
        assert result.signal == "positive"
        assert result.summary_line == "코스피 강세 흐름."
        assert result.created_at == 1766839200
        assert len(result.highlight_badges) == 1
        assert result.highlight_badges[0].name == "RSI"

    @patch("alphapulse.webapp.api.dashboard.Config.get_today_str", return_value="20260422")
    def test_is_today_false_when_yesterday(self, _today):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260421",
            "created_at": 1766752800,
            "payload": {
                "pulse_result": {"score": 40.0, "signal": "neutral"},
                "daily_result_msg": "전일 혼조.",
                "commentary": None,
            },
        }]
        result = _build_briefing_hero(store)
        assert result is not None
        assert result.is_today is False
        assert result.summary_line == "전일 혼조."

    def test_summary_line_falls_back_to_commentary(self):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1,
            "payload": {
                "pulse_result": {"score": 0, "signal": "neutral"},
                "daily_result_msg": "",
                "commentary": "첫 문장. 두 번째 문장.",
            },
        }]
        result = _build_briefing_hero(store)
        assert result.summary_line == "첫 문장."

    def test_summary_line_empty_when_both_missing(self):
        store = MagicMock()
        store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1,
            "payload": {"pulse_result": {"score": 0, "signal": "neutral"}},
        }]
        result = _build_briefing_hero(store)
        assert result.summary_line == ""
```

- [ ] **Step 2.2: Run to verify failures**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildBriefingHero -v`
Expected: FAIL — `cannot import name '_build_briefing_hero'`

- [ ] **Step 2.3: 구현 추가**

파일 `alphapulse/webapp/api/dashboard.py` 에서 `_select_top3_indicators` 아래에 추가 (필요한 import 도 상단에 추가):

기존 imports 블록에 다음을 추가:

```python
from alphapulse.core.config import Config
from alphapulse.core.storage.briefings import BriefingStore
```

함수 추가 (`_select_top3_indicators` 바로 아래):

```python
def _build_briefing_hero(store: BriefingStore) -> BriefingHeroData | None:
    """최신 브리핑 한 건을 `BriefingHeroData` 로 변환한다. 없으면 None."""
    records = store.get_recent(days=1)
    if not records:
        return None
    record = records[0]
    payload = record.get("payload") or {}
    pulse_result = payload.get("pulse_result") or {}

    score = float(pulse_result.get("score", 0.0))
    signal = str(pulse_result.get("signal", "neutral"))

    daily = payload.get("daily_result_msg") or ""
    first_line = daily.split("\n", 1)[0].strip() if daily else ""
    if not first_line:
        commentary = payload.get("commentary") or ""
        first_line = commentary.split(".", 1)[0].strip()
        if first_line:
            first_line += "."

    badges = [HighlightBadge(**b) for b in _select_top3_indicators(pulse_result)]

    today = Config.get_today_str()
    return BriefingHeroData(
        date=str(record["date"]),
        created_at=int(record.get("created_at") or 0),
        score=score,
        signal=signal,
        summary_line=first_line,
        highlight_badges=badges,
        is_today=(str(record["date"]) == today),
    )
```

- [ ] **Step 2.4: 테스트 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildBriefingHero -v`
Expected: 5 passed

- [ ] **Step 2.5: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/dashboard.py
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): _build_briefing_hero 헬퍼"
```

---

## Task 3: `_build_pulse_widget` 헬퍼

**목적:** `PulseHistory.get_recent(days=7)` 결과를 `PulseWidgetData`(latest + chronological history7)로 변환.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 3.1: 테스트 추가**

`tests/webapp/api/test_dashboard.py` 끝에 추가:

```python
from alphapulse.webapp.api.dashboard import _build_pulse_widget


class TestBuildPulseWidget:
    def test_empty_returns_none_latest(self):
        hist = MagicMock()
        hist.get_recent.return_value = []
        result = _build_pulse_widget(hist)
        assert result.latest is None
        assert result.history7 == []

    def test_latest_is_first_record(self):
        hist = MagicMock()
        hist.get_recent.return_value = [
            {"date": "20260422", "score": 62.5, "signal": "positive"},
            {"date": "20260421", "score": 30.0, "signal": "neutral"},
        ]
        result = _build_pulse_widget(hist)
        assert result.latest is not None
        assert result.latest.date == "20260422"
        assert result.latest.score == 62.5

    def test_history7_reversed_for_chart(self):
        hist = MagicMock()
        hist.get_recent.return_value = [
            {"date": "20260422", "score": 3.0, "signal": "positive"},
            {"date": "20260421", "score": 2.0, "signal": "neutral"},
            {"date": "20260420", "score": 1.0, "signal": "negative"},
        ]
        result = _build_pulse_widget(hist)
        # 차트는 과거→현재 순으로 보고 싶어함
        assert [p.date for p in result.history7] == ["20260420", "20260421", "20260422"]

    def test_days_argument_is_7(self):
        hist = MagicMock()
        hist.get_recent.return_value = []
        _build_pulse_widget(hist)
        hist.get_recent.assert_called_once_with(days=7)
```

- [ ] **Step 3.2: Run to verify failure**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildPulseWidget -v`
Expected: FAIL — `cannot import name '_build_pulse_widget'`

- [ ] **Step 3.3: 구현 추가**

`dashboard.py` 상단 imports 추가:

```python
from alphapulse.core.storage.history import PulseHistory
```

`_build_briefing_hero` 아래에 함수 추가:

```python
def _build_pulse_widget(history: PulseHistory) -> PulseWidgetData:
    """최근 7일 Pulse 이력을 위젯 데이터로 변환한다."""
    records = history.get_recent(days=7)
    if not records:
        return PulseWidgetData(latest=None, history7=[])

    latest = PulseLatest(
        date=str(records[0]["date"]),
        score=float(records[0]["score"]),
        signal=str(records[0]["signal"]),
    )
    chronological = list(reversed(records))
    history7 = [
        PulseHistoryPoint(
            date=str(r["date"]),
            score=float(r["score"]),
            signal=str(r["signal"]),
        )
        for r in chronological
    ]
    return PulseWidgetData(latest=latest, history7=history7)
```

- [ ] **Step 3.4: 테스트 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildPulseWidget -v`
Expected: 4 passed

- [ ] **Step 3.5: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/dashboard.py
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): _build_pulse_widget 헬퍼"
```

---

## Task 4: `_build_feedback_widget` 헬퍼

**목적:** `FeedbackEvaluator` 에서 7일 적중률 + 지표별 accuracy TOP2 를 합성.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 4.1: 테스트 추가**

`tests/webapp/api/test_dashboard.py` 끝에 추가:

```python
from alphapulse.webapp.api.dashboard import _build_feedback_widget


class TestBuildFeedbackWidget:
    def test_returns_none_when_no_records(self):
        ev = MagicMock()
        ev.get_hit_rates.return_value = {
            "hit_rate_1d": 0.0, "hit_rate_3d": 0.0, "hit_rate_5d": 0.0,
            "total_evaluated": 0,
        }
        result = _build_feedback_widget(ev)
        assert result is None

    def test_hit_rate_maps_from_1d(self):
        ev = MagicMock()
        ev.get_hit_rates.return_value = {
            "hit_rate_1d": 0.714, "hit_rate_3d": 0.5, "hit_rate_5d": 0.6,
            "total_evaluated": 7,
        }
        ev.get_indicator_accuracy.return_value = {}
        result = _build_feedback_widget(ev)
        assert result is not None
        assert result.hit_rate_7d == 0.714
        assert result.top_indicators == []

    def test_top_indicators_limited_to_2_and_ordered_by_accuracy(self):
        ev = MagicMock()
        ev.get_hit_rates.return_value = {
            "hit_rate_1d": 0.5, "hit_rate_3d": 0, "hit_rate_5d": 0,
            "total_evaluated": 10,
        }
        ev.get_indicator_accuracy.return_value = {
            "RSI": {"accuracy": 0.80, "hits": 4, "total": 5},
            "MA": {"accuracy": 0.60, "hits": 3, "total": 5},
            "VIX": {"accuracy": 0.90, "hits": 9, "total": 10},
            "FX_LOWN": {"accuracy": 1.0, "hits": 1, "total": 1},   # total < 3 제외
            "VOL_LOWN": {"accuracy": 1.0, "hits": 2, "total": 2},  # total < 3 제외
        }
        result = _build_feedback_widget(ev)
        names = [i.name for i in result.top_indicators]
        assert names == ["VIX", "RSI"]
        assert result.top_indicators[0].hit_rate == 0.90

    def test_days_argument_is_7(self):
        ev = MagicMock()
        ev.get_hit_rates.return_value = {
            "hit_rate_1d": 0, "hit_rate_3d": 0, "hit_rate_5d": 0,
            "total_evaluated": 0,
        }
        _build_feedback_widget(ev)
        ev.get_hit_rates.assert_called_once_with(days=7)
```

- [ ] **Step 4.2: Run to verify failure**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildFeedbackWidget -v`
Expected: FAIL — `cannot import name '_build_feedback_widget'`

- [ ] **Step 4.3: 구현 추가**

`dashboard.py` 상단 imports 추가:

```python
from alphapulse.feedback.evaluator import FeedbackEvaluator
```

`_build_pulse_widget` 아래 함수 추가:

```python
def _build_feedback_widget(evaluator: FeedbackEvaluator) -> FeedbackWidgetData | None:
    """최근 7일 피드백 요약 (적중률 + 지표 TOP2)."""
    rates = evaluator.get_hit_rates(days=7)
    if rates.get("total_evaluated", 0) == 0:
        return None

    acc = evaluator.get_indicator_accuracy(days=7, threshold=50.0)
    qualified = [
        (name, float(v["accuracy"]))
        for name, v in acc.items()
        if v.get("total", 0) >= 3
    ]
    qualified.sort(key=lambda t: t[1], reverse=True)
    top = qualified[:2]

    return FeedbackWidgetData(
        hit_rate_7d=float(rates.get("hit_rate_1d", 0.0)),
        top_indicators=[FeedbackIndicator(name=n, hit_rate=r) for n, r in top],
    )
```

- [ ] **Step 4.4: 테스트 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildFeedbackWidget -v`
Expected: 4 passed

- [ ] **Step 4.5: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/dashboard.py
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): _build_feedback_widget 헬퍼"
```

---

## Task 5: `_build_content_widget` 헬퍼

**목적:** `ContentReader.list_reports(size=3, sort="newest")` 결과를 위젯 데이터로 변환.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 5.1: 테스트 추가**

```python
from alphapulse.webapp.api.dashboard import _build_content_widget


class TestBuildContentWidget:
    def test_empty_result_returns_empty_list(self):
        reader = MagicMock()
        reader.list_reports.return_value = {
            "items": [], "total": 0, "page": 1, "size": 3, "categories": [],
        }
        result = _build_content_widget(reader)
        assert result.recent == []

    def test_maps_items_to_recent(self):
        reader = MagicMock()
        reader.list_reports.return_value = {
            "items": [
                {
                    "filename": "samsung.md",
                    "title": "삼성전자 분석",
                    "category": "기업",
                    "published": "2026-04-22",
                    "analyzed_at": "2026-04-22T08:30",
                },
                {
                    "filename": "ai.md",
                    "title": "AI 테마",
                    "category": "테마",
                    "published": "2026-04-21",
                    "analyzed_at": "2026-04-21T10:00",
                },
            ],
            "total": 2, "page": 1, "size": 3, "categories": ["기업", "테마"],
        }
        result = _build_content_widget(reader)
        assert len(result.recent) == 2
        assert result.recent[0].filename == "samsung.md"
        assert result.recent[0].title == "삼성전자 분석"
        assert result.recent[0].date == "2026-04-22"

    def test_called_with_size_3_newest(self):
        reader = MagicMock()
        reader.list_reports.return_value = {
            "items": [], "total": 0, "page": 1, "size": 3, "categories": [],
        }
        _build_content_widget(reader)
        reader.list_reports.assert_called_once_with(size=3, sort="newest")
```

- [ ] **Step 5.2: Run to verify failure**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildContentWidget -v`
Expected: FAIL

- [ ] **Step 5.3: 구현 추가**

`dashboard.py` 상단 imports 추가:

```python
from alphapulse.webapp.store.readers.content import ContentReader
```

함수 추가:

```python
def _build_content_widget(reader: ContentReader) -> ContentWidgetData:
    """최근 3건 리포트를 위젯 데이터로 변환한다."""
    result = reader.list_reports(size=3, sort="newest")
    items = result.get("items", [])
    recent = [
        ContentRecentItem(
            date=str(m.get("analyzed_at") or "")[:10],
            filename=str(m.get("filename") or ""),
            title=str(m.get("title") or ""),
        )
        for m in items
    ]
    return ContentWidgetData(recent=recent)
```

- [ ] **Step 5.4: 테스트 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py::TestBuildContentWidget -v`
Expected: 3 passed

- [ ] **Step 5.5: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/dashboard.py
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): _build_content_widget 헬퍼"
```

---

## Task 6: `home()` 엔드포인트 재작성 — 섹션 격리 + 신규 응답 통합

**목적:** 기존 `home()` 을 새 `HomeResponse` 로 교체. `recent_backtests`/`recent_audits` 필드 제거, Phase 3 필드 추가. 각 섹션 try/except 격리.

**Files:**
- Modify: `alphapulse/webapp/api/dashboard.py`
- Modify: `tests/webapp/api/test_dashboard.py`

- [ ] **Step 6.1: 통합 테스트 추가 (`TestHomeV2`)**

`tests/webapp/api/test_dashboard.py` 에서 기존 `app` fixture 를 확장한다. 기존 fixture 위치(약 19~78줄)를 수정:

```python
@pytest.fixture
def app(webapp_db):  # noqa: PLR0915
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

    # Phase 3 readers (신규)
    briefing_store = MagicMock()
    briefing_store.get_recent.return_value = []
    app.state.briefing_store = briefing_store

    pulse_history = MagicMock()
    pulse_history.get_recent.return_value = []
    app.state.pulse_history = pulse_history

    feedback_evaluator = MagicMock()
    feedback_evaluator.get_hit_rates.return_value = {
        "hit_rate_1d": 0.0, "hit_rate_3d": 0.0, "hit_rate_5d": 0.0,
        "total_evaluated": 0,
    }
    feedback_evaluator.get_indicator_accuracy.return_value = {}
    app.state.feedback_evaluator = feedback_evaluator

    content_reader = MagicMock()
    content_reader.list_reports.return_value = {
        "items": [], "total": 0, "page": 1, "size": 3, "categories": [],
    }
    app.state.content_reader = content_reader

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
    app.include_router(dash_router)
    return app
```

기존 `TestHome::test_aggregates` 아래(같은 클래스 안)에 새 테스트를 추가:

```python
class TestHomeV2:
    def test_phase3_fields_present_and_null_when_empty(self, client):
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert "briefing" in body and body["briefing"] is None
        assert "pulse" in body and body["pulse"] == {"latest": None, "history7": []}
        assert "feedback" in body and body["feedback"] is None
        assert "content" in body and body["content"] == {"recent": []}

    def test_removed_legacy_fields(self, client):
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert "recent_backtests" not in body
        assert "recent_audits" not in body

    def test_briefing_returns_hero_when_present(self, client, app):
        app.state.briefing_store.get_recent.return_value = [{
            "date": "20260422",
            "created_at": 1766839200,
            "payload": {
                "pulse_result": {"score": 62.5, "signal": "positive", "indicators": {"RSI": 80}},
                "daily_result_msg": "코스피 강세.\n추가 코멘트.",
            },
        }]
        r = client.get("/api/v1/dashboard/home")
        body = r.json()
        assert body["briefing"]["date"] == "20260422"
        assert body["briefing"]["score"] == 62.5
        assert body["briefing"]["summary_line"] == "코스피 강세."
        assert len(body["briefing"]["highlight_badges"]) == 1

    def test_pulse_failure_isolated(self, client, app):
        app.state.pulse_history.get_recent.side_effect = RuntimeError("boom")
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["pulse"] is None
        # 나머지 섹션은 정상
        assert body["portfolio"] is not None

    def test_feedback_failure_isolated(self, client, app):
        app.state.feedback_evaluator.get_hit_rates.side_effect = RuntimeError("x")
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["feedback"] is None

    def test_content_failure_isolated(self, client, app):
        app.state.content_reader.list_reports.side_effect = OSError("fs")
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["content"] == {"recent": []}
```

또한 기존 `TestHome::test_aggregates` 는 legacy 필드 존재 검증에서 Phase 3 필드 존재 검증으로 업데이트:

```python
    def test_aggregates(self, client):
        r = client.get("/api/v1/dashboard/home")
        assert r.status_code == 200
        body = r.json()
        assert body["portfolio"]["total_value"] == 100_000_000
        assert body["risk"]["report"]["var_95"] == -2.5
        assert "tables" in body["data_status"]
        # 신규 필드 존재
        assert "briefing" in body
        assert "pulse" in body
        assert "feedback" in body
        assert "content" in body
```

- [ ] **Step 6.2: Run to verify failures**

Run: `pytest tests/webapp/api/test_dashboard.py::TestHomeV2 -v`
Expected: FAIL (필드 없음 / legacy 필드 잔존)

- [ ] **Step 6.3: `dashboard.py` 의 `HomeResponse` + `home()` 재작성**

파일 `alphapulse/webapp/api/dashboard.py` 전체를 다음으로 교체한다:

```python
"""Dashboard home — 여러 도메인 aggregate 1회 호출."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from alphapulse.core.config import Config
from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.core.storage.history import PulseHistory
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class HighlightBadge(BaseModel):
    name: str
    direction: str
    sentiment: str


class BriefingHeroData(BaseModel):
    date: str
    created_at: int
    score: float
    signal: str
    summary_line: str
    highlight_badges: list[HighlightBadge]
    is_today: bool


class PulseLatest(BaseModel):
    date: str
    score: float
    signal: str


class PulseHistoryPoint(BaseModel):
    date: str
    score: float
    signal: str


class PulseWidgetData(BaseModel):
    latest: PulseLatest | None
    history7: list[PulseHistoryPoint]


class FeedbackIndicator(BaseModel):
    name: str
    hit_rate: float


class FeedbackWidgetData(BaseModel):
    hit_rate_7d: float | None
    top_indicators: list[FeedbackIndicator]


class ContentRecentItem(BaseModel):
    date: str
    filename: str
    title: str


class ContentWidgetData(BaseModel):
    recent: list[ContentRecentItem]


class HomeResponse(BaseModel):
    briefing: BriefingHeroData | None
    pulse: PulseWidgetData | None
    feedback: FeedbackWidgetData | None
    content: ContentWidgetData
    portfolio: dict | None
    portfolio_history: list
    risk: dict | None
    data_status: dict


def _select_top3_indicators(pulse_result: dict) -> list[dict]:
    source = pulse_result.get("indicator_descriptions") or pulse_result.get("indicators")
    if not isinstance(source, dict) or not source:
        return []
    scored: list[tuple[str, float]] = []
    for name, value in source.items():
        if isinstance(value, dict):
            raw = value.get("score")
        else:
            raw = value
        if raw is None:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        scored.append((name, score))
    scored.sort(key=lambda t: abs(t[1]), reverse=True)
    result: list[dict] = []
    for name, score in scored[:3]:
        if score > 0:
            direction, sentiment = "up", "positive"
        elif score < 0:
            direction, sentiment = "down", "negative"
        else:
            direction, sentiment = "neutral", "neutral"
        result.append({"name": name, "direction": direction, "sentiment": sentiment})
    return result


def _build_briefing_hero(store: BriefingStore) -> BriefingHeroData | None:
    records = store.get_recent(days=1)
    if not records:
        return None
    record = records[0]
    payload = record.get("payload") or {}
    pulse_result = payload.get("pulse_result") or {}

    score = float(pulse_result.get("score", 0.0))
    signal = str(pulse_result.get("signal", "neutral"))

    daily = payload.get("daily_result_msg") or ""
    first_line = daily.split("\n", 1)[0].strip() if daily else ""
    if not first_line:
        commentary = payload.get("commentary") or ""
        first_line = commentary.split(".", 1)[0].strip()
        if first_line:
            first_line += "."

    badges = [HighlightBadge(**b) for b in _select_top3_indicators(pulse_result)]

    today = Config.get_today_str()
    return BriefingHeroData(
        date=str(record["date"]),
        created_at=int(record.get("created_at") or 0),
        score=score,
        signal=signal,
        summary_line=first_line,
        highlight_badges=badges,
        is_today=(str(record["date"]) == today),
    )


def _build_pulse_widget(history: PulseHistory) -> PulseWidgetData:
    records = history.get_recent(days=7)
    if not records:
        return PulseWidgetData(latest=None, history7=[])
    latest = PulseLatest(
        date=str(records[0]["date"]),
        score=float(records[0]["score"]),
        signal=str(records[0]["signal"]),
    )
    chronological = list(reversed(records))
    history7 = [
        PulseHistoryPoint(
            date=str(r["date"]),
            score=float(r["score"]),
            signal=str(r["signal"]),
        )
        for r in chronological
    ]
    return PulseWidgetData(latest=latest, history7=history7)


def _build_feedback_widget(evaluator: FeedbackEvaluator) -> FeedbackWidgetData | None:
    rates = evaluator.get_hit_rates(days=7)
    if rates.get("total_evaluated", 0) == 0:
        return None
    acc = evaluator.get_indicator_accuracy(days=7, threshold=50.0)
    qualified = [
        (name, float(v["accuracy"]))
        for name, v in acc.items()
        if v.get("total", 0) >= 3
    ]
    qualified.sort(key=lambda t: t[1], reverse=True)
    return FeedbackWidgetData(
        hit_rate_7d=float(rates.get("hit_rate_1d", 0.0)),
        top_indicators=[FeedbackIndicator(name=n, hit_rate=r) for n, r in qualified[:2]],
    )


def _build_content_widget(reader: ContentReader) -> ContentWidgetData:
    result = reader.list_reports(size=3, sort="newest")
    items = result.get("items", [])
    recent = [
        ContentRecentItem(
            date=str(m.get("analyzed_at") or "")[:10],
            filename=str(m.get("filename") or ""),
            title=str(m.get("title") or ""),
        )
        for m in items
    ]
    return ContentWidgetData(recent=recent)


def get_portfolio(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


def get_risk(request: Request) -> RiskReader:
    return request.app.state.risk_reader


def get_data(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_briefing_store(request: Request) -> BriefingStore:
    return request.app.state.briefing_store


def get_pulse_history(request: Request) -> PulseHistory:
    return request.app.state.pulse_history


def get_feedback_evaluator(request: Request) -> FeedbackEvaluator:
    return request.app.state.feedback_evaluator


def get_content_reader(request: Request) -> ContentReader:
    return request.app.state.content_reader


@router.get("/home", response_model=HomeResponse)
async def home(
    _: User = Depends(get_current_user),
    portfolio: PortfolioReader = Depends(get_portfolio),
    risk: RiskReader = Depends(get_risk),
    data: DataStatusReader = Depends(get_data),
    briefing_store: BriefingStore = Depends(get_briefing_store),
    pulse_history: PulseHistory = Depends(get_pulse_history),
    feedback_evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
    content_reader: ContentReader = Depends(get_content_reader),
):
    mode = "paper"

    briefing = None
    try:
        briefing = _build_briefing_hero(briefing_store)
    except Exception as e:
        logger.warning("home: briefing fetch failed: %s", e)

    pulse = None
    try:
        pulse = _build_pulse_widget(pulse_history)
    except Exception as e:
        logger.warning("home: pulse fetch failed: %s", e)

    feedback = None
    try:
        feedback = _build_feedback_widget(feedback_evaluator)
    except Exception as e:
        logger.warning("home: feedback fetch failed: %s", e)

    content = ContentWidgetData(recent=[])
    try:
        content = _build_content_widget(content_reader)
    except Exception as e:
        logger.warning("home: content fetch failed: %s", e)

    portfolio_snap = None
    portfolio_hist: list = []
    try:
        portfolio_snap = portfolio.get_latest(mode=mode)
        portfolio_hist = portfolio.get_history(mode=mode, days=30)
    except Exception as e:
        logger.warning("home: portfolio fetch failed: %s", e)

    risk_data = None
    if portfolio_snap is not None:
        try:
            risk_data = risk.get_report(mode=mode)
        except Exception as e:
            logger.warning("home: risk fetch failed: %s", e)

    data_status_data: dict = {"tables": [], "gaps_count": 0}
    try:
        data_status_data = {
            "tables": [t.__dict__ for t in data.get_status()],
            "gaps_count": len(data.detect_gaps(days=5)),
        }
    except Exception as e:
        logger.warning("home: data_status fetch failed: %s", e)

    return HomeResponse(
        briefing=briefing,
        pulse=pulse,
        feedback=feedback,
        content=content,
        portfolio=portfolio_snap.__dict__ if portfolio_snap else None,
        portfolio_history=[s.__dict__ for s in portfolio_hist],
        risk=risk_data,
        data_status=data_status_data,
    )
```

- [ ] **Step 6.4: 테스트 전체 통과 확인**

Run: `pytest tests/webapp/api/test_dashboard.py -v`
Expected: 모두 PASS (TestHome, TestHomeV2, 그리고 Task 1~5 의 헬퍼 테스트까지)

- [ ] **Step 6.5: 전체 테스트 확인 (regression)**

Run: `pytest tests/webapp/ -q --tb=short`
Expected: all pass (기존 webapp 테스트 영향 없음 확인)

- [ ] **Step 6.6: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/dashboard.py
git add alphapulse/webapp/api/dashboard.py tests/webapp/api/test_dashboard.py
git commit -m "feat(webapp): Home API Phase 3 통합 — briefing/pulse/feedback/content + 섹션 격리"
```

---

## Task 7: BriefingHeroPlus + MissingBriefingBanner 컴포넌트

**목적:** 상단 Hero 카드 + 오늘 미생성 배너. signalStyle 유틸 재사용.

**Files:**
- Create: `webapp-ui/components/domain/home/briefing-hero-plus.tsx`
- Create: `webapp-ui/components/domain/home/missing-briefing-banner.tsx`

- [ ] **Step 7.1: `briefing-hero-plus.tsx` 작성**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type HighlightBadge = {
  name: string
  direction: "up" | "down" | "neutral"
  sentiment: "positive" | "negative" | "neutral"
}

export type BriefingHero = {
  date: string
  created_at: number
  score: number
  signal: string
  summary_line: string
  highlight_badges: HighlightBadge[]
  is_today: boolean
}

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epoch: number): string {
  if (!epoch) return ""
  const d = new Date(epoch * 1000)
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
}

function directionArrow(d: HighlightBadge["direction"]): string {
  if (d === "up") return "↑"
  if (d === "down") return "↓"
  return "·"
}

function badgeClass(b: HighlightBadge): string {
  if (b.sentiment === "positive") return "bg-emerald-900/30 text-emerald-400"
  if (b.sentiment === "negative") return "bg-rose-900/30 text-rose-400"
  return "bg-amber-900/30 text-amber-400"
}

export function BriefingHeroPlus({ hero }: { hero: BriefingHero | null }) {
  if (!hero) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-400">
          브리핑 데이터가 없습니다. 먼저 브리핑을 생성하세요.
        </p>
      </Card>
    )
  }
  const style = signalStyle(hero.signal)
  const sign = hero.score >= 0 ? "+" : ""
  const timeText = formatTime(hero.created_at)
  return (
    <Card className="p-6 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs text-neutral-400">
            브리핑 · {formatDate(hero.date)}{timeText && ` · ${timeText} 저장`}
          </p>
          <div className="flex items-baseline gap-4 flex-wrap">
            <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
              {sign}{hero.score.toFixed(1)}
            </span>
            <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
              {style.label}
            </span>
          </div>
          {hero.summary_line && (
            <p className="text-sm text-neutral-300">{hero.summary_line}</p>
          )}
          {hero.highlight_badges.length > 0 && (
            <div className="flex gap-2 flex-wrap pt-1">
              {hero.highlight_badges.map((b) => (
                <span key={b.name} className={`px-2 py-1 text-xs rounded ${badgeClass(b)}`}>
                  {b.name} {directionArrow(b.direction)}
                </span>
              ))}
            </div>
          )}
        </div>
        <Link
          href={`/briefings/${hero.date}`}
          className="text-sm text-neutral-400 hover:text-neutral-200 shrink-0"
        >
          → 상세 보기
        </Link>
      </div>
    </Card>
  )
}
```

- [ ] **Step 7.2: `missing-briefing-banner.tsx` 작성**

```tsx
"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/api-client"

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function todayYYYYMMDD(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`
}

export function MissingBriefingBanner({ latestDate }: { latestDate: string | null }) {
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const today = todayYYYYMMDD()
  const todayPretty = formatDate(today)

  async function onRun() {
    setRunning(true)
    setMessage(null)
    try {
      await apiFetch("/api/v1/briefings/run", { method: "POST" })
      setMessage("브리핑 작업이 시작되었습니다. 잠시 후 새로고침하세요.")
    } catch (e) {
      setMessage(`실행 실패: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRunning(false)
    }
  }

  const text = latestDate
    ? `⚠ 오늘(${todayPretty}) 브리핑 미생성 · 어제(${formatDate(latestDate)}) 기준 표시 중`
    : `⚠ 브리핑 데이터가 없습니다.`

  return (
    <div className="rounded-md border border-amber-900/40 bg-amber-950/30 px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
      <p className="text-sm text-amber-300">{text}</p>
      <div className="flex items-center gap-3">
        {message && <span className="text-xs text-neutral-400">{message}</span>}
        <Button onClick={onRun} disabled={running} variant="default" size="sm">
          {running ? "실행 중..." : "지금 실행"}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 7.3: 린트 + 빌드 검증**

Run (from `webapp-ui/`):
```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```
Expected: no errors related to new files.

- [ ] **Step 7.4: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/home/briefing-hero-plus.tsx webapp-ui/components/domain/home/missing-briefing-banner.tsx
git commit -m "feat(webapp-ui): BriefingHeroPlus + MissingBriefingBanner 컴포넌트"
```

---

## Task 8: Insight Widgets — PulseWidget + FeedbackWidget + ContentWidget

**목적:** 3개 Insight Row 위젯을 일관된 Card 형태로 생성.

**Files:**
- Create: `webapp-ui/components/domain/home/pulse-widget.tsx`
- Create: `webapp-ui/components/domain/home/feedback-widget.tsx`
- Create: `webapp-ui/components/domain/home/content-widget.tsx`

- [ ] **Step 8.1: `pulse-widget.tsx` 작성**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type PulsePoint = { date: string; score: number; signal: string }
export type PulseData = {
  latest: PulsePoint | null
  history7: PulsePoint[]
}

function barColor(signal: string): string {
  if (signal === "positive") return "bg-emerald-500"
  if (signal === "negative") return "bg-rose-500"
  return "bg-amber-500"
}

export function PulseWidget({ data }: { data: PulseData | null }) {
  if (!data || data.latest === null) {
    return (
      <Link href="/market/pulse" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Market Pulse</div>
          <p className="text-sm text-neutral-500">데이터 없음</p>
        </Card>
      </Link>
    )
  }
  const style = signalStyle(data.latest.signal)
  const max = Math.max(100, ...data.history7.map((p) => Math.abs(p.score)))
  return (
    <Link href="/market/pulse" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Market Pulse</div>
        <div className="flex items-baseline gap-3 mb-3">
          <span className={`text-2xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {data.latest.score >= 0 ? "+" : ""}{data.latest.score.toFixed(1)}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${style.badge}`}>{style.label}</span>
        </div>
        <div className="flex items-end gap-1 h-12">
          {data.history7.map((p) => {
            const height = Math.max(4, (Math.abs(p.score) / max) * 100)
            return (
              <div
                key={p.date}
                className={`flex-1 rounded-sm ${barColor(p.signal)}`}
                style={{ height: `${height}%` }}
                title={`${p.date}: ${p.score.toFixed(1)}`}
              />
            )
          })}
        </div>
        <p className="text-[10px] text-neutral-500 mt-2">최근 7일</p>
      </Card>
    </Link>
  )
}
```

- [ ] **Step 8.2: `feedback-widget.tsx` 작성**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

export type FeedbackIndicator = { name: string; hit_rate: number }
export type FeedbackData = {
  hit_rate_7d: number | null
  top_indicators: FeedbackIndicator[]
}

export function FeedbackWidget({ data }: { data: FeedbackData | null }) {
  if (!data || data.hit_rate_7d === null) {
    return (
      <Link href="/feedback" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Feedback</div>
          <p className="text-sm text-neutral-500">피드백 데이터 없음</p>
        </Card>
      </Link>
    )
  }
  const pct = (data.hit_rate_7d * 100).toFixed(1)
  return (
    <Link href="/feedback" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Feedback · 7일</div>
        <div className="text-3xl font-bold font-mono text-emerald-400 mb-2">{pct}%</div>
        <p className="text-xs text-neutral-500 mb-3">시그널 적중률 (1일)</p>
        {data.top_indicators.length > 0 ? (
          <ul className="space-y-1">
            {data.top_indicators.map((i) => (
              <li key={i.name} className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">{i.name}</span>
                <span className="font-mono text-neutral-300">{(i.hit_rate * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-neutral-500">지표별 집계 없음</p>
        )}
      </Card>
    </Link>
  )
}
```

- [ ] **Step 8.3: `content-widget.tsx` 작성**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

export type ContentItem = { date: string; filename: string; title: string }
export type ContentData = { recent: ContentItem[] }

export function ContentWidget({ data }: { data: ContentData }) {
  return (
    <Link href="/content/reports" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Content 최근</div>
        {data.recent.length === 0 ? (
          <p className="text-sm text-neutral-500">신규 리포트 없음</p>
        ) : (
          <ul className="space-y-2">
            {data.recent.map((r) => (
              <li key={r.filename} className="text-sm">
                <div className="text-neutral-200 truncate" title={r.title}>📄 {r.title}</div>
                <div className="text-[10px] text-neutral-500">{r.date}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Link>
  )
}
```

- [ ] **Step 8.4: 린트**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

- [ ] **Step 8.5: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/home/pulse-widget.tsx webapp-ui/components/domain/home/feedback-widget.tsx webapp-ui/components/domain/home/content-widget.tsx
git commit -m "feat(webapp-ui): Insight Row 위젯 — Pulse/Feedback/Content"
```

---

## Task 9: Trading Row — PortfolioWidget / RiskStatusWidget 리라이트 + DataHealthWidget 생성

**목적:** 기존 Portfolio/Risk 위젯을 홈 축소판으로 재작성. 기존 `data-status-widget` 을 `data-health-widget` 로 교체 (이름/경로 일관성).

**Files:**
- Rewrite: `webapp-ui/components/domain/home/portfolio-widget.tsx`
- Rewrite: `webapp-ui/components/domain/home/risk-status-widget.tsx`
- Create: `webapp-ui/components/domain/home/data-health-widget.tsx`

- [ ] **Step 9.1: 기존 `portfolio-widget.tsx` 내용 확인 (참고)**

Run: `cat webapp-ui/components/domain/home/portfolio-widget.tsx | head -40`

(파일 내용을 읽어 props shape 확인. 기존 시그니처 유지하여 호출부 변경 최소화.)

- [ ] **Step 9.2: `portfolio-widget.tsx` 전체 교체**

파일 `webapp-ui/components/domain/home/portfolio-widget.tsx` 를 다음으로 교체:

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type PortfolioSnapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
  positions: { code: string; name: string; quantity: number; current_price: number }[]
}

function formatKRW(v: number): string {
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(2)}억`
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(0)}만`
  return v.toLocaleString()
}

function pctColor(v: number): string {
  if (v > 0) return "text-emerald-400"
  if (v < 0) return "text-rose-400"
  return "text-neutral-400"
}

export function PortfolioWidget({
  portfolio,
  history: _history,
}: {
  portfolio: PortfolioSnapshot | null
  history?: { date: string; total_value: number }[]
}) {
  if (!portfolio) {
    return (
      <Link href="/portfolio" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Portfolio</div>
          <p className="text-sm text-neutral-500">포트폴리오 스냅샷 없음</p>
        </Card>
      </Link>
    )
  }
  const sign = (v: number) => (v >= 0 ? "+" : "")
  return (
    <Link href="/portfolio" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Portfolio</div>
        <div className="text-2xl font-bold font-mono mb-2">₩{formatKRW(portfolio.total_value)}</div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-neutral-400">일간</span>
            <span className={`font-mono ${pctColor(portfolio.daily_return)}`}>
              {sign(portfolio.daily_return)}{portfolio.daily_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-400">누적</span>
            <span className={`font-mono ${pctColor(portfolio.cumulative_return)}`}>
              {sign(portfolio.cumulative_return)}{portfolio.cumulative_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-400">드로다운</span>
            <span className={`font-mono ${pctColor(portfolio.drawdown)}`}>
              {portfolio.drawdown.toFixed(2)}%
            </span>
          </div>
        </div>
      </Card>
    </Link>
  )
}
```

- [ ] **Step 9.3: `risk-status-widget.tsx` 전체 교체**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type RiskReport = {
  report?: {
    var_95?: number
    cvar_95?: number
    drawdown_status?: string
    alerts?: { level: string; message: string }[]
  }
}

export function RiskStatusWidget({ risk }: { risk: RiskReport | null }) {
  const alerts = risk?.report?.alerts ?? []
  return (
    <Link href="/risk" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Risk</div>
        {!risk ? (
          <p className="text-sm text-neutral-500">리스크 데이터 없음</p>
        ) : alerts.length === 0 ? (
          <>
            <div className="text-2xl font-bold text-emerald-400 mb-2">정상</div>
            <p className="text-xs text-neutral-500">경고 없음</p>
          </>
        ) : (
          <>
            <div className="text-2xl font-bold text-amber-400 mb-2">⚠ {alerts.length}건</div>
            <p className="text-xs text-neutral-300 line-clamp-2">{alerts[0].message}</p>
          </>
        )}
      </Card>
    </Link>
  )
}
```

- [ ] **Step 9.4: `data-health-widget.tsx` 생성**

```tsx
"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type DataStatus = {
  tables: { name: string; row_count: number; latest_date: string | null }[]
  gaps_count: number
}

export function DataHealthWidget({ status }: { status: DataStatus }) {
  const gaps = status.gaps_count
  const latest = status.tables[0]?.latest_date ?? null
  return (
    <Link href="/data" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Data Health</div>
        {gaps === 0 ? (
          <div className="text-2xl font-bold text-emerald-400 mb-2">✓ 정상</div>
        ) : (
          <div className="text-2xl font-bold text-rose-400 mb-2">갭 {gaps}건</div>
        )}
        <p className="text-xs text-neutral-500">
          {latest ? `최신 수집: ${latest}` : "수집 기록 없음"}
        </p>
      </Card>
    </Link>
  )
}
```

- [ ] **Step 9.5: 린트**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

- [ ] **Step 9.6: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/home/portfolio-widget.tsx webapp-ui/components/domain/home/risk-status-widget.tsx webapp-ui/components/domain/home/data-health-widget.tsx
git commit -m "feat(webapp-ui): Trading Row 위젯 — Portfolio/Risk 축소판 + DataHealth"
```

---

## Task 10: `page.tsx` 재작성 + 레거시 위젯 삭제

**목적:** 홈 페이지를 신규 레이아웃으로 교체. 사용하지 않는 위젯 파일 삭제. `HomeData` 타입을 새 응답 스키마에 맞춤.

**Files:**
- Rewrite: `webapp-ui/app/(dashboard)/page.tsx`
- Delete: `webapp-ui/components/domain/home/recent-backtests-widget.tsx`
- Delete: `webapp-ui/components/domain/home/recent-audit-widget.tsx`
- Delete: `webapp-ui/components/domain/home/data-status-widget.tsx`

- [ ] **Step 10.1: 삭제 대상이 홈 외 다른 곳에서 사용되지 않는지 확인**

Run:
```bash
cd /Users/gwangsoo/alpha-pulse
grep -rn "recent-backtests-widget\|recent-audit-widget\|data-status-widget" webapp-ui/ --include="*.tsx" --include="*.ts"
```
Expected: 오직 `webapp-ui/app/(dashboard)/page.tsx` 또는 위젯 자기 자신에서만 참조됨. 다른 페이지가 import 하면 중단 후 별도 처리.

- [ ] **Step 10.2: `page.tsx` 전체 교체**

파일 `webapp-ui/app/(dashboard)/page.tsx` 를 다음으로 교체:

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { BriefingHeroPlus, type BriefingHero } from "@/components/domain/home/briefing-hero-plus"
import { MissingBriefingBanner } from "@/components/domain/home/missing-briefing-banner"
import { PulseWidget, type PulseData } from "@/components/domain/home/pulse-widget"
import { FeedbackWidget, type FeedbackData } from "@/components/domain/home/feedback-widget"
import { ContentWidget, type ContentData } from "@/components/domain/home/content-widget"
import { PortfolioWidget } from "@/components/domain/home/portfolio-widget"
import { RiskStatusWidget } from "@/components/domain/home/risk-status-widget"
import { DataHealthWidget } from "@/components/domain/home/data-health-widget"

export const dynamic = "force-dynamic"

type PortfolioSnapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
  positions: { code: string; name: string; quantity: number; current_price: number }[]
}

type HomeData = {
  briefing: BriefingHero | null
  pulse: PulseData | null
  feedback: FeedbackData | null
  content: ContentData
  portfolio: PortfolioSnapshot | null
  portfolio_history: { date: string; total_value: number }[]
  risk: { report?: { alerts?: { level: string; message: string }[] } } | null
  data_status: {
    tables: { name: string; row_count: number; latest_date: string | null }[]
    gaps_count: number
  }
}

export default async function HomePage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<HomeData>("/api/v1/dashboard/home", {
    headers: h, cache: "no-store",
  })
  const showBanner = !data.briefing || !data.briefing.is_today
  return (
    <div className="space-y-4">
      {showBanner && (
        <MissingBriefingBanner latestDate={data.briefing?.date ?? null} />
      )}
      <BriefingHeroPlus hero={data.briefing} />
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        <PulseWidget data={data.pulse} />
        <FeedbackWidget data={data.feedback} />
        <ContentWidget data={data.content} />
        <PortfolioWidget portfolio={data.portfolio} history={data.portfolio_history} />
        <RiskStatusWidget risk={data.risk} />
        <DataHealthWidget status={data.data_status} />
      </div>
    </div>
  )
}
```

- [ ] **Step 10.3: 레거시 위젯 3개 삭제**

```bash
cd /Users/gwangsoo/alpha-pulse
rm webapp-ui/components/domain/home/recent-backtests-widget.tsx
rm webapp-ui/components/domain/home/recent-audit-widget.tsx
rm webapp-ui/components/domain/home/data-status-widget.tsx
```

- [ ] **Step 10.4: 타입 체크 + 린트 + 빌드**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm build
```
Expected: 빌드 성공. 모든 타입/린트 에러 없음.

- [ ] **Step 10.5: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/app/\(dashboard\)/page.tsx
git add -u webapp-ui/components/domain/home/
git commit -m "feat(webapp-ui): Home 페이지 Phase 3 통합 레이아웃 + 레거시 위젯 제거"
```

---

## Task 11: Playwright E2E 스모크

**목적:** 홈 페이지 로드, 6개 위젯 노출, 클릭 네비게이션을 자동 검증.

**Files:**
- Create: `webapp-ui/e2e/home.spec.ts`

- [ ] **Step 11.1: `home.spec.ts` 작성**

```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Home Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("홈 로드 → Hero + 6개 위젯 영역 존재", async ({ page }) => {
    await page.goto("/")
    // 각 위젯 라벨 (uppercase UPPERCASE 라벨)
    await expect(page.locator("text=/Market Pulse/i").first()).toBeVisible()
    await expect(page.locator("text=/Feedback/i").first()).toBeVisible()
    await expect(page.locator("text=/Content/i").first()).toBeVisible()
    await expect(page.locator("text=/Portfolio/i").first()).toBeVisible()
    await expect(page.locator("text=/Risk/i").first()).toBeVisible()
    await expect(page.locator("text=/Data Health/i").first()).toBeVisible()
  })

  test("Pulse 위젯 클릭 → /market/pulse 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/market/pulse']")
    await expect(page).toHaveURL(/\/market\/pulse/)
  })

  test("Feedback 위젯 클릭 → /feedback 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/feedback']")
    await expect(page).toHaveURL(/\/feedback$/)
  })

  test("Content 위젯 클릭 → /content/reports 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/content/reports']")
    await expect(page).toHaveURL(/\/content\/reports/)
  })
})
```

- [ ] **Step 11.2: 린트**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

- [ ] **Step 11.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/e2e/home.spec.ts
git commit -m "test(webapp-ui): Home E2E 스모크 — 6개 위젯 + 드릴다운"
```

---

## Task 12: 전체 검증 (CI Gate)

**목적:** 최종적으로 전체 pytest + ruff + pnpm build 가 통과하는지 확인.

- [ ] **Step 12.1: 전체 pytest**

Run: `pytest tests/ -x -q --tb=short`
Expected: all pass (pre-existing 1218 + 신규 webapp/api 테스트)

- [ ] **Step 12.2: ruff**

Run: `ruff check alphapulse/`
Expected: All checks passed!

- [ ] **Step 12.3: FE 빌드**

Run:
```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm build
```
Expected: 빌드 성공.

- [ ] **Step 12.4: (선택) 수동 스모크**

브라우저로 http://localhost:3000 접속 → 홈 레이아웃 확인. 개발 서버 없으면 이 단계 스킵.

- [ ] **Step 12.5: 커밋 없음 — 모든 검증 통과 후 다음 단계(머지) 로**

---

## Implementation Notes

1. **순서 준수**: Task 1→6 까지는 TDD 백엔드, Task 7→10 까지는 프런트 컴포넌트 후 페이지 통합, Task 11 은 E2E. Task 6 은 기존 `HomeResponse` 를 교체하므로 **반드시 Task 1~5 헬퍼가 모두 존재한 뒤** 실행한다.
2. **레거시 필드 제거 영향**: `recent_backtests`/`recent_audits` 필드는 `page.tsx` 외에는 소비자 없음 (Step 10.1 grep 으로 확인). 다른 페이지가 사용하면 중단 후 별도 대응.
3. **DataHealth vs DataStatus 이름**: 스펙의 명시적 컴포넌트 이름이 `DataHealthWidget` 이고, API 필드는 기존 `data_status` 로 유지. 파일은 새로 만들고 구 `data-status-widget.tsx` 삭제.
4. **signalStyle 재사용**: 기존 `webapp-ui/lib/market-labels.ts` 의 `signalStyle()` 을 그대로 사용. 새로 만들지 않음.
5. **Config.get_today_str()**: `alphapulse/core/config.py` 에 이미 존재 (static method). KST가 아닌 서버 로컬 시간 사용이지만 기존 서비스 전체가 그 가정 하에 돌아가므로 일치시킴.
6. **에러 격리 로깅**: 모든 try/except 블록이 `logger.warning` 으로 로깅한다. 운영 중 한 섹션이 계속 실패하면 로그로 감지 가능.
7. **프런트 단위 테스트 생략**: 프로젝트에 Vitest `.test.tsx` 가 전무. 신규 테스트 프레임워크 도입은 범위 밖. Playwright E2E + tsc + lint 로 검증.

## Spec Coverage 체크

- [x] §1 원칙 → Task 1~6 (백엔드), Task 7~10 (프런트)
- [x] §2 레이아웃 → Task 10 `page.tsx`
- [x] §3.1 BriefingHeroPlus → Task 7
- [x] §3.2 MissingBriefingBanner → Task 7
- [x] §3.3 PulseWidget → Task 8
- [x] §3.4 FeedbackWidget → Task 8
- [x] §3.5 ContentWidget → Task 8
- [x] §3.6 PortfolioWidget 축소 → Task 9
- [x] §3.7 RiskStatusWidget 축소 → Task 9
- [x] §3.8 DataHealthWidget → Task 9
- [x] §4.1 API 응답 모델 → Task 1 & 6
- [x] §4.2 섹션 격리 → Task 6
- [x] §4.3 헬퍼 책임 → Task 1~5
- [x] §4.4 프런트 구조 → Task 7~10
- [x] §5 에러 처리 매트릭스 → Task 6 테스트 + Task 7 배너
- [x] §6.1 백엔드 테스트 → Task 1~6 각 TDD 단계
- [x] §6.2 프런트 단위 테스트 → 스펙에는 있으나 프로젝트에 Vitest 없음 — E2E 로 대체(§Implementation Notes 7)
- [x] §6.3 E2E 스모크 → Task 11
- [x] §7 성공 기준 → Task 12
- [x] §8 마이그레이션 → Task 10 Step 10.1 grep 으로 소비자 확인 후 삭제
