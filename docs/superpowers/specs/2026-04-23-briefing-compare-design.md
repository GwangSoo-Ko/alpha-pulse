# Briefing 비교 뷰 — Design Spec

**작성일**: 2026-04-23
**대상 경로**: `/briefings/compare?a=YYYYMMDD&b=YYYYMMDD`
**연관 페이지**: `/briefings` (목록), `/briefings/{date}` (상세)
**목표**: 임의의 두 날짜 브리핑을 side-by-side 로 비교해 "무엇이 어떻게 바뀌었는지" 빠르게 파악.

---

## 1. 원칙

- **정량 중심**: 종합 score + signal + 11개 지표 변화량을 표 형태로 한눈에.
- **짧은 텍스트만**: daily_result_msg + commentary 만 side-by-side. synthesis/news/post_analysis 는 제외 (각자 상세에서 확인).
- **임의 두 날짜 자유 선택**: Gmail-style 체크박스 2개 선택 → 비교 페이지 이동.
- **실존 데이터만 선택 가능**: 목록 테이블의 체크박스로 시작하므로 오입력 방지.
- **신규 API 없음**: 기존 `GET /api/v1/briefings/{date}` 를 두 번 병렬 호출해 SSR.
- **부분 렌더**: 한쪽 날짜 데이터 누락 시 다른 쪽만 정상 표시, 누락 슬롯은 empty state.

## 2. 레이아웃

```
┌────────────────────────────────────────────────────────────────┐
│ [← 목록으로] 브리핑 비교                                        │
├────────────────────────────────────────────────────────────────┤
│ Hero Row (score/signal 비교)                                   │
│ ┌──────────────────┬──────┬──────────────────┐                 │
│ │  A — 2026-04-21  │  Δ   │  B — 2026-04-22  │                 │
│ │  +45.2  [긍정]    │ +17  │  +62.5  [긍정]    │                 │
│ └──────────────────┴──────┴──────────────────┘                 │
├────────────────────────────────────────────────────────────────┤
│ Indicator Diff Table                                           │
│ ┌─────────────────┬──────┬──────┬─────────┐                    │
│ │ 지표            │ 4-21 │ 4-22 │   Δ     │                    │
│ ├─────────────────┼──────┼──────┼─────────┤                    │
│ │ 외국인수급       │ +42  │ +78  │ +36 ↑   │                    │
│ │ V-KOSPI         │ -15  │ -30  │ -15 ↓   │                    │
│ │ ... (11개)      │ ...  │ ...  │  ...    │                    │
│ └─────────────────┴──────┴──────┴─────────┘                    │
│ 기본 정렬: |Δ| 내림차순 (변화 큰 지표가 위로)                     │
├────────────────────────────────────────────────────────────────┤
│ Text Section (side-by-side, 2열)                              │
│ ┌──────────────────────┬──────────────────────┐                │
│ │ daily_result_msg (A) │ daily_result_msg (B) │                │
│ │ commentary (A)       │ commentary (B)       │                │
│ └──────────────────────┴──────────────────────┘                │
└────────────────────────────────────────────────────────────────┘
```

### 반응형

| Breakpoint | Hero | Indicator Table | Text Section |
|---|---|---|---|
| Desktop (≥1024px) | 3열 (A / Δ / B) | 1열 (기본) | 2열 |
| Tablet (≥768px) | 3열 | 1열 | 1열 세로 스택 (A, B) |
| Mobile (<768px) | 1열 세로 (A, Δ, B) | 가로 스크롤 허용 | 1열 |

## 3. 컴포넌트 상세

### 3.1 목록 페이지 수정 (`/briefings`)

**파일**: `webapp-ui/components/domain/briefing/briefings-table.tsx` (수정), `webapp-ui/components/domain/briefing/briefings-compare-button.tsx` (신규)

- 테이블 왼쪽에 체크박스 컬럼 추가
- 체크박스 선택 상태 관리: `useState<string[]>` (날짜 배열). 테이블 컴포넌트를 client component 로 전환 (필요시 page 는 server 유지하고 선택 UI 부분만 client 화)
- 상단 "비교하기" 버튼: `selected.length === 2` 일 때만 `disabled=false`
- 3개째 선택 시도: FIFO — 가장 오래 선택한 것 자동 해제 (경고 없음)
- 클릭 시 이동: `/briefings/compare?a={오래된날짜}&b={최신날짜}` (문자열 비교 기반 정렬)

