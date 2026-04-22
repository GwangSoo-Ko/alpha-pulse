# Daily Briefing 웹 대시보드 — 설계 문서

**작성일:** 2026-04-21
**스코프:** AlphaPulse 웹 UI 에 `briefing` 도메인 추가 (Phase 3 세 번째 도메인, Market Pulse / Content 이후)
**후속:** AI Commentary / Feedback 은 별도 spec 사이클

---

## 1. 목적 & 배경

현재 `alphapulse/briefing/` 모듈은 CLI daemon (`ap briefing --daemon`) 로 매일 아침 텔레그램에 종합 브리핑을 발송한다. 그러나:
- **브리핑 결과가 영속화되지 않음** — 텔레그램 메시지만 보내고 끝
- **AI Commentary / Senior Synthesis 는 메모리에만 존재** → 실행 후 사라짐
- 웹에서 과거 브리핑을 회상(review)하거나 특정 날짜 상세를 보는 수단이 없음

본 spec 은:
- **신규 저장소 `briefings.db` 도입** — `BriefingOrchestrator.run_async()` 반환 dict 전체를 영속화
- 웹 UI 에 리스트 + 상세 마크다운 뷰 + 수동 실행 Job 제공
- CLI daemon 실행분도 자동으로 DB 축적 → 과거 이력 점진적 확보

---

## 2. 스코프

### 포함 (이번 사이클)
- 신규 `BriefingStore` (SQLite, `briefings` 단일 테이블)
- `BriefingOrchestrator.run_async` 완료 후 `BriefingStore.save()` 호출 (CLI + 웹 공통)
- `/briefings` 리스트 (페이지네이션)
- `/briefings/[date]` 상세 — Pulse 요약 + synthesis + commentary + 뉴스 + post_analysis + feedback context (각 섹션별 컴포넌트)
- `/briefings/jobs/[id]` Job 진행 페이지 (3~10분 긴 실행 대응 안내)
- FastAPI 라우터 `alphapulse/webapp/api/briefing.py` (4 엔드포인트)
- Job 어댑터 `alphapulse/webapp/services/briefing_runner.py` — `send_telegram=False`
- `JobKind` 에 `"briefing"` 추가
- 사이드바 "브리핑" 진입점
- E2E 스모크 (진입점 + 리스트 렌더)

### 제외 (YAGNI / 후속 사이클)
- CLI daemon 웹 제어 (시작/정지)
- 브리핑 삭제/편집 — 읽기 전용
- 풀텍스트 검색 — 날짜 리스트 + 30일 스크롤
- 커스텀 date range
- 브리핑 비교 뷰 (두 날짜)
- 텔레그램 발송 토글 — 웹은 항상 off
- Feedback 섹션의 풍부한 시각화 — Feedback 도메인 spec 에서 처리
- 과거 CLI 실행분 백필 — 불가능
- 홈 대시보드 위젯

---

## 3. 아키텍처

### 레이어 구조
```
┌──────────────────────────────────────────┐
│ Frontend (Next.js 15 App Router)         │
│  webapp-ui/app/(dashboard)/briefings/    │
│  webapp-ui/components/domain/briefing/   │
└───────────────┬──────────────────────────┘
                │ SSR fetch / client mutate
                ▼
┌──────────────────────────────────────────┐
│ FastAPI router                           │
│  alphapulse/webapp/api/briefing.py       │
│  alphapulse/webapp/services/             │
│    briefing_runner.py                    │
└────────┬──────────────────┬──────────────┘
         │ read             │ run
         ▼                  ▼
┌────────────────┐  ┌──────────────────────┐
│ BriefingStore  │  │ BriefingOrchestrator │
│ (briefings.db) │◄─┤   .run_async()       │
└────────────────┘  │   (async pipeline)   │
                    └──────────────────────┘
```

### Sync/Async 경계
- `alphapulse/briefing/` 은 **async** (AI 호출 + Telegram 발송)
- `BriefingOrchestrator.run_async()` 는 coroutine function
- JobRunner 는 Content 작업에서 추가된 `iscoroutinefunction` 분기로 직접 await
- `BriefingStore` 는 sync (sqlite3); orchestrator 안에서 `await asyncio.to_thread(store.save, ...)` 로 non-blocking 호출

### 데이터 흐름

