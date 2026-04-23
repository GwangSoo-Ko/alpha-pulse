# CSV 내보내기 + 컬럼 정렬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5개 핵심 분석 테이블 (trades / positions / signal-history / runs / reports) 에 컬럼 정렬 + CSV 내보내기 지원.

**Architecture:** 공용 백엔드 유틸 `stream_csv_response` + FE `SortableTh` / `ExportButton`. 페이지네이션 3개는 server-side sort (API `sort/dir` 파라미터 + SQL 화이트리스트), 단일 응답 2개는 client-side sort. CSV 는 UTF-8 BOM + chunk streaming (Excel 한글 호환, 메모리 O(1)).

**Tech Stack:** Python csv + FastAPI StreamingResponse, Next.js 15 + shadcn Button.

**Branch:** `feature/csv-export-sort` (spec 커밋 `2144bb3` 완료)

**Spec:** `docs/superpowers/specs/2026-04-23-csv-export-sort-design.md`

---

## File Structure

### Backend (공용 유틸 + 3개 store + 4개 API 파일)
- **Create:** `alphapulse/webapp/utils/__init__.py` (없으면)
- **Create:** `alphapulse/webapp/utils/csv_stream.py` — `stream_csv_response`, `csv_filename`
- **Modify:** `alphapulse/core/storage/feedback.py` — `get_recent(sort, dir)` 추가
- **Modify:** `alphapulse/webapp/store/readers/backtest.py` — `list_runs(sort, dir)` 추가
- **Modify:** `alphapulse/webapp/store/readers/content.py` — `list_reports(sort, dir)` 확장 (기존 `sort="newest"` 유지하면서 `dir` 추가)
- **Modify:** `alphapulse/webapp/api/feedback.py` — `/history` sort 파라미터 + `/history/export`
- **Modify:** `alphapulse/webapp/api/backtest.py` — `/runs` sort + `/runs/export`, `/runs/{id}/trades/export`, `/runs/{id}/positions/export`
- **Modify:** `alphapulse/webapp/api/content.py` — `/reports` sort + `/reports/export`

### Frontend (공용 컴포넌트 + 5개 테이블 수정)
- **Create:** `webapp-ui/components/ui/sortable-th.tsx`
- **Create:** `webapp-ui/components/ui/export-button.tsx`
- **Modify:** `webapp-ui/components/domain/feedback/signal-history-table.tsx`
- **Modify:** `webapp-ui/components/domain/backtest/runs-table.tsx`
- **Modify:** `webapp-ui/components/domain/backtest/trades-table.tsx`
- **Modify:** `webapp-ui/components/domain/backtest/position-viewer.tsx`
- **Modify:** `webapp-ui/components/domain/content/reports-table.tsx`

### 테스트
- **Create:** `tests/webapp/utils/test_csv_stream.py`
- **Modify:** `tests/feedback/test_store.py`, `tests/webapp/api/test_feedback.py`
- **Modify:** `tests/webapp/store/readers/test_backtest_reader.py` (있으면 — 확인 후)
- **Modify:** `tests/webapp/api/test_backtest_runs.py`, `test_backtest_read.py`
- **Modify:** `tests/webapp/api/test_content.py`
- **Modify:** `webapp-ui/e2e/feedback.spec.ts`, `backtest-flow.spec.ts`

---

## Conventions

- 백엔드: 각 store sort 확장 → TDD (화이트리스트 검증 테스트 포함)
- 각 export 엔드포인트: CSV BOM + 헤더 + 필터/정렬 적용 테스트
- FE: Vitest 미도입 → `pnpm lint` + `pnpm tsc --noEmit` + E2E
- 각 Task 개별 커밋

---

## Task 1: CSV streaming 공용 유틸리티

**Files:**
- Create: `alphapulse/webapp/utils/__init__.py` (빈 파일, 패키지 표시)
- Create: `alphapulse/webapp/utils/csv_stream.py`
- Create: `tests/webapp/utils/__init__.py` (빈 파일, 이미 있으면 skip)
- Create: `tests/webapp/utils/test_csv_stream.py`

Step 1.1: 패키지 디렉터리 준비.

```bash
mkdir -p alphapulse/webapp/utils tests/webapp/utils
touch alphapulse/webapp/utils/__init__.py tests/webapp/utils/__init__.py
```

Step 1.2: 테스트 파일 생성 `tests/webapp/utils/test_csv_stream.py`:

```python
"""CSV 스트리밍 응답 공용 유틸리티 테스트."""

import io

from alphapulse.webapp.utils.csv_stream import (
    csv_filename,
    stream_csv_response,
)


def _consume(response) -> str:
    """StreamingResponse body iterator → 전체 문자열."""
    chunks = []
    for chunk in response.body_iterator:
        chunks.append(chunk)
    return "".join(chunks)


def test_stream_csv_response_includes_bom():
    rows = [{"a": 1}]
    cols = [("A", "a")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r)
    assert body.startswith("\ufeff")


def test_stream_csv_response_writes_header_and_rows():
    rows = [{"name": "알파", "score": 62.5}, {"name": "베타", "score": -15.0}]
    cols = [("이름", "name"), ("점수", "score")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r)
    # BOM 제거
    body = body.lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0] == "이름,점수"
    assert lines[1] == "알파,62.5"
    assert lines[2] == "베타,-15.0"


def test_stream_csv_response_chunks_large_data():
    rows = ({"n": i} for i in range(2500))
    cols = [("N", "n")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv", chunk_size=1000)
    body = _consume(r)
    lines = body.lstrip("\ufeff").strip().split("\r\n")
    assert lines[0] == "N"
    assert len(lines) == 2501  # header + 2500


def test_stream_csv_response_empty_rows_only_header():
    rows = iter([])
    cols = [("A", "a"), ("B", "b")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r).lstrip("\ufeff")
    # 헤더 + 줄바꿈만
    assert body.strip() == "A,B"


def test_stream_csv_response_content_disposition_header():
    r = stream_csv_response(iter([]), columns=[("A", "a")], filename="my_file.csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "my_file.csv" in r.headers["content-disposition"]


def test_stream_csv_response_handles_missing_keys():
    rows = [{"a": 1}]  # 'b' 없음
    cols = [("A", "a"), ("B", "b")]
    r = stream_csv_response(rows, columns=cols, filename="t.csv")
    body = _consume(r).lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[1] == "1,"  # b 는 빈 문자열


def test_csv_filename_format():
    name = csv_filename("backtest", "trades")
    assert name.startswith("backtest_trades_")
    assert name.endswith(".csv")
    # YYYYMMDD_HHMMSS 패턴
    import re
    assert re.match(r"^backtest_trades_\d{8}_\d{6}\.csv$", name)
```

