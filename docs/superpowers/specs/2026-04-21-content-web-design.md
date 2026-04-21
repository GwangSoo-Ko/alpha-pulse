# Content/BlogPulse 웹 대시보드 — 설계 문서

**작성일:** 2026-04-21
**스코프:** AlphaPulse 웹 UI 에 `content` 도메인 추가 (Phase 3 두 번째 도메인, Market Pulse 이후)
**후속:** Daily Briefing / AI Commentary / Feedback 은 별도 spec 사이클

---

## 1. 목적 & 배경

현재 `alphapulse/content/` (BlogPulse) 모듈은 CLI (`ap content monitor`) 전용으로만 실행되고, 분석 결과는 `./reports/*.md` 마크다운 파일로만 저장된다. 파일 시스템에 쌓인 리포트를 훑어보거나 카테고리·날짜로 필터링할 수단이 없다.

본 spec 은 웹 UI 에 **Content 도메인** 을 추가하여:
- 기존 리포트(`./reports/*.md`)를 리스트 + 필터 + 상세 마크다운 렌더로 조회
- "지금 실행" 버튼으로 `BlogMonitor.run_once()` 를 Job 으로 트리거 (텔레그램 발송 off)
- Market Pulse 와 동일한 Viewer + Runner 패턴 유지

---

## 2. 스코프

### 포함 (이번 사이클)
- `/content` — 리포트 리스트 (페이지네이션 + 카테고리 다중 필터 + 날짜 range + 제목 검색)
- `/content/reports/[filename]` — 단일 리포트 상세 (마크다운 본문 렌더)
- `/content/jobs/[id]` — BlogMonitor 실행 Job 진행률
- FastAPI 라우터 `alphapulse/webapp/api/content.py`
- Job 어댑터 `alphapulse/webapp/api/content_runner.py` — `BlogMonitor.run_once(send_telegram=False)` 호출
- 리포트 리더 `alphapulse/webapp/store/readers/content.py` — 디렉토리 스캔 + YAML frontmatter 파싱
- JobRunner 확장 — async coroutine 함수 지원
- 사이드바 "콘텐츠" 항목 추가
- E2E 스모크 (Playwright)

### 제외 (YAGNI / 후속 사이클)
- TelegramChannelMonitor 웹 노출 — 세션 유지 + 실시간 스트리밍, 웹 부적합
- 데몬 시작/정지 웹 제어
- `force_latest=N` 재처리 옵션 (CLI 전용)
- 리포트 삭제/편집 — 읽기 전용
- SQLite 인덱스 (`content.db`) — 파일 수천 개 넘으면 후속 마이그레이션
- AI 분석 재실행 기능
- 리포트 내 풀텍스트 검색 — 제목 부분일치만
- 홈 대시보드 Content 위젯

---

## 3. 아키텍처

### 레이어 구조
```
┌──────────────────────────────────────────┐
│ Frontend (Next.js 15 App Router)         │
│  webapp-ui/app/(dashboard)/content/      │
│  webapp-ui/components/domain/content/    │
└───────────────┬──────────────────────────┘
                │ SSR fetch / client mutate
                ▼
┌──────────────────────────────────────────┐
│ FastAPI router                           │
│  alphapulse/webapp/api/content.py        │
│  alphapulse/webapp/api/content_runner.py │
└───────┬──────────────────┬───────────────┘
        │ read             │ run
        ▼                  ▼
┌────────────────┐  ┌──────────────────────┐
│ ContentReader  │  │ BlogMonitor (async)  │
│ (파일 스캔 +   │  │ - detector/crawler/  │
│  YAML 파싱)    │  │   analyzer/reporter  │
└───────┬────────┘  └──────────────────────┘
        │
        ▼
┌────────────────┐
│ ./reports/*.md │ ← ReportWriter 가 BlogMonitor 내부에서 저장
└────────────────┘
```

### Sync/Async 경계 (CLAUDE.md 준수)
- `alphapulse/content/` 는 **ASYNC only** (`.claude/rules/async-modules.md`)
- `BlogMonitor.run_once()` 는 `async def`
- 현재 `JobRunner.run()` 은 sync 함수 전제 → `asyncio.to_thread(func, *args)` 호출
- **JobRunner 확장 필요:** coroutine function 여부 감지해서 분기
  ```python
  import inspect
  if inspect.iscoroutinefunction(func):
      result = await func(*args, **kwargs)
  else:
      result = await asyncio.to_thread(func, *args, **kwargs)
  ```

### 데이터 흐름