### 3.2 비교 페이지 (`/briefings/compare`)

**파일**: `webapp-ui/app/(dashboard)/briefings/compare/page.tsx`

- Server component, SSR
- `searchParams.a`, `searchParams.b` 파싱
- 검증:
  - 둘 다 8자리 YYYYMMDD 정규식 매치 아니면 422 (throw HTTPException equivalent — Next.js 에서는 `notFound()` 또는 error boundary)
  - a === b 이면 `redirect('/briefings/' + a)`
  - a 또는 b 누락이면 `redirect('/briefings')`
- `Promise.all` 로 `/api/v1/briefings/{date}` 두 번 호출
  - 각 호출은 404 catch → `null` 반환하도록 래핑
- 결과 `a: BriefingDetail | null`, `b: BriefingDetail | null` 로 렌더
  - 둘 다 null 이면 전체 empty state ("두 날짜 모두 브리핑이 없습니다")
  - 한쪽 null 이면 해당 슬롯만 empty, 다른 쪽 정상 렌더

### 3.3 BriefingCompareHero

**파일**: `webapp-ui/components/domain/briefing/briefing-compare-hero.tsx`

- 3 grid: A 카드 / Δ badge / B 카드
- A/B 카드 props: `{ date, detail: BriefingDetail | null }`
- 각 카드:
  - 날짜 헤더 (YYYY-MM-DD 포맷)
  - score: `+/-{score.toFixed(1)}` 큰 숫자 (signal 색상)
  - signal badge: `signalStyle(signal)` 재사용
  - detail null 이면 "해당 날짜 브리핑 없음"
- Δ 영역:
  - 둘 다 있으면: `b.score - a.score` 계산, `+/-{delta.toFixed(1)}`, 색상 (+초록/-빨강/0중립)
  - 한쪽 없으면: `—`

### 3.4 IndicatorDiffTable

**파일**: `webapp-ui/components/domain/briefing/indicator-diff-table.tsx`

- Props: `{ a: BriefingDetail | null, b: BriefingDetail | null }`
- 로직:
  ```ts
  const scoresA = a?.pulse_result?.indicator_scores ?? {}
  const scoresB = b?.pulse_result?.indicator_scores ?? {}
  const keys = Array.from(new Set([...Object.keys(scoresA), ...Object.keys(scoresB)]))
  ```
- 각 row: `{ key, labelKo, a?: number, b?: number, delta?: number }`
- labelKo: `INDICATOR_LABELS[key] ?? key` (기존 `webapp-ui/lib/market-labels.ts`)
- delta: 둘 다 있을 때만 `b - a`, 아니면 `null`
- 정렬: 클라이언트 state `sortBy: 'key' | 'delta' | 'a' | 'b'`, `dir: 'asc' | 'desc'`
- 기본: `sortBy='delta', dir='desc'` — `|delta|` 절대값 내림차순, null 은 맨 아래
- 컬럼 헤더 클릭 시 정렬 전환
- 표 스타일:
  - a/b 숫자: monospace, signal 색상 톤(양수=초록/음수=빨강/0=회색)
  - delta: 양수(+초록 ↑), 음수(-빨강 ↓), null(—), 0(·)
- 둘 다 pulse_result 없는 경우: "지표 데이터 없음" 한 줄 표시

### 3.5 TextCompareSection

**파일**: `webapp-ui/components/domain/briefing/text-compare-section.tsx`

- Props: `{ a: BriefingDetail | null, b: BriefingDetail | null }`
- 2열 grid (desktop/tablet), 1열 스택 (mobile)
- 각 열:
  - 날짜 헤더
  - `daily_result_msg`: whitespace-pre-wrap (짧은 요약 메시지)
  - `commentary`: react-markdown 없이 plain text (paragraph)
  - detail null → "데이터 없음"
  - 필드 비어있음 → "—"