Step 1.3: Red.

```bash
cd /Users/gwangsoo/alpha-pulse
pytest tests/webapp/utils/test_csv_stream.py -v
```
Expected: FAIL — 모듈 미존재.

Step 1.4: 구현 `alphapulse/webapp/utils/csv_stream.py`:

```python
"""CSV 스트리밍 응답 공용 유틸리티."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse


def stream_csv_response(
    rows: Iterable[dict[str, Any]],
    *,
    columns: list[tuple[str, str]],
    filename: str,
    chunk_size: int = 1000,
) -> StreamingResponse:
    """dict iterable 을 CSV 로 스트리밍.

    Args:
        rows: dict iterable. 각 dict 는 columns 의 key 에 해당하는 값을 가진다.
        columns: [(header_label, dict_key), ...]. 순서대로 컬럼.
        filename: Content-Disposition 에 포함될 파일명.
        chunk_size: 몇 행마다 yield 할지 (메모리 제어).

    Returns:
        StreamingResponse with UTF-8 BOM + header + body.
    """
    def _iter_csv():
        yield "\ufeff"  # Excel 한글 호환 BOM
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

Step 1.5: Green.

```bash
pytest tests/webapp/utils/test_csv_stream.py -v
```
Expected: 7 passed.

Step 1.6: 린트 + 커밋.

```bash
ruff check alphapulse/webapp/utils/ tests/webapp/utils/
git add alphapulse/webapp/utils/ tests/webapp/utils/
git commit -m "feat(webapp): csv_stream 공용 유틸 (BOM + chunk streaming)"
```

---

## Task 2: FeedbackStore.get_recent(sort, dir)

**Files:**
- Modify: `alphapulse/core/storage/feedback.py`
- Modify: `tests/feedback/test_store.py`

Step 2.1: 테스트 추가 (append to `tests/feedback/test_store.py`):

```python
def test_get_recent_sort_by_score_desc(store):
    store.save_signal("20260401", 10.0, "매수 우위", {})
    store.save_signal("20260402", 80.0, "매수 우위", {})
    store.save_signal("20260403", 50.0, "매수 우위", {})
    rows = store.get_recent(limit=10, offset=0, sort="score", dir="desc")
    assert [r["score"] for r in rows] == [80.0, 50.0, 10.0]


def test_get_recent_sort_by_score_asc(store):
    store.save_signal("20260401", 10.0, "매수 우위", {})
    store.save_signal("20260402", 80.0, "매수 우위", {})
    rows = store.get_recent(limit=10, offset=0, sort="score", dir="asc")
    assert [r["score"] for r in rows] == [10.0, 80.0]


def test_get_recent_sort_invalid_column_falls_back(store):
    """화이트리스트 밖 컬럼은 기본 (date desc) 으로 fallback."""
    store.save_signal("20260401", 10.0, "매수 우위", {})
    store.save_signal("20260402", 80.0, "매수 우위", {})
    rows = store.get_recent(limit=10, offset=0, sort="hacker; DROP TABLE x;", dir="desc")
    assert [r["date"] for r in rows] == ["20260402", "20260401"]


def test_get_recent_sort_invalid_dir_falls_back(store):
    store.save_signal("20260401", 10.0, "매수 우위", {})
    store.save_signal("20260402", 80.0, "매수 우위", {})
    rows = store.get_recent(limit=10, offset=0, sort="date", dir="garbage")
    assert [r["date"] for r in rows] == ["20260402", "20260401"]
```

Step 2.2: Red.

```bash
pytest tests/feedback/test_store.py -k "sort" -v
```
Expected: FAIL — `sort`/`dir` 키워드 미지원.

Step 2.3: 구현 `alphapulse/core/storage/feedback.py`. 기존 `get_recent` 시그니처 확장:

```python
    def get_recent(
        self,
        limit: int = 30,
        offset: int = 0,
        sort: str = "date",
        dir: str = "desc",
    ) -> list[dict]:
        """최근 N건의 피드백 레코드를 조회한다.

        Args:
            limit: 최대 행 수.
            offset: 페이지네이션 offset.
            sort: 정렬 컬럼 (화이트리스트 검증). 기본 "date".
            dir: "asc" or "desc". 기본 "desc".
        """
        ALLOWED = {"date", "score", "return_1d", "hit_1d"}
        col = sort if sort in ALLOWED else "date"
        direction = "DESC" if dir.lower() == "desc" else (
            "ASC" if dir.lower() == "asc" else "DESC"
        )
        sql = (
            f"SELECT * FROM signal_feedback "
            f"ORDER BY {col} {direction} LIMIT ? OFFSET ?"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (limit, offset)).fetchall()
        return [dict(row) for row in rows]
```

Step 2.4: Green.

```bash
pytest tests/feedback/test_store.py -v
```
Expected: 전체 통과.

Step 2.5: 린트 + 커밋.

```bash
ruff check alphapulse/core/storage/feedback.py tests/feedback/test_store.py
git add alphapulse/core/storage/feedback.py tests/feedback/test_store.py
git commit -m "feat(feedback): FeedbackStore.get_recent sort/dir 파라미터 (화이트리스트 검증)"
```

---

## Task 3: /feedback/history sort + /feedback/history/export 엔드포인트

**Files:**
- Modify: `alphapulse/webapp/api/feedback.py`
- Modify: `tests/webapp/api/test_feedback.py`

Step 3.1: 테스트 추가 (append to `tests/webapp/api/test_feedback.py`):

```python
def test_history_sort_by_score_desc(client, feedback_store):
    feedback_store.save_signal("20260401", 10.0, "매수 우위", {})
    feedback_store.save_signal("20260402", 80.0, "매수 우위", {})
    r = client.get("/api/v1/feedback/history?sort=score&dir=desc")
    assert r.status_code == 200
    scores = [item["score"] for item in r.json()["items"]]
    assert scores == [80.0, 10.0]