**조회 (주 경로)**
```
사용자 → /briefings?page=1 접속
 → SSR: GET /api/v1/briefings?page=1&size=20&days=30
 → BriefingStore.get_recent(30) → 날짜 DESC 정렬 → 페이지 슬라이스
 → 응답: [{date, score, signal, has_synthesis, has_commentary, created_at}]
 → 렌더: BriefingsTable
```

**상세 조회**
```
사용자 → /briefings/{date} 접속
 → SSR: GET /api/v1/briefings/{date}
 → BriefingStore.get(date) → payload JSON unpack
 → 응답: BriefingDetail (12 필드)
 → 렌더: 섹션별 컴포넌트 (hero + synthesis + commentary + news + post_analysis + feedback + raw_messages)
```

**실행 (임시 경로)**
```
사용자 → "지금 실행" 클릭
 → 오늘 이력 있으면 RunConfirmModal (Market Pulse 컴포넌트 재사용)
 → POST /api/v1/briefings/run {date?}
 → 중복 running Job 감지 (find_running_by_kind_and_date("briefing", date))
    있으면 {job_id, reused: true} 반환
    없으면 새 Job 생성 + BackgroundTasks → runner.run(..., run_briefing_async)
 → runner.run 이 iscoroutinefunction 분기로 await run_briefing_async(...)
 → run_briefing_async 가 BriefingOrchestrator.run_async(date, send_telegram=False) 호출
 → orchestrator 완료 시 BriefingStore.save(date, payload) 수행
 → Job result_ref = 저장된 date (YYYYMMDD 8자리)
 → 프론트: /briefings/jobs/{id} 폴링 → status=done → result_ref 있으면 /briefings/{date} replace
```

---

## 4. API 설계

베이스: `/api/v1/briefings`
인증: 모든 엔드포인트 `get_current_user` 필수

### 4.1 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/briefings/latest` | 가장 최근 저장된 Briefing |
| GET | `/briefings?days=30&page=1&size=20` | 최근 N일 요약 리스트 |
| GET | `/briefings/{date}` | 특정 날짜 상세 (YYYYMMDD path param 정규식 검증) |
| POST | `/briefings/run` | 실행 Job 시작 |
| GET | `/jobs/{job_id}` | Job 상태 폴링 (기존 재사용) |

### 4.2 요청 스키마

```python
class RunBriefingRequest(BaseModel):
    date: str | None = None   # YYYYMMDD, None 이면 오늘
```

### 4.3 응답 스키마

```python
class BriefingSummary(BaseModel):
    """리스트용 축약."""
    date: str
    score: float                     # pulse_result["score"]
    signal: str                      # pulse_result["signal"]
    has_synthesis: bool              # bool(synthesis)
    has_commentary: bool             # bool(commentary)
    created_at: float

class BriefingListResponse(BaseModel):
    items: list[BriefingSummary]
    page: int
    size: int
    total: int

class BriefingDetail(BaseModel):
    """상세 — payload JSON 펼침."""
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
    news: dict                       # {"articles": [{"title", "url", ...}]}
    post_analysis: dict | None
    generated_at: str                # ISO timestamp from orchestrator

class RunBriefingResponse(BaseModel):
    job_id: str
    reused: bool
```

### 4.4 경로 파라미터 검증

```python
@router.get("/briefings/{date}", ...)
async def get_briefing(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    ...
): ...
```

잘못된 포맷(`foo`, `2026-04-21`) → 422 (not 404).

### 4.5 에러 처리
| 상황 | 응답 |
|---|---|
| 인증 실패 | 401 |
| `GET /briefings/{date}` 저장 없음 | 404 |
| `GET /briefings/latest` 전체 없음 | 200 `null` |
| 잘못된 date 포맷 (path) | 422 |
| `POST /run` 잘못된 date 입력 | 422 (`ValueError` → `HTTPException`) |
| Job 내부 예외 | Job status=`failed` + error (응답 200) |

### 4.6 감사 로그

- `POST /briefings/run` → `AuditLogger.log("webapp.briefing.run", component="webapp", data={user_id, job_id, date})`
- 조회 엔드포인트 감사 없음 (Phase 2 정책)

### 4.7 중복 Job 감지

