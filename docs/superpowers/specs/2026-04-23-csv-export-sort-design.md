# CSV 내보내기 + 컬럼 정렬 — Design Spec

**작성일**: 2026-04-23
**대상 페이지**: `/feedback` (이력 탭), `/backtest` (목록 + 상세의 trades/positions 탭), `/content`
**목표**: 5개 핵심 분석 테이블에 (1) 컬럼 헤더 클릭 정렬, (2) 현재 필터+정렬 조건의 CSV streaming 내보내기 추가.

---

## 1. 원칙

- **5개 테이블로 범위 제한**: `trades-table`, `position-viewer`, `signal-history-table`, `runs-table`, `reports-table`. 나머지 12개는 범위 밖.
- **정렬 방식 혼합**: 페이지네이션 3개(history/runs/reports) → server-side, 단일 응답 2개(trades/positions) → client-side.
- **CSV export 는 현재 필터+정렬 그대로 전체 매칭 데이터**: 페이지네이션 무시, 매칭 전체 스트림.
- **UTF-8 BOM + streaming**: Excel 한글 호환 + 대용량 메모리 안전.
- **SQL injection 방지**: `sort` 파라미터는 서버측 화이트리스트로 검증 후 f-string 삽입.
- **단순한 브라우저 다운로드**: `<a>` 링크 + `Content-Disposition: attachment` — fetch/blob 불필요.

## 2. 대상 테이블 요약

### 2.1 Paginated (server-side 정렬)

| 테이블 | 목록 API | 정렬 가능 컬럼 | Export 엔드포인트 |
|---|---|---|---|
| `signal-history-table` | `GET /api/v1/feedback/history` | `date`, `score`, `return_1d`, `hit_1d` | `GET /api/v1/feedback/history/export` |
| `runs-table` | `GET /api/v1/backtest/runs` | `created_at`, `name`, `start_date`, `final_return` | `GET /api/v1/backtest/runs/export` |
| `reports-table` | `GET /api/v1/content/reports` | `analyzed_at`, `published`, `title`, `category` | `GET /api/v1/content/reports/export` |

API 변경: `sort`, `dir` 쿼리 파라미터 추가. Reader/Store 에 `sort`, `dir` 전달. Export 엔드포인트는 동일 sort 적용 + 페이지네이션 무시.

### 2.2 Non-paginated (client-side 정렬)

| 테이블 | 데이터 소스 | 정렬 가능 컬럼 | Export 엔드포인트 |
|---|---|---|---|
| `trades-table` | `GET /api/v1/backtest/runs/{id}` 응답의 `trades` | `date`, `code`, `side`, `pnl`, `return_pct` | `GET /api/v1/backtest/runs/{id}/trades/export` |
| `position-viewer` | `GET /api/v1/backtest/runs/{id}/positions` | `date`, `code`, `quantity`, `value` | `GET /api/v1/backtest/runs/{id}/positions/export` |

구현: FE `useState<{col, dir}>` + 렌더 시 정렬. 데이터 크기 작음 (단일 run ≤ 수천 건). Export 는 서버 raw (순서는 서버 기본).

## 3. 공통 규약

### 3.1 Sort UI 계약

- `<th>` 클릭 가능 (cursor-pointer + hover 강조)
- 활성 컬럼에 `▲`/`▼` 표시
- `aria-sort="ascending" | "descending" | "none"` (접근성)
- 같은 컬럼 재클릭: asc ↔ desc 토글
- 다른 컬럼 클릭: 해당 컬럼 기본 방향 (숫자/날짜 desc, 텍스트 asc)
- 기본 정렬: 각 테이블 도메인 기존 기본값 유지 (date desc 등)

### 3.2 Export UI 계약

- 테이블 상단 우측 `[📥 내보내기]` 버튼 (`shadcn Button`, `variant="outline"`, `size="sm"`)
- 클릭 시 `<a href="/api/v1/.../export?...">` 로 브라우저 네이티브 다운로드
- URL 에 현재 필터 + 정렬 상태 포함 (기존 searchParams 재사용)
- 파일명: `{domain}_{resource}_{YYYYMMDD_HHMMSS}.csv`

