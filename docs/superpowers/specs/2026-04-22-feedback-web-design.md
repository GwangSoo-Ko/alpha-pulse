# Feedback 웹 대시보드 — 설계 문서

**작성일:** 2026-04-22
**스코프:** AlphaPulse 웹 UI 에 `feedback` 도메인 추가 (Phase 3 네 번째이자 마지막 도메인)

---

## 1. 목적 & 배경

`alphapulse/feedback/` 모듈은 일일 브리핑 발행 이후 **시장 결과 + 적중 판정 + 사후분석**을 `feedback.db` 에 축적한다. 현재 이 데이터는 CLI (`ap feedback report/indicators/history`) 로만 접근 가능해, 적중률 추이·지표별 성과·개별 시그널 상세를 웹에서 한눈에 볼 수 없다.

본 spec 은 웹 UI 에 **Feedback 도메인** 을 추가하여:
- 적중률 요약 대시보드 (1일/3일/5일) + score ↔ return_1d 상관계수
- 11개 지표별 정확도 시각화 (가로 bar chart)
- 시그널 vs 결과 이력 테이블
- 특정 날짜 상세 (시그널 / 수익률 / 사후분석 / Briefing 링크)

**조회 전용** — 실행(evaluate/analyze) 은 Briefing 파이프라인이 이미 자동 수행.

---

## 2. 스코프

### 포함 (이번 사이클)
- `/feedback` — 대시보드 (적중률 카드 3 + 상관 카드 1 + 지표 차트 + 이력 테이블, 기간 토글 30/60/90일)
- `/feedback/[date]` — 날짜별 상세 (고유 필드 + Briefing 링크)
- FastAPI 라우터 `alphapulse/webapp/api/feedback.py` (3 엔드포인트)
- `Config.FEEDBACK_DB` 상수 추가 (현재 `DATA_DIR / "feedback.db"` 인라인 호출만 있음)
- 사이드바 "피드백" 진입점
- E2E 스모크 테스트

### 제외 (YAGNI / 후속 사이클)
- Job 실행 (`evaluate`, `analyze` 수동 트리거) — Briefing 자동
- CSV/Excel export
- 지표별 Drill-down 페이지
- 차트 종류 확장 (scatter, 시계열 추이)
- 커스텀 date range 필터
- 누락 피드백 경고 배너
- Feedback 삭제/편집
- 알림 (적중률 급락 알림)
- 홈 대시보드 Feedback 위젯

---

## 3. 아키텍처

### 레이어 구조
```
┌──────────────────────────────────────────┐
│ Frontend (Next.js 15)                    │
│  webapp-ui/app/(dashboard)/feedback/     │
│  webapp-ui/components/domain/feedback/   │
└───────────────┬──────────────────────────┘
                │ SSR fetch (cookie forward)
                ▼
┌──────────────────────────────────────────┐
│ FastAPI router                           │
│  alphapulse/webapp/api/feedback.py       │
└───────┬───────────┬──────────────────────┘
        │ stats     │ rows
        ▼           ▼
┌─────────────┐ ┌──────────────┐
│ Feedback    │ │ Feedback     │
│ Evaluator   │ │ Store        │
│ (read-only) │ │ (read-only)  │
└─────────────┘ └──────────────┘
                        │
                        ▼
                ┌──────────────────┐
                │ feedback.db      │
                │ (signal_feedback)│
                └──────────────────┘
```

### Sync/Async 경계
- `alphapulse/feedback/` 는 sync (sqlite3, pandas, pure compute)
- FastAPI 라우터는 `async def` (기존 Phase 2/3 패턴), sync 호출 직접 수행 (응답 <20ms)
- `asyncio.to_thread` 불필요

### 데이터 흐름

**대시보드 (주 경로)**
```
사용자 → /feedback?days=30
 → SSR: GET /api/v1/feedback/summary?days=30
   └─ FeedbackEvaluator.get_hit_rates(30)
   └─ FeedbackEvaluator.get_correlation(30)
   └─ FeedbackEvaluator.get_indicator_accuracy(30)
   └─ FeedbackStore.get_recent(10)       # 최근 10건 미리보기
 → 응답 조합 → 렌더
```

**이력 테이블 페이지 이동**
```
사용자 → "다음 페이지" 클릭
 → GET /api/v1/feedback/history?days=30&page=2&size=20
 → FeedbackStore.get_recent(days) → 메모리 슬라이스
```

**날짜 상세**
```
사용자 → /feedback/20260421
 → GET /api/v1/feedback/20260421
 → FeedbackStore.get("20260421") → 단일 row 전체 필드
```

---

## 4. API 설계

베이스: `/api/v1/feedback`
인증: 모든 엔드포인트 `get_current_user` 필수
감사 로그: 없음 (조회 전용)

