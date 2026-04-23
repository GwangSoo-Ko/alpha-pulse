# 성능 개선 Phase 1 — Design Spec

**작성일**: 2026-04-23
**범위**: Feedback · Briefings · Content · Market Pulse 페이지의 SSR/API 응답 개선
**트리거**: 성능 감사 결과 (컨텍스트 참조)

---

## 1. 원칙

- **측정 가능한 이득**: 페이지별 TTFB 감소 또는 API 응답 크기 감소로 입증 가능한 변경만.
- **범위 제한**: Redis/인프라 변경 없음. 애플리케이션 레벨 (Python + Next.js) 만.
- **기존 공개 API 호환**: 응답 필드 제거는 신중히 (소비자 확인 후). 필드 추가는 자유.
- **TDD 유지**: 캐싱/페이지네이션 경계 케이스는 테스트로 검증.

## 2. 범위

### 2.1 Major Items (5)

| # | 이슈 | 파일 | 핵심 변경 |
|---|---|---|---|
| 1 | Evaluator N+1 | `alphapulse/feedback/evaluator.py` + `webapp/api/feedback.py` | `get_all_analytics(days)` 단일 메서드 — 4 데이터셋 one-pass. `/analytics` 가 단일 호출. |
| 2 | 리퀘스트 내 메모이제이션 | `alphapulse/feedback/evaluator.py` | Evaluator 가 `self._records_cache: dict[int, list]` 보유, 동일 `limit` 재조회 시 반환. Evaluator 인스턴스 생명주기 = HTTP 요청 (FastAPI Depends 가 default scope 로 함수 단위라 이미 request-scoped). |
| 3 | DB 레벨 페이지네이션 | `alphapulse/core/storage/briefings.py`, `alphapulse/core/storage/feedback.py` | `get_recent(limit, offset=0)` 에 offset 추가. `get_page(page, size)` 신규 (briefings) — SQL LIMIT/OFFSET. |
| 4 | ContentReader 캐시 | `alphapulse/webapp/store/readers/content.py` | `_scan()` 결과 60초 TTL in-memory 캐시. 파일 생성/수정 시 자동 무효화 (mtime 기반). |
| 5 | Briefing 목록 경량 payload | `alphapulse/webapp/api/briefing.py`, `alphapulse/core/storage/briefings.py` | `BriefingStore.list_summaries()` — payload 파싱 시 필요한 필드만 추출 (date/score/signal/has_synthesis/has_commentary/created_at). 전체 payload 읽지 않음 (SQLite 에 payload 가 TEXT 라 로드는 피할 수 없지만 → 별도 컬럼 추가 또는 `json_extract` SQL 함수 사용). |

### 2.2 Quick Wins (3)

| # | 이슈 | 파일 | 변경 |
|---|---|---|---|
| QW-1 | `signal_feedback` 인덱스 | `alphapulse/core/storage/feedback.py` | `CREATE INDEX IF NOT EXISTS` 3개 (hit_1d/3d/5d partial WHERE NOT NULL). |
| QW-2 | Pulse history 서버 정렬 | `alphapulse/webapp/api/market.py` | history 엔드포인트 응답을 ASC 로 반환. FE `history-chart.tsx` re-sort 제거. |
| QW-3 | Revalidate 활성화 | 각 `page.tsx` | 변경 빈도 낮은 페이지에 `export const revalidate = N` 추가. 구체: `/briefings` 목록 (3600s), `/market/pulse` (600s). 주의: `cache: "no-store"` 와 공존 불가 — apiFetch 패턴 조정 필요. |

### 2.3 Out of Scope

- Redis / Memcached (infrastructure)
- Recharts 경량화 (효과 대비 공수)
- Service Worker / offline
- Lazy hydration / React Server Components 경계 재설계

## 3. 주요 변경 상세

### 3.1 Item #1: FeedbackEvaluator.get_all_analytics

