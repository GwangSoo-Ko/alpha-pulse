# Market Pulse 웹 대시보드 — 설계 문서

**작성일:** 2026-04-21
**스코프:** AlphaPulse 웹 UI에 `market` 도메인 추가 (Phase 2 웹앱 위에 도메인 확장)
**후속:** Content / Briefing / Commentary / Feedback 도메인은 별도 spec 사이클

---

## 1. 목적 & 배경

현재 `alphapulse/market/`(Market Pulse, 11개 정량 지표)는 CLI 전용(`ap market pulse`)으로만 접근 가능하다. Phase 1/2에서 완성된 웹앱은 `trading` 도메인(Backtest/Screening/Portfolio/Risk/Data/Settings/Audit)만 커버한다.

본 spec은 웹 UI에 **Market Pulse 도메인**을 추가하여:
- CLI `ap market pulse/investor/program/sector/macro/fund/history` 를 대체할 수 있는 조회 UX 제공
- 이미 저장된 `PulseHistory` 를 시각화 (차트 + 카드)
- 필요 시 웹에서 직접 Job으로 재계산 (briefing 스케줄 외 임시 실행)

---

## 2. 스코프

### 포함 (이번 사이클)
- `/market/pulse` 메인 대시보드 — 최신 스코어 + 30/60/90일 히스토리 차트 + 11개 지표 카드
- `/market/pulse/[date]` 날짜별 상세 — 모든 지표 펼친 상태 + 이전/다음 날짜 네비게이션
- `/market/pulse/jobs/[id]` — 실행 Job 진행률 (Phase 2 `JobProgress` 재사용)
- FastAPI 라우터 `alphapulse/webapp/api/market.py` (5개 엔드포인트)
- Job 어댑터 `alphapulse/webapp/api/market_runner.py` — `SignalEngine.run()` → background ThreadPoolExecutor
- 사이드바에 "시황" 항목 추가
- E2E 스모크 테스트 (로그인 → 조회 → 실행 → 완료)

### 제외 (YAGNI / 후속 사이클)
- `period=weekly/monthly` 파라미터 — daily 고정
- 지표별 독립 페이지 (`/market/investor` 등) — 점수 카드로 대체
- 두 날짜 비교 뷰
- 실시간 자동 새로고침 (장 중 폴링)
- `PulseHistory` 테이블 스키마 변경 (details JSON 본문은 `indicator_descriptions` 키 추가로 확장)
- 시그널 알림 (Telegram 발송은 기존 `briefing` 이 담당)
- CLI `ap market report` HTML 완전 재현 — 웹 페이지 자체가 대체

---

## 3. 아키텍처

### 레이어 구조
```
┌──────────────────────────────────────────┐
│ Frontend (Next.js 15 App Router)         │
│  webapp-ui/app/(dashboard)/market/pulse/ │
│  webapp-ui/components/domain/market/     │
└───────────────┬──────────────────────────┘
                │ SSR fetch / client mutate
                ▼
┌──────────────────────────────────────────┐
│ FastAPI router                           │
│  alphapulse/webapp/api/market.py         │
│  alphapulse/webapp/api/market_runner.py  │
└───────┬──────────────────┬───────────────┘
        │ read             │ write/run
        ▼                  ▼
┌────────────────┐  ┌──────────────────────┐
│ PulseHistory   │  │ SignalEngine         │
│ (history.db,   │  │ (11개 analyzer +     │
│  읽기 + upsert)│  │  collectors)         │
└────────────────┘  └──────────────────────┘
```

### Sync/Async 규칙 준수
- `alphapulse/market/` 는 **sync only** (CLAUDE.md 규칙)
- FastAPI 라우터는 `def` (async 아님) + 필요 시 `run_in_threadpool` 사용
- Job 실행은 기존 Phase 2 의 `ThreadPoolExecutor` 패턴 재사용 → 블로킹 `SignalEngine.run()` 을 백그라운드에서 실행

### 데이터 흐름
**조회 (99% 경로)**
```
사용자 → /market/pulse 접속
 → SSR: GET /api/v1/market/pulse/latest + /market/pulse/history?days=30
 → PulseHistory.get(today) + PulseHistory.get_recent(30) (DB-only, ~50ms)
 → 렌더: ScoreHeroCard + PulseHistoryChart + IndicatorGrid
```

**실행 (임시 경로)**
```
사용자 → "지금 실행" 클릭
 → 프론트: 오늘 이력 있으면 RunConfirmModal 표시 → 확인
 → POST /api/v1/market/pulse/run { date? }
 → 백엔드: 같은 date 의 running Job 있으면 기존 job_id 반환 (reused=true)
           없으면 새 Job 생성, ThreadPool 에 submit(SignalEngine.run)
 → 완료 시: PulseHistory.save() (upsert), Job status=done, result_date 기록
 → 프론트: /market/pulse/jobs/{id} 폴링 → 완료 → /market/pulse 로 복귀
```