### 3.3 CSV 포맷 계약

- UTF-8 + BOM (`\ufeff`) 시작 — Excel 한글 호환
- 헤더 행 (한글 라벨)
- 값 변환: bool → `"O" | "X"`, null → 빈 문자열
- chunk 단위 flush (기본 1000행) — 메모리 O(1)

## 4. Backend

### 4.1 신규 공용 유틸: `alphapulse/webapp/utils/csv_stream.py`

```python
"""CSV 스트리밍 응답 공용 유틸리티."""

import csv
import io
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse


def stream_csv_response(
    rows: Iterable[dict[str, Any]],
    *,
    columns: list[tuple[str, str]],  # [(header_label, dict_key), ...]
    filename: str,
    chunk_size: int = 1000,
) -> StreamingResponse:
    """dict iterable 을 CSV 로 스트리밍 (UTF-8 BOM 포함)."""
    def _iter_csv():
        yield "\ufeff"  # Excel 한글 호환
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([label for label, _ in columns])
        yield buf.getvalue()
        buf = io.StringIO()
        writer = csv.writer(buf)
        count = 0
        for row in rows:
            writer.writerow([row.get(key, "") for _, key in columns])
            count += 1
            if count % chunk_size == 0:
                yield buf.getvalue()
                buf = io.StringIO()
                writer = csv.writer(buf)
        if buf.getvalue():
            yield buf.getvalue()

    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def csv_filename(domain: str, resource: str) -> str:
    """{domain}_{resource}_{YYYYMMDD_HHMMSS}.csv"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{domain}_{resource}_{ts}.csv"
```

### 4.2 Reader/Store — sort 확장

**화이트리스트 패턴** (모든 store 공통):

```python
def get_recent(
    self, limit: int = 30, offset: int = 0,
    sort: str = "date", dir: str = "desc",
) -> list[dict]:
    ALLOWED_COLUMNS = {"date", "score", "return_1d", "hit_1d"}
    col = sort if sort in ALLOWED_COLUMNS else "date"
    direction = "DESC" if dir.lower() == "desc" else "ASC"
    sql = (
        f"SELECT * FROM signal_feedback "
        f"ORDER BY {col} {direction} LIMIT ? OFFSET ?"
    )
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, (limit, offset)).fetchall()]
```

**주의**: `col`/`direction` 은 파라미터 바인딩 불가능 (SQL DDL 토큰). 반드시 화이트리스트 검증 후 f-string 삽입.

**영향 받는 파일**:
- `alphapulse/core/storage/feedback.py` — `get_recent` 확장
- `alphapulse/webapp/store/readers/backtest.py` — `list_runs` 확장
- `alphapulse/webapp/store/readers/content.py` — `list_reports` 확장 (FTS `search` 는 rank 기반이라 별도, 기존 `sort` 파라미터와 통합)

### 4.3 Export 엔드포인트 (5개)

예시 — `/feedback/history/export`:

```python
@router.get("/history/export")
async def export_history(
    days: int = Query(30, ge=1, le=365),
    sort: str = Query("date"),
    dir: str = Query("desc"),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    rows = store.get_recent(limit=days, offset=0, sort=sort, dir=dir)

    def _format(r):
        hit = r.get("hit_1d")
        return {
            "date": r["date"],
            "score": r["score"],
            "signal": r["signal"],
            "return_1d": r.get("return_1d") or "",
            "hit_1d": "O" if hit == 1 else ("X" if hit == 0 else ""),
        }

    columns = [
        ("날짜", "date"),
        ("점수", "score"),
        ("시그널", "signal"),
        ("1일 수익률(%)", "return_1d"),
        ("1일 적중", "hit_1d"),
    ]
    return stream_csv_response(
        (_format(r) for r in rows),
        columns=columns,
        filename=csv_filename("feedback", "history"),
    )
```

나머지 4개 (`runs`, `trades`, `positions`, `reports`) 동일 패턴 — columns 정의만 다름.

### 4.4 API 변경 요약