### 3.6 파일 목록

```
신규:
  webapp-ui/app/(dashboard)/briefings/compare/page.tsx
  webapp-ui/components/domain/briefing/briefing-compare-hero.tsx
  webapp-ui/components/domain/briefing/indicator-diff-table.tsx
  webapp-ui/components/domain/briefing/text-compare-section.tsx
  webapp-ui/components/domain/briefing/briefings-compare-button.tsx

수정:
  webapp-ui/components/domain/briefing/briefings-table.tsx  (체크박스 컬럼)

E2E:
  webapp-ui/e2e/briefings-compare.spec.ts  (신규)
```

## 4. 데이터 흐름

### 4.1 API 계약

변경 없음. 기존 `GET /api/v1/briefings/{date}` → `BriefingDetail | null (404)` 를 두 번 병렬 호출.

### 4.2 압축된 호출 흐름

```ts
// app/(dashboard)/briefings/compare/page.tsx
async function load(date: string, cookie: string): Promise<BriefingDetail | null> {
  try {
    return await apiFetch<BriefingDetail>(`/api/v1/briefings/${date}`, {
      headers: { cookie }, cache: "no-store",
    })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

const [aDetail, bDetail] = await Promise.all([load(a, h), load(b, h)])
```

## 5. 에러 처리

| 상황 | 동작 |
|---|---|
| `a` 또는 `b` searchParam 누락 | `redirect("/briefings")` |
| `a === b` | `redirect("/briefings/" + a)` |
| `a` 또는 `b` YYYYMMDD 정규식 불량 | `notFound()` |
| `a` 정상 / `b` 404 | B 슬롯 empty, A 정상 |
| 둘 다 404 | 전체 empty state |
| `pulse_result` 없음 (둘 다) | Hero/IndicatorDiffTable 가 empty 문구 표시 |
| indicator_scores 한쪽만 있는 지표 | Δ="—", 있는 쪽 값만 표시 |
| 네트워크 5xx | Next.js default error boundary 로 전파 |

## 6. 테스트

### 6.1 백엔드

API 변경 없음 → 신규 테스트 없음. 기존 `tests/webapp/api/test_briefing.py::test_detail_returns_404_for_missing_date` 만족.

### 6.2 프런트 컴포넌트 단위 테스트

프로젝트에 Vitest 미도입 (Phase 3 와 동일 조건) → 단위 테스트 생략. E2E + tsc + lint 로 검증.

### 6.3 Playwright E2E (`webapp-ui/e2e/briefings-compare.spec.ts`)

- **체크박스 → 비교 버튼**: `/briefings` 에서 체크박스 2개 선택 → "비교하기" 버튼 enabled → 클릭 → URL `/briefings/compare` 포함 확인
- **비교 페이지 기본 렌더**: 직접 `/briefings/compare?a=YYYYMMDD&b=YYYYMMDD` 진입 → Hero / Table / Text 3 섹션 텍스트 존재
- **같은 날짜 리다이렉트**: `/briefings/compare?a=20260421&b=20260421` → `/briefings/20260421` 로 이동
- **누락 날짜 부분 렌더**: 존재하지 않는 b 날짜 → B 슬롯 "해당 날짜 브리핑 없음" 문구 표시, A 슬롯 정상

## 7. 성공 기준

- 비교 페이지 TTFB ≤ 400ms (2개 병렬 SQLite 읽기)
- 11개 지표 diff 정렬/색상 정확
- 한쪽 날짜 누락 시 부분 렌더 (다른 쪽 정상)
- `pnpm lint` · `pnpm build` · Playwright 스모크 전체 통과

## 8. 범위 밖 (Out of Scope)

- 3개 이상 비교 (다중 비교)
- synthesis / news / post_analysis / feedback_context 비교
- 긴 텍스트의 diff highlighting (단어 단위 diff 알고리즘)
- 기간 집계 비교 (이번주 vs 지난주 평균)
- 비교 결과 PDF/CSV 내보내기
- URL 공유 시 선택된 날짜 유지 (이미 searchParam 으로 포함됨 — 별도 작업 불필요)
