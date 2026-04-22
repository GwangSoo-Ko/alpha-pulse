# 홈 대시보드 재설계 — Design Spec

**작성일**: 2026-04-22
**대상 경로**: `/` (로그인 후 기본 페이지)
**현행 구조**: `webapp-ui/app/(dashboard)/page.tsx` (Phase 2 trading 중심)
**목표**: Phase 3 5개 도메인(Briefing / Market Pulse / Content / Feedback) 통합. "오늘 장 어떻게 볼까?" 질문에 5초 안에 답하고, 필요 시 각 도메인 페이지로 자연스럽게 드릴다운.

---

## 1. 원칙

- **Briefing-first**: 상단 Hero는 오늘의 브리핑 요약. 사용자의 첫 시선이 닿는 위치에 "오늘의 판단"이 있다.
- **Compact + Highlights**: Hero는 점수·시그널·한 줄 요약 + 주요 지표 badge 3개. 본문은 드릴다운.
- **Stale + 배너**: 오늘자 브리핑이 없으면 어제 꺼를 그대로 보여주고 상단 배너로 "미생성 + [지금 실행]" CTA.
- **Balanced 2×3 Grid**: Hero 아래는 6개 위젯 동등 비중 (Pulse/Feedback/Content + Portfolio/Risk/DataHealth).
- **Display-only 위젯**: 각 카드는 표시만. 클릭 시 도메인 페이지로 이동. 홈에서의 실행 액션은 브리핑 재생성 1개로 한정.
- **에러 격리**: 한 섹션 조회 실패가 다른 섹션 렌더를 막지 않는다.

## 2. 레이아웃

```
┌──────────────────────────────────────────────────────────────┐
│ [⚠ 오늘 브리핑 미생성 · 어제(4-21) 기준 · [지금 실행]]         │  ← 조건부 배너
├──────────────────────────────────────────────────────────────┤
│ HERO — BriefingHeroPlus                                      │
│  브리핑 · 2026-04-22 · 08:30                                 │
│  +62.5  [긍정]                                               │
│  코스피 강세 흐름. 외국인 순매수 유입.                        │
│  [RSI ↑] [외인 ↑] [VIX ↓]                  [→ 상세 보기]    │
├──────────────────────────────────────────────────────────────┤
│ Insight Row (Phase 3)                                        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│ │ Pulse    │ │ Feedback │ │ Content  │                       │
│ └──────────┘ └──────────┘ └──────────┘                       │
├──────────────────────────────────────────────────────────────┤
│ Trading Row (Phase 2)                                        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│ │ Portfolio│ │ Risk     │ │ DataHealth│                      │
│ └──────────┘ └──────────┘ └──────────┘                       │
└──────────────────────────────────────────────────────────────┘
```

### 반응형

| Breakpoint | Hero | Support Widgets |
|---|---|---|
| Desktop (≥1024px) | full width | 3열 (grid-cols-3) |
| Tablet (≥768px) | full width | 2열 (grid-cols-2, Data 단독) |
| Mobile (<768px) | full width | 1열 세로 스택 |

카드 공통 속성: `min-height: 160px`, 카드 전체 클릭 영역.

## 3. 위젯 상세

### 3.1 BriefingHeroPlus (신규)

**표시 요소**
- 날짜 · 저장 시각 (예: `브리핑 · 2026-04-22 · 08:30`)
- `score`: signed float, 색상은 `signalStyle(signal)` (기존 `lib/market-labels.ts`) 재사용
- `signal` badge: positive/neutral/negative
- `summary_line`: `daily_result_msg` 의 첫 줄 (줄바꿈 기준, 없으면 `commentary` 첫 문장)
- `highlight_badges`: 3개 — 각 `{name, direction: "up"|"down"|"neutral", sentiment: "positive"|"negative"}`
  - 서버에서 `pulse_result.indicator_descriptions` 또는 `indicators` 에서 기여도 절대값 TOP3 선택
- `[→ 상세 보기]` 링크 → `/briefings/{date}`

**Stale 상태** (`is_today === false`)
- 위에 `MissingBriefingBanner` 노출 (§3.2)
- Hero 내부에는 별도 표시 변경 없음(어제 데이터 그대로)

**Empty (brief 전체 None)**
- `"브리핑 데이터가 없습니다. 먼저 브리핑을 생성하세요."` 문구 + 배너의 "지금 실행" 버튼

**파일**: `webapp-ui/components/domain/home/briefing-hero-plus.tsx`

### 3.2 MissingBriefingBanner (신규)