def test_history_export_returns_csv_with_bom(client, feedback_store):
    feedback_store.save_signal("20260401", 40.0, "매수 우위", {})
    feedback_store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    r = client.get("/api/v1/feedback/history/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    body = r.content.decode("utf-8")
    assert body.startswith("\ufeff")
    # 헤더 + 1행
    lines = body.lstrip("\ufeff").strip().split("\r\n")
    assert lines[0].startswith("날짜,점수,시그널")
    assert len(lines) >= 2


def test_history_export_applies_sort(client, feedback_store):
    feedback_store.save_signal("20260401", 10.0, "매수 우위", {})
    feedback_store.update_result("20260401", 2650, 1.0, 870, 0.5, 0.5, 1)
    feedback_store.save_signal("20260402", 80.0, "매수 우위", {})
    feedback_store.update_result("20260402", 2650, 1.0, 870, 0.5, 1.5, 1)
    r = client.get("/api/v1/feedback/history/export?sort=score&dir=asc")
    body = r.content.decode("utf-8").lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    # 첫 데이터 행 = 가장 낮은 score
    assert "10" in lines[1]  # 10.0 이 먼저
```

Step 3.2: Red.

```bash
pytest tests/webapp/api/test_feedback.py -k "sort or export" -v
```
Expected: FAIL (아직 엔드포인트/sort 미지원).

Step 3.3: 구현 `alphapulse/webapp/api/feedback.py`. 기존 `@router.get("/history")` 엔드포인트 확장 + 신규 export 엔드포인트 추가.

먼저 imports 에 추가 (이미 있으면 skip):

```python
from alphapulse.webapp.utils.csv_stream import csv_filename, stream_csv_response
```

기존 `get_history` 엔드포인트 시그니처에 `sort`, `dir` 추가:

```python
@router.get("/history", response_model=FeedbackHistoryResponse)
async def get_history(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("date"),
    dir: str = Query("desc"),
    user: User = Depends(get_current_user),
    store: FeedbackStore = Depends(get_feedback_store),
):
    total_rows = store.get_recent(limit=days, offset=0, sort=sort, dir=dir)
    total = len(total_rows)
    offset = (page - 1) * size
    if offset >= days:
        page_rows = []
    else:
        page_rows = store.get_recent(
            limit=size, offset=offset, sort=sort, dir=dir,
        )

    return FeedbackHistoryResponse(
        items=[
            SignalHistoryItem(
                date=r["date"],
                score=float(r["score"]),
                signal=r["signal"],
                kospi_change_pct=r["kospi_change_pct"],
                return_1d=r["return_1d"],
                return_3d=r["return_3d"],
                return_5d=r["return_5d"],
                hit_1d=_int_to_bool(r["hit_1d"]),
                hit_3d=_int_to_bool(r["hit_3d"]),
                hit_5d=_int_to_bool(r["hit_5d"]),
            )
            for r in page_rows
        ],
        page=page,
        size=size,
        total=min(total, days),
    )
```

신규 `/history/export` 엔드포인트 추가 (`/history` 바로 아래):

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
            "return_1d": r.get("return_1d") if r.get("return_1d") is not None else "",
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

**주의**: FastAPI 라우트 순서 — `/history/export` 는 `/history` 보다 아래에 있어도 정확 매칭 우선이라 문제없음. `/{date}` path param 매칭 이전에 선언되어야 하므로 기존 `/{date}` 엔드포인트 위에 위치.

Step 3.4: Green.

```bash
pytest tests/webapp/api/test_feedback.py -v
```
Expected: 모두 통과.

Step 3.5: 린트 + 커밋.

```bash
ruff check alphapulse/webapp/api/feedback.py tests/webapp/api/test_feedback.py
git add alphapulse/webapp/api/feedback.py tests/webapp/api/test_feedback.py
git commit -m "feat(feedback): /history sort 파라미터 + /history/export CSV"
```

---

## Task 4: BacktestReader.list_runs(sort, dir)

**Files:**
- Modify: `alphapulse/webapp/store/readers/backtest.py`
- Modify (or Create): `tests/webapp/store/readers/test_backtest_reader.py`

Step 4.1: 테스트 파일 확인 + 테스트 추가.

```bash
ls tests/webapp/store/readers/ | grep backtest
```

기존 파일이 있으면 append, 없으면 신규 파일:

```python
"""BacktestReader.list_runs sort/dir 테스트."""

import pytest

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.store.readers.backtest import BacktestReader


@pytest.fixture
def reader(tmp_path):
    db = tmp_path / "backtest.db"
    BacktestStore(db_path=db)  # schema
    return BacktestReader(db_path=db)


def _seed(reader, name: str, created_at: float, final_return: float):
    import sqlite3
    with sqlite3.connect(reader.db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, name, strategies, start_date, end_date, "
            "capital, cost_model, created_at, metrics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"r-{name}", name, '["momentum"]', "20260101", "20260301",
                10_000_000.0, '{}', created_at,
                f'{{"final_return": {final_return}}}',
            ),
        )


def test_list_runs_sort_by_name_asc(reader):
    _seed(reader, "alpha", 100.0, 5.0)
    _seed(reader, "bravo", 200.0, 3.0)
    page = reader.list_runs(page=1, size=10, sort="name", dir="asc")
    names = [r.name for r in page.items]
    assert names == ["alpha", "bravo"]


def test_list_runs_sort_by_created_at_default(reader):
    _seed(reader, "first", 100.0, 5.0)
    _seed(reader, "second", 200.0, 3.0)
    page = reader.list_runs(page=1, size=10)
    names = [r.name for r in page.items]
    assert names == ["second", "first"]  # desc default


def test_list_runs_sort_invalid_falls_back(reader):
    _seed(reader, "first", 100.0, 5.0)
    _seed(reader, "second", 200.0, 3.0)
    page = reader.list_runs(page=1, size=10, sort="DROP TABLE", dir="desc")
    # 기본 created_at DESC 로 fallback
    names = [r.name for r in page.items]
    assert names == ["second", "first"]
