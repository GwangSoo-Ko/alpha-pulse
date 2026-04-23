# Feedback 시각화 확장 — Design Spec

**작성일**: 2026-04-23
**대상 페이지**: `/feedback`
**목표**: 기존 Feedback 페이지에 4개 신규 시각화(Hit Rate 추이 / Score-Return 산점도 / 지표 히트맵 / 시그널 breakdown) 추가. 탭 기반 레이아웃으로 재구성.

---

## 1. 원칙

- **탭 분리**: `요약 · 추이 · 지표 · 이력` 4탭 — 관심사별 진입 경로 분리.
- **기존 컴포넌트 보존**: CorrelationCard / HitRateCards / IndicatorAccuracyChart / SignalHistoryTable 재사용, 적절한 탭에 재배치.
- **신규 API 1개**: `GET /api/v1/feedback/analytics?days=N` — 4개 데이터셋 번들. `/summary` 는 건드리지 않음.
- **SSR 3-way 병렬**: `summary + history + analytics` `Promise.all` 로 호출.
- **집계 기본값**: Hit rate trend = rolling 7-day average. Heatmap = 지표 점수 (-100~+100) 직접 표시.
- **차트 라이브러리**: `recharts` (기존 사용). 히트맵은 `recharts` 미지원 → Tailwind div grid.
- **빈 상태 처리**: `summary.hit_rates.total_evaluated === 0` 이면 전체 `<NoFeedback />`. 기간 내 특정 차트 데이터 부족 시 개별 empty state.

## 2. 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│ 피드백                                            [기간 ▾]    │
├─────────────────────────────────────────────────────────────┤
│ [요약] [추이] [지표] [이력]                                  │
├─────────────────────────────────────────────────────────────┤
│ 탭 1 — 요약                                                 │
│   HitRateCards (1d/3d/5d)                                   │
│   CorrelationCard                                           │
│   SignalBreakdownTable                                      │
│                                                             │
│ 탭 2 — 추이                                                 │
│   HitRateTrendChart (line, rolling 7-day)                   │
│   ScoreReturnScatter (scatter, color by signal)             │
│                                                             │
│ 탭 3 — 지표                                                 │
│   IndicatorAccuracyChart (기존 horizontal bar)              │
│   IndicatorHeatmap (11 × N grid)                            │
│                                                             │
│ 탭 4 — 이력                                                 │
│   SignalHistoryTable (paginated, 기존)                      │
└─────────────────────────────────────────────────────────────┘
```

**기본 탭**: `요약`.

**반응형**
- 탭 스트립: 항상 가로 (`TabsList`). 탭 수 적어 모바일도 한 줄 수용.
- 각 탭 내부는 단일 컬럼 스택 (모바일/데스크톱 공통). 폭이 넉넉하면 차트가 자연스럽게 늘어남.

## 3. 컴포넌트 상세

### 3.1 Backend — `GET /api/v1/feedback/analytics`

**파일**: `alphapulse/webapp/api/feedback.py` (기존 파일에 추가)

**신규 Pydantic 모델:**

```python
class HitRateTrendPoint(BaseModel):
    date: str                            # YYYYMMDD
    rolling_hit_rate_1d: float | None   # 0~1, window 내 평가 부족 시 None

class ScoreReturnPoint(BaseModel):
    date: str
    score: float
    return_1d: float                     # % 단위 (기존 store 와 일치)
    signal: str                          # DB 저장 형태 그대로 (한글 라벨 가능)

class IndicatorHeatmapCell(BaseModel):
    date: str                            # YYYYMMDD
    indicator: str                       # key (investor_flow, vkospi, ...)
    score: float                         # -100 ~ +100

class SignalBreakdownRow(BaseModel):
    signal: str                          # DB 저장 형태 그대로
    count: int
    hit_rate_1d: float | None            # 0~1, 평가 0건이면 None
    hit_rate_3d: float | None
    hit_rate_5d: float | None

class AnalyticsResponse(BaseModel):
    days: int
    hit_rate_trend: list[HitRateTrendPoint]
    score_return_points: list[ScoreReturnPoint]
    indicator_heatmap: list[IndicatorHeatmapCell]    # sparse: None score 생략
    signal_breakdown: list[SignalBreakdownRow]
