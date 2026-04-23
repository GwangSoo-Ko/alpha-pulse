# Feedback 시각화 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 Feedback 페이지에 4개 신규 시각화(Hit Rate 추이 / Score-Return 산점도 / 지표 히트맵 / 시그널 breakdown) 추가. 탭 기반(`요약 · 추이 · 지표 · 이력`) 레이아웃으로 재구성.

**Architecture:** 신규 `GET /api/v1/feedback/analytics` 엔드포인트 1개가 4개 데이터셋 번들 반환. `FeedbackEvaluator` 4개 메서드 추가. 페이지는 `/summary` + `/history` + `/analytics` 3-way 병렬 SSR. shadcn `Tabs` 컴포넌트 사용.

**Tech Stack:** FastAPI + Pydantic (BE), Next.js 15 + shadcn/ui + recharts (FE), Tailwind div grid (heatmap — recharts 미지원).

**Branch:** `feature/feedback-visualization` (spec 커밋 `a3ba1ea` 완료 상태)

**Spec:** `docs/superpowers/specs/2026-04-23-feedback-visualization-design.md`

---

## File Structure

### Backend
- **Modify:** `alphapulse/feedback/evaluator.py` — 4 신규 메서드: `get_hit_rate_trend`, `get_score_return_points`, `get_indicator_heatmap`, `get_signal_breakdown`
- **Modify:** `alphapulse/webapp/api/feedback.py` — 5 Pydantic 모델 + `AnalyticsResponse` + `/analytics` 엔드포인트
- **Modify:** `tests/feedback/test_evaluator.py` — 12 신규 케이스
- **Modify:** `tests/webapp/api/test_feedback.py` — 3 신규 케이스

### Frontend (신규)
- **Create:** `webapp-ui/components/domain/feedback/hit-rate-trend-chart.tsx` — LineChart (rolling 7d)
- **Create:** `webapp-ui/components/domain/feedback/score-return-scatter.tsx` — ScatterChart (color by signal)
- **Create:** `webapp-ui/components/domain/feedback/indicator-heatmap.tsx` — Tailwind div grid
- **Create:** `webapp-ui/components/domain/feedback/signal-breakdown-table.tsx` — 테이블

### Frontend (수정)
- **Modify:** `webapp-ui/app/(dashboard)/feedback/page.tsx` — Tabs 재구성 + analytics 호출

### E2E
- **Modify:** `webapp-ui/e2e/feedback.spec.ts` — 탭 전환 검증

---

## Conventions

- 백엔드는 TDD (test first → red → implement → green → commit)
- 프로젝트에 Vitest 미도입 → FE 컴포넌트는 `pnpm lint` + `pnpm tsc --noEmit` + E2E 로 검증
- 각 Task 완료마다 커밋
- ruff clean 필수
- Store call: `store.get_recent(limit=days)` (Phase 3 tech-debt 로 `days` → `limit` 로 rename 완료)

---

## Task 1: `FeedbackEvaluator.get_hit_rate_trend`

**Files:**
- Modify: `alphapulse/feedback/evaluator.py`
- Modify: `tests/feedback/test_evaluator.py`

- [ ] **Step 1.1: 테스트 추가**

`tests/feedback/test_evaluator.py` 끝에 추가:

```python
def test_get_hit_rate_trend_empty_returns_empty_list(evaluator):
    result = evaluator.get_hit_rate_trend(days=30)
    assert result == []


def test_get_hit_rate_trend_returns_dates_ascending(evaluator, store):
    _seed_data(store, 10)
    result = evaluator.get_hit_rate_trend(days=30)
    dates = [p["date"] for p in result]
    assert dates == sorted(dates)


def test_get_hit_rate_trend_computes_rolling_7d_average(evaluator, store):
    # 14일 데이터, 앞 7일 hit=1, 뒤 7일 hit=0
    for i in range(14):
        date = f"20260401" if i == 0 else f"202604{i+1:02d}"
        store.save_signal(date, 40.0, "매수 우위", {})
        hit = 1 if i < 7 else 0
        store.update_result(date, 2650 + i, 1.0, 870, 0.5, 1.0, hit)
    result = evaluator.get_hit_rate_trend(days=30, window=7)
    # 7번째 (index 6) 시점: 앞 7개(i=0..6) 모두 hit=1 → 1.0
    # 14번째 (index 13): 앞 7개(i=7..13) 모두 hit=0 → 0.0
    assert len(result) == 14
    assert result[6]["rolling_hit_rate_1d"] == 1.0
    assert result[13]["rolling_hit_rate_1d"] == 0.0


def test_get_hit_rate_trend_returns_null_when_window_has_no_evaluated(evaluator, store):
    # 평가되지 않은(return_1d=None) 레코드만 존재
    for i in range(5):
        store.save_signal(f"202604{i+1:02d}", 40.0, "매수 우위", {})
    result = evaluator.get_hit_rate_trend(days=30)
    assert len(result) == 5
    assert all(p["rolling_hit_rate_1d"] is None for p in result)
```