**조회 (99% 경로)**
```
사용자 → /content?page=1&category=경제 접속
 → SSR: GET /api/v1/content/reports?page=1&category=경제
 → ContentReader: os.scandir(REPORTS_DIR) → *.md 만 필터
 → 각 파일 head 20 줄 읽어 YAML frontmatter 파싱
 → 메모리에서 필터(카테고리/날짜/검색) → 정렬 → 페이지네이션
 → 렌더: ReportsTable
```

**상세 조회**
```
사용자 → /content/reports/{filename} 접속
 → SSR: GET /api/v1/content/reports/{filename}
 → 파일명 검증 (.md 확장자, path traversal 차단)
 → 파일 전체 읽기 → frontmatter + body 분리
 → 응답: {metadata 필드들, body: markdown}
 → ReportMarkdownView: react-markdown + remark-gfm 렌더
```

**실행 (임시 경로)**
```
사용자 → "지금 실행" 클릭
 → POST /api/v1/content/monitor/run {}
 → 중복 Job (kind="content_monitor", pending/running) 있으면 reused=true 반환
 → 없으면 새 Job 생성, BackgroundTasks 에서 BlogMonitor.run_once(send_telegram=False) 실행
 → Job 완료 시 result_ref 에 "처리 N개, 스킵 M개" 같은 요약 저장
 → 프론트: /content/jobs/{id} 폴링 → 완료 → /content 로 replace
```

---

## 4. API 설계

베이스: `/api/v1/content`
인증: 모든 엔드포인트 `get_current_user` 필수

### 4.1 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/content/reports` | 리포트 리스트 (페이지네이션 + 필터) |
| GET | `/content/reports/{filename}` | 단일 리포트 상세 |
| POST | `/content/monitor/run` | BlogMonitor Job 시작 |
| GET | `/jobs/{job_id}` | Job 상태 폴링 (기존 재사용) |

### 4.2 요청 파라미터 (리스트)

```
GET /content/reports?
    page=1          (ge=1, default 1)
    size=20         (ge=1, le=100, default 20)
    category=경제    (optional, 다중 반복 가능 — category=경제&category=주식)
    from=20260301   (optional, YYYYMMDD, published 기준)
    to=20260331     (optional, YYYYMMDD, 포함)
    q=검색어         (optional, max 200자, 제목 부분일치 case-insensitive)
    sort=newest     (newest | oldest, default newest; analyzed_at 기준)
```

### 4.3 응답 스키마

```python
class ReportSummary(BaseModel):
    filename: str          # URL-safe path 파라미터
    title: str             # frontmatter.title (없으면 파일명 stem)
    category: str          # frontmatter.category (없으면 "미분류")
    published: str         # frontmatter.published (빈 문자열 가능)
    analyzed_at: str       # frontmatter.analyzed_at (없으면 파일 mtime)
    source: str            # frontmatter.source (원문 URL)
    source_tag: str = ""   # frontmatter.source_tag (텔레그램 채널 등)

class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    page: int
    size: int
    total: int
    categories: list[str]  # 현재 reports/ 디렉토리 전체에서 추출한 고유 카테고리

class ReportDetail(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str = ""
    body: str              # frontmatter 제거 후 순수 마크다운 본문

class MonitorRunRequest(BaseModel):
    pass                   # 이번 사이클은 파라미터 없음 (force_latest 는 CLI 전용)

class MonitorRunResponse(BaseModel):
    job_id: str
    reused: bool
```

### 4.4 파일명 검증 (보안)

```python
def _validate_filename(name: str) -> str:
    if not name.endswith(".md"):
        raise HTTPException(400, "Invalid filename — must end with .md")
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, "Invalid filename — path traversal not allowed")
    return name
```

### 4.5 에러 처리
| 상황 | 응답 |
|---|---|
| 인증 실패 | 401 |
| `GET /reports/{filename}` 파일 없음 | 404 `{detail: "Report not found"}` |
| path traversal 시도 | 400 |
| 비-.md 확장자 | 400 |
| Pydantic 검증 실패 (days/size 범위 등) | 422 |
| Job 내부 예외 | Job status=failed + error (200 응답) |

### 4.6 감사 로그
- `POST /content/monitor/run` → `AuditLogger.log("webapp.content.monitor.run", actor=user_id, data={job_id})`
- 조회는 감사 없음 (Phase 2 정책)

### 4.7 frontmatter 파싱 규약

- `---` 로 감싸진 첫 블록을 `yaml.safe_load()` 로 파싱
- 파싱 실패 또는 frontmatter 없음 → fallback:
  - `title=파일명 stem`
  - `category="미분류"`
  - `published=""`, `analyzed_at=파일 mtime`, `source=""`