```

**엔드포인트:**

```python
@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
):
    return AnalyticsResponse(
        days=days,
        hit_rate_trend=[HitRateTrendPoint(**p) for p in evaluator.get_hit_rate_trend(days=days)],
        score_return_points=[ScoreReturnPoint(**p) for p in evaluator.get_score_return_points(days=days)],
        indicator_heatmap=[IndicatorHeatmapCell(**c) for c in evaluator.get_indicator_heatmap(days=days)],
        signal_breakdown=[SignalBreakdownRow(**r) for r in evaluator.get_signal_breakdown(days=days)],
    )
```

### 3.2 Backend — `FeedbackEvaluator` 4개 메서드

**파일**: `alphapulse/feedback/evaluator.py` (기존 파일에 추가)

```python
def get_hit_rate_trend(self, days: int = 30, window: int = 7) -> list[dict]:
    """날짜 ASC. 각 시점 기준 최근 `window`일 hit_1d 이동평균.

    Returns: [{date, rolling_hit_rate_1d}]. window 내 evaluated 0건이면 None.
    """

def get_score_return_points(self, days: int = 30) -> list[dict]:
    """return_1d is not None 인 레코드만.

    Returns: [{date, score, return_1d, signal}].
    """

def get_indicator_heatmap(self, days: int = 30) -> list[dict]:
    """각 (date, indicator) 별 score. indicator_scores JSON 파싱.

    Returns: [{date, indicator, score}]. score is None 은 skip. 파싱 실패 시 해당 record 전체 skip.
    """

def get_signal_breakdown(self, days: int = 30) -> list[dict]:
    """signal 값 기준 group by.

    Returns: [{signal, count, hit_rate_1d, hit_rate_3d, hit_rate_5d}].
    hit_rate_*는 평가된 레코드만 평균; 0건이면 None.
    """
```

**입력 데이터**: `self.store.get_recent(limit=days)` (기존 rename 완료, Feedback store는 date PK라 `limit=N` ≈ 최근 N 거래일). 호출 형태는 기존 evaluator 메서드들과 일치.

### 3.3 Frontend — `HitRateTrendChart`

**파일**: `webapp-ui/components/domain/feedback/hit-rate-trend-chart.tsx`

- Props: `{ points: HitRateTrendPoint[] }`
- 전부 null 이거나 빈 배열: `<Card>` empty ("추이 데이터 없음")
- 아니면 recharts `ResponsiveContainer` + `LineChart` + `Line`:
  - X axis: date (MM-DD format)
  - Y axis: 0 ~ 100 (%)
  - stroke `#10b981` (emerald)
  - `connectNulls={false}` — null 구간은 gap
- 변환: `rolling_hit_rate_1d * 100` 으로 %

### 3.4 Frontend — `ScoreReturnScatter`

**파일**: `webapp-ui/components/domain/feedback/score-return-scatter.tsx`

- Props: `{ points: ScoreReturnPoint[] }`
- 빈 배열: empty card
- recharts `ScatterChart` + `Scatter`:
  - X axis: score (-100 ~ +100)
  - Y axis: return_1d (%)
  - 각 signal 값 별로 그룹핑해 `<Scatter>` 반복 — signal 별 색상 (signalStyle 기반)
  - `ReferenceLine y={0}` + `ReferenceLine x={0}`
  - `Tooltip` — date, score, return_1d, signal

### 3.5 Frontend — `IndicatorHeatmap`

**파일**: `webapp-ui/components/domain/feedback/indicator-heatmap.tsx`

- Props: `{ cells: IndicatorHeatmapCell[] }`
- 내부 변환: cells → `Map<indicator, Map<date, score>>`, 날짜는 정렬, 지표는 `INDICATOR_ORDER` 순서
- 빈 cells: empty card
- Grid DOM (커스텀, Tailwind):
  ```
  <div class="overflow-x-auto">
    <div class="inline-grid grid-rows-[auto_repeat(11,auto)]">
      <div class="date-header-row">  ... </div>
      { INDICATOR_ORDER.map((key) => (
          <div class="indicator-row">
            <div class="label-cell">{INDICATOR_LABELS[key]}</div>
            { dates.map((date) => (
              <div class={cellColor(scoreMap[key][date])} title={...}/>
            ))}
          </div>
        ))
      }
    </div>
  </div>
  ```
- 셀 색상: `cellColor(v)`:
  - null → `bg-neutral-900`
  - v==0 → `bg-neutral-800`
  - v>0 → `bg-emerald-{700|500|300}` (|v|≥66 | ≥33 | else)
  - v<0 → `bg-rose-{700|500|300}` (|v|≥66 | ≥33 | else)
- 셀 크기: 고정 `w-4 h-6`, gap `1px` (SVG 없이 div)
- 날짜 헤더: 7일 간격으로 라벨 표시, 나머지 빈 공간 (30일 구간엔 5개 라벨). 모든 셀에 `title` 로 `{date}: {indicator} = {score}` hover.