- `JobRepository.find_running_by_kind_and_date("briefing", target_date)` 사용 — Market Pulse Task 2 에서 이미 추가된 헬퍼 재사용
- 같은 date 의 pending/running Job 있으면 `{job_id: existing.id, reused: true}` 반환

### 4.8 Briefing Runner

`alphapulse/webapp/services/briefing_runner.py`:
```python
from typing import Callable
from alphapulse.briefing.orchestrator import BriefingOrchestrator


async def run_briefing_async(
    *,
    date: str | None,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """BriefingOrchestrator 를 텔레그램 발송 없이 실행.

    Returns:
        저장된 date (YYYYMMDD) — Job.result_ref 에 기록됨.
    """
    progress_callback(0, 1, "브리핑 실행 중 (3~10분 소요, 브라우저 닫아도 계속)")
    orch = BriefingOrchestrator()
    result = await orch.run_async(date=date, send_telegram=False)
    saved_date = result["pulse_result"]["date"]
    progress_callback(1, 1, f"완료 ({saved_date})")
    return saved_date
```

---

## 5. 프론트엔드 설계

### 5.1 라우트
```
webapp-ui/app/(dashboard)/briefings/
├── page.tsx                      # 리스트 (SSR)
├── [date]/page.tsx               # 상세 (SSR)
└── jobs/[id]/page.tsx            # Job 진행률
```

### 5.2 사이드바 변경
`webapp-ui/components/layout/sidebar.tsx` ITEMS 배열에 "콘텐츠" 다음 삽입:
```ts
{ href: "/briefings", label: "브리핑" },
```

### 5.3 컴포넌트 (`components/domain/briefing/`)

| 컴포넌트 | 역할 | 주요 props |
|---|---|---|
| `briefings-table.tsx` | 리스트 테이블 + 페이지네이션 | `data: BriefingListResponse` |
| `briefing-summary-row.tsx` | 단일 행 (날짜 링크 / 점수 / 시그널 배지 / 종합판단 ✓/✗) | `item: BriefingSummary` |
| `briefing-hero-card.tsx` | 상세 헤더 (날짜 + Pulse 점수 + 시그널 + 생성시각 + daily_result_msg) | `detail: BriefingDetail` |
| `briefing-synthesis-section.tsx` | 종합 판단 마크다운 렌더 (prose) | `synthesis: string \| null` |
| `briefing-commentary-section.tsx` | AI 해설 마크다운 | `commentary: string \| null` |
| `briefing-news-section.tsx` | 장 후 뉴스 기사 리스트 | `news: { articles: Array<{title: string, url?: string}> }` |
| `briefing-post-analysis-section.tsx` | 사후 분석 (senior_synthesis + blind_spots 필드) | `postAnalysis: Record<string, any> \| null` |
| `briefing-feedback-section.tsx` | 피드백 컨텍스트 요약 + 전일 결과 메시지 | `feedbackContext: Record<string, any> \| null, dailyResultMsg: string` |
| `briefing-raw-messages.tsx` | 텔레그램 원본 메시지 (quant_msg + synth_msg) `<details>` 접힘 | `quantMsg: string, synthMsg: string` |
| `run-briefing-button.tsx` | "지금 실행" 버튼 + 오늘 이력 있으면 `RunConfirmModal` 표시 | `latestToday: BriefingSummary \| null` |
| `briefing-job-progress.tsx` | Job 진행률 + 장기 실행 안내. result_ref 가 YYYYMMDD 면 `/briefings/{date}` replace | `jobId: string` |
| `no-briefings.tsx` | 빈 상태 (전체 없음 / 필터 결과 없음) | `onRun?: () => void` |

각 마크다운 섹션은 Content 에서 만든 `ReportMarkdownView` (`react-markdown + remark-gfm + prose`) 를 래핑 — 별도 MD 렌더러 불필요.

### 5.4 페이지 구성

**`/briefings`** (리스트)
```
[h1: 브리핑]   [RunBriefingButton]
[BriefingsTable]
 ┌────────────┬────────┬──────────┬──────┐
 │ 날짜        │ 점수   │ 시그널    │ 종합 │
 ├────────────┼────────┼──────────┼──────┤
 │ 2026-04-21 │ +42.3  │ 강세     │ ✓    │ → /briefings/20260421
 │ 2026-04-20 │ -15.0  │ 중립     │ ✓    │
 │ 2026-04-19 │ ...    │ ...      │ ✗    │
[페이지네이션]
```
- 빈 상태 → `<NoBriefings onRun=... />`