```

Step 4.2: Red.

```bash
pytest tests/webapp/store/readers/test_backtest_reader.py -v
```
Expected: FAIL (sort 미지원).

Step 4.3: 구현 `alphapulse/webapp/store/readers/backtest.py`. 기존 `list_runs` 시그니처 확장:

```python
    def list_runs(
        self,
        page: int = 1,
        size: int = 20,
        name_contains: str | None = None,
        sort: str = "created_at",
        dir: str = "desc",
    ) -> Page:
        ALLOWED = {"created_at", "name", "start_date", "final_return"}
        col = sort if sort in ALLOWED else "created_at"
        direction = "DESC" if dir.lower() == "desc" else (
            "ASC" if dir.lower() == "asc" else "DESC"
        )
        # final_return 은 metrics JSON 안의 값 — json_extract 사용
        if col == "final_return":
            order_expr = "CAST(json_extract(metrics, '$.final_return') AS REAL)"
        else:
            order_expr = col
        offset = (page - 1) * size
        where = ""
        params: list = []
        if name_contains:
            where = "WHERE name LIKE ?"
            params.append(f"%{name_contains}%")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM runs {where}", params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM runs {where} "
                f"ORDER BY {order_expr} {direction} LIMIT ? OFFSET ?",
                [*params, size, offset],
            ).fetchall()
        items = [self._row_to_summary(r) for r in rows]
        return Page(items=items, page=page, size=size, total=total)
```

Step 4.4: Green.

```bash
pytest tests/webapp/store/readers/test_backtest_reader.py -v
```

Step 4.5: 린트 + 커밋.

```bash
ruff check alphapulse/webapp/store/readers/backtest.py tests/webapp/store/readers/test_backtest_reader.py
git add alphapulse/webapp/store/readers/backtest.py tests/webapp/store/readers/test_backtest_reader.py
git commit -m "feat(backtest): BacktestReader.list_runs sort/dir"
```

---

## Task 5: /backtest/runs sort + 3 export 엔드포인트

**Files:**
- Modify: `alphapulse/webapp/api/backtest.py`
- Modify: `tests/webapp/api/test_backtest_runs.py`, `test_backtest_read.py`

Step 5.1: 테스트 추가 (test_backtest_runs.py — runs 정렬 + runs export).

먼저 기존 fixture 확인:

```bash
grep -n "def client\|def app\|@pytest.fixture" tests/webapp/api/test_backtest_runs.py | head -10
```

Append tests (fixture 이름에 맞춰 조정 — 아래는 일반 패턴):

```python
def test_runs_sort_by_name_asc(client):
    # 사전 조건: 런 2개 시드 (테스트 fixture 에서 이미 시드되어있을 수 있음 — 확인 후 조정)
    r = client.get("/api/v1/backtest/runs?sort=name&dir=asc")
    assert r.status_code == 200
    # 이름 정렬 확인은 시드된 데이터에 따라 다름 — 최소 응답 정상 확인
    body = r.json()
    assert "items" in body