- [ ] **Step 1.2: Red 확인**

Run: `pytest tests/feedback/test_evaluator.py::test_get_hit_rate_trend_empty_returns_empty_list -v`
Expected: FAIL — `AttributeError: 'FeedbackEvaluator' object has no attribute 'get_hit_rate_trend'`

- [ ] **Step 1.3: 구현 추가**

`alphapulse/feedback/evaluator.py` 의 `get_correlation` 메서드 **아래** 에 다음을 추가:

```python
    def get_hit_rate_trend(self, days: int = 30, window: int = 7) -> list[dict]:
        """날짜 ASC. 각 시점 기준 최근 window 일 hit_1d 이동평균.

        Args:
            days: 조회 기간 (최대 레코드 수).
            window: rolling window 일수.

        Returns:
            [{date, rolling_hit_rate_1d}] — window 내 평가 0건이면 None.
        """
        records = self.store.get_recent(limit=days)
        # DESC → ASC
        records_asc = list(reversed(records))
        result: list[dict] = []
        for i in range(len(records_asc)):
            window_records = records_asc[max(0, i - window + 1): i + 1]
            evaluated = [r["hit_1d"] for r in window_records if r["hit_1d"] is not None]
            avg = round(sum(evaluated) / len(evaluated), 4) if evaluated else None
            result.append({
                "date": records_asc[i]["date"],
                "rolling_hit_rate_1d": avg,
            })
        return result
```

- [ ] **Step 1.4: Green 확인**

Run: `pytest tests/feedback/test_evaluator.py -k "hit_rate_trend" -v`
Expected: 4 passed

- [ ] **Step 1.5: 린트 + 커밋**

```bash
ruff check alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git add alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git commit -m "feat(feedback): FeedbackEvaluator.get_hit_rate_trend — rolling 7d"
```

---

## Task 2: `FeedbackEvaluator.get_score_return_points`

**Files:**
- Modify: `alphapulse/feedback/evaluator.py`
- Modify: `tests/feedback/test_evaluator.py`

- [ ] **Step 2.1: 테스트 추가**

`tests/feedback/test_evaluator.py` 끝에:

```python
def test_get_score_return_points_empty_returns_empty_list(evaluator):
    assert evaluator.get_score_return_points(days=30) == []


def test_get_score_return_points_filters_null_return_1d(evaluator, store):
    # 2건 평가, 1건 미평가
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    store.save_signal("20260402", -30.0, "매도 우위", {})
    store.update_result("20260402", 2640, -0.4, 870, 0.1, -0.8, 1)
    store.save_signal("20260403", 20.0, "매수 우위", {})  # not evaluated
    result = evaluator.get_score_return_points(days=30)
    assert len(result) == 2
    dates = {p["date"] for p in result}
    assert dates == {"20260401", "20260402"}


def test_get_score_return_points_returns_all_four_fields(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    result = evaluator.get_score_return_points(days=30)
    assert len(result) == 1
    p = result[0]
    assert p["date"] == "20260401"
    assert p["score"] == 40.0
    assert p["return_1d"] == 1.5
    assert p["signal"] == "매수 우위"
```

- [ ] **Step 2.2: Red**

Run: `pytest tests/feedback/test_evaluator.py -k "score_return" -v`
Expected: FAIL (method not exists)

- [ ] **Step 2.3: 구현**

`alphapulse/feedback/evaluator.py` 의 `get_hit_rate_trend` **아래** 에 추가:

```python
    def get_score_return_points(self, days: int = 30) -> list[dict]:
        """return_1d 평가된 레코드만 score-return 점으로 변환.

        Returns: [{date, score, return_1d, signal}]
        """
        records = self.store.get_recent(limit=days)
        return [
            {
                "date": r["date"],
                "score": float(r["score"]),
                "return_1d": float(r["return_1d"]),
                "signal": r["signal"],
            }
            for r in records
            if r["return_1d"] is not None
        ]
```

- [ ] **Step 2.4: Green**

Run: `pytest tests/feedback/test_evaluator.py -k "score_return" -v`
Expected: 3 passed

- [ ] **Step 2.5: 린트 + 커밋**

```bash
ruff check alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git add alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git commit -m "feat(feedback): get_score_return_points — 평가된 (score, return) 점"
```

---

## Task 3: `FeedbackEvaluator.get_indicator_heatmap`

**Files:**
- Modify: `alphapulse/feedback/evaluator.py`
- Modify: `tests/feedback/test_evaluator.py`

- [ ] **Step 3.1: 테스트 추가**

`tests/feedback/test_evaluator.py` 끝에:

```python
def test_get_indicator_heatmap_empty_returns_empty_list(evaluator):
    assert evaluator.get_indicator_heatmap(days=30) == []


def test_get_indicator_heatmap_skips_none_scores(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위",
                      {"investor_flow": 80, "vkospi": None, "fund_flow": -30})
    result = evaluator.get_indicator_heatmap(days=30)
    indicators = {c["indicator"] for c in result}
    assert indicators == {"investor_flow", "fund_flow"}


def test_get_indicator_heatmap_flat_cells(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {"investor_flow": 80})
    store.save_signal("20260402", -30.0, "매도 우위", {"investor_flow": -60, "vkospi": 50})
    result = evaluator.get_indicator_heatmap(days=30)
    assert len(result) == 3  # 1 + 2
    # 각 cell shape 확인
    for c in result:
        assert set(c.keys()) == {"date", "indicator", "score"}


def test_get_indicator_heatmap_score_is_float(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {"investor_flow": 80})
    result = evaluator.get_indicator_heatmap(days=30)
    assert isinstance(result[0]["score"], float)
    assert result[0]["score"] == 80.0
```

- [ ] **Step 3.2: Red**

Run: `pytest tests/feedback/test_evaluator.py -k "indicator_heatmap" -v`
Expected: FAIL

- [ ] **Step 3.3: 구현**

`alphapulse/feedback/evaluator.py` 의 `get_score_return_points` **아래** 에 추가:

```python
    def get_indicator_heatmap(self, days: int = 30) -> list[dict]:
        """각 (date, indicator) 별 score flat list. None 은 skip.

        indicator_scores 는 JSON 문자열 또는 이미 dict.
        파싱 실패 시 해당 record 전체 skip (로그 warning).

        Returns: [{date, indicator, score}]
        """
        records = self.store.get_recent(limit=days)
        cells: list[dict] = []
        for record in records:
            raw = record["indicator_scores"]
            try:
                scores = (
                    json.loads(raw) if isinstance(raw, str) else raw
                )
            except (json.JSONDecodeError, TypeError):
                logger.warning("indicator_heatmap: skip %s — JSON parse fail", record["date"])
                continue
            if not isinstance(scores, dict):
                continue
            for key, value in scores.items():
                if value is None:
                    continue
                try:
                    cells.append({
                        "date": record["date"],
                        "indicator": key,
                        "score": float(value),
                    })
                except (TypeError, ValueError):
                    continue
        return cells
```

- [ ] **Step 3.4: Green**

Run: `pytest tests/feedback/test_evaluator.py -k "indicator_heatmap" -v`
Expected: 4 passed

- [ ] **Step 3.5: 린트 + 커밋**

```bash
ruff check alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git add alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git commit -m "feat(feedback): get_indicator_heatmap — 지표×날짜 flat cells"
```

---

## Task 4: `FeedbackEvaluator.get_signal_breakdown`

**Files:**
- Modify: `alphapulse/feedback/evaluator.py`
- Modify: `tests/feedback/test_evaluator.py`

- [ ] **Step 4.1: 테스트 추가**

`tests/feedback/test_evaluator.py` 끝에:

```python
def test_get_signal_breakdown_empty_returns_empty_list(evaluator):
    assert evaluator.get_signal_breakdown(days=30) == []


def test_get_signal_breakdown_groups_by_signal(evaluator, store):
    # 3건 "매수 우위" (2건 hit=1, 1건 hit=0), 2건 "매도 우위" (둘 다 hit=1)
    for i, (sig, hit) in enumerate([
        ("매수 우위", 1), ("매수 우위", 1), ("매수 우위", 0),
        ("매도 우위", 1), ("매도 우위", 1),
    ]):
        date = f"202604{i+1:02d}"
        store.save_signal(date, 40.0 if "매수" in sig else -30.0, sig, {})
        store.update_result(date, 2650, 0.5, 870, 0.1, 0.3, hit)
    result = evaluator.get_signal_breakdown(days=30)
    by_signal = {r["signal"]: r for r in result}
    assert by_signal["매수 우위"]["count"] == 3
    assert by_signal["매수 우위"]["hit_rate_1d"] == pytest.approx(2 / 3, abs=0.01)
    assert by_signal["매도 우위"]["count"] == 2
    assert by_signal["매도 우위"]["hit_rate_1d"] == 1.0


def test_get_signal_breakdown_null_when_all_unevaluated(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.save_signal("20260402", 40.0, "매수 우위", {})
    result = evaluator.get_signal_breakdown(days=30)
    assert len(result) == 1
    assert result[0]["signal"] == "매수 우위"
    assert result[0]["count"] == 2
    assert result[0]["hit_rate_1d"] is None
    assert result[0]["hit_rate_3d"] is None
    assert result[0]["hit_rate_5d"] is None
```

- [ ] **Step 4.2: Red**

Run: `pytest tests/feedback/test_evaluator.py -k "signal_breakdown" -v`
Expected: FAIL

- [ ] **Step 4.3: 구현**

`alphapulse/feedback/evaluator.py` 상단에 `from collections import defaultdict` 추가(없으면). 그리고 `get_indicator_heatmap` **아래** 에 추가:

```python
    def get_signal_breakdown(self, days: int = 30) -> list[dict]:
        """signal 값 기준 group by. count + hit_rate (1d/3d/5d) 평균.

        Returns: [{signal, count, hit_rate_1d, hit_rate_3d, hit_rate_5d}]
        """
        from collections import defaultdict
        records = self.store.get_recent(limit=days)
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            groups[r["signal"]].append(r)

        def _rate(group: list[dict], key: str) -> float | None:
            vals = [r[key] for r in group if r[key] is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        return [
            {
                "signal": signal,
                "count": len(group),
                "hit_rate_1d": _rate(group, "hit_1d"),
                "hit_rate_3d": _rate(group, "hit_3d"),
                "hit_rate_5d": _rate(group, "hit_5d"),
            }
            for signal, group in groups.items()
        ]
```

- [ ] **Step 4.4: Green**

Run: `pytest tests/feedback/test_evaluator.py -k "signal_breakdown" -v`
Expected: 3 passed

- [ ] **Step 4.5: 린트 + 커밋**

```bash
ruff check alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git add alphapulse/feedback/evaluator.py tests/feedback/test_evaluator.py
git commit -m "feat(feedback): get_signal_breakdown — signal 별 count + hit_rate"
```

---

## Task 5: `/api/v1/feedback/analytics` 엔드포인트

**Files:**
- Modify: `alphapulse/webapp/api/feedback.py`
- Modify: `tests/webapp/api/test_feedback.py`

- [ ] **Step 5.1: 테스트 추가**

`tests/webapp/api/test_feedback.py` 끝에:

```python
def test_analytics_returns_all_four_fields(client, feedback_store):
    # 간단 시드: 평가된 1건
    feedback_store.save_signal("20260401", 40.0, "매수 우위", {"investor_flow": 80})
    feedback_store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    r = client.get("/api/v1/feedback/analytics?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30
    assert "hit_rate_trend" in body
    assert "score_return_points" in body
    assert "indicator_heatmap" in body
    assert "signal_breakdown" in body


def test_analytics_days_param_validated(client):
    r = client.get("/api/v1/feedback/analytics?days=0")
    assert r.status_code == 422
    r = client.get("/api/v1/feedback/analytics?days=400")
    assert r.status_code == 422


def test_analytics_requires_auth(app):
    from fastapi.testclient import TestClient
    unauthed = TestClient(app, base_url="https://testserver")
    r = unauthed.get("/api/v1/feedback/analytics?days=30")
    assert r.status_code == 401
```

- [ ] **Step 5.2: Red**

Run: `pytest tests/webapp/api/test_feedback.py -k "analytics" -v`
Expected: FAIL — 404 on endpoint not exists

- [ ] **Step 5.3: 구현**

`alphapulse/webapp/api/feedback.py` 의 `FeedbackDetail` 모델 **아래**, `get_feedback_store` **위** 에 다음 Pydantic 모델들 추가:

```python
class HitRateTrendPoint(BaseModel):
    date: str
    rolling_hit_rate_1d: float | None


class ScoreReturnPoint(BaseModel):
    date: str
    score: float
    return_1d: float
    signal: str


class IndicatorHeatmapCell(BaseModel):
    date: str
    indicator: str
    score: float


class SignalBreakdownRow(BaseModel):
    signal: str
    count: int
    hit_rate_1d: float | None
    hit_rate_3d: float | None
    hit_rate_5d: float | None


class AnalyticsResponse(BaseModel):
    days: int
    hit_rate_trend: list[HitRateTrendPoint]
    score_return_points: list[ScoreReturnPoint]
    indicator_heatmap: list[IndicatorHeatmapCell]
    signal_breakdown: list[SignalBreakdownRow]
```

그리고 기존 `@router.get("/{date}", ...)` **위** (즉 `/history` 엔드포인트 아래) 에 다음 엔드포인트 추가:

```python
@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
):
    """4개 시각화 데이터셋 번들."""
    return AnalyticsResponse(
        days=days,
        hit_rate_trend=[HitRateTrendPoint(**p) for p in evaluator.get_hit_rate_trend(days=days)],
        score_return_points=[ScoreReturnPoint(**p) for p in evaluator.get_score_return_points(days=days)],
        indicator_heatmap=[IndicatorHeatmapCell(**c) for c in evaluator.get_indicator_heatmap(days=days)],
        signal_breakdown=[SignalBreakdownRow(**r) for r in evaluator.get_signal_breakdown(days=days)],
    )
```

**주의**: 신규 라우트 `/analytics` 는 `/{date}` 매치 이전에 정의되어야 함 (FastAPI 는 선언 순서대로 매칭). `/{date}` 가 상위면 `analytics` 도 date 로 잡힐 수 있음 — 순서 확인 필수.

- [ ] **Step 5.4: Green + 전체 테스트**