| 엔드포인트 | 변경 |
|---|---|
| `GET /api/v1/feedback/history` | `sort`, `dir` 파라미터 추가 |
| `GET /api/v1/feedback/history/export` | 신규 |
| `GET /api/v1/backtest/runs` | `sort`, `dir` 추가 |
| `GET /api/v1/backtest/runs/export` | 신규 |
| `GET /api/v1/backtest/runs/{id}/trades/export` | 신규 |
| `GET /api/v1/backtest/runs/{id}/positions/export` | 신규 |
| `GET /api/v1/content/reports` | `sort`, `dir` 추가 (기존 `sort="newest"` 와 통합) |
| `GET /api/v1/content/reports/export` | 신규 |

## 5. Frontend

### 5.1 공용 컴포넌트 — `webapp-ui/components/ui/sortable-th.tsx`

```tsx
"use client"

export function SortableTh<K extends string>({
  label, sortKey, currentSort, currentDir, onSort, className,
}: {
  label: string
  sortKey: K
  currentSort: K | null
  currentDir: "asc" | "desc"
  onSort: (key: K) => void
  className?: string
}) {
  const active = currentSort === sortKey
  const ariaSort = active ? (currentDir === "asc" ? "ascending" : "descending") : "none"
  const arrow = active ? (currentDir === "asc" ? " ▲" : " ▼") : ""
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`cursor-pointer select-none ${className ?? ""}`}
      onClick={() => onSort(sortKey)}
    >
      {label}{arrow}
    </th>
  )
}
```

### 5.2 공용 컴포넌트 — `webapp-ui/components/ui/export-button.tsx`

```tsx
import Link from "next/link"
import { Button } from "@/components/ui/button"

export function ExportButton({ href }: { href: string }) {
  return (
    <Link href={href}>
      <Button size="sm" variant="outline">📥 내보내기</Button>
    </Link>
  )
}
```

### 5.3 Server-side 정렬 (paginated) — URL searchParams 패턴

- SSR 페이지에서 `sort`, `dir` searchParam 파싱 → API 쿼리 전달
- `SortableTh.onSort(key)` → `router.push(/path?{현재 SP}&sort=key&dir=계산)`
- 같은 키 재클릭 → dir 토글. 다른 키 → 해당 컬럼의 기본 dir

### 5.4 Client-side 정렬 (trades/positions)

```tsx
const [sort, setSort] = useState<{ col: "date" | "code" | "pnl"; dir: "asc" | "desc" }>({
  col: "date", dir: "desc",
})

const sorted = useMemo(() => {
  return [...data].sort((a, b) => {
    const av = (a as any)[sort.col], bv = (b as any)[sort.col]
    const cmp = av < bv ? -1 : av > bv ? 1 : 0
    return sort.dir === "asc" ? cmp : -cmp
  })
}, [data, sort])
```

### 5.5 Export 버튼 URL 생성

현재 페이지의 searchParams 를 그대로 전달하고 `export` 서브경로만 추가:

```tsx
function exportHref(basePath: string, sp: URLSearchParams): string {
  const qs = new URLSearchParams(sp)
  qs.delete("page")  // export 은 페이지네이션 무시
  return `${basePath}/export?${qs.toString()}`
}
```

### 5.6 파일 목록

**신규**:
```
alphapulse/webapp/utils/csv_stream.py
webapp-ui/components/ui/sortable-th.tsx
webapp-ui/components/ui/export-button.tsx
tests/webapp/utils/test_csv_stream.py
```