def test_runs_export_returns_csv(client):
    r = client.get("/api/v1/backtest/runs/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.content.decode("utf-8").lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0].startswith("이름,전략")  # 헤더 (컬럼 정의에 따라)
```

`test_backtest_read.py` (trades/positions export):

```python
def test_trades_export_returns_csv(client, sample_run):
    run_id = sample_run.run_id
    r = client.get(f"/api/v1/backtest/runs/{run_id}/trades/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.content.decode("utf-8").lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0]  # 헤더 존재


def test_positions_export_returns_csv(client, sample_run):
    run_id = sample_run.run_id
    r = client.get(f"/api/v1/backtest/runs/{run_id}/positions/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
```

**주의**: `sample_run` fixture 이름은 기존 파일의 실제 fixture 에 맞춰 조정. 없으면 inline setup.

Step 5.2: Red.

```bash
pytest tests/webapp/api/test_backtest_runs.py tests/webapp/api/test_backtest_read.py -k "export or sort" -v
```

Step 5.3: 구현 `alphapulse/webapp/api/backtest.py`. 기존 `list_runs` + 3 신규 export 엔드포인트.

Imports 에 추가:

```python
from alphapulse.webapp.utils.csv_stream import csv_filename, stream_csv_response
```

기존 `list_runs` 확장:

```python
@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    name: str | None = None,
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    p = reader.list_runs(
        page=page, size=size, name_contains=name, sort=sort, dir=dir,
    )
    return RunListResponse(
        items=[_summary_to_api(s) for s in p.items],
        page=p.page, size=p.size, total=p.total,
    )
```

**참고**: `_summary_to_api` 가 기존에 있으면 그대로 사용. 없으면 현재 응답 매핑 패턴 유지.

신규 3 export 엔드포인트 (각각 /runs, /trades, /positions 아래에):

```python
@router.get("/runs/export")
async def export_runs(
    name: str | None = None,
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    # 전체 매칭 데이터 — 큰 페이지 사이즈로 한 번에
    p = reader.list_runs(page=1, size=10_000, name_contains=name, sort=sort, dir=dir)

    def _format(s):
        return {
            "name": s.name,
            "strategies": ",".join(s.strategies) if isinstance(s.strategies, list) else str(s.strategies),
            "start_date": s.start_date,
            "end_date": s.end_date,
            "final_return": s.metrics.get("final_return", "") if isinstance(s.metrics, dict) else "",
            "run_id": s.run_id,
        }

    columns = [
        ("이름", "name"),
        ("전략", "strategies"),
        ("시작일", "start_date"),
        ("종료일", "end_date"),
        ("최종 수익률", "final_return"),
        ("Run ID", "run_id"),
    ]
    return stream_csv_response(
        (_format(s) for s in p.items),
        columns=columns,
        filename=csv_filename("backtest", "runs"),
    )


@router.get("/runs/{run_id}/trades/export")
async def export_trades(
    run_id: str,
    code: str | None = None,
    winner: bool | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = reader.get_trades(s.run_id, code=code, winner=winner)

    def _format(t):
        # t 는 dict 형태로 reader.get_trades 에서 반환 (실제 shape 확인 필요)
        return {
            "date": t.get("date", ""),
            "code": t.get("code", ""),
            "side": t.get("side", ""),
            "quantity": t.get("quantity", ""),
            "price": t.get("price", ""),
            "pnl": t.get("pnl", ""),
            "return_pct": t.get("return_pct", ""),
        }

    columns = [
        ("날짜", "date"),
        ("종목", "code"),
        ("매매", "side"),
        ("수량", "quantity"),
        ("가격", "price"),
        ("손익", "pnl"),
        ("수익률(%)", "return_pct"),
    ]
    return stream_csv_response(
        (_format(t) for t in rows),
        columns=columns,
        filename=csv_filename("backtest", f"trades_{s.run_id[:8]}"),
    )


@router.get("/runs/{run_id}/positions/export")
async def export_positions(
    run_id: str,
    date: str | None = None,
    code: str | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = reader.get_positions(s.run_id, date=date, code=code)

    def _format(p):
        return {
            "date": p.get("date", ""),
            "code": p.get("code", ""),
            "quantity": p.get("quantity", ""),
            "avg_price": p.get("avg_price", ""),
            "value": p.get("value", ""),
        }

    columns = [
        ("날짜", "date"),
        ("종목", "code"),
        ("수량", "quantity"),
        ("평단가", "avg_price"),
        ("평가금액", "value"),
    ]
    return stream_csv_response(
        (_format(p) for p in rows),
        columns=columns,
        filename=csv_filename("backtest", f"positions_{s.run_id[:8]}"),
    )
```

**주의**: `reader.get_trades`, `reader.get_positions` 반환 shape 이 dict 인지 Pydantic 인지 확인 필요. Pydantic 이면 `t.model_dump()` 또는 속성 접근 `t.date` 로 수정. 실제 코드 읽고 맞춤.

Step 5.4: Green.

```bash
pytest tests/webapp/api/test_backtest_runs.py tests/webapp/api/test_backtest_read.py -v
```

Step 5.5: 린트 + 커밋.

```bash
ruff check alphapulse/webapp/api/backtest.py tests/webapp/api/test_backtest_runs.py tests/webapp/api/test_backtest_read.py
git add alphapulse/webapp/api/backtest.py tests/webapp/api/test_backtest_runs.py tests/webapp/api/test_backtest_read.py
git commit -m "feat(backtest): /runs sort + 3 export 엔드포인트 (runs/trades/positions)"
```

---

## Task 6: ContentReader.list_reports(sort, dir) 확장

**Files:**
- Modify: `alphapulse/webapp/store/readers/content.py`
- Modify: `tests/webapp/store/readers/test_content_cache.py` 또는 `test_content_search.py`

Step 6.1: 현재 `list_reports` 시그니처 확인:

```bash
grep -n "def list_reports" alphapulse/webapp/store/readers/content.py
```

기존: `sort: Literal["newest", "oldest"] = "newest"`.

새로 추가: `dir` 파라미터 + `sort` 에 더 많은 값 허용 — 하지만 호환성 위해 "newest"/"oldest" 는 유지.

Step 6.2: 테스트 추가 (append to `tests/webapp/store/readers/test_content_search.py`):

```python
class TestListReportsSort:
    def test_list_reports_sort_by_title_asc(self, tmp_path):
        _write_report(tmp_path, "a.md", title="감")
        _write_report(tmp_path, "b.md", title="배")
        _write_report(tmp_path, "c.md", title="딸기")
        reader = ContentReader(reports_dir=tmp_path)
        result = reader.list_reports(sort="title", dir="asc")
        titles = [i["title"] for i in result["items"]]
        assert titles == ["감", "딸기", "배"]

    def test_list_reports_sort_newest_still_works(self, tmp_path):
        _write_report(tmp_path, "a.md")
        _write_report(tmp_path, "b.md")
        reader = ContentReader(reports_dir=tmp_path)
        result = reader.list_reports(sort="newest")
        # analyzed_at 기준 DESC — 기존 동작 유지
        assert len(result["items"]) == 2

    def test_list_reports_sort_invalid_falls_back_to_newest(self, tmp_path):
        _write_report(tmp_path, "a.md")
        reader = ContentReader(reports_dir=tmp_path)
        result = reader.list_reports(sort="DROP TABLE", dir="desc")
        # fallback — 에러 없이 응답
        assert len(result["items"]) == 1
```

Step 6.3: Red.

```bash
pytest tests/webapp/store/readers/test_content_search.py -k "TestListReportsSort" -v
```

Step 6.4: 구현 `alphapulse/webapp/store/readers/content.py` 의 `list_reports` 메서드. 기존 substring 경로 (FTS 아닌 쪽) 의 정렬 로직을 확장:

```python
    def list_reports(
        self,
        *,
        categories=None,
        date_from=None,
        date_to=None,
        query=None,
        sort="newest",
        dir="desc",
        page=1,
        size=20,
    ):
        # FTS 가능 + query 있으면 search() 로 위임 (기존 경로)
        if query and self._fts_available:
            return self.search(
                q=query, categories=categories,
                date_from=date_from, date_to=date_to,
                page=page, size=size,
            )

        # Sort 화이트리스트 + 레거시 값 호환
        ALLOWED = {"analyzed_at", "published", "title", "category", "newest", "oldest"}
        sort_col = sort if sort in ALLOWED else "newest"
        # 레거시 값 매핑
        if sort_col == "newest":
            sort_col, reverse = "analyzed_at", True
        elif sort_col == "oldest":
            sort_col, reverse = "analyzed_at", False
        else:
            reverse = dir.lower() == "desc"

        all_metas = self._scan()
        filtered = [
            m for m in all_metas
            if (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
            and (not query or query.lower() in m["title"].lower())
        ]
        filtered.sort(key=lambda m: m.get(sort_col, ""), reverse=reverse)
        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        items = filtered[start:end]
        categories_all = sorted({m["category"] for m in all_metas})
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "categories": categories_all,
        }
```

Step 6.5: Green.

```bash
pytest tests/webapp/store/readers/test_content_search.py tests/webapp/store/readers/test_content_cache.py -v
```
Expected: 모두 통과 (기존 테스트 회귀 없음 + 신규 3 통과).

Step 6.6: 린트 + 커밋.

```bash
ruff check alphapulse/webapp/store/readers/content.py tests/webapp/store/readers/test_content_search.py
git add alphapulse/webapp/store/readers/content.py tests/webapp/store/readers/test_content_search.py
git commit -m "feat(content): ContentReader.list_reports sort/dir 확장 (화이트리스트 + 레거시 호환)"
```

---

## Task 7: /content/reports sort + /content/reports/export 엔드포인트

**Files:**
- Modify: `alphapulse/webapp/api/content.py`
- Modify: `tests/webapp/api/test_content.py`

Step 7.1: 테스트 추가.

```python
def test_reports_sort_by_title_asc(client_fts, content_reports_dir):
    from tests.webapp.store.readers.test_content_search import _write_report
    _write_report(content_reports_dir, "a.md", title="감")
    _write_report(content_reports_dir, "b.md", title="배")
    r = client_fts.get("/api/v1/content/reports?sort=title&dir=asc")
    assert r.status_code == 200
    titles = [item["title"] for item in r.json()["items"]]
    assert titles == ["감", "배"]


def test_reports_export_returns_csv(client_fts, content_reports_dir):
    from tests.webapp.store.readers.test_content_search import _write_report
    _write_report(content_reports_dir, "a.md", title="테스트 리포트")
    r = client_fts.get("/api/v1/content/reports/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.content.decode("utf-8").lstrip("\ufeff")
    lines = body.strip().split("\r\n")
    assert lines[0].startswith("제목,카테고리,발행일,분석일")
```

Fixture 이름은 test_content.py 의 실제 fixture 에 맞춰 조정.

Step 7.2: Red.

Step 7.3: 구현 `alphapulse/webapp/api/content.py`. 기존 `list_reports` 엔드포인트 확장:

```python
@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: list[str] | None = Query(None),
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    sort: str = Query("newest"),
    dir: str = Query("desc"),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    result = reader.list_reports(
        categories=category,
        date_from=date_from,
        date_to=date_to,
        query=q,
        sort=sort,
        dir=dir,
        page=page,
        size=size,
    )
    return ReportListResponse(
        items=[
            ReportSummary(
                filename=i["filename"],
                title=i["title"],
                category=i["category"],
                published=i["published"],
                analyzed_at=i["analyzed_at"],
                highlight=i.get("highlight"),
            )
            for i in result["items"]
        ],
        page=result["page"],
        size=result["size"],
        total=result["total"],
        categories=result["categories"],
    )
```

신규 export 엔드포인트:

```python
@router.get("/reports/export")
async def export_reports(
    category: list[str] | None = Query(None),
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    sort: str = Query("newest"),
    dir: str = Query("desc"),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    result = reader.list_reports(
        categories=category,
        date_from=date_from,
        date_to=date_to,
        query=q,
        sort=sort,
        dir=dir,
        page=1,
        size=10_000,
    )

    def _format(i):
        return {
            "title": i["title"],
            "category": i["category"],
            "published": i["published"],
            "analyzed_at": i["analyzed_at"],
            "filename": i["filename"],
        }

    columns = [
        ("제목", "title"),
        ("카테고리", "category"),
        ("발행일", "published"),
        ("분석일", "analyzed_at"),
        ("파일명", "filename"),
    ]
    return stream_csv_response(
        (_format(i) for i in result["items"]),
        columns=columns,
        filename=csv_filename("content", "reports"),
    )
```

Imports: `from alphapulse.webapp.utils.csv_stream import csv_filename, stream_csv_response`.

**라우트 순서**: `/reports/export` 는 `/reports/{filename:path}` 보다 **위** 에 있어야 함. 기존 파일에서 `/{filename}` 이 나중에 정의되어 있으면 문제없음. 확인 필요.

Step 7.4: Green + 회귀.

Step 7.5: 린트 + 커밋 `feat(content): /reports sort + /reports/export CSV`.

---

## Task 8: FE 공용 컴포넌트 (SortableTh + ExportButton)

**Files:**
- Create: `webapp-ui/components/ui/sortable-th.tsx`
- Create: `webapp-ui/components/ui/export-button.tsx`

Step 8.1: `sortable-th.tsx`:

```tsx
"use client"

export function SortableTh<K extends string>({
  label,
  sortKey,
  currentSort,
  currentDir,
  onSort,
  className,
}: {
  label: string
  sortKey: K
  currentSort: K | null
  currentDir: "asc" | "desc"
  onSort: (key: K) => void
  className?: string
}) {
  const active = currentSort === sortKey
  const ariaSort: "ascending" | "descending" | "none" = active
    ? currentDir === "asc"
      ? "ascending"
      : "descending"
    : "none"
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

Step 8.2: `export-button.tsx`:

```tsx
import Link from "next/link"
import { Button } from "@/components/ui/button"

export function ExportButton({ href, label = "내보내기" }: { href: string; label?: string }) {
  return (
    <Link href={href}>
      <Button size="sm" variant="outline">📥 {label}</Button>
    </Link>
  )
}
```

Step 8.3: 린트 + 빌드 확인.

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep -E "sortable-th|export-button" || echo "no errors"
```

Step 8.4: 커밋.

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/ui/sortable-th.tsx webapp-ui/components/ui/export-button.tsx
git commit -m "feat(webapp-ui): SortableTh + ExportButton 공용 컴포넌트"
```

---

## Task 9: SignalHistoryTable — SortableTh + ExportButton (server-side)

**Files:**
- Modify: `webapp-ui/components/domain/feedback/signal-history-table.tsx`

**Context**: 이 테이블은 `/feedback` 페이지의 이력 탭. 현재 `SignalHistoryItem[]` 을 받아 렌더. URL searchParams 를 `sort`, `dir` 로 업데이트하면 SSR 페이지가 재로드.

Step 9.1: 기존 파일 읽기.

```bash
cat webapp-ui/components/domain/feedback/signal-history-table.tsx
```

Step 9.2: SortableTh + ExportButton 통합.

파일 상단에 imports:

```tsx
"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { SortableTh } from "@/components/ui/sortable-th"
import { ExportButton } from "@/components/ui/export-button"
```

컴포넌트 내부 — 정렬 클릭 핸들러:

```tsx
const router = useRouter()
const sp = useSearchParams()
const currentSort = (sp?.get("sort") ?? "date") as "date" | "score" | "return_1d" | "hit_1d"
const currentDir = (sp?.get("dir") ?? "desc") as "asc" | "desc"

function onSort(key: string) {
  const next = new URLSearchParams(sp?.toString() ?? "")
  if (currentSort === key) {
    next.set("dir", currentDir === "asc" ? "desc" : "asc")
  } else {
    next.set("sort", key)
    // 숫자/날짜는 desc, 텍스트는 asc 기본
    next.set("dir", key === "signal" ? "asc" : "desc")
  }
  next.delete("page")
  router.push(`/feedback?${next}`)
}
```

ExportButton URL:

```tsx
const exportQs = new URLSearchParams(sp?.toString() ?? "")
exportQs.delete("page")
const exportHref = `/api/v1/feedback/history/export?${exportQs}`
```

Table header 부분 `<thead>` 에서 `<th>` 를 `<SortableTh>` 로 교체 (각 정렬 가능 컬럼):

```tsx
<thead>
  <tr>
    <SortableTh label="날짜" sortKey="date" currentSort={currentSort} currentDir={currentDir} onSort={onSort} className="px-3 py-2 text-left text-xs text-neutral-400" />
    <SortableTh label="점수" sortKey="score" currentSort={currentSort} currentDir={currentDir} onSort={onSort} className="px-3 py-2 text-right text-xs text-neutral-400" />
    <th scope="col" className="px-3 py-2 text-left text-xs text-neutral-400">시그널</th>
    <SortableTh label="1일 수익률" sortKey="return_1d" currentSort={currentSort} currentDir={currentDir} onSort={onSort} className="px-3 py-2 text-right text-xs text-neutral-400" />
    <SortableTh label="적중" sortKey="hit_1d" currentSort={currentSort} currentDir={currentDir} onSort={onSort} className="px-3 py-2 text-center text-xs text-neutral-400" />
  </tr>
</thead>
```

테이블 상단 title 줄에 ExportButton 추가:

```tsx
<div className="flex items-center justify-between mb-2">
  <p className="text-sm text-neutral-400">총 {data.total}건</p>
  <ExportButton href={exportHref} />
</div>
```

기존 pagination 로직은 유지.

**페이지 SSR 측면 (`webapp-ui/app/(dashboard)/feedback/page.tsx`)**: `searchParams` 에서 `sort`, `dir` 읽어 API URL 에 전달. 현재 `days`, `page` 만 전달 중 — 추가:

```tsx
const sort = sp.sort ?? "date"
const dir = sp.dir ?? "desc"
const historyUrl = `/api/v1/feedback/history?days=${days}&page=${page}&size=20&sort=${sort}&dir=${dir}`
```

Step 9.3: 린트 + 빌드.

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep signal-history || echo "no errors"
pnpm build 2>&1 | tail -5
```

Step 9.4: 커밋.

```bash
git add webapp-ui/components/domain/feedback/signal-history-table.tsx webapp-ui/app/\(dashboard\)/feedback/page.tsx
git commit -m "feat(webapp-ui): SignalHistoryTable 정렬 + 내보내기"
```

---

## Task 10: RunsTable (backtest 목록) — SortableTh + ExportButton (server-side)

**Files:**
- Modify: `webapp-ui/components/domain/backtest/runs-table.tsx`
- Possibly modify: `webapp-ui/app/(dashboard)/backtest/page.tsx` (SSR searchParams 전달)

Step 10.1: 파일 확인 + Task 9 패턴 적용. 컬럼: created_at / name / start_date / final_return.

정렬 가능 컬럼들을 SortableTh 로 교체, ExportButton 추가 (`/api/v1/backtest/runs/export?{현재 sp 제외 page}`).

Step 10.2: 린트 + 빌드 + 커밋.

```bash
ruff check ...  # BE 변경 없음 skip
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint && pnpm build 2>&1 | tail -5
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/backtest/runs-table.tsx webapp-ui/app/\(dashboard\)/backtest/page.tsx
git commit -m "feat(webapp-ui): RunsTable 정렬 + 내보내기"
```

---

## Task 11: TradesTable (client-side 정렬) + ExportButton

**Files:**
- Modify: `webapp-ui/components/domain/backtest/trades-table.tsx`

Step 11.1: 파일 확인.

Step 11.2: Client-side 정렬 + ExportButton:

```tsx
"use client"
import { useMemo, useState } from "react"
import { SortableTh } from "@/components/ui/sortable-th"
import { ExportButton } from "@/components/ui/export-button"

type SortKey = "date" | "code" | "side" | "pnl" | "return_pct"

export function TradesTable({ runId, trades }: { runId: string; trades: Trade[] }) {
  const [sort, setSort] = useState<{ col: SortKey; dir: "asc" | "desc" }>({
    col: "date", dir: "desc",
  })

  const sorted = useMemo(() => {
    const copy = [...trades]
    copy.sort((a, b) => {
      const av = (a as Record<string, unknown>)[sort.col]
      const bv = (b as Record<string, unknown>)[sort.col]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sort.dir === "asc" ? cmp : -cmp
    })
    return copy
  }, [trades, sort])

  function onSort(col: SortKey) {
    setSort((prev) =>
      prev.col === col
        ? { col, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { col, dir: col === "code" || col === "side" ? "asc" : "desc" },
    )
  }

  const exportHref = `/api/v1/backtest/runs/${runId}/trades/export`

  return (
    <>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">체결 {trades.length}건</h3>
        <ExportButton href={exportHref} />
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <SortableTh label="날짜" sortKey="date" currentSort={sort.col} currentDir={sort.dir} onSort={onSort} className="px-3 py-2 text-left text-xs text-neutral-400" />
            <SortableTh label="종목" sortKey="code" currentSort={sort.col} currentDir={sort.dir} onSort={onSort} className="px-3 py-2 text-left text-xs text-neutral-400" />
            <SortableTh label="매매" sortKey="side" currentSort={sort.col} currentDir={sort.dir} onSort={onSort} className="px-3 py-2 text-left text-xs text-neutral-400" />
            <SortableTh label="손익" sortKey="pnl" currentSort={sort.col} currentDir={sort.dir} onSort={onSort} className="px-3 py-2 text-right text-xs text-neutral-400" />
            <SortableTh label="수익률" sortKey="return_pct" currentSort={sort.col} currentDir={sort.dir} onSort={onSort} className="px-3 py-2 text-right text-xs text-neutral-400" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            /* 기존 row 렌더 */
          ))}
        </tbody>
      </table>
    </>
  )
}
```

`Trade` 타입 / 기존 row 렌더링은 기존 코드 보존. `runId` prop 을 호출부에서 전달하는지 확인 — 없으면 `backtest/[runId]/page.tsx` 에서 전달.

Step 11.3: 린트 + 빌드 + 커밋.

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint && pnpm build 2>&1 | tail -5
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/backtest/trades-table.tsx
git commit -m "feat(webapp-ui): TradesTable client-side 정렬 + 내보내기"
```

---

## Task 12: PositionViewer (client-side 정렬) + ExportButton

**Files:**
- Modify: `webapp-ui/components/domain/backtest/position-viewer.tsx`

Task 11 과 동일 패턴. 컬럼: date / code / quantity / value. Export URL `/api/v1/backtest/runs/{runId}/positions/export`.

Step 12.1~12.3: Task 11 방식 적용.

커밋 메시지: `feat(webapp-ui): PositionViewer client-side 정렬 + 내보내기`.

---

## Task 13: ReportsTable — SortableTh + ExportButton (server-side)

**Files:**
- Modify: `webapp-ui/components/domain/content/reports-table.tsx`
- Possibly modify: `webapp-ui/app/(dashboard)/content/page.tsx` (sort/dir 전달)

Task 9 방식 적용. 컬럼: analyzed_at / published / title / category. Export URL `/api/v1/content/reports/export?{현재 sp 제외 page}`.

**주의**: ReportsTable 은 Task 7 (C-4) 에서 highlight row 가 추가됨. Fragment 안에 hidden row 가 있으므로 <thead> 변경만 집중.

커밋 메시지: `feat(webapp-ui): ReportsTable 정렬 + 내보내기`.

---

## Task 14: Playwright E2E 확장

**Files:**
- Modify: `webapp-ui/e2e/feedback.spec.ts`
- Modify: `webapp-ui/e2e/backtest-flow.spec.ts`

Step 14.1: feedback.spec.ts 에 추가 (기존 describe 안):

```typescript
  test("이력 탭 컬럼 클릭 시 정렬 URL 반영", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음")
    await page.getByRole("tab", { name: "이력" }).click()
    await page.getByRole("columnheader", { name: /점수/ }).click()
    await expect(page).toHaveURL(/sort=score/)
  })

  test("이력 탭 내보내기 버튼 클릭 시 다운로드 시작", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음")
    await page.getByRole("tab", { name: "이력" }).click()
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: /내보내기/ }).click(),
    ])
    expect(download.suggestedFilename()).toMatch(/feedback_history_.*\.csv/)
  })
```

Step 14.2: backtest-flow.spec.ts 에 추가:

```typescript
  test("체결 테이블 컬럼 클릭 정렬 (client-side)", async ({ page }) => {
    // 런 목록에서 최근 런 클릭해 상세로 이동 필요 — 실제 E2E 시나리오 확인 후 조정
    await page.goto("/backtest")
    const firstLink = page.locator("a[href*='/backtest/']").first()
    const visible = await firstLink.isVisible().catch(() => false)
    test.skip(!visible, "런 데이터 없음")
    await firstLink.click()
    await page.getByRole("tab", { name: /체결/ }).click()
    const header = page.getByRole("columnheader", { name: /손익/ }).first()
    if (await header.isVisible()) {
      await header.click()
      await expect(header).toHaveAttribute("aria-sort", /ascending|descending/)
    }
  })
```

Step 14.3: 린트 + 커밋.

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/e2e/feedback.spec.ts webapp-ui/e2e/backtest-flow.spec.ts
git commit -m "test(webapp-ui): 정렬 + 내보내기 E2E 스모크"
```

---

## Task 15: 전체 CI Gate 검증

Step 15.1: `pytest tests/ -x -q --tb=short | tail -5` → 1323+ passed.
Step 15.2: `ruff check alphapulse/` → clean.
Step 15.3: `cd webapp-ui && pnpm lint && pnpm build` → success.

Step 15.4: 커밋 없음 — 검증 통과 시 병합 단계.

---

## Spec Coverage 체크

- [x] §2.1 server-side sort (3 테이블) → Task 2, 4, 6
- [x] §2.2 client-side sort (2 테이블) → Task 11, 12
- [x] §3.1 Sort UI 계약 (SortableTh) → Task 8
- [x] §3.2 Export UI 계약 (ExportButton) → Task 8
- [x] §3.3 CSV 포맷 계약 → Task 1 (유틸)
- [x] §4.1 stream_csv_response → Task 1
- [x] §4.2 Store sort 확장 → Task 2, 4, 6
- [x] §4.3 Export 엔드포인트 (5개) → Task 3, 5, 7
- [x] §5 FE 공용 컴포넌트 + 테이블 통합 → Task 8-13
- [x] §6 에러 처리 (화이트리스트 fallback) → Task 2 테스트 + store 구현
- [x] §7.1 csv_stream 단위 테스트 → Task 1
- [x] §7.2 API 통합 테스트 → Task 3, 5, 7
- [x] §7.3 E2E → Task 14
- [x] §8 CI Gate → Task 15

## Implementation Notes

1. **Task 순서**: 1 (공용 유틸) → 2-3 (feedback) → 4-5 (backtest) → 6-7 (content) → 8 (FE 공용) → 9-13 (FE 테이블) → 14 (E2E) → 15 (CI).
2. **FastAPI 라우트 순서 주의**: `/history/export`, `/reports/export`, `/runs/export` 모두 같은 prefix 의 path param 엔드포인트 (`/{date}`, `/{filename:path}`, `/{run_id}`) 보다 **위**에 선언되어야 매칭 충돌 없음.
3. **sort 화이트리스트**: SQL injection 방지 핵심. 테스트 `test_get_recent_sort_invalid_column_falls_back` 가 가드.
4. **Export 메모리 안전**: `stream_csv_response` 가 generator 기반. Reader 가 대용량 list 를 만들면 의미 없으니, 필요시 store 에서도 generator 로 변경 (본 PR 범위 밖).
5. **FE URL 상태 관리**: Server-side sort 테이블 (9/10/13) 은 `router.push` 로 URL 변경 → SSR 재호출. Client-side (11/12) 는 단순 useState. 둘 다 `searchParams` 를 Export URL 빌더에 재사용.
6. **Task 5 trades/positions shape**: `reader.get_trades/get_positions` 반환이 dict 인지 Pydantic 인지 실제 코드 확인 후 `_format` 함수 조정 필요.
7. **Task 6 content sort 레거시**: 기존 `sort="newest"/"oldest"` 를 호환 유지 — 기존 `/content` 페이지 FE 는 그대로 동작.