**`/briefings/[date]`** (상세)
```
[← 브리핑 목록]
[BriefingHeroCard]

## 종합 판단
[BriefingSynthesisSection — synthesis markdown]

## AI 해설
[BriefingCommentarySection — commentary markdown]

## 장 후 뉴스
[BriefingNewsSection — article titles + links]

## 사후 분석
[BriefingPostAnalysisSection]

## 피드백 컨텍스트
[BriefingFeedbackSection]

<details><summary>텔레그램 메시지 원문</summary>
[BriefingRawMessages]
</details>
```
- 섹션 데이터 없으면 "생성되지 않음" placeholder
- 404 (저장 없음) → `notFound()` (`ApiError.status === 404` 감지, Content 패턴 동일)
- 기본 전부 펼친 상태 (독서용)

**`/briefings/jobs/[id]`** (Job 진행)
- `<BriefingJobProgress jobId={id} />`
- 긴 실행 안내: "RSS + 정량분석 + AI Commentary + Senior Synthesis 로 3~10분 소요됩니다. 브라우저 닫아도 백그라운드에서 계속 실행됩니다."
- 완료 시 result_ref 정규식 매칭(`^\d{8}$`) → `/briefings/{date}` replace, 아니면 `/briefings` fallback
- 실패 시 에러 + "돌아가기" → `/briefings`

### 5.5 "지금 실행" 상호작용

```
사용자 → RunBriefingButton 클릭
 → 오늘 이력 있으면 RunConfirmModal 표시
    (재사용: webapp-ui/components/domain/market/run-confirm-modal.tsx)
 → 확인 또는 이력 없음 → POST /api/v1/briefings/run {date: null}
 → 응답 { job_id, reused }
 → router.push(`/briefings/jobs/${job_id}`)
 → 폴링 → 완료 → /briefings/{saved_date} redirect
```

**결정:** `RunConfirmModal` 은 Market Pulse 에서 만든 컴포넌트 그대로 import 해서 사용. 범용 이름 (`existingSavedAt`, `onConfirm`, `onCancel`) 이라 Briefing 용으로 수정 불필요.

### 5.6 마크다운 렌더

Content 작업에서 `react-markdown + remark-gfm + @tailwindcss/typography` 이미 설치됨. 추가 설치 불필요.

---

## 6. 데이터 모델

### 신규 저장소

**파일 `alphapulse/core/storage/briefings.py`**:

```sql
CREATE TABLE IF NOT EXISTS briefings (
    date TEXT PRIMARY KEY,           -- YYYYMMDD
    payload TEXT,                    -- JSON: orchestrator.run_async() 반환 dict
    created_at REAL                  -- 저장 시각 (UPSERT 시 갱신)
);
```

**`BriefingStore` 인터페이스:**
```python
class BriefingStore:
    def __init__(self, db_path: Path | str) -> None: ...

    def save(self, date: str, payload: dict) -> None:
        """UPSERT. payload 안 numpy 타입은 json.dumps(default=...) 로 sanitize."""

    def get(self, date: str) -> dict | None:
        """{date, payload: dict, created_at: float} 또는 None."""

    def get_recent(self, days: int = 30) -> list[dict]:
        """날짜 DESC 정렬, 최대 days 건."""
```

### Config 변경

`alphapulse/core/config.py`:
```python
self.BRIEFINGS_DB = self.DATA_DIR / "briefings.db"
```

### Orchestrator 수정

`alphapulse/briefing/orchestrator.py` `run_async()` 말미 (현재 `return result_dict` 직전):

```python
# 저장 — 실패해도 메인 흐름 중단 금지
try:
    from alphapulse.core.storage.briefings import BriefingStore
    store = BriefingStore(self.config.BRIEFINGS_DB)
    await asyncio.to_thread(
        store.save,
        pulse_result["date"],
        result_dict,
    )
except Exception as e:
    logger.warning(f"Briefing 저장 실패: {e}")
```

`result_dict` 는 기존에 return 하던 10-키 dict. 저장 + 기존 return 둘 다 수행.

### Job 저장소 (기존 재사용)

`JobKind` 에 `"briefing"` 추가. 기존 `find_running_by_kind_and_date(kind, date)` 그대로 사용 (Market Pulse 에서 이미 만듦).