---

## 4. API 설계

베이스: `/api/v1/market`
인증: 모든 엔드포인트 Phase 2 와 동일한 `session_dependency` 필수

### 4.1 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/market/pulse/latest` | 가장 최근 저장된 Pulse |
| GET | `/market/pulse/history?days=30` | 히스토리 시계열 (차트용) |
| GET | `/market/pulse/{date}` | 특정 날짜 상세 (YYYYMMDD) |
| POST | `/market/pulse/run` | 실행 Job 시작 |
| GET | `/market/pulse/jobs/{job_id}` | Job 상태 폴링 |

### 4.2 요청 스키마

```python
class RunPulseRequest(BaseModel):
    date: str | None = None   # YYYYMMDD, None 이면 직전 거래일
```

- `period`, `force` 는 **제거** (API 단순화).
  - period=daily 고정.
  - 덮어쓰기 확인은 프론트 책임 (서버는 요청 그대로 실행).

### 4.3 응답 스키마

```python
class PulseSnapshot(BaseModel):
    date: str
    score: float
    signal: str   # strong_bullish | moderately_bullish | neutral | moderately_bearish | strong_bearish
    indicator_scores: dict[str, float | None]  # 11개 key (없는 지표는 null)
    indicator_descriptions: dict[str, str | None]  # 11개 key, 사람이 읽는 설명. 과거 저장분은 null
    period: str   # "daily" (저장 시점의 period)
    created_at: float

class HistoryItem(BaseModel):
    date: str
    score: float
    signal: str

class HistoryResponse(BaseModel):
    items: list[HistoryItem]  # 날짜 오름차순 (차트 친화)

class RunPulseResponse(BaseModel):
    job_id: str
    reused: bool   # True = 기존 running Job 재사용

class JobStatusResponse(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    progress: float | None = None   # 0.0 ~ 1.0, 없으면 null
    result_date: str | None = None  # done 시 저장된 날짜
    error: str | None = None
    created_at: float
    updated_at: float
```

### 4.4 에러 처리
| 상황 | 응답 |
|---|---|
| 인증 실패 | 401 (기존 미들웨어) |
| `/pulse/{date}` 이력 없음 | 404 `{detail: "Pulse history not found for {date}"}` |
| `/pulse/latest` 전체 이력 없음 | 200 `null` (프론트가 NoSnapshot 렌더) |
| `POST /run` 검증 실패(잘못된 date) | 422 (Pydantic) |
| Job 내부 예외 | `status=failed` + `error` 메시지 (200 응답) |

### 4.5 감사 로그
`POST /market/pulse/run` 은 Phase 2 `AuditTrail` 패턴으로 기록:
- action: `market.pulse.run`
- actor: 로그인 사용자
- payload: `{date, job_id}`

---

## 5. 프론트엔드 설계

### 5.0 지표 카드 표시 범위

카드는 **접힌 상태 + 클릭 확장** 방식으로 두 단계 정보를 제공한다:

**접힌 상태 (기본)**
- 지표 한글명 (예: "외국인+기관 수급")
- 점수 숫자 (소수점 1자리, +/- 부호)
- 색상 바 (−100 ~ +100 구간을 5색으로 표시)

**펼친 상태 (클릭 후)**
- 위 내용 + `indicator_descriptions[key]` 의 analyzer 생성 문자열
  - 예: "외국인 +580억 | 기관 -220억 | 5일 외국인 +2,100억 | KOSPI 외국인 +580억..."
  - 예: "USD/KRW 1,385.2 (원화 약세, +0.42%)"
- 과거 저장분(`indicator_descriptions[key] == null`)은 "설명 저장 이전 날짜" 안내 표시

**확장 정책**
- 메인 대시보드: 기본 접힘, 사용자 클릭으로 개별 토글 (다중 펼침 허용)
- `/pulse/[date]` 상세: 기본 전부 펼침 (`expandAll=true`) — 읽기 위해 들어온 페이지이므로 펼침이 default
- 추가 API 호출 없음 — 모든 설명은 `PulseSnapshot.indicator_descriptions` 에 함께 옴

### 5.1 라우트
```
webapp-ui/app/(dashboard)/market/
└── pulse/
    ├── page.tsx              # 메인 대시보드 (SSR)
    ├── [date]/page.tsx       # 날짜 상세 (SSR)
    └── jobs/[id]/page.tsx    # Job 진행률
```