### 3.6 Frontend — `SignalBreakdownTable`

**파일**: `webapp-ui/components/domain/feedback/signal-breakdown-table.tsx`

- Props: `{ rows: SignalBreakdownRow[] }`
- 빈 배열: empty card
- Table:
  | Signal | Count | Hit 1d | Hit 3d | Hit 5d |
  - Signal 컬럼: `signalStyle(row.signal)` 기반 badge
  - Hit rate: null → "—", else `(rate * 100).toFixed(1) + '%'`
- 정렬 순서: `SIGNAL_ORDER` (strong_bullish → strong_bearish). DB 라벨이 섞여있을 수 있어 `normalizeSignalKey` 사용 후 정렬.
- `scope="col"` on headers

### 3.7 Frontend — 페이지 재구성

**파일**: `webapp-ui/app/(dashboard)/feedback/page.tsx` — 전면 재작성

```tsx
// 3개 API 병렬 호출 (기존 2개 + 신규 analytics)
const [summary, history, analytics] = await Promise.all([...])

// summary.hit_rates.total_evaluated === 0 → <NoFeedback />
// 아니면:
<Tabs defaultValue="summary">
  <TabsList>
    <TabsTrigger value="summary">요약</TabsTrigger>
    <TabsTrigger value="trend">추이</TabsTrigger>
    <TabsTrigger value="indicators">지표</TabsTrigger>
    <TabsTrigger value="history">이력</TabsTrigger>
  </TabsList>
  <TabsContent value="summary">
    <HitRateCards rates={summary.hit_rates} />
    <CorrelationCard correlation={summary.correlation} />
    <SignalBreakdownTable rows={analytics.signal_breakdown} />
  </TabsContent>
  <TabsContent value="trend">
    <HitRateTrendChart points={analytics.hit_rate_trend} />
    <ScoreReturnScatter points={analytics.score_return_points} />
  </TabsContent>
  <TabsContent value="indicators">
    <IndicatorAccuracyChart items={summary.indicator_accuracy} />
    <IndicatorHeatmap cells={analytics.indicator_heatmap} />
  </TabsContent>
  <TabsContent value="history">
    <SignalHistoryTable data={history} />
  </TabsContent>
</Tabs>
```

### 3.8 파일 목록

```
백엔드 수정:
  alphapulse/webapp/api/feedback.py         (+ 5 모델 + 1 엔드포인트)
  alphapulse/feedback/evaluator.py           (+ 4 메서드)

백엔드 테스트:
  tests/feedback/test_evaluator.py           (+ ~9 케이스)
  tests/webapp/api/test_feedback.py          (+ ~3 케이스)

프런트 신규:
  webapp-ui/components/domain/feedback/hit-rate-trend-chart.tsx
  webapp-ui/components/domain/feedback/score-return-scatter.tsx
  webapp-ui/components/domain/feedback/indicator-heatmap.tsx
  webapp-ui/components/domain/feedback/signal-breakdown-table.tsx

프런트 수정:
  webapp-ui/app/(dashboard)/feedback/page.tsx (Tabs 재구성)

E2E:
  webapp-ui/e2e/feedback.spec.ts             (탭 전환 검증 추가)
```

## 4. 데이터 흐름

### 4.1 SSR 호출

```tsx
const [summary, history, analytics] = await Promise.all([
  apiFetch<SummaryResponse>(
    `/api/v1/feedback/summary?days=${days}`,
    { headers, cache: "no-store" }),
  apiFetch<HistoryResponse>(
    `/api/v1/feedback/history?days=${days}&page=${page}&size=20`,
    { headers, cache: "no-store" }),
  apiFetch<AnalyticsResponse>(
    `/api/v1/feedback/analytics?days=${days}`,
    { headers, cache: "no-store" }),
])
```

### 4.2 `get_hit_rate_trend` 로직

1. `records = store.get_recent(limit=days)` — 날짜 DESC
2. ASC 로 정렬: `records_asc = records[::-1]`
3. 각 index i 에 대해 `window=7` 내 `hit_1d` 평균:
   ```python
   window_records = records_asc[max(0, i - window + 1): i + 1]
   evaluated = [r["hit_1d"] for r in window_records if r["hit_1d"] is not None]
   avg = sum(evaluated) / len(evaluated) if evaluated else None
   ```
4. Return `[{date: r["date"], rolling_hit_rate_1d: avg}]`