### numpy 타입 sanitize

`BriefingStore.save()` 내부:
```python
def save(self, date: str, payload: dict) -> None:
    safe = json.loads(json.dumps(
        payload,
        default=lambda o: float(o) if hasattr(o, "__float__") else str(o),
    ))
    with sqlite3.connect(self.db_path) as conn:
        conn.execute(
            "INSERT INTO briefings (date, payload, created_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "payload=excluded.payload, created_at=excluded.created_at",
            (date, json.dumps(safe, ensure_ascii=False), time.time()),
        )
```

---

## 7. 테스트 전략

### 7.1 백엔드 (pytest, TDD)

**`tests/core/storage/test_briefings.py`**
- 빈 DB 에서 `get` → None
- `save` 후 `get` 일치
- 같은 date 재 save → upsert (새 payload 로 덮어쓰기)
- `get_recent(30)` 날짜 DESC 정렬
- numpy float 포함 payload → sanitize 후 저장 + round-trip 동일

**`tests/webapp/api/test_briefing.py`**
- 인증 필요 (401)
- GET `/briefings` empty, with items, pagination
- GET `/briefings/latest` null / returns most recent
- GET `/briefings/{date}` 정상 / 404 / 잘못된 포맷 → 422
- POST `/run` — Job 생성, reused 반환, audit 로그
- 중복 같은 date running → reused=true

**`tests/webapp/services/test_briefing_runner.py`**
- `BriefingOrchestrator.run_async` mock → `send_telegram=False` 확인
- return value 가 `pulse_result.date` 문자열
- progress_callback 호출 순서 (시작 → 완료)
- 예외 전파 (Job failed 로 마킹됨)

**`tests/briefing/test_orchestrator_save.py`**
- `run_async` 완료 후 `BriefingStore.save` 호출 검증
- `save` 실패해도 `run_async` 는 정상 return 완료 (try/except 보호)

### 7.2 프론트엔드 (Playwright E2E)

**`webapp-ui/e2e/briefings.spec.ts`**
- 로그인 → `/briefings` 로드 → 리스트 또는 빈 상태 렌더
- 사이드바 "브리핑" 진입점
- "지금 실행" 버튼 렌더

장기 실행 Job 실제 돌리지 않음 (CI 에 부적합).

### 7.3 회귀
- 기존 1100+ 테스트 그대로 PASS
- 신규 pytest 약 20~25건 + E2E 1 스펙

---

## 8. 파일 구조 요약

### 신규 (백엔드)
```
alphapulse/core/storage/briefings.py
alphapulse/webapp/api/briefing.py
alphapulse/webapp/services/briefing_runner.py
tests/core/storage/test_briefings.py
tests/webapp/api/test_briefing.py
tests/webapp/services/test_briefing_runner.py
tests/briefing/test_orchestrator_save.py
```

### 신규 (프론트엔드)
```
webapp-ui/app/(dashboard)/briefings/page.tsx
webapp-ui/app/(dashboard)/briefings/[date]/page.tsx
webapp-ui/app/(dashboard)/briefings/jobs/[id]/page.tsx
webapp-ui/components/domain/briefing/briefings-table.tsx
webapp-ui/components/domain/briefing/briefing-summary-row.tsx
webapp-ui/components/domain/briefing/briefing-hero-card.tsx
webapp-ui/components/domain/briefing/briefing-synthesis-section.tsx
webapp-ui/components/domain/briefing/briefing-commentary-section.tsx
webapp-ui/components/domain/briefing/briefing-news-section.tsx
webapp-ui/components/domain/briefing/briefing-post-analysis-section.tsx
webapp-ui/components/domain/briefing/briefing-feedback-section.tsx
webapp-ui/components/domain/briefing/briefing-raw-messages.tsx
webapp-ui/components/domain/briefing/run-briefing-button.tsx
webapp-ui/components/domain/briefing/briefing-job-progress.tsx
webapp-ui/components/domain/briefing/no-briefings.tsx
webapp-ui/e2e/briefings.spec.ts
```