### 5.2 사이드바 변경
`webapp-ui/components/layout/sidebar.tsx` `ITEMS` 배열에 추가 (홈 다음):
```ts
{ href: "/market/pulse", label: "시황" },
```

### 5.3 컴포넌트 (`components/domain/market/`)

| 컴포넌트 | 역할 | 주요 props |
|---|---|---|
| `score-hero-card.tsx` | 최신 스코어 숫자 + 시그널 배지 + 계산 시각 + "지금 실행" 버튼 | `snapshot: PulseSnapshot \| null`, `showRunButton: boolean` |
| `pulse-history-chart.tsx` | recharts LineChart + 시그널 구간 색상, 30/60/90일 토글 | `items: HistoryItem[]`, `range: 30\|60\|90` |
| `indicator-grid.tsx` | 11개 지표 카드 그리드 (반응형 2-4열) | `scores: Record<string, number \| null>`, `descriptions: Record<string, string \| null>`, `expandAll?: boolean` |
| `indicator-card.tsx` | 개별 지표: 이름/점수/색상 바 + 클릭 시 설명 확장 | `name: string`, `koreanName: string`, `score: number \| null`, `description: string \| null`, `defaultExpanded?: boolean` |
| `run-confirm-modal.tsx` | "오늘 이미 계산됨 (HH:MM). 재실행?" 모달 | `existingSavedAt: number`, `onConfirm/onCancel` |
| `no-pulse-snapshot.tsx` | 빈 상태 (이력 없음) — 안내 + "지금 실행" CTA | `onRun?: () => void` |
| `date-picker-inline.tsx` | prev/next/최신 버튼 | `currentDate: string`, `availableDates: string[]` |

### 5.4 페이지 구성

**`/market/pulse`** (메인 대시보드)
```
[ScoreHeroCard: 최신]       [RunButton]
[PulseHistoryChart(30일)] [30/60/90 토글]
[IndicatorGrid (11개 지표 카드, 기본 접힘 + 클릭 확장)]
```
- 이력 전무 시: `<NoPulseSnapshot />` 렌더

**`/market/pulse/[date]`** (상세)
```
[DatePickerInline: prev | {date} | next | "최신"]
[ScoreHeroCard: 해당 날짜, RunButton 없음]
[IndicatorGrid (expandAll=true, 설명 전부 펼침)]
```
- 해당 날짜 이력 없음 → 404 (Next.js `notFound()`)
- `indicator_descriptions` 의 각 키가 null 이면 카드에 "설명 저장 이전 날짜 — '지금 실행' 으로 재계산하세요" 안내 노출

**`/market/pulse/jobs/[id]`** (진행)
- Phase 2 `JobProgress` 재사용
- 완료 시 redirect: `/market/pulse/{result_date}` (단, `result_date == 오늘` 이면 `/market/pulse` 로)

### 5.5 시그널 색상 매핑

기존 터미널 리포터와 동일한 5단계:
```ts
export const SIGNAL_STYLE: Record<string, { bar: string; badge: string; label: string }> = {
  strong_bullish:     { bar: "bg-green-500",   badge: "bg-green-500/20 text-green-300",   label: "강한 강세" },
  moderately_bullish: { bar: "bg-emerald-500", badge: "bg-emerald-500/20 text-emerald-300", label: "중립-강세" },
  neutral:            { bar: "bg-yellow-500",  badge: "bg-yellow-500/20 text-yellow-300", label: "중립" },
  moderately_bearish: { bar: "bg-orange-500",  badge: "bg-orange-500/20 text-orange-300", label: "중립-약세" },
  strong_bearish:     { bar: "bg-red-500",     badge: "bg-red-500/20 text-red-300",       label: "강한 약세" },
}
```

### 5.6 지표 한글 이름
`alphapulse/market/reporters/terminal.py` 의 `INDICATOR_NAMES` 를 그대로 참조 (중복 선언 방지를 위해 API 응답에 포함하거나, 프론트 `lib/market-labels.ts` 에 하드코딩).
→ **결정:** 프론트에 `lib/market-labels.ts` 로 복제 (작은 파일, 자주 바뀌지 않음). core/constants.py 의 `INDICATOR_NAMES` 와 동일하게 유지.

### 5.7 "지금 실행" 상호작용

```
사용자: RunButton 클릭
 → 오늘 이력 있으면: RunConfirmModal 표시
 → 확인 or 이력 없음: POST /api/v1/market/pulse/run
 → 응답 { job_id, reused }
    reused=true → 토스트 "이미 실행 중 (~분 전 시작)", job 페이지로 이동
    reused=false → 바로 job 페이지로 이동
 → /market/pulse/jobs/{id} 폴링 (3초 간격)
 → 완료 → /market/pulse 또는 /market/pulse/{result_date} 로 redirect
```