```bash
pytest tests/webapp/api/test_feedback.py -k "analytics" -v
pytest tests/webapp/api/test_feedback.py -v
pytest tests/feedback/ tests/webapp/api/test_feedback.py -q --tb=short
```
Expected: 모두 통과.

- [ ] **Step 5.5: 린트 + 커밋**

```bash
ruff check alphapulse/webapp/api/feedback.py tests/webapp/api/test_feedback.py
git add alphapulse/webapp/api/feedback.py tests/webapp/api/test_feedback.py
git commit -m "feat(webapp): /api/v1/feedback/analytics 엔드포인트 — 4 번들"
```

---

## Task 6: FE — `HitRateTrendChart`

**Files:**
- Create: `webapp-ui/components/domain/feedback/hit-rate-trend-chart.tsx`

- [ ] **Step 6.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"

export type HitRateTrendPoint = {
  date: string
  rolling_hit_rate_1d: number | null
}

function formatDateShort(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function HitRateTrendChart({ points }: { points: HitRateTrendPoint[] }) {
  if (points.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">적중률 추이 (7일 이동평균)</h3>
        <p className="text-sm text-neutral-500">추이 데이터 없음</p>
      </Card>
    )
  }

  const data = points.map((p) => ({
    date: formatDateShort(p.date),
    hit_rate: p.rolling_hit_rate_1d !== null ? p.rolling_hit_rate_1d * 100 : null,
  }))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">적중률 추이 (7일 이동평균)</h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis dataKey="date" stroke="#9ca3af" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 100]}
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{ background: "#0f0f12", border: "1px solid #2a2a2f" }}
            formatter={(v: number) => [`${v.toFixed(1)}%`, "적중률"]}
          />
          <Line
            type="monotone"
            dataKey="hit_rate"
            stroke="#10b981"
            strokeWidth={2}
            connectNulls={false}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}
```

- [ ] **Step 6.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep hit-rate-trend-chart || echo "no type errors"
```

- [ ] **Step 6.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/feedback/hit-rate-trend-chart.tsx
git commit -m "feat(webapp-ui): HitRateTrendChart — rolling 7d line"
```

---

## Task 7: FE — `ScoreReturnScatter`

**Files:**
- Create: `webapp-ui/components/domain/feedback/score-return-scatter.tsx`

- [ ] **Step 7.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"
import {
  CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts"
import { normalizeSignalKey, SIGNAL_STYLE } from "@/lib/market-labels"

export type ScoreReturnPoint = {
  date: string
  score: number
  return_1d: number
  signal: string
}

// Tailwind bg-* class → 실제 hex (dot fill 에 쓰기 위해)
const SIGNAL_HEX: Record<string, string> = {
  strong_bullish: "#22c55e",
  moderately_bullish: "#10b981",
  neutral: "#eab308",
  moderately_bearish: "#f97316",
  strong_bearish: "#ef4444",
}

export function ScoreReturnScatter({ points }: { points: ScoreReturnPoint[] }) {
  if (points.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">Score vs Return (1d)</h3>
        <p className="text-sm text-neutral-500">평가된 데이터 없음</p>
      </Card>
    )
  }

  // signal 별 그룹핑 (정규화된 key 기준)
  const groups: Record<string, ScoreReturnPoint[]> = {}
  for (const p of points) {
    const key = normalizeSignalKey(p.signal)
    if (!groups[key]) groups[key] = []
    groups[key].push(p)
  }

  const orderedKeys = ["strong_bullish", "moderately_bullish", "neutral", "moderately_bearish", "strong_bearish"]

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Score vs Return (1d)</h3>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis
            dataKey="score"
            type="number"
            domain={[-100, 100]}
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            name="Score"
          />
          <YAxis
            dataKey="return_1d"
            type="number"
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            name="Return 1d"
          />
          <ReferenceLine x={0} stroke="#404040" />
          <ReferenceLine y={0} stroke="#404040" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{ background: "#0f0f12", border: "1px solid #2a2a2f" }}
            formatter={(v: number, name: string) => {
              if (name === "Return 1d") return [`${v.toFixed(2)}%`, name]
              if (name === "Score") return [v.toFixed(1), name]
              return [v, name]
            }}
            labelFormatter={() => ""}
          />
          {orderedKeys.map((key) =>
            groups[key] ? (
              <Scatter
                key={key}
                name={SIGNAL_STYLE[key as keyof typeof SIGNAL_STYLE].label}
                data={groups[key].map((p) => ({ date: p.date, score: p.score, return_1d: p.return_1d }))}
                fill={SIGNAL_HEX[key]}
              />
            ) : null,
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </Card>
  )
}
```

- [ ] **Step 7.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep score-return-scatter || echo "no type errors"
```

- [ ] **Step 7.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/feedback/score-return-scatter.tsx
git commit -m "feat(webapp-ui): ScoreReturnScatter — signal 색상 산점도"
```

---

## Task 8: FE — `IndicatorHeatmap`