### 수정
```
alphapulse/core/config.py                     # BRIEFINGS_DB 상수
alphapulse/core/storage/__init__.py           # BriefingStore 재수출
alphapulse/briefing/orchestrator.py           # run_async 말미 save 추가
alphapulse/webapp/jobs/models.py              # JobKind 에 "briefing"
alphapulse/webapp/main.py                     # briefing_store state + briefing_router
webapp-ui/components/layout/sidebar.tsx       # "브리핑" 항목
```

---

## 9. 위험 요소 & 의존성

| 항목 | 위험 | 완화 |
|---|---|---|
| 긴 실행 시간 (3~10분) | 브라우저 닫혀도 Job 계속 실행되어야 | FastAPI BackgroundTasks 는 응답 후 분리. JobRepository 가 상태 유지. 프론트에 "닫아도 됨" 명시 |
| 외부 의존성 부분 실패 (Gemini, KRX, FRED, Investing, News) | 필드 누락 | Orchestrator 내부 try/except 로 fallback. 누락 필드는 None/빈 dict 로 저장. 프론트는 `?? null` 처리 |
| CLI daemon + 웹 Job 동시 실행 (같은 date) | 중복 AI 크레딧 소모 | `find_running_by_kind_and_date` 체크. 단 daemon 은 Job 테이블 사용 안 함 → race 가능. 매일 1회 daemon 이므로 low risk. 웹은 적극 감지 |
| payload 크기 | ~50KB/건, 365일 × 365 = 18MB | SQLite 문제없음 |
| orchestrator save 추가로 기존 테스트 깨짐 | `try/except` 로 save 실패 허용 | 신규 테스트 `test_orchestrator_save.py` 로 save 호출 검증 + 실패해도 main 흐름 완료 검증 |
| numpy 타입 sanitize 누락 | pulse_result.indicator_scores 에 numpy float | `BriefingStore.save` 내부에서 `json.dumps(default=...)` 적용 |
| 과거 CLI 실행분 백필 불가 | 이전 브리핑 볼 수 없음 | 수용 — 앞으로 쌓일 데이터로 충분. spec 명시 |

---

## 10. 결정 요약

| 항목 | 선택 | 이유 |
|---|---|---|
| 실행 방식 | Viewer + Runner (Job 기반) | Market Pulse / Content 일관성 |
| 페이지 구조 | 리스트 + 상세 + Job 3-page | 익숙한 패턴 |
| 저장소 | 신규 `briefings.db` SQLite (옵션 A1) | 쿼리 빠름, webapp 패턴 |
| 저장 범위 | payload 전체 10 필드 | 재실행 비용 >> 저장 비용 |
| 중복 Job 정책 | date 기반 reuse (Market Pulse 재사용) | 기존 헬퍼 재활용 |
| 덮어쓰기 확인 | 프론트 `RunConfirmModal` (Market Pulse 컴포넌트 재사용) | API 단순 |
| 텔레그램 발송 | 웹 Job 은 항상 `send_telegram=False` | Content 와 동일, 스팸 방지 |
| 상세 레이아웃 | 단일 세로 스크롤 + 섹션 헤더 + `<details>` 접기 | 독서용, tab 보다 scannable |
| 마크다운 렌더 | Content 에서 설치한 `react-markdown + remark-gfm` 재사용 | 의존성 추가 없음 |
| `BriefingStore` 위치 | `alphapulse/core/storage/` | `PulseHistory` 와 같은 층 |
| Orchestrator save 위치 | `run_async` 말미 `try/except` | CLI daemon + 웹 공통, 실패해도 main 흐름 유지 |
| JobRunner 수정 | 없음 | Content 에서 이미 coroutine 분기 추가됨 |
| `find_running_by_kind_and_date` 재사용 | Market Pulse 헬퍼 그대로 | 신규 헬퍼 불필요 |

---

## 11. 향후 사이클 (별도 spec)

- **AI Commentary 도메인** — 전용 commentary 뷰어 (Briefing 상세에도 포함되지만 개별 commentary 비교 / 이력은 별도 제공 가능)
- **Feedback 도메인** — 적중률 시각화 + 사후 분석 상세 (Briefing `feedback-section` 은 텍스트 요약만)
- **홈 대시보드 최신 Briefing 위젯** — 오늘/어제 요약 카드
- **Briefing 비교 뷰** — 두 날짜 side-by-side

Briefing 패턴(JSON payload store + 섹션별 뷰어)을 Feedback / Commentary 에도 재사용 가능.