### 4.1 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/feedback/summary?days=30` | 대시보드 통합 (적중률 + 상관 + 지표별 + 최근 10건) |
| GET | `/feedback/history?days=30&page=1&size=20` | 이력 페이지네이션 |
| GET | `/feedback/{date}` | 특정 날짜 상세 |

### 4.2 응답 스키마

```python
class HitRates(BaseModel):
    total_evaluated: int
    hit_rate_1d: float | None        # 0-1
    hit_rate_3d: float | None
    hit_rate_5d: float | None
    count_1d: int
    count_3d: int
    count_5d: int


class IndicatorAccuracy(BaseModel):
    key: str                          # "investor_flow" 등
    accuracy: float                   # 0-1
    count: int                        # 평가 건수


class SignalHistoryItem(BaseModel):
    date: str                         # YYYYMMDD
    score: float
    signal: str
    kospi_change_pct: float | None
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    hit_1d: bool | None               # 0/1 → bool; None 은 미평가
    hit_3d: bool | None
    hit_5d: bool | None


class FeedbackSummaryResponse(BaseModel):
    days: int
    hit_rates: HitRates
    correlation: float | None         # -1 ~ +1
    indicator_accuracy: list[IndicatorAccuracy]  # accuracy 내림차순
    recent_history: list[SignalHistoryItem]      # 최근 10건


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
```

### 4.3 경로 파라미터 검증

```python
@router.get("/feedback/{date}", ...)
async def get_feedback(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    ...
): ...
```

### 4.4 에러 처리

| 상황 | 응답 |
|---|---|
| 인증 실패 | 401 |
| `GET /{date}` 저장 없음 | 404 |
| `GET /summary` 데이터 전무 | 200 — empty arrays + `total_evaluated=0` + `correlation=null` |
| 잘못된 date 포맷 | 422 |

### 4.5 Indicator Accuracy 정규화

`FeedbackEvaluator.get_indicator_accuracy(days)` 실제 반환:
```python
{"investor_flow": {"hits": 35, "total": 45, "accuracy": 0.78}, ...}
```

API 변환:
```python
items = [
    IndicatorAccuracy(key=k, accuracy=v["accuracy"], count=v["total"])
    for k, v in raw.items()
    if v["total"] > 0                # count=0 제외
]
items.sort(key=lambda x: x.accuracy, reverse=True)
```

### 4.6 hit_* 필드 변환

`FeedbackStore` 는 INTEGER (0/1/NULL) 로 저장. API 는 `bool | None`:
- 0 → False
- 1 → True
- NULL → None (미평가)

변환 헬퍼 `_row_to_history_item()` 에서 처리.

---

## 5. 프론트엔드 설계

### 5.1 라우트
```
webapp-ui/app/(dashboard)/feedback/
├── page.tsx              # 대시보드 (SSR, ?days=30 쿼리)
└── [date]/page.tsx       # 상세 (SSR)
```

### 5.2 사이드바 변경
`webapp-ui/components/layout/sidebar.tsx` ITEMS 배열에 "브리핑" 다음 삽입:
```ts
{ href: "/feedback", label: "피드백" },
```

### 5.3 컴포넌트 (`components/domain/feedback/`)

| 컴포넌트 | 역할 | 주요 props |
|---|---|---|
| `hit-rate-cards.tsx` | 1일/3일/5일 적중률 카드 3개 (퍼센트 + 건수) | `rates: HitRates` |
| `correlation-card.tsx` | score ↔ return_1d 상관계수 카드 + 해석 텍스트 | `correlation: number \| null` |
| `indicator-accuracy-chart.tsx` | 11개 지표 가로 bar chart (recharts) | `items: IndicatorAccuracy[]` |
| `signal-history-table.tsx` | 이력 테이블 + 페이지네이션 | `data: FeedbackHistoryResponse` |
| `feedback-detail-card.tsx` | 상세 헤더 (시그널/시장결과/수익률/적중) | `detail: FeedbackDetail` |
| `post-analysis-section.tsx` | post_analysis + blind_spots 마크다운 | `postAnalysis: string \| null`, `blindSpots: string \| null` |
| `news-summary-section.tsx` | news_summary 텍스트 렌더 | `newsSummary: string \| null` |
| `period-toggle.tsx` | 30/60/90일 토글 (URL 쿼리) | `current: number` |
| `no-feedback.tsx` | 빈 상태 (total_evaluated == 0) | - |

재사용:
- `@/components/domain/content/report-markdown-view` — post_analysis/blind_spots 렌더
- `@/lib/market-labels` — INDICATOR_LABELS, signalStyle

### 5.4 페이지 구성

**`/feedback?days=30`** (대시보드)
```
[h1: 피드백]                    [PeriodToggle: 30/60/90일]
[HitRateCards × 3]              [CorrelationCard]
[IndicatorAccuracyChart]
[SignalHistoryTable (최근 N건 + 페이지네이션)]
```