### 4.3 `get_indicator_heatmap` 로직

1. `records = store.get_recent(limit=days)`
2. 각 record 에서 `indicator_scores` JSON 파싱:
   ```python
   try:
       scores = json.loads(record["indicator_scores"]) if isinstance(record["indicator_scores"], str) else record["indicator_scores"]
   except (json.JSONDecodeError, TypeError):
       continue  # skip record
   ```
3. 각 (key, value) 에 대해 value is not None → `{date, indicator: key, score: float(value)}` append
4. Flat list 반환 (sparse)

### 4.4 `get_signal_breakdown` 로직

1. `records = store.get_recent(limit=days)`
2. Group by `record["signal"]`:
   ```python
   from collections import defaultdict
   groups = defaultdict(list)
   for r in records:
       groups[r["signal"]].append(r)
   ```
3. 각 그룹에서:
   ```python
   def rate(key):
       vals = [r[key] for r in group if r[key] is not None]
       return round(sum(vals) / len(vals), 4) if vals else None
   ```
4. `[{signal, count, hit_rate_1d, hit_rate_3d, hit_rate_5d}]` 반환

## 5. 에러 처리

| 상황 | 동작 |
|---|---|
| DB 전체 비어있음 (`total_evaluated === 0`) | `<NoFeedback />` 전체 대체, 탭 숨김 |
| `analytics.hit_rate_trend` 빈 배열 | HitRateTrendChart 가 "추이 데이터 없음" 카드 렌더 |
| `score_return_points` 빈 배열 | ScoreReturnScatter 가 "데이터 없음" 카드 |
| `indicator_heatmap` 빈 배열 | IndicatorHeatmap 이 "지표 데이터 없음" 카드 |
| `signal_breakdown` 빈 배열 | SignalBreakdownTable 이 "시그널 분포 없음" 카드 |
| `indicator_scores` 파싱 실패 | 해당 record 전체 heatmap 에서 skip (로그 warning) |
| 특정 window 에 evaluated 없음 | `rolling_hit_rate_1d: null`, LineChart gap |
| `return_1d is None` | scatter 점에서 제외 |
| Evaluator 예외 | 500 전파 (도메인 전체가 feedback, 홈처럼 부분 격리 불필요) |

## 6. 테스트

### 6.1 백엔드 Evaluator (`tests/feedback/test_evaluator.py` 확장)

- `test_get_hit_rate_trend_empty_returns_empty_list`
- `test_get_hit_rate_trend_computes_rolling_7d_average`
- `test_get_hit_rate_trend_returns_null_when_window_has_no_evaluated`
- `test_get_hit_rate_trend_dates_sorted_ascending`
- `test_get_score_return_points_filters_null_return_1d`
- `test_get_score_return_points_returns_four_fields`
- `test_get_indicator_heatmap_skips_none_scores`
- `test_get_indicator_heatmap_parses_json_string`
- `test_get_indicator_heatmap_parses_dict_directly`
- `test_get_signal_breakdown_groups_by_signal`
- `test_get_signal_breakdown_counts_correctly`
- `test_get_signal_breakdown_null_when_all_unevaluated`

### 6.2 백엔드 API (`tests/webapp/api/test_feedback.py` 확장)

- `test_analytics_returns_all_four_fields`
- `test_analytics_days_query_param_range` — 1 ≤ days ≤ 365 validation
- `test_analytics_requires_auth`

### 6.3 E2E (`webapp-ui/e2e/feedback.spec.ts` 확장)

- `탭 4개 렌더 확인`
- `요약 → 추이 탭 전환 → HitRateTrendChart 영역 노출`
- `지표 탭 전환 → IndicatorAccuracyChart + IndicatorHeatmap 영역 노출`
- `이력 탭 전환 → SignalHistoryTable 렌더`
- `빈 DB 시나리오: NoFeedback + 탭 숨김` (기존 테스트 유지)

## 7. 성공 기준

- pytest 1255 + 15 = 1270+ passed
- ruff clean
- pnpm lint / pnpm build 성공
- 4탭 모두 렌더, 각 차트 데이터 반영
- 데이터 없음 경로도 렌더 깨지지 않음

## 8. 범위 밖 (Out of Scope)

- Hit rate trend window 를 사용자 조절 (고정 7-day). 추후 요구 시 확장.
- 상관계수 시계열 (rolling correlation).
- 지표 간 correlation matrix.
- 시그널 정확도 예측 모델링.
- Heatmap zoom / pan / brush selection.
- CSV export (C-6 로 별도 작업).