- 에러는 `logger.warning` 으로만 기록 (스캔 계속)

---

## 5. 프론트엔드 설계

### 5.1 라우트
```
webapp-ui/app/(dashboard)/content/
├── page.tsx                                # 리스트 (SSR, URL 쿼리 기반)
├── reports/
│   └── [filename]/page.tsx                 # 상세
└── jobs/
    └── [id]/page.tsx                       # Job 진행률
```

### 5.2 사이드바 변경
`webapp-ui/components/layout/sidebar.tsx` ITEMS 배열에 "시황" 다음 삽입:
```ts
{ href: "/content", label: "콘텐츠" },
```

### 5.3 컴포넌트 (`components/domain/content/`)

| 컴포넌트 | 역할 | 주요 props |
|---|---|---|
| `reports-filter-bar.tsx` | 카테고리 체크박스 + 날짜 range + 검색 input + "지금 실행" 버튼 | `categories: string[]`, `current: FilterState` |
| `reports-table.tsx` | 리포트 테이블 + 페이지네이션 | `data: ReportListResponse`, `filters: FilterState` |
| `report-summary-row.tsx` | 단일 행 (제목 링크 / 카테고리 배지 / 날짜) | `item: ReportSummary` |
| `report-markdown-view.tsx` | `react-markdown` + `remark-gfm` 본문 렌더 | `body: string` |
| `run-content-button.tsx` | "지금 실행" 버튼 + POST + router.push | — |
| `content-job-progress.tsx` | Job 진행률 + 완료 시 `/content` replace | `jobId: string` |
| `no-reports.tsx` | 빈 상태 (전체 없음 or 필터 결과 없음) | `mode: "empty" \| "filtered"`, `onRun?` |

### 5.4 페이지 구성

**`/content`** (리스트)
```
[h1: 콘텐츠]
[ReportsFilterBar: 카테고리(체크박스) | 날짜 range | 검색 input | "지금 실행" 버튼]
[ReportsTable: 제목 | 카테고리 | 발행일 | 분석시각 | (→)]
[페이지네이션]
```
- 빈 상태:
  - `total=0 && 필터 없음` → `<NoReports mode="empty" onRun=... />`
  - `total=0 && 필터 있음` → `<NoReports mode="filtered" />`

**`/content/reports/[filename]`** (상세)
```
[← 콘텐츠 목록으로 (BackLink)]
[제목 h1]
[메타: 카테고리 배지 · 발행일 · 분석시각 · 원문 링크]
[ReportMarkdownView: prose 스타일 + react-markdown + remark-gfm]
```
- 404 → Next.js `notFound()`
- 에러 처리: `ApiError.status === 404` 감지

**`/content/jobs/[id]`**
- `<ContentJobProgress jobId={id} />`
- 완료 → `/content` 로 replace
- 실패 → 에러 메시지 + "돌아가기" 버튼

### 5.5 필터 상태 관리 (URL 쿼리 기반)

```tsx
// ReportsFilterBar 내부
const router = useRouter()
const searchParams = useSearchParams()

const updateFilter = (next: FilterState) => {
  const params = new URLSearchParams()
  if (next.page > 1) params.set("page", String(next.page))
  next.categories.forEach((c) => params.append("category", c))
  if (next.from) params.set("from", next.from)
  if (next.to) params.set("to", next.to)
  if (next.q) params.set("q", next.q)
  if (next.sort !== "newest") params.set("sort", next.sort)
  router.push(`/content?${params}`)
}
```

- 필터 변경 → URL 업데이트 → SSR 재실행
- 딥링크 공유 가능

### 5.6 "지금 실행" 상호작용

```
사용자 → "지금 실행" 클릭
 → apiMutate("/api/v1/content/monitor/run", "POST", {})
 → 응답 { job_id, reused }
 → router.push(`/content/jobs/${job_id}`)
 → (reused 여부 무관하게 Job 페이지 이동 — 유저는 같은 job 진행 관찰)
 → 폴링 → 완료 → /content 로 replace
```

### 5.7 마크다운 렌더링

새 의존성 추가:
```bash
pnpm add react-markdown remark-gfm @tailwindcss/typography
```

`webapp-ui/tailwind.config.ts` 에 plugin 추가:
```ts
plugins: [require("@tailwindcss/typography")]
```

사용:
```tsx
<article className="prose prose-invert max-w-none">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
</article>
```

XSS 안전성: `rehype-raw` 미사용 → HTML 태그는 escape 됨. 마크다운만 렌더.

---

## 6. 데이터 모델