**수정**:
```
alphapulse/core/storage/feedback.py           (get_recent: sort/dir)
alphapulse/webapp/store/readers/backtest.py   (list_runs: sort/dir)
alphapulse/webapp/store/readers/content.py    (list_reports: sort/dir, search 는 rank 기반 유지)
alphapulse/webapp/api/feedback.py             (history sort 추가 + export 엔드포인트)
alphapulse/webapp/api/backtest.py             (runs sort + 3 export 엔드포인트)
alphapulse/webapp/api/content.py              (reports sort + export 엔드포인트)

webapp-ui/components/domain/feedback/signal-history-table.tsx    (SortableTh + ExportButton)
webapp-ui/components/domain/backtest/runs-table.tsx               (동일)
webapp-ui/components/domain/backtest/trades-table.tsx             (client sort + ExportButton)
webapp-ui/components/domain/backtest/position-viewer.tsx          (동일)
webapp-ui/components/domain/content/reports-table.tsx             (SortableTh + ExportButton)

tests/webapp/api/test_feedback.py, test_backtest_runs.py,
  test_backtest_read.py, test_content.py                          (export 테스트)
tests/feedback/test_store.py, tests/webapp/store/readers/*.py      (sort 테스트)
webapp-ui/e2e/feedback.spec.ts, backtest-flow.spec.ts              (정렬 + 다운로드)
```

## 6. 에러 처리

| 상황 | 동작 |
|---|---|
| `sort` 파라미터 값이 화이트리스트 밖 | 기본값으로 fallback (조용히). SQL injection 방지 최우선 |
| `dir` 이 asc/desc 외 | `desc` fallback |
| Export 중 DB 에러 (헤더 전송 후) | chunk 중단 → 불완전 CSV. 로그 warning |
| Export 레코드 0건 | BOM + 헤더 + 빈 바디 (정상) |
| 인증 실패 | 기존 `get_current_user` 401 |
| 대용량 (10만+ 건) | chunk_size=1000 스트림으로 메모리 O(1). 시간만 소요 |
| Export URL 에 `&` 포함 필터값 | `<Link href>` 의 Next.js URL 인코딩 자동 처리 |

## 7. 테스트

### 7.1 백엔드 단위

**`tests/webapp/utils/test_csv_stream.py` (신규)**
- `test_stream_csv_response_includes_bom`
- `test_stream_csv_response_writes_header`
- `test_stream_csv_response_chunks_large_data`
- `test_stream_csv_response_empty_rows_only_header`
- `test_csv_filename_format`

**Sort 파라미터 테스트**
- `tests/feedback/test_store.py`: `test_get_recent_sort_by_score_desc`, `test_get_recent_sort_invalid_falls_back`, `test_get_recent_sort_prevents_sql_injection`
- `tests/webapp/store/readers/test_backtest_reader.py`: `test_list_runs_sort_*`
- `tests/webapp/store/readers/test_content_search.py`: `test_list_reports_sort_*` (FTS 경로 외, 기본 경로 대상)

### 7.2 API 통합

- `tests/webapp/api/test_feedback.py`: `test_history_export_returns_csv_with_bom`, `test_history_export_applies_sort`
- `tests/webapp/api/test_backtest_runs.py`: `test_runs_export_returns_csv`
- `tests/webapp/api/test_backtest_read.py`: `test_trades_export_returns_csv`, `test_positions_export_returns_csv`
- `tests/webapp/api/test_content.py`: `test_reports_export_returns_csv`

### 7.3 E2E (Playwright)

- `webapp-ui/e2e/feedback.spec.ts`: 이력 탭에서 컬럼 클릭 시 URL `sort=...` 반영 + 내보내기 버튼 클릭 → `page.waitForEvent('download')` 로 파일명 확인
- `webapp-ui/e2e/backtest-flow.spec.ts`: runs 테이블 정렬 + 체결 테이블 client 정렬 + 내보내기

## 8. 성공 기준

- pytest 1323 + 신규 (~15) 통과
- ruff clean
- pnpm lint / pnpm build 성공
- 수동 확인:
  - 5 테이블 컬럼 헤더 클릭 시 정렬 동작
  - 각 "내보내기" 버튼 클릭 → CSV 다운로드, 파일명 규약 맞음
  - 다운로드한 CSV 를 Excel 에서 열어 한글 정상 표시

## 9. 범위 밖

- Excel (.xlsx) 포맷 (`openpyxl` 의존)
- 사용자가 Export 열 선택
- 스케줄된/자동 export
- 차트 이미지 export
- 다중 컬럼 동시 정렬 (secondary sort)
- 나머지 12개 테이블 (home widgets, audit, stress, screening 등) — 필요 시 별도 PR