빈 상태: 전체 `<NoFeedback />` 렌더.

**`/feedback/[date]`** (상세)
```
[← 피드백 대시보드]
[FeedbackDetailCard]
[NewsSummarySection]           # news_summary 있을 때만
[PostAnalysisSection]          # post_analysis/blind_spots 하나라도 있으면
[→ 이 날짜 브리핑 전체 보기]    # /briefings/{date} 링크
```

404 → Next.js `notFound()`.

### 5.5 IndicatorAccuracyChart 구현

recharts horizontal BarChart:
- Y축: `INDICATOR_LABELS[key]` (한글명)
- X축: 정확도 (0-100%)
- 바 색상 규칙:
  - `accuracy >= 0.70` → 녹색 (`#22c55e`)
  - `accuracy >= 0.50` → 노랑 (`#eab308`)
  - `accuracy < 0.50` → 빨강 (`#ef4444`)
- 툴팁: "정확도 78% · 평가 45건"
- `count < 5` 지표는 옅은 색 + "데이터 부족" 뱃지
- `count == 0` 지표는 API 에서 제외 (4.5 참조)

### 5.6 Period Toggle (URL 쿼리 기반)

```tsx
// period-toggle.tsx
const onPick = (days: number) => {
  const sp = new URLSearchParams(searchParams)
  sp.set("days", String(days))
  router.push(`/feedback?${sp}`)
}
```

- 3개 버튼 (`30/60/90`), 현재 선택은 `default` variant, 나머지는 `outline`

### 5.7 SignalHistoryTable 페이지네이션

- 메인 대시보드는 `recent_history` (10건) 프리뷰만
- "이력 전체 보기" 링크로 `/feedback?days=30&page=1` (페이지 파라미터 등장 시 full table 모드)
- 또는 별도 `/feedback/history` 페이지? → YAGNI, 메인에서 table 확장 모드로 처리

**결정:** 메인 페이지에 `?page=N` 쿼리 시 summary 위에 테이블 전환 모드 렌더 (간단). 또는 단순히 메인 대시보드 하단 테이블이 페이지네이션 포함하여 항상 표시. **후자가 더 단순** — 스펙 5.4 페이지 구성 그대로.

최종 동작: 메인 페이지 하단 테이블이 항상 페이지네이션 된 전체 이력 표시. `/feedback/history` 는 API 만 있고 UI 라우트는 없음.

---

## 6. 데이터 모델

### 스키마 변경 없음 (기존 `FeedbackStore` 재사용)

`feedback.db` 의 `signal_feedback` 테이블 (20 컬럼) 그대로 조회.

### Config 추가 (선택 사항)

`alphapulse/core/config.py`:
```python
self.FEEDBACK_DB = self.DATA_DIR / "feedback.db"
```

현재 `DATA_DIR / "feedback.db"` 로 인라인 구성 중. 상수화하면 main.py 에서 `Config().FEEDBACK_DB` 로 깔끔히 주입. 다른 저장소와 일관 (HISTORY_DB / BRIEFINGS_DB 패턴).

### main.py 상태 주입

```python
from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator

feedback_store = FeedbackStore(db_path=core.FEEDBACK_DB)
feedback_evaluator = FeedbackEvaluator(store=feedback_store)

app.state.feedback_store = feedback_store
app.state.feedback_evaluator = feedback_evaluator

app.include_router(feedback_router)
```

---

## 7. 테스트 전략

### 7.1 백엔드 (pytest, TDD)

**`tests/webapp/api/test_feedback.py`**
- `GET /summary` 인증 필요 (401)
- `GET /summary` 빈 DB → empty arrays + total_evaluated=0 + correlation=null
- `GET /summary?days=30` 적중률/상관/지표/최근 반환 + 지표 내림차순
- `GET /history?page=2&size=10` 페이지네이션
- `GET /history?size=500` → 422
- `GET /{date}` 존재하는 날짜 → 정상
- `GET /{date}` 없음 → 404
- `GET /{date}` 잘못된 포맷 → 422
- hit_* INTEGER → bool/None 변환 검증
- indicator_accuracy: count=0 제외, accuracy 내림차순

**기존 테스트 재사용** — `tests/feedback/test_evaluator.py`, `tests/feedback/test_collector.py` 가 이미 evaluator/store 커버하므로 API 레이어만 얇게 테스트.

### 7.2 프론트엔드 (Playwright E2E)

**`webapp-ui/e2e/feedback.spec.ts`**
- 로그인 → `/feedback` 이동 → 대시보드 또는 NoFeedback 렌더
- 사이드바 "피드백" 진입점
- 기간 토글 버튼 3개 존재