기존: `/analytics` 핸들러가 4 메서드 순차 호출 → 각 메서드 `store.get_recent(limit=days)` 개별 호출.

변경:
```python
def get_all_analytics(self, days: int = 30, *, window: int = 7) -> dict:
    """4개 분석 데이터를 단일 get_recent 호출로 생성."""
    records = self.store.get_recent(limit=days)
    return {
        "hit_rate_trend": self._compute_trend(records, window),
        "score_return_points": self._compute_score_return(records),
        "indicator_heatmap": self._compute_heatmap(records),
        "signal_breakdown": self._compute_breakdown(records),
    }
```

기존 4 메서드는 유지 (하위 호환성) 하지만 내부에서 `_compute_*` 헬퍼에 위임. `_compute_*` 는 pre-fetched records 를 받아 순수 연산만.

### 3.2 Item #2: Evaluator 리퀘스트 스코프 캐싱

`FeedbackEvaluator.__init__` 에 `self._cache: dict[tuple, list] = {}` 추가. `get_recent(limit)` 결과를 `(limit,)` 키로 캐싱. 이후 동일 limit 재조회 시 캐시 반환.

단, 기존 `evaluator.get_hit_rates()` 등이 `get_recent(limit=days)` 를 직접 호출하는 패턴을 `_get_cached_records(limit)` 로 변경.

**주의**: FastAPI Depends `get_feedback_evaluator` 가 `request.app.state.feedback_evaluator` 를 반환 — **앱 전역 싱글턴**. 요청 간 캐시가 공유되면 stale 데이터 위험.

해결: Evaluator 는 싱글턴 유지하되 캐시 키에 `record count snapshot` (예: `store.count()`) 포함. 또는 더 단순하게 — **싱글턴 구조 깨고** request-scoped 로 변경: `get_feedback_evaluator` 가 매번 새 인스턴스 생성.

선택: **request-scoped** (더 안전, 인스턴스 생성 비용은 무시할 수준).

### 3.3 Item #3: DB 레벨 페이지네이션

- `BriefingStore.get_recent(days: int = 30, offset: int = 0) -> list[dict]` — `days` 는 LIMIT, `offset` 추가.
- `FeedbackStore.get_recent(limit: int = 30, offset: int = 0) -> list[dict]` — 동일 패턴.
- API 호출 측 (briefing.py, feedback.py) 이 page/size 를 offset 으로 변환해 전달.

### 3.4 Item #4: ContentReader 캐시

```python
class ContentReader:
    _scan_cache: list[ReportMeta] | None = None
    _scan_cache_mtime: float | None = None

    def _scan(self) -> list[ReportMeta]:
        dir_mtime = self.reports_dir.stat().st_mtime if self.reports_dir.is_dir() else 0
        if self._scan_cache is not None and self._scan_cache_mtime == dir_mtime:
            return self._scan_cache
        # ... existing scan logic ...
        self._scan_cache = metas
        self._scan_cache_mtime = dir_mtime
        return metas
```

디렉터리 mtime 기반 무효화 — 파일 추가/삭제 시 자동 감지. 개별 파일 수정은 감지 못 하지만, 신규 리포트 생성 → 디렉터리 mtime 변경 패턴이 일반적.

### 3.5 Item #5: Briefing 목록 경량 payload

현재 `/api/v1/briefings?page=N&size=20` 의 `BriefingListResponse.items` 는 `BriefingSummary` (date/score/signal/has_synthesis/has_commentary/created_at) — 이미 경량. 그러나 뒤에서 `BriefingStore.get_recent()` 가 **payload 전체 JSON** 을 파싱해서 summary 추출 중.

변경:
```python
def list_summaries(self, limit: int, offset: int = 0) -> list[dict]:
    """payload 의 필요한 필드만 json_extract 로 추출."""
    SELECT
        date,
        created_at,
        json_extract(payload, '$.pulse_result.score') AS score,
        json_extract(payload, '$.pulse_result.signal') AS signal,
        (json_extract(payload, '$.synthesis') IS NOT NULL) AS has_synthesis,
        (json_extract(payload, '$.commentary') IS NOT NULL) AS has_commentary
    FROM briefings
    ORDER BY date DESC
    LIMIT ? OFFSET ?
```