- 조건: `briefing.is_today === false` (즉 최신 브리핑 날짜 ≠ 오늘)
- 노출 문구: `⚠ 오늘({YYYY-MM-DD}) 브리핑 미생성 · 어제({prev_date}) 기준 표시 중`
- 우측 버튼: `[지금 실행]` → `POST /api/v1/briefings/run` (기존 엔드포인트) 호출 후 토스트 `"브리핑 작업이 시작되었습니다."` + 5초 뒤 `router.refresh()` 안내
- `briefing === null` (아예 없음)이면 배너 문구를 `"브리핑 데이터가 없습니다."`로 치환

**파일**: `webapp-ui/components/domain/home/missing-briefing-banner.tsx`

### 3.3 PulseWidget (신규)

- **표시**: 최신 score(큰 숫자 + signal badge) · 7일 mini bar chart (positive=green / neutral=amber / negative=red)
- **데이터**: `pulse.latest` + `pulse.history7`
- **클릭**: 카드 전체 → `/market/pulse`
- **Empty**: "Market Pulse 데이터 없음"

**파일**: `webapp-ui/components/domain/home/pulse-widget.tsx`

### 3.4 FeedbackWidget (신규)

- **표시**: 최근 7일 적중률(큰 %) · 지표 TOP2 (예: `RSI 80% · MA 60%`)
- **데이터**: `feedback.hit_rate_7d` + `feedback.top_indicators[:2]`
- **클릭**: 카드 전체 → `/feedback`
- **Empty**: "피드백 데이터 없음"

**파일**: `webapp-ui/components/domain/home/feedback-widget.tsx`

### 3.5 ContentWidget (신규)

- **표시**: 최근 3건 리포트 (제목 + 날짜) 리스트
- **데이터**: `content.recent[:3]` — 각 item `{date, filename, title}`
- **클릭**: 카드 전체 → `/content/reports`
- **Empty**: "신규 리포트 없음"

**파일**: `webapp-ui/components/domain/home/content-widget.tsx`

### 3.6 PortfolioWidget (축소, 기존 교체)

- 기존 `portfolio-widget.tsx` 내용을 홈 카드 크기로 재설계
- **표시**: 총 자산(₩), 일간 수익률(%), 누적 수익률(%)
- **제거**: 기존 차트 (상세 페이지로 이동)
- **클릭**: 카드 전체 → `/portfolio`
- **Empty**: "포트폴리오 스냅샷 없음"

### 3.7 RiskStatusWidget (축소, 기존 교체)

- **표시**: 경고 건수(`alerts.length`) + 최우선 alert 1줄(`alerts[0].message`) — 경고 없으면 `"리스크 정상"`
- **클릭**: 카드 전체 → `/risk`
- **Empty**: "리스크 데이터 없음"

### 3.8 DataHealthWidget (신규, 기존 `data-status-widget` 교체)

- **표시**: 갭 건수 + 최근 수집 성공/실패 (`data_status.tables[0]` 기준)
- **클릭**: 카드 전체 → `/data`
- **Empty**: "데이터 상태 불명"

## 4. 데이터 흐름

### 4.1 API 확장 — `/api/v1/dashboard/home`

기존 `HomeResponse` 를 다음과 같이 변경한다.

```python
# 신규 모델 (alphapulse/webapp/api/dashboard.py 내부 정의)

class BriefingHeroData(BaseModel):
    date: str                                   # YYYY-MM-DD
    created_at: int                             # epoch
    score: float
    signal: str                                 # positive | neutral | negative
    summary_line: str
    highlight_badges: list[dict]                # [{name, direction, sentiment}]
    is_today: bool

class PulseHistoryPoint(BaseModel):
    date: str
    score: float
    signal: str

class PulseLatest(BaseModel):
    date: str
    score: float
    signal: str

class PulseWidgetData(BaseModel):
    latest: PulseLatest | None
    history7: list[PulseHistoryPoint]           # 최근 7일

class FeedbackIndicator(BaseModel):
    name: str
    hit_rate: float                             # 0~1

class FeedbackWidgetData(BaseModel):
    hit_rate_7d: float | None                   # 0~1, 데이터 없으면 None
    top_indicators: list[FeedbackIndicator]     # 최대 2

class ContentRecentItem(BaseModel):
    date: str                                   # YYYY-MM-DD
    filename: str
    title: str                                  # 파일 본문 첫 # 또는 파일명

class ContentWidgetData(BaseModel):
    recent: list[ContentRecentItem]             # 최대 3

class HomeResponse(BaseModel):
    briefing: BriefingHeroData | None           # 신규
    pulse: PulseWidgetData | None               # 신규
    feedback: FeedbackWidgetData | None         # 신규
    content: ContentWidgetData                  # 신규, 항상 존재(빈 리스트 가능)
    portfolio: dict | None                      # 유지
    portfolio_history: list                     # 유지
    risk: dict | None                           # 유지
    data_status: dict                           # 유지
    # recent_backtests, recent_audits 필드는 제거
```

### 4.2 섹션 격리 패턴

각 블록을 독립 try/except 로 감싼다.