---

## 6. 데이터 모델

### 기존 재사용 (스키마 변경 없음)
- `PulseHistory` (`alphapulse/core/storage/history.py`) — `pulse_history` 테이블
  - PK: `date` (YYYYMMDD)
  - 필드: `score REAL, signal TEXT, details TEXT(JSON), created_at REAL`
  - 메서드: `save / get / get_range / get_recent`
  - **테이블 스키마 변경 없음.** `details` JSON 본문에 새 키 `indicator_descriptions` 추가 (하위 호환)

### SignalEngine 저장 payload 변경
`alphapulse/market/engine/signal_engine.py` `run()` 말미의 `self.history.save(...)` 호출에서 `details` dict 확장:
```python
# 기존
self.history.save(target_date, final_score, signal, {
    "indicator_scores": serializable_scores,
    "period": period,
})

# 변경 후
indicator_descriptions = {
    k: (v.get("details") if isinstance(v, dict) else None)
    for k, v in details.items()  # details는 각 analyzer의 전체 반환 dict
}
self.history.save(target_date, final_score, signal, {
    "indicator_scores": serializable_scores,
    "indicator_descriptions": indicator_descriptions,  # 신규
    "period": period,
})
```
- analyzer 의 반환 dict 중 `"details"` 문자열만 추출 (DataFrames 등 직렬화 불가 필드 제외)
- analyzer 가 실패해 `details["indicator_key"]` 가 없는 경우 `None`

### API 응답 빌더
`/pulse/{date}`, `/pulse/latest` 는 `PulseHistory.get()` 로 읽은 row 의 `details` JSON 을 언팩해 응답:
- `indicator_scores` — `details.indicator_scores` (없으면 `{}`)
- `indicator_descriptions` — `details.indicator_descriptions` (없으면 11 키 모두 `None` 인 dict, 즉 과거 저장분)
- `period` — `details.period` (없으면 `"daily"`)

### Job 저장소 (Phase 2 재사용)
`alphapulse.webapp.store.jobs` 의 Job 테이블 그대로 사용. 새 job kind 추가:
- `kind: "market_pulse"` — `params` 필드에 `{"date": "YYYYMMDD"}` 포함 (실제 Job 스키마 필드명 `params`, JSON TEXT)
- 중복 감지 쿼리: `WHERE kind='market_pulse' AND status IN ('queued','running') AND json_extract(params, '$.date') = ?`
- 완료 시 `result_date` 는 `params` 에 덮어쓰기 (현재 Job 스키마에 전용 result 필드 없음. 혹은 `progress_text` 마지막 값에 "saved=YYYYMMDD" 기록). **결정:** `params` JSON 에 `result_date` 키 추가 upsert.

### 새 스키마 없음
- PulseHistory 그대로 읽기 + upsert
- Job 테이블 재사용

---

## 7. 테스트 전략

### 7.1 백엔드 (pytest, TDD)

**`tests/webapp/api/test_market_api.py`**
- 인증 없으면 401
- `GET /latest` — 이력 없을 때 null 응답
- `GET /latest` — 이력 있을 때 최신 레코드 반환
- `GET /history?days=30` — 범위 반환, 오름차순
- `GET /pulse/{date}` — 존재 시 200, 없을 때 404
- `POST /run` — 새 Job 생성 → job_id 반환, reused=false
- `POST /run` — 동일 date running Job 있으면 reused=true, 같은 job_id
- `GET /jobs/{id}` — 상태별 응답 (queued/running/done/failed)

**`tests/webapp/api/test_market_runner.py`**
- `SignalEngine.run` mock → 성공 시 `PulseHistory.save` 호출 + Job done + result_date 기록
- `SignalEngine.run` 예외 → Job failed + error 메시지 저장
- 중복 감지 로직 단위 테스트

### 7.2 프론트엔드 (Playwright E2E)

**`webapp-ui/e2e/market-pulse.spec.ts`**
- 로그인 → `/market/pulse` 이동 → ScoreHeroCard 또는 NoPulseSnapshot 렌더 확인
- IndicatorGrid 렌더 (카드 11개 existence)
- "지금 실행" 클릭 → Job 페이지 이동 확인 (fake/stub backend)
- 차트 렌더 (recharts responsive container 존재 확인)

단위 테스트는 Phase 2 관례대로 생략 (E2E 중심).

### 7.3 회귀 방지
- 기존 857+ 테스트(Phase 2 기준) 그린 유지
- 신규 pytest 8~10건, E2E 1 스펙