E2E 에서 실제 차트 내용 검증은 스킵 (데이터 의존).

### 7.3 회귀
- 기존 1200+ 테스트 그대로 PASS
- 신규 pytest ~10~12건 + E2E 1스펙

---

## 8. 파일 구조 요약

### 신규 (백엔드)
```
alphapulse/webapp/api/feedback.py
tests/webapp/api/test_feedback.py
```

### 신규 (프론트엔드)
```
webapp-ui/app/(dashboard)/feedback/page.tsx
webapp-ui/app/(dashboard)/feedback/[date]/page.tsx
webapp-ui/components/domain/feedback/hit-rate-cards.tsx
webapp-ui/components/domain/feedback/correlation-card.tsx
webapp-ui/components/domain/feedback/indicator-accuracy-chart.tsx
webapp-ui/components/domain/feedback/signal-history-table.tsx
webapp-ui/components/domain/feedback/feedback-detail-card.tsx
webapp-ui/components/domain/feedback/post-analysis-section.tsx
webapp-ui/components/domain/feedback/news-summary-section.tsx
webapp-ui/components/domain/feedback/period-toggle.tsx
webapp-ui/components/domain/feedback/no-feedback.tsx
webapp-ui/e2e/feedback.spec.ts
```

### 수정
```
alphapulse/core/config.py           # FEEDBACK_DB 상수 (선택)
alphapulse/webapp/main.py           # feedback_store/_evaluator state + router
webapp-ui/components/layout/sidebar.tsx   # "피드백" 항목
```

---

## 9. 위험 요소 & 의존성

| 항목 | 위험 | 완화 |
|---|---|---|
| `get_indicator_accuracy` 반환 shape | evaluator 내부 구현이 `dict[key: {hits,total,accuracy}]` 임을 spec 에 명시 | API 변환 로직 고정 |
| NULL 값 대량 (pending 시그널) | 통계가 왜곡 | `total_evaluated==0` 시 NoFeedback; 각 계산은 이미 null-safe |
| 긴 기간 조회 (365일) | `/summary.recent_history` 10건 고정이라 문제 없음. `/history` 는 페이지네이션 | size 상한 100 강제 |
| indicator_scores NULL 또는 legacy numpy | `FeedbackStore` 가 이미 sanitize 저장 (이전 fix). 과거 데이터는 이미 JSON primitive | 방어 코드 없음 (spec 4.5 가정 유지) |
| Briefing 링크 깨짐 | feedback.db 에는 있지만 briefings.db 에는 없는 date | 프론트에서 단순 Link. 404 는 Briefing 의 notFound() 가 처리 |
| `Config.FEEDBACK_DB` 도입이 기존 인라인 사용과 중복 | 기존 `Config().DATA_DIR / "feedback.db"` 호출 지점 다수 | 이번 사이클은 main.py 주입 경로만 상수 사용. 기존 호출 그대로 (후속 cleanup) |

---

## 10. 결정 요약

| 항목 | 선택 | 이유 |
|---|---|---|
| 실행 방식 | 조회 전용 (A) | Briefing 이 evaluate/analyze 자동 수행 |
| 페이지 구조 | 대시보드 + 상세 2-page (A) | 대시보드 성격 일치 |
| 상세 페이지 범위 | Feedback 고유 + Briefing 링크 (B) | 중복 없이 연결 |
| 엔드포인트 구성 | `/summary` 통합 + `/history` 분리 + `/{date}` 상세 | 초기 로딩 최적화 + 페이지네이션 |
| 기간 토글 | 30/60/90일 URL 쿼리 | 사전 정의 + 딥링크 |
| 차트 | recharts horizontal BarChart | 기존 사용 중 |
| 신규 저장소 | 없음 (FeedbackStore/Evaluator 재사용) | 스키마 변경 0 |
| Config 상수 | `FEEDBACK_DB` 추가 (main.py 주입용) | 다른 도메인과 일관 |
| Job 엔드포인트 | 없음 | YAGNI |
| 홈 위젯 | 후속 사이클 | 범위 분리 |

---

## 11. 향후 사이클 (별도 spec)

- **홈 대시보드 Feedback 위젯** — 최근 7일 적중률 카드
- **알림** — 적중률 특정 임계값 이탈 시 Telegram
- **CSV/Excel Export** — `/feedback/export?days=90&format=csv`
- **지표 Drill-down** — 지표 bar 클릭 → 해당 지표가 극단값이었던 시그널만 필터링한 테이블
- **Scatter plot** — score vs return_1d 산점도
- **지표별 시계열 적중률 추이** — 최근 N일간 일별 적중률 LineChart

Phase 3 B안 5개 도메인이 모두 완성되면 Phase 3 전체 통합 회고 + 홈 대시보드 재설계 사이클 고려 가능.