```python
async def home(...):
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

    # 기존 Phase 2 블록 (동일 패턴)
    portfolio_snap = None
    portfolio_hist = []
    try:
        portfolio_snap = portfolio.get_latest(mode=mode)
        portfolio_hist = portfolio.get_history(mode=mode, days=30)
    except Exception as e:
        logger.warning("home: portfolio fetch failed: %s", e)

    risk_data = None
    if portfolio_snap:
        try:
            risk_data = risk.get_report(mode=mode)
        except Exception as e:
            logger.warning("home: risk fetch failed: %s", e)

    data_status_data = {"tables": [], "gaps_count": 0}
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

### 4.3 Helper 함수 책임

- `_build_briefing_hero(store: BriefingStore) -> BriefingHeroData | None`
  - `store.get_recent(days=1)` 로 가장 최근 한 건 조회 (리스트 첫 요소)
  - 빈 리스트면 `None` 반환
  - `is_today` = `record["date"] == today_kst_yyyymmdd()`
  - `created_at` = `record["created_at"]` (epoch float → int)
  - `payload = record["payload"]` 에서 `pulse_result`, `daily_result_msg`, `commentary` 추출
  - `score` = `payload["pulse_result"].get("score", 0.0)`
  - `signal` = `payload["pulse_result"].get("signal", "neutral")`
  - `summary_line` = `(payload.get("daily_result_msg") or "").split("\n")[0]` — 비어있으면 `payload.get("commentary")` 첫 문장(마침표 split), 둘 다 없으면 빈 문자열
  - `highlight_badges` = `_select_top3_indicators(payload["pulse_result"])`
- `_select_top3_indicators(pulse_result: dict) -> list[dict]`
  - 우선 `pulse_result.get("indicator_descriptions")` 사용(존재 시), 없으면 `pulse_result.get("indicators")`, 둘 다 없으면 빈 리스트
  - 각 지표의 `score` 절대값 내림차순 TOP3
  - `direction`: score > 0 → "up", score < 0 → "down", else "neutral"
  - `sentiment`: score > 0 → "positive", score < 0 → "negative", else "neutral"
  - 결과 형식: `[{"name": "RSI", "direction": "up", "sentiment": "positive"}, ...]`
- `_build_pulse_widget(history: PulseHistory) -> PulseWidgetData`
  - `records = history.get_recent(days=7)` (날짜 DESC)
  - `latest = records[0]` (있으면 `{date, score, signal}`, 없으면 `None`)
  - `history7 = [{date, score, signal} for r in reversed(records)]` (오래된 → 최신 순, 차트 친화적)
  - 전부 비어있으면 `PulseWidgetData(latest=None, history7=[])`
- `_build_feedback_widget(evaluator: FeedbackEvaluator) -> FeedbackWidgetData | None`
  - `rates = evaluator.get_hit_rates(days=7)` → `rates["hit_rate_1d"]` 사용 (0~1 float)
  - `rates["total_evaluated"] == 0` 이면 `None` 반환
  - `acc = evaluator.get_indicator_accuracy(days=7, threshold=50.0)` → `{name: {accuracy, hits, total}}`
  - `top_indicators` = `total >= 3` 인 항목 중 `accuracy` 내림차순 상위 2개 → `[FeedbackIndicator(name, hit_rate=accuracy)]`
  - 반환: `FeedbackWidgetData(hit_rate_7d=rates["hit_rate_1d"], top_indicators=...)`
- `_build_content_widget(reader: ContentReader) -> ContentWidgetData`
  - `result = reader.list_reports(size=3, sort="newest")`
  - `items = result["items"]` (각 item 은 `ReportMeta` TypedDict: `filename`, `title`, `category`, `published`, `analyzed_at`)
  - 반환: `ContentWidgetData(recent=[ContentRecentItem(date=m["analyzed_at"][:10], filename=m["filename"], title=m["title"]) for m in items])`

### 4.4 프런트엔드 구조

```
webapp-ui/
  app/(dashboard)/page.tsx                          (전면 교체)
  components/domain/home/
    briefing-hero-plus.tsx                          (신규)
    missing-briefing-banner.tsx                     (신규)
    pulse-widget.tsx                                (신규)
    feedback-widget.tsx                             (신규)
    content-widget.tsx                              (신규)
    data-health-widget.tsx                          (신규, 기존 data-status-widget 대체)
    portfolio-widget.tsx                            (기존 파일 내용 리라이트 — 홈 축소판)
    risk-status-widget.tsx                          (기존 파일 내용 리라이트 — 홈 축소판)
    recent-backtests-widget.tsx                     (삭제)
    recent-audit-widget.tsx                         (삭제)