전체 payload 로드 없이 SQLite `json_extract` 로 필요한 필드만 스칼라 추출. 페이지 로드 시간 + 메모리 감소.

### 3.6 Quick Wins

**QW-1**: `alphapulse/core/storage/feedback.py` 의 `_create_table` 에 추가:
```python
CREATE INDEX IF NOT EXISTS idx_feedback_hit_1d
  ON signal_feedback(hit_1d) WHERE hit_1d IS NOT NULL;
-- hit_3d, hit_5d 도 동일.
```

**QW-2**: `/api/v1/market/pulse/history` 응답을 ASC 로 정렬. FE 의 재정렬 코드 제거.

**QW-3**: `webapp-ui/app/(dashboard)/briefings/page.tsx`, `.../market/pulse/page.tsx` 등에서 `export const dynamic = "force-dynamic"` 제거하고 `export const revalidate = 3600` (briefings) / `600` (pulse) 추가. `apiFetch` 호출의 `cache: "no-store"` 를 `next: { revalidate: 3600 }` 으로 교체.

**주의**: 쿠키 인증이 필요한 API 호출은 Next.js 의 `fetch` 캐시와 충돌 가능 — 테스트 필수. 실패 시 해당 페이지만 `force-dynamic` 유지.

## 4. 측정 방법

- 현재 상태 TTFB 기록 (각 페이지 3회 평균) — 변경 전
- 각 item 단위 변경 후 TTFB 재측정
- 개선율 포함해 PR 설명에 기록

로컬 측정이라 참고값. 실제 배포는 별도.

## 5. 에러 처리

- 캐시 무효화 실패: 디렉터리 mtime 읽기 에러 시 캐시 우회 (scan 재실행)
- `json_extract` 결과 NULL: Pydantic default 로 처리 (`score: float = 0.0`)
- 인덱스 생성 실패: `IF NOT EXISTS` 로 idempotent
- FE revalidate 오동작: 해당 페이지만 force-dynamic 으로 롤백

## 6. 테스트

### 6.1 백엔드

- `FeedbackEvaluator.get_all_analytics`: 기존 4 메서드와 동등 결과 검증 (골든 테스트)
- `FeedbackEvaluator._get_cached_records`: 동일 limit 연속 호출 시 `store.get_recent` 1회만 호출
- `BriefingStore.list_summaries`: json_extract 결과 타입 검증 (score: float, has_synthesis: bool)
- `BriefingStore.get_recent(offset=N)`: offset 페이지네이션 정확성
- `FeedbackStore.get_recent(offset=N)`: 동일
- `ContentReader._scan` 캐싱: 두 번째 호출 시 파일 I/O 없음 (mocking)
- `ContentReader._scan` 무효화: dir mtime 변경 시 재스캔

### 6.2 API 회귀

- 기존 `tests/webapp/api/test_feedback.py::test_analytics_*` 통과 유지
- `tests/webapp/api/test_briefing.py` 리스트 응답 스키마 불변 확인

### 6.3 FE

- Pulse history 정렬 수정 후 차트 렌더 정상 (Playwright 스모크)
- Revalidate 적용 페이지 하이드레이션 정상

## 7. 성공 기준

- pytest 1272+ passed (회귀 없음, 신규 테스트 추가)
- ruff clean
- pnpm build success
- `/feedback` TTFB 1/2 이하 (로컬 측정)
- `/content` TTFB 대폭 개선 (캐시 hit 시)

## 8. 범위 밖

- Redis / Memcached
- 쿼리 분석/EXPLAIN 세부 최적화 (이미 PK/자동 인덱스 활용 중인 경우)
- Recharts 대체
- N+1 외의 다른 쿼리 최적화 (별도 작업)