---

## 8. 파일 구조 요약

### 신규
```
alphapulse/webapp/api/market.py
alphapulse/webapp/api/market_runner.py
tests/webapp/api/test_market_api.py
tests/webapp/api/test_market_runner.py

webapp-ui/app/(dashboard)/market/pulse/page.tsx
webapp-ui/app/(dashboard)/market/pulse/[date]/page.tsx
webapp-ui/app/(dashboard)/market/pulse/jobs/[id]/page.tsx
webapp-ui/components/domain/market/score-hero-card.tsx
webapp-ui/components/domain/market/pulse-history-chart.tsx
webapp-ui/components/domain/market/indicator-grid.tsx
webapp-ui/components/domain/market/indicator-card.tsx
webapp-ui/components/domain/market/run-confirm-modal.tsx
webapp-ui/components/domain/market/no-pulse-snapshot.tsx
webapp-ui/components/domain/market/date-picker-inline.tsx
webapp-ui/lib/market-labels.ts
webapp-ui/e2e/market-pulse.spec.ts
```

### 수정
```
alphapulse/webapp/app.py                            # market router 등록
alphapulse/market/engine/signal_engine.py           # history.save payload 에 indicator_descriptions 추가
webapp-ui/components/layout/sidebar.tsx             # "시황" 항목 추가
tests/market/engine/test_signal_engine.py           # (존재 시) save payload 스펙 검증 추가
```

---

## 9. 위험 요소 & 의존성

| 항목 | 위험 | 완화 |
|---|---|---|
| SignalEngine 외부 의존(KRX/FRED/Investing) | 장애 시 Job failed | 기존 briefing 과 동일한 위험, 신규 아님. Job 실패는 UI 에 error 메시지로 노출 |
| Job 실행 시간 30~60초 | 사용자가 오래 기다림 | 진행률 폴링(3초) + 명시 "최대 1분 소요" 안내 |
| history.db 경로 주입 | webapp config 에 `HISTORY_DB` 없으면 에러 | `Config.HISTORY_DB` 기본값 재사용 (기존 CLI 와 동일 경로) |
| 동시 실행 race condition | 같은 날짜 두 Job 동시 실행 시 중복 저장 (덮어쓰기는 idempotent 하지만 자원 낭비) | DB-level 체크 + INSERT 전 재확인. 완벽 배제 아니나 수용 가능 |
| SignalEngine save payload 변경 | 기존 테스트(`tests/market/engine/`)가 저장된 details 구조를 assertion 하면 깨질 수 있음 | 기존 키(`indicator_scores`, `period`) 유지 + 신규 키만 추가 (비파괴적). 관련 테스트 있으면 기대값 갱신 |
| 과거 이력 description 부재 | 이전 저장 날짜는 카드 펼쳐도 "설명 없음" | 프론트에 "재계산하세요" 안내. 기대 동작으로 문서화 |

---

## 10. 결정 요약

| 결정 사항 | 선택 | 이유 |
|---|---|---|
| 실행 주체 | Job 기반 (Viewer + Runner) | CLI 대체 목표 |
| 페이지 구조 | 메인 + 날짜 상세 + Job 3페이지 | Phase 2 스크리닝/백테스트 패턴 일관성 |
| 중복 실행 정책 | 기존 running Job 재사용 (reused 플래그) | Idempotent UX |
| 덮어쓰기 확인 | 프론트 모달 (서버 `force` 플래그 없음) | API 단순화 |
| 지표 표시 | 11개 카드 + 클릭 확장(설명 표시) | SignalEngine 에서 description 저장 → 카드 확장 시 인라인 표시 |
| 과거 저장분 처리 | description=null 로 응답, 프론트에 "재계산 요망" 안내 | 스키마 변경 없이 하위 호환 |
| period 지원 | daily 고정 | YAGNI |
| 지표별 독립 페이지 | 만들지 않음 | YAGNI, 탭/카드로 대체 |
| 스키마 변경 | 없음 | `PulseHistory` 재사용 |
| 차트 라이브러리 | recharts | 기존 사용 중 |

---

## 11. 향후 사이클 (별도 spec)

- **Content/BlogPulse 도메인** — 크롤링 이벤트 타임라인
- **Daily Briefing 도메인** — 과거 브리핑 조회 + 수동 실행
- **AI Commentary 뷰어** — 일별 AI 해설 조회
- **Feedback 도메인** — 적중률 리포트 + 사후 분석 (가장 복잡)

각 도메인은 본 Market Pulse spec 을 템플릿으로 동일 패턴(메인 + 상세 + Job) 적용 가능.