```

페이지 로더는 기존 패턴 유지: `cookies()` 헤더 전달 + `apiFetch<HomeResponse>("/api/v1/dashboard/home", { cache: "no-store" })`.

## 5. 에러 처리 및 엣지

| 상황 | 동작 |
|---|---|
| 오늘자 브리핑 없음 | Hero는 최신(어제) 데이터 렌더, 배너 노출 |
| 브리핑 전혀 없음(최초) | Hero 영역에 Empty 문구 + 배너 "브리핑 데이터 없음" |
| Pulse 조회 실패 | `pulse=null` 반환, 위젯은 Empty state |
| Feedback 데이터 부족 | `hit_rate_7d=null`, `top_indicators=[]` → "데이터 수집 중" |
| Content 디렉터리 없음 | `recent=[]` → "신규 리포트 없음" |
| Portfolio 스냅샷 없음 | `portfolio=null` → "포트폴리오 없음" (기존 동작) |
| Risk alerts 0건 | Risk 위젯은 "리스크 정상" 표시 |
| 전체 aggregate 500 에러 | 프런트에서 기본 에러 페이지 (apiFetch 기본 동작) |

## 6. 테스트

### 6.1 백엔드 (`tests/webapp/api/test_dashboard.py` 확장)

- `test_home_includes_phase3_fields`
- `test_home_briefing_is_today_true_when_today_matches`
- `test_home_briefing_is_today_false_when_yesterday`
- `test_home_briefing_none_when_store_empty`
- `test_home_pulse_failure_isolated` — PulseHistory 예외 시 `pulse=None`, 나머지 정상
- `test_home_feedback_failure_isolated` — FeedbackEvaluator 예외 시 `feedback=None`
- `test_home_content_failure_isolated` — ContentReader 예외 시 `content.recent=[]`
- `test_home_badge_selection_top3_by_abs_score` — `_select_top3_indicators` 정렬 검증
- `test_home_feedback_top_indicators_limit_2` — 최대 2개 반환
- `test_home_backwards_compat_fields_removed` — recent_backtests, recent_audits 필드 없음

### 6.2 프런트 컴포넌트 (Vitest, `webapp-ui/components/domain/home/__tests__/`)

- `briefing-hero-plus.test.tsx` — 데이터 있음/없음/badges 3개 렌더
- `missing-briefing-banner.test.tsx` — `is_today=false` 시 노출, 버튼 클릭 → `POST /api/v1/briefings/run` 호출
- `pulse-widget.test.tsx` — 7일 mini bar 렌더, empty state
- `feedback-widget.test.tsx` — hit_rate 표시, top_indicators 2개 제한
- `content-widget.test.tsx` — 3건 리스트, 빈 배열 시 empty state
- `data-health-widget.test.tsx` — 갭 건수 표시

### 6.3 E2E 스모크 (`tests/webapp-ui/e2e/home.spec.ts` 또는 기존 파일 확장)

- 홈 로드 → Hero 스코어 + badges 3개 표시
- 6개 위젯 모두 렌더 확인
- Pulse 위젯 클릭 → URL `/market/pulse` 이동
- Feedback 위젯 클릭 → `/feedback`
- Content 위젯 클릭 → `/content/reports`
- 오늘 브리핑 부재 시나리오(briefing.is_today=false 모킹) → 배너 노출

## 7. 성공 기준

- 홈 TTFB ≤ 500ms (SSR, 모든 섹션 SQLite 조회)
- 한 섹션 실패가 다른 섹션 렌더를 막지 않음 (격리 확인)
- `pytest tests/webapp/api/test_dashboard.py` 전체 통과
- Vitest home 컴포넌트 테스트 전체 통과
- Playwright home E2E 스모크 통과
- Lighthouse a11y ≥ 90

## 8. 마이그레이션 / 호환성

- `/api/v1/dashboard/home` 응답의 `recent_backtests`, `recent_audits` 필드 **제거**. 기존 `app/(dashboard)/page.tsx` 가 유일한 소비자이며 동시에 교체되므로 외부 영향 없음.
- 삭제 대상 컴포넌트 2개(`recent-backtests-widget.tsx`, `recent-audit-widget.tsx`)는 홈 전용이며 다른 페이지에서 사용되지 않음 — grep 으로 확인 후 삭제.
- Phase 2 Portfolio/Risk 위젯은 동일 이름으로 교체(홈 축소판) — 다른 페이지에서 재사용되지 않는지 grep 으로 확인. 사용되는 경우 파일명을 `portfolio-home-card.tsx` 형태로 분리.

## 9. 범위 밖 (Out of Scope)

- Briefing/Pulse/Feedback 상세 페이지 자체 개선 (각 도메인 별도 작업)
- 실시간 WebSocket/SSE 업데이트
- 알림/푸시 (추후 Alert 시스템 설계 시)
- 위젯 커스터마이징(사용자가 숨김/순서 변경)
- 다크모드 외 테마