### 변경 없음 (파일시스템 그대로)
- `./reports/*.md` — `ReportWriter._build_report()` 포맷 (YAML frontmatter + 마크다운)
- `STATE_FILE` — seen_ids JSON (BlogMonitor 가 관리)

### Job 저장소 (Phase 2 재사용)
- `JobKind` 에 `"content_monitor"` 추가
- `params`: `{}` (이번 사이클 빈 객체)
- 중복 감지: `find_running_by_kind_and_date` 대신 새 헬퍼 `find_running_by_kind(kind)` 필요
  - Market Pulse 는 date 기반이었지만 Content 는 단순 kind 기반
  - **신규 메서드:** `JobRepository.find_running_by_kind(kind: JobKind) -> Job | None`
- 완료 시 `result_ref` 에 `"처리 N개, 스킵 M개"` 요약 문자열 저장

### ContentReader 인터페이스

```python
class ContentReader:
    def __init__(self, reports_dir: Path): ...

    def list_reports(
        self,
        *,
        categories: list[str] | None = None,   # None = all
        date_from: str | None = None,           # YYYYMMDD, published 기준
        date_to: str | None = None,
        query: str | None = None,               # 제목 부분일치
        sort: Literal["newest", "oldest"] = "newest",
        page: int = 1,
        size: int = 20,
    ) -> PageResult[ReportMeta]: ...

    def get_report(self, filename: str) -> ReportFull | None: ...

    def distinct_categories(self) -> list[str]: ...
```

`ReportMeta` 은 frontmatter 파싱 결과 + filename. `ReportFull` 은 ReportMeta + body.

---

## 7. 테스트 전략

### 7.1 백엔드 (pytest, TDD)

**`tests/webapp/store/readers/test_content_reader.py`**
- 디렉토리 스캔 (빈 디렉토리, .md 만, 기타 파일 skip)
- frontmatter 정상 파싱
- frontmatter 없는 파일 → 파일명 fallback
- frontmatter 깨진 YAML → 경고 + fallback
- 카테고리 다중 필터 (OR 조건)
- 날짜 range 필터
- 제목 검색 case-insensitive
- 정렬 (newest / oldest)
- 페이지네이션
- `distinct_categories` 반환값

**`tests/webapp/api/test_content_api.py`**
- 인증 필요 (401)
- GET /reports 페이지네이션, 필터 쿼리
- GET /reports/{filename} — 정상, 404, path traversal 차단 (400), 비-.md 차단
- POST /monitor/run — Job 생성, `reused` 플래그, audit 로그
- Job kind 중복 reuse 동작

**`tests/webapp/services/test_content_runner.py`**
- `BlogMonitor` mock → `run_once(send_telegram=False)` 호출 확인
- 예외 전파 (Job failed)
- result_ref 포맷 검증

**`tests/webapp/store/test_jobs_find_running_by_kind.py`**
- 신규 메서드 스모크 (date 무관, kind 기반)

**`tests/webapp/jobs/test_runner_coroutine.py`**
- JobRunner 가 coroutine function 을 `await` 로 호출하는지 검증
- sync function 은 기존대로 `asyncio.to_thread`

### 7.2 프론트엔드 (Playwright E2E)

**`webapp-ui/e2e/content.spec.ts`**
- 로그인 → `/content` 로 이동 → 리스트 또는 빈 상태 렌더
- 카테고리 체크박스 클릭 → URL 쿼리 변경 확인
- 리포트 행 클릭 → 상세 페이지 이동 → 마크다운 렌더 확인
- "지금 실행" 클릭 → Job 페이지 이동 확인

### 7.3 회귀 방지
- 기존 1105+ 테스트 그린 유지
- 신규 pytest 약 20~25건, E2E 1 스펙

---

## 8. 파일 구조 요약

### 신규
```
alphapulse/webapp/api/content.py
alphapulse/webapp/api/content_runner.py
alphapulse/webapp/store/readers/content.py
tests/webapp/api/test_content_api.py
tests/webapp/services/test_content_runner.py
tests/webapp/store/readers/test_content_reader.py
tests/webapp/store/test_jobs_find_running_by_kind.py
tests/webapp/jobs/test_runner_coroutine.py

webapp-ui/app/(dashboard)/content/page.tsx
webapp-ui/app/(dashboard)/content/reports/[filename]/page.tsx
webapp-ui/app/(dashboard)/content/jobs/[id]/page.tsx
webapp-ui/components/domain/content/reports-filter-bar.tsx
webapp-ui/components/domain/content/reports-table.tsx
webapp-ui/components/domain/content/report-summary-row.tsx
webapp-ui/components/domain/content/report-markdown-view.tsx
webapp-ui/components/domain/content/run-content-button.tsx
webapp-ui/components/domain/content/content-job-progress.tsx
webapp-ui/components/domain/content/no-reports.tsx
webapp-ui/e2e/content.spec.ts
```