**Files:**
- Create: `webapp-ui/components/domain/feedback/indicator-heatmap.tsx`

- [ ] **Step 8.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS, INDICATOR_ORDER } from "@/lib/market-labels"

export type IndicatorHeatmapCell = {
  date: string
  indicator: string
  score: number
}

function formatDateShort(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function cellColor(score: number | null): string {
  if (score === null) return "bg-neutral-900"
  const abs = Math.abs(score)
  if (score === 0) return "bg-neutral-800"
  if (score > 0) {
    if (abs >= 66) return "bg-emerald-700"
    if (abs >= 33) return "bg-emerald-500"
    return "bg-emerald-300/60"
  }
  if (abs >= 66) return "bg-rose-700"
  if (abs >= 33) return "bg-rose-500"
  return "bg-rose-300/60"
}

export function IndicatorHeatmap({ cells }: { cells: IndicatorHeatmapCell[] }) {
  if (cells.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">지표 히트맵</h3>
        <p className="text-sm text-neutral-500">지표 데이터 없음</p>
      </Card>
    )
  }

  // cells → scoreMap[indicator][date] = score, dates 정렬
  const scoreMap: Record<string, Record<string, number>> = {}
  const dateSet = new Set<string>()
  for (const c of cells) {
    if (!scoreMap[c.indicator]) scoreMap[c.indicator] = {}
    scoreMap[c.indicator][c.date] = c.score
    dateSet.add(c.date)
  }
  const dates = Array.from(dateSet).sort()

  // 7일 간격 label
  const labelStep = Math.max(1, Math.ceil(dates.length / 10))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">지표 히트맵</h3>
      <div className="overflow-x-auto">
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th scope="col" className="pr-3 text-left text-neutral-400 font-normal sticky left-0 bg-[var(--card)] z-10"></th>
              {dates.map((d, i) => (
                <th
                  key={d}
                  scope="col"
                  className="text-[10px] text-neutral-500 font-normal px-0.5"
                  style={{ minWidth: 16 }}
                >
                  {i % labelStep === 0 ? formatDateShort(d) : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {INDICATOR_ORDER.map((key) => (
              <tr key={key}>
                <th scope="row" className="pr-3 text-left text-neutral-300 font-normal whitespace-nowrap sticky left-0 bg-[var(--card)] z-10">
                  {INDICATOR_LABELS[key] ?? key}
                </th>
                {dates.map((d) => {
                  const score = scoreMap[key]?.[d] ?? null
                  return (
                    <td
                      key={d}
                      className={`${cellColor(score)} w-4 h-6 p-0`}
                      title={`${d}: ${INDICATOR_LABELS[key] ?? key} = ${score !== null ? score.toFixed(1) : "—"}`}
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
```

- [ ] **Step 8.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep indicator-heatmap || echo "no type errors"
```

- [ ] **Step 8.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/feedback/indicator-heatmap.tsx
git commit -m "feat(webapp-ui): IndicatorHeatmap — 11×N Tailwind grid"
```

---

## Task 9: FE — `SignalBreakdownTable`

**Files:**
- Create: `webapp-ui/components/domain/feedback/signal-breakdown-table.tsx`

- [ ] **Step 9.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"
import { normalizeSignalKey, signalStyle } from "@/lib/market-labels"

export type SignalBreakdownRow = {
  signal: string
  count: number
  hit_rate_1d: number | null
  hit_rate_3d: number | null
  hit_rate_5d: number | null
}

const SIGNAL_ORDER: Record<string, number> = {
  strong_bullish: 0,
  moderately_bullish: 1,
  neutral: 2,
  moderately_bearish: 3,
  strong_bearish: 4,
}

function formatRate(v: number | null): string {
  if (v === null) return "—"
  return `${(v * 100).toFixed(1)}%`
}

export function SignalBreakdownTable({ rows }: { rows: SignalBreakdownRow[] }) {
  if (rows.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">시그널 분포</h3>
        <p className="text-sm text-neutral-500">시그널 분포 없음</p>
      </Card>
    )
  }

  // 정규화된 key 기준으로 정렬
  const sorted = [...rows].sort(
    (a, b) => (SIGNAL_ORDER[normalizeSignalKey(a.signal)] ?? 99) - (SIGNAL_ORDER[normalizeSignalKey(b.signal)] ?? 99),
  )

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">시그널 분포</h3>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th scope="col" className="px-3 py-2">시그널</th>
            <th scope="col" className="px-3 py-2 text-right">건수</th>
            <th scope="col" className="px-3 py-2 text-right">적중 1d</th>
            <th scope="col" className="px-3 py-2 text-right">적중 3d</th>
            <th scope="col" className="px-3 py-2 text-right">적중 5d</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const style = signalStyle(r.signal)
            return (
              <tr key={r.signal} className="border-t border-neutral-800">
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{r.count}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_1d)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_3d)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_5d)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}
```

- [ ] **Step 9.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep signal-breakdown || echo "no type errors"
```

- [ ] **Step 9.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/feedback/signal-breakdown-table.tsx
git commit -m "feat(webapp-ui): SignalBreakdownTable — signal 별 count + hit_rate"
```

---

## Task 10: 페이지 재구성 (Tabs + Analytics 호출)

**Files:**
- Modify: `webapp-ui/app/(dashboard)/feedback/page.tsx`

- [ ] **Step 10.1: 페이지 전체 교체**

파일 `webapp-ui/app/(dashboard)/feedback/page.tsx` 를 다음으로 교체:

```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import {
  HitRateTrendChart,
  type HitRateTrendPoint,
} from "@/components/domain/feedback/hit-rate-trend-chart"
import {
  ScoreReturnScatter,
  type ScoreReturnPoint,
} from "@/components/domain/feedback/score-return-scatter"
import {
  IndicatorHeatmap,
  type IndicatorHeatmapCell,
} from "@/components/domain/feedback/indicator-heatmap"
import {
  SignalBreakdownTable,
  type SignalBreakdownRow,
} from "@/components/domain/feedback/signal-breakdown-table"

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

type AnalyticsResponse = {
  days: number
  hit_rate_trend: HitRateTrendPoint[]
  score_return_points: ScoreReturnPoint[]
  indicator_heatmap: IndicatorHeatmapCell[]
  signal_breakdown: SignalBreakdownRow[]
}

export default async function FeedbackPage({ searchParams }: Props) {
  const sp = await searchParams
  const days = Math.min(365, Math.max(1, Number(sp.days || 30)))
  const page = Math.max(1, Number(sp.page || 1))

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const [summary, history, analytics] = await Promise.all([
    apiFetch<SummaryResponse>(
      `/api/v1/feedback/summary?days=${days}`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<HistoryResponse>(
      `/api/v1/feedback/history?days=${days}&page=${page}&size=20`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<AnalyticsResponse>(
      `/api/v1/feedback/analytics?days=${days}`,
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
        <Tabs defaultValue="summary" className="space-y-4">
          <TabsList>
            <TabsTrigger value="summary">요약</TabsTrigger>
            <TabsTrigger value="trend">추이</TabsTrigger>
            <TabsTrigger value="indicators">지표</TabsTrigger>
            <TabsTrigger value="history">이력</TabsTrigger>
          </TabsList>

          <TabsContent value="summary" className="space-y-4">
            <HitRateCards rates={summary.hit_rates} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <CorrelationCard correlation={summary.correlation} />
            </div>
            <SignalBreakdownTable rows={analytics.signal_breakdown} />
          </TabsContent>

          <TabsContent value="trend" className="space-y-4">
            <HitRateTrendChart points={analytics.hit_rate_trend} />
            <ScoreReturnScatter points={analytics.score_return_points} />
          </TabsContent>

          <TabsContent value="indicators" className="space-y-4">
            <IndicatorAccuracyChart items={summary.indicator_accuracy} />
            <IndicatorHeatmap cells={analytics.indicator_heatmap} />
          </TabsContent>

          <TabsContent value="history" className="space-y-4">
            <SignalHistoryTable data={history} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
```

- [ ] **Step 10.2: 린트 + tsc + 빌드**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep "feedback/page" || echo "no type errors in feedback page"
pnpm build 2>&1 | tail -10
```
Expected: 빌드 성공, `/feedback` 라우트 정상.

- [ ] **Step 10.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add "webapp-ui/app/(dashboard)/feedback/page.tsx"
git commit -m "feat(webapp-ui): Feedback 페이지 Tabs 재구성 + 시각화 4개 통합"
```

---

## Task 11: Playwright E2E 탭 전환 검증

**Files:**
- Modify: `webapp-ui/e2e/feedback.spec.ts`

- [ ] **Step 11.1: 기존 파일 읽어서 수정**

먼저 기존 파일 확인:

```bash
cat webapp-ui/e2e/feedback.spec.ts | head -30
```

기존 `test.describe("Feedback", ...)` 블록 안에 새 탭 전환 테스트들을 **추가** 한다. 기존 테스트는 유지. 추가할 테스트:

```typescript
  test("탭 4개 렌더 + 기본 요약 탭", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("피드백 기록이 없습니다")
    const visible = await empty.isVisible().catch(() => false)
    test.skip(visible, "DB 비어있음 — 탭 스모크 스킵")
    await expect(page.getByRole("tab", { name: "요약" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "추이" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "지표" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "이력" })).toBeVisible()
  })

  test("추이 탭 클릭 → HitRateTrendChart 영역", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("피드백 기록이 없습니다")
    const visible = await empty.isVisible().catch(() => false)
    test.skip(visible, "DB 비어있음")
    await page.getByRole("tab", { name: "추이" }).click()
    await expect(page.getByText(/적중률 추이/)).toBeVisible()
  })

  test("지표 탭 클릭 → 히트맵 영역", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("피드백 기록이 없습니다")
    const visible = await empty.isVisible().catch(() => false)
    test.skip(visible, "DB 비어있음")
    await page.getByRole("tab", { name: "지표" }).click()
    await expect(page.getByText(/지표 히트맵/)).toBeVisible()
  })

  test("이력 탭 클릭 → 시그널 히스토리 테이블", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("피드백 기록이 없습니다")
    const visible = await empty.isVisible().catch(() => false)
    test.skip(visible, "DB 비어있음")
    await page.getByRole("tab", { name: "이력" }).click()
    await expect(page.getByRole("table")).toBeVisible()
  })
```

**주의**: 추가 위치는 기존 describe 블록 안. `test.skip` 은 DB 비어있을 때 `<NoFeedback/>` 로 탭 숨겨지는 경우 피함. 실제 `NoFeedback` 의 문구는 `webapp-ui/components/domain/feedback/no-feedback.tsx` 에서 확인 (만약 "피드백 기록이 없습니다" 가 아닌 다른 문구면 그에 맞춰 수정). 먼저 확인:

```bash
cat webapp-ui/components/domain/feedback/no-feedback.tsx
```

해당 파일의 실제 표시 문구를 사용하여 `empty` 로케이터를 맞춘다.

- [ ] **Step 11.2: 린트**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

- [ ] **Step 11.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/e2e/feedback.spec.ts
git commit -m "test(webapp-ui): Feedback 탭 전환 E2E 추가"
```

---

## Task 12: 전체 CI Gate 검증

**목적**: 모든 변경 종합 확인.

- [ ] **Step 12.1: pytest 전체**

```bash
cd /Users/gwangsoo/alpha-pulse
pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
Expected: 1255 + (4 + 3 + 4 + 3 + 3) = 1272+ passed.

- [ ] **Step 12.2: ruff**

```bash
ruff check alphapulse/
```
Expected: All checks passed!

- [ ] **Step 12.3: FE 빌드**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm build 2>&1 | tail -10
```
Expected: 빌드 성공.

- [ ] **Step 12.4: 커밋 없음** — 검증 통과 시 병합 단계.

---

## Spec Coverage 체크

- [x] §3.1 Backend /analytics 엔드포인트 + 5 Pydantic 모델 → Task 5
- [x] §3.2 FeedbackEvaluator 4 메서드 → Task 1-4
- [x] §3.3 HitRateTrendChart → Task 6
- [x] §3.4 ScoreReturnScatter → Task 7
- [x] §3.5 IndicatorHeatmap → Task 8
- [x] §3.6 SignalBreakdownTable → Task 9
- [x] §3.7 페이지 Tabs 재구성 → Task 10
- [x] §4 데이터 흐름 (3-way Promise.all) → Task 10
- [x] §5 에러 처리 (empty states, JSON fail skip) → Task 1-4 내부 + 각 컴포넌트
- [x] §6.1 Evaluator 단위 테스트 → Task 1-4
- [x] §6.2 API 통합 테스트 → Task 5
- [x] §6.3 E2E 탭 전환 → Task 11
- [x] §7 성공 기준 → Task 12

## Implementation Notes

1. **Task 순서 준수**: Task 1-4 (evaluator 메서드) → Task 5 (API 엔드포인트가 evaluator 메서드 모두 필요) → Task 6-9 (FE 컴포넌트 독립) → Task 10 (페이지가 모든 FE + /analytics 필요) → Task 11 (E2E) → Task 12 (검증).
2. **FastAPI 라우트 순서**: `/analytics` 는 `/{date}` 보다 위에 등록되어야 함 — path param 이 "analytics" 를 date 로 오해하는 매칭 회피. Task 5 Step 5.3 에서 명시.
3. **`normalizeSignalKey` 활용**: 백엔드가 DB 의 `signal` 을 라벨 그대로 내림. 프런트 `ScoreReturnScatter`/`SignalBreakdownTable` 모두 정규화 후 매칭.
4. **Heatmap 스크롤**: 기간 길면 가로 넘침 → `overflow-x-auto` + sticky indicator label 왼쪽 고정. table 구조 (≥ 90일도 읽을 수 있음).
5. **차트 색상**: Dark theme 일관 — axis/grid 는 neutral-400/neutral-800, 데이터는 emerald (positive) / rose (negative).
6. **`SIGNAL_HEX` 매핑**: recharts Scatter 는 Tailwind class 를 직접 못 먹어서 hex 로 매핑. `SIGNAL_STYLE` 의 색상과 시각적으로 유사한 Tailwind palette 기본값 사용.
7. **Empty state 응답 통일**: 각 차트/테이블이 "데이터 없음" 카드 독자 렌더. 페이지 전체 empty 는 `NoFeedback` 하나로 단순화.
8. **`test.skip`**: E2E 테스트는 DB 내용에 의존 — `<NoFeedback/>` 렌더 상황에선 skip 으로 우회.