### 수정
```
alphapulse/webapp/main.py                            # content_router + app.state.content_reader
alphapulse/webapp/jobs/models.py                     # JobKind 에 "content_monitor"
alphapulse/webapp/jobs/runner.py                     # coroutine function 지원
alphapulse/webapp/store/jobs.py                      # find_running_by_kind 헬퍼
webapp-ui/components/layout/sidebar.tsx              # "콘텐츠" 항목
webapp-ui/package.json                               # react-markdown + remark-gfm + @tailwindcss/typography
webapp-ui/tailwind.config.ts                         # typography plugin
```

---

## 9. 위험 요소 & 의존성

| 항목 | 위험 | 완화 |
|---|---|---|
| JobRunner sync-only 전제 | `BlogMonitor.run_once()` 는 async → 기존 `asyncio.to_thread(func)` 미호환 | `inspect.iscoroutinefunction()` 분기로 coroutine 지원 (전용 테스트 추가) |
| REPORTS_DIR 경로 주입 | webapp 이 `Config().REPORTS_DIR` 몰라 에러 | main.py 에서 `app.state.content_reader = ContentReader(Config().REPORTS_DIR)` 로 주입 |
| 한글 파일명 URL 인코딩 | 깨진 링크 가능성 | Next.js Link href 자동 인코딩, FastAPI path 자동 디코딩, 테스트에 한글 파일명 케이스 포함 |
| pyyaml 의존성 | 이미 설치됨 (6.0.3) | 추가 작업 없음 |
| react-markdown XSS | 사용자 제공 마크다운 렌더 | `rehype-raw` 미사용 → HTML 태그 escape. `react-markdown` 기본값 안전 |
| 빠른 성장 (수천 파일) | 매 요청 파일 스캔 → 응답 지연 | 현재 규모 OK. 1000개 넘으면 후속 사이클에서 SQLite 인덱스 |
| BlogMonitor 외부 의존 (네이버 RSS, Gemini, crawl4ai) | 실행 실패 가능 | Job failed + error 표면화. CLI 도 같은 위험 |
| 동시 "지금 실행" race | 같은 kind running 감지 전에 두 Job 생성 가능 | kind 기반 중복 감지 + 후속 고유 인덱스는 YAGNI. Market Pulse 와 동일 수용 |

---

## 10. 결정 요약

| 항목 | 선택 | 이유 |
|---|---|---|
| 실행 방식 | Viewer + Runner (Job 기반) | Market Pulse 일관성 |
| 페이지 구조 | 리스트 중심 (3 페이지) | Content 는 피드 성격 |
| 저장소 | 파일 스캔 (YAGNI) | 현재 규모 충분 |
| 중복 Job 정책 | kind 기반 reuse | 날짜 개념 없는 연속 스트림 |
| 텔레그램 발송 | 웹 Job 은 `send_telegram=False` | 디버깅/재확인 시 스팸 방지 |
| `force_latest` 노출 | 하지 않음 (단일 "지금 실행" 버튼) | YAGNI |
| 마크다운 렌더 | react-markdown + remark-gfm + Tailwind prose | 경량, XSS 안전, 표준 |
| 필터 상태 | URL 쿼리 (server-driven) | SSR + 딥링크 |
| 사이드바 레이블 | "콘텐츠" | 향후 채널 확장 대비 |
| TelegramChannelMonitor | 제외 | 세션 유지 복잡, YAGNI |
| JobRunner 확장 | coroutine 감지 분기 | Content 가 async 이므로 기존 sync-only 전제 확장 필요 |
| 스키마 변경 | 없음 (파일 + Job 테이블 재사용) | — |

---

## 11. 향후 사이클 (별도 spec)

- **Daily Briefing 도메인** — 과거 브리핑 조회 + 수동 실행
- **AI Commentary 뷰어** — 일별 AI 해설 조회
- **Feedback 도메인** — 적중률 리포트 + 사후 분석

Content 패턴(리스트 + 상세 + Job)을 재사용 가능.

**Content 확장 (별도 사이클):**
- TelegramChannelMonitor 웹 통합 (WebSocket 이나 SSE 로 실시간 메시지 스트림)
- SQLite 인덱스 마이그레이션 (파일 수천 개 시)
- 풀텍스트 검색 (SQLite FTS5)
- 분석 재실행 기능
