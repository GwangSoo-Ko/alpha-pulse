# Content/BlogPulse Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AlphaPulse 웹앱에 Content 도메인을 추가해 `./reports/*.md` 리포트를 리스트 + 필터 + 상세 마크다운으로 열람하고, Job 기반으로 `BlogMonitor.run_once()` 를 실행한다.

**Architecture:** 파일시스템 스캔 + YAML frontmatter 파싱(`ContentReader`) + FastAPI 라우터 + 기존 `JobRunner` (coroutine 지원 확장) + Next.js 3-page 구조(`/content`, `/content/reports/[filename]`, `/content/jobs/[id]`).

**Tech Stack:** FastAPI, Pydantic, pyyaml (기존), Next.js 15 App Router, react-markdown + remark-gfm (신규), @tailwindcss/typography (신규). Content 도메인은 ASYNC only — `BlogMonitor.run_once()` 는 coroutine function.

**Spec 참조:** `docs/superpowers/specs/2026-04-21-content-web-design.md`

---

## 파일 구조 (최종)

**신규 (백엔드):**
- `alphapulse/webapp/api/content.py` — FastAPI 라우터 (3 엔드포인트: GET /reports, GET /reports/{filename}, POST /monitor/run)
- `alphapulse/webapp/api/content_runner.py` — Job 어댑터 (async wrapper around BlogMonitor)
- `alphapulse/webapp/store/readers/content.py` — `ContentReader` (디렉토리 스캔 + YAML frontmatter)
- `tests/webapp/api/test_content.py`
- `tests/webapp/services/test_content_runner.py`
- `tests/webapp/store/readers/test_content_reader.py`
- `tests/webapp/store/test_jobs_find_running_by_kind.py`
- `tests/webapp/jobs/test_runner_coroutine.py`

**신규 (프론트엔드):**
- `webapp-ui/components/domain/content/reports-filter-bar.tsx`
- `webapp-ui/components/domain/content/reports-table.tsx`
- `webapp-ui/components/domain/content/report-summary-row.tsx`
- `webapp-ui/components/domain/content/report-markdown-view.tsx`
- `webapp-ui/components/domain/content/run-content-button.tsx`
- `webapp-ui/components/domain/content/content-job-progress.tsx`
- `webapp-ui/components/domain/content/no-reports.tsx`
- `webapp-ui/app/(dashboard)/content/page.tsx`
- `webapp-ui/app/(dashboard)/content/reports/[filename]/page.tsx`
- `webapp-ui/app/(dashboard)/content/jobs/[id]/page.tsx`
- `webapp-ui/e2e/content.spec.ts`

**수정:**
- `alphapulse/content/monitor.py` — `BlogMonitor.run_once()` 가 통계 dict 반환 (`{processed, skipped, no_new}`)
- `alphapulse/webapp/jobs/models.py` — `JobKind` Literal 에 `"content_monitor"` 추가
- `alphapulse/webapp/store/jobs.py` — `find_running_by_kind` 헬퍼
- `alphapulse/webapp/jobs/runner.py` — coroutine function 감지 분기
- `alphapulse/webapp/main.py` — `ContentReader` 인스턴스화 + app.state 주입 + content_router include
- `webapp-ui/components/layout/sidebar.tsx` — "콘텐츠" 항목 추가
- `webapp-ui/package.json` — react-markdown, remark-gfm, @tailwindcss/typography 의존성 추가
- `webapp-ui/tailwind.config.ts` — typography plugin 등록

---

## Task 1: JobKind 확장 + JobRepository.find_running_by_kind 헬퍼

**Files:**
- Modify: `alphapulse/webapp/jobs/models.py`
- Modify: `alphapulse/webapp/store/jobs.py`
- Create: `tests/webapp/store/test_jobs_find_running_by_kind.py`

- [ ] **Step 1: Write failing test**

Create `tests/webapp/store/test_jobs_find_running_by_kind.py`:
```python
"""JobRepository.find_running_by_kind — kind 기반 중복 Job 감지 (date 무관)."""

from alphapulse.webapp.store.jobs import JobRepository


def test_returns_none_when_no_matching_job(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    assert repo.find_running_by_kind("content_monitor") is None


def test_returns_job_when_pending_with_matching_kind(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-1"


def test_returns_job_when_running(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "running")
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-1"


def test_ignores_done_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "done")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_failed_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "failed")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_cancelled_jobs(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "cancelled")
    assert repo.find_running_by_kind("content_monitor") is None


def test_ignores_different_kind(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-1", kind="screening",
        params={}, user_id=1,
    )
    repo.update_status("job-1", "running")
    assert repo.find_running_by_kind("content_monitor") is None


def test_returns_most_recent_when_multiple_match(webapp_db):
    """동일 kind 에 2건이면 최신 Job 반환 (ORDER BY created_at DESC)."""
    import time
    repo = JobRepository(db_path=webapp_db)
    repo.create(
        job_id="job-old", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-old", "running")
    time.sleep(0.01)
    repo.create(
        job_id="job-new", kind="content_monitor",
        params={}, user_id=1,
    )
    repo.update_status("job-new", "running")
    hit = repo.find_running_by_kind("content_monitor")
    assert hit is not None
    assert hit.id == "job-new"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/store/test_jobs_find_running_by_kind.py -v`
Expected: FAIL — JobKind doesn't have "content_monitor" yet → `create()` rejects, OR `find_running_by_kind` method missing

- [ ] **Step 3: Extend JobKind literal**

Edit `alphapulse/webapp/jobs/models.py` line 10:
```python
# before
JobKind = Literal["backtest", "screening", "data_update", "market_pulse"]

# after
JobKind = Literal["backtest", "screening", "data_update", "market_pulse", "content_monitor"]
```

- [ ] **Step 4: Add find_running_by_kind method**

Add to `alphapulse/webapp/store/jobs.py` (at the end of `JobRepository` class, after `find_running_by_kind_and_date`):

```python
    def find_running_by_kind(self, kind: JobKind) -> Job | None:
        """kind 가 일치하는 pending/running Job 을 1건 반환.

        date 무관 중복 실행 방지용 (날짜 개념 없는 연속 스트림 Job).
        동시 호출 시 이 메서드 → create 사이에 race window 가 존재하므로
        호출부(API 레이어)에서 추가 보호가 필요할 수 있다.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE kind = ? "
                "AND status IN ('pending', 'running') "
                "ORDER BY created_at DESC LIMIT 1",
                (kind,),
            ).fetchone()
        return _row_to_job(row) if row else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/webapp/store/test_jobs_find_running_by_kind.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Run existing Job tests to confirm no regression**

Run: `pytest tests/webapp/store/test_jobs.py tests/webapp/store/test_jobs_find_running.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add alphapulse/webapp/jobs/models.py alphapulse/webapp/store/jobs.py tests/webapp/store/test_jobs_find_running_by_kind.py
git commit -m "feat(webapp): JobRepository.find_running_by_kind — Content Job 중복 감지"
```

---

## Task 2: JobRunner coroutine function 지원

**Files:**
- Modify: `alphapulse/webapp/jobs/runner.py`
- Create: `tests/webapp/jobs/test_runner_coroutine.py`

- [ ] **Step 1: Write failing test**

Create `tests/webapp/jobs/test_runner_coroutine.py`:
```python
"""JobRunner — coroutine function 지원 테스트."""
import asyncio

import pytest

from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.store.jobs import JobRepository


@pytest.fixture
def setup(webapp_db):
    repo = JobRepository(db_path=webapp_db)
    runner = JobRunner(job_repo=repo)
    return repo, runner


def test_sync_function_still_works(setup):
    """기존 sync 함수는 asyncio.to_thread 로 계속 실행."""
    repo, runner = setup
    repo.create(job_id="j1", kind="screening", params={}, user_id=1)

    def sync_task(progress_callback=None) -> str:
        if progress_callback:
            progress_callback(1, 1, "done")
        return "sync-result"

    asyncio.run(runner.run("j1", sync_task))

    j = repo.get("j1")
    assert j is not None
    assert j.status == "done"
    assert j.result_ref == "sync-result"


def test_async_function_awaited_directly(setup):
    """async def 함수는 await 로 직접 실행 (to_thread 사용 안 함)."""
    repo, runner = setup
    repo.create(job_id="j2", kind="content_monitor", params={}, user_id=1)

    async def async_task(progress_callback=None) -> str:
        if progress_callback:
            progress_callback(1, 1, "done")
        await asyncio.sleep(0)  # 진짜 async 동작 확인
        return "async-result"

    asyncio.run(runner.run("j2", async_task))

    j = repo.get("j2")
    assert j is not None
    assert j.status == "done"
    assert j.result_ref == "async-result"


def test_async_function_exception_marked_failed(setup):
    """async 함수 예외도 기존처럼 Job failed 로 마킹."""
    repo, runner = setup
    repo.create(job_id="j3", kind="content_monitor", params={}, user_id=1)

    async def async_failing(progress_callback=None) -> str:
        raise RuntimeError("boom")

    asyncio.run(runner.run("j3", async_failing))

    j = repo.get("j3")
    assert j is not None
    assert j.status == "failed"
    assert j.error is not None
    assert "boom" in j.error
```

Also create `tests/webapp/jobs/__init__.py` if it doesn't exist (empty file).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/jobs/test_runner_coroutine.py -v`
Expected: FAIL — `test_async_function_awaited_directly` fails because `asyncio.to_thread(async_func)` returns a coroutine (not the function result), so `result` is a coroutine object, not `"async-result"`.

- [ ] **Step 3: Extend JobRunner.run to detect coroutine functions**

Edit `alphapulse/webapp/jobs/runner.py`. Import `inspect` at top:
```python
import inspect
```

Replace the `try` block inside `run()`:

```python
        kwargs = {**kwargs, "progress_callback": _on_progress}
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            self.jobs.update_status(
                job_id, "done",
                result_ref=str(result) if result is not None else None,
                finished_at=time.time(),
            )
        except Exception as e:
            logger.exception("job %s failed", job_id)
            self.jobs.update_status(
                job_id, "failed",
                error=f"{type(e).__name__}: {e}",
                finished_at=time.time(),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/jobs/test_runner_coroutine.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Full webapp regression**

Run: `pytest tests/webapp/ -q --tb=short`
Expected: 모두 PASS (기존 backtest/screening/data/market 등 영향 없음; 1개 pre-existing 무관 실패 허용)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/jobs/runner.py tests/webapp/jobs/test_runner_coroutine.py tests/webapp/jobs/__init__.py
git commit -m "feat(webapp): JobRunner coroutine function 지원 (Content 도메인 준비)"
```

---

## Task 3: ContentReader — 파일 스캔 + YAML frontmatter 파싱

**Files:**
- Create: `alphapulse/webapp/store/readers/content.py`
- Create: `tests/webapp/store/readers/test_content_reader.py`

- [ ] **Step 1: Write failing test**

Create `tests/webapp/store/readers/test_content_reader.py`:
```python
"""ContentReader — 디렉토리 스캔 + frontmatter 파싱 + 필터."""
from pathlib import Path

import pytest

from alphapulse.webapp.store.readers.content import ContentReader


def _write_report(
    dirpath: Path,
    filename: str,
    *,
    title: str = "테스트",
    category: str = "경제",
    published: str = "2026-04-20",
    analyzed_at: str = "2026-04-20 15:30:00",
    source: str = "https://example.com",
    source_tag: str = "",
    body: str = "본문",
) -> Path:
    tag_line = f'source_tag: "{source_tag}"\n' if source_tag else ""
    content = (
        f'---\n'
        f'title: "{title}"\n'
        f'source: "{source}"\n'
        f'published: "{published}"\n'
        f'analyzed_at: "{analyzed_at}"\n'
        f'category: "{category}"\n'
        f'{tag_line}'
        f'---\n\n'
        f'{body}\n'
    )
    path = dirpath / filename
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


def test_list_reports_empty(reports_dir):
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["items"] == []
    assert result["total"] == 0
    assert result["page"] == 1
    assert result["size"] == 20


def test_list_reports_parses_frontmatter(reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", category="경제")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["filename"] == "a.md"
    assert item["title"] == "글 A"
    assert item["category"] == "경제"
    assert item["published"] == "2026-04-20"
    assert item["source"] == "https://example.com"


def test_list_reports_ignores_non_md_files(reports_dir):
    _write_report(reports_dir, "a.md")
    (reports_dir / "b.txt").write_text("not md")
    (reports_dir / ".hidden.md").write_text("hidden")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    # .md 이면서 숨김이 아닌 것만
    assert result["total"] == 1


def test_list_reports_filters_by_category(reports_dir):
    _write_report(reports_dir, "a.md", title="A", category="경제")
    _write_report(reports_dir, "b.md", title="B", category="주식")
    _write_report(reports_dir, "c.md", title="C", category="사회")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(categories=["경제", "주식"])
    titles = {i["title"] for i in result["items"]}
    assert titles == {"A", "B"}


def test_list_reports_filters_by_date_range(reports_dir):
    _write_report(reports_dir, "a.md", title="A", published="2026-03-10")
    _write_report(reports_dir, "b.md", title="B", published="2026-04-15")
    _write_report(reports_dir, "c.md", title="C", published="2026-05-01")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(date_from="20260401", date_to="20260430")
    titles = {i["title"] for i in result["items"]}
    assert titles == {"B"}


def test_list_reports_filters_by_query_case_insensitive(reports_dir):
    _write_report(reports_dir, "a.md", title="버핏의 투자 철학")
    _write_report(reports_dir, "b.md", title="테슬라 주가 분석")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(query="버핏")
    assert result["total"] == 1
    assert result["items"][0]["title"] == "버핏의 투자 철학"


def test_list_reports_sort_newest_first_by_analyzed_at(reports_dir):
    _write_report(reports_dir, "a.md", title="A", analyzed_at="2026-04-20 10:00:00")
    _write_report(reports_dir, "b.md", title="B", analyzed_at="2026-04-21 10:00:00")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(sort="newest")
    assert [i["title"] for i in result["items"]] == ["B", "A"]


def test_list_reports_sort_oldest_first(reports_dir):
    _write_report(reports_dir, "a.md", title="A", analyzed_at="2026-04-20 10:00:00")
    _write_report(reports_dir, "b.md", title="B", analyzed_at="2026-04-21 10:00:00")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports(sort="oldest")
    assert [i["title"] for i in result["items"]] == ["A", "B"]


def test_list_reports_pagination(reports_dir):
    for i in range(5):
        _write_report(
            reports_dir, f"r{i:02d}.md", title=f"R{i}",
            analyzed_at=f"2026-04-{20-i:02d} 10:00:00",
        )
    reader = ContentReader(reports_dir=reports_dir)
    page1 = reader.list_reports(page=1, size=2)
    page2 = reader.list_reports(page=2, size=2)
    page3 = reader.list_reports(page=3, size=2)
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 1


def test_list_reports_fallback_for_missing_frontmatter(reports_dir):
    """frontmatter 없는 파일도 skip 하지 않고 파일명을 title 로 사용."""
    (reports_dir / "no_fm.md").write_text("# 그냥 마크다운\n\n본문", encoding="utf-8")
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["filename"] == "no_fm.md"
    assert item["title"] == "no_fm"   # stem
    assert item["category"] == "미분류"


def test_list_reports_fallback_for_malformed_yaml(reports_dir):
    """깨진 YAML 도 skip 하지 않고 fallback 사용."""
    (reports_dir / "bad.md").write_text(
        "---\ntitle: 짝 따옴표 없음\n bad: : yaml\n---\n본문",
        encoding="utf-8",
    )
    reader = ContentReader(reports_dir=reports_dir)
    result = reader.list_reports()
    assert result["total"] == 1


def test_get_report_returns_body(reports_dir):
    _write_report(reports_dir, "a.md", title="글", body="이것은 본문이다")
    reader = ContentReader(reports_dir=reports_dir)
    detail = reader.get_report("a.md")
    assert detail is not None
    assert detail["title"] == "글"
    assert "이것은 본문이다" in detail["body"]
    # frontmatter 는 body 에 포함되지 않음
    assert "---" not in detail["body"][:10]


def test_get_report_returns_none_when_missing(reports_dir):
    reader = ContentReader(reports_dir=reports_dir)
    assert reader.get_report("missing.md") is None


def test_distinct_categories(reports_dir):
    _write_report(reports_dir, "a.md", category="경제")
    _write_report(reports_dir, "b.md", category="주식")
    _write_report(reports_dir, "c.md", category="경제")
    reader = ContentReader(reports_dir=reports_dir)
    cats = reader.distinct_categories()
    assert sorted(cats) == ["경제", "주식"]
```

Also ensure `tests/webapp/store/readers/__init__.py` exists (check — if not, create empty file).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/store/readers/test_content_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.store.readers.content'`

- [ ] **Step 3: Implement ContentReader**

Create `alphapulse/webapp/store/readers/content.py`:
```python
"""ContentReader — ./reports/*.md 디렉토리 스캔 + YAML frontmatter 파싱.

Read-only. 실제 리포트 쓰기는 `alphapulse.content.reporter.ReportWriter` 가 담당.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, TypedDict

import yaml

logger = logging.getLogger(__name__)


class ReportMeta(TypedDict):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str


class ReportFull(ReportMeta):
    body: str


class ListResult(TypedDict):
    items: list[ReportMeta]
    total: int
    page: int
    size: int
    categories: list[str]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """마크다운 텍스트에서 frontmatter + body 분리.

    frontmatter 가 없거나 파싱 실패 시 (빈 dict, 원본 텍스트).
    """
    if not text.startswith("---"):
        return {}, text
    # 첫 줄 이후 --- 까지 찾기
    lines = text.split("\n")
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx < 0:
        return {}, text
    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    try:
        meta = yaml.safe_load(yaml_text) or {}
        if not isinstance(meta, dict):
            logger.warning("frontmatter 가 dict 가 아님: %r", meta)
            return {}, body
        return meta, body
    except yaml.YAMLError as e:
        logger.warning("YAML 파싱 실패: %s", e)
        return {}, body


def _meta_from_file(path: Path) -> ReportMeta:
    """파일에서 frontmatter 파싱. 실패 시 fallback."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("파일 읽기 실패 %s: %s", path, e)
        text = ""
    fm, _body = _parse_frontmatter(text)
    return {
        "filename": path.name,
        "title": str(fm.get("title") or path.stem),
        "category": str(fm.get("category") or "미분류"),
        "published": str(fm.get("published") or ""),
        "analyzed_at": str(fm.get("analyzed_at") or ""),
        "source": str(fm.get("source") or ""),
        "source_tag": str(fm.get("source_tag") or ""),
    }


def _date_in_range(
    published: str, date_from: str | None, date_to: str | None,
) -> bool:
    """published(YYYY-MM-DD 또는 YYYYMMDD) 가 date_from~date_to 범위에 있는지."""
    if not date_from and not date_to:
        return True
    if not published:
        return False
    normalized = published.replace("-", "").replace(".", "")[:8]
    if not normalized.isdigit() or len(normalized) != 8:
        return False
    if date_from and normalized < date_from:
        return False
    if date_to and normalized > date_to:
        return False
    return True


class ContentReader:
    """./reports/*.md 읽기 전용 리더."""

    def __init__(self, reports_dir: Path | str) -> None:
        self.reports_dir = Path(reports_dir)

    def _scan(self) -> list[ReportMeta]:
        if not self.reports_dir.is_dir():
            return []
        metas: list[ReportMeta] = []
        for entry in self.reports_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".md":
                continue
            if entry.name.startswith("."):
                continue
            metas.append(_meta_from_file(entry))
        return metas

    def list_reports(
        self,
        *,
        categories: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        query: str | None = None,
        sort: Literal["newest", "oldest"] = "newest",
        page: int = 1,
        size: int = 20,
    ) -> ListResult:
        all_metas = self._scan()
        # 필터
        filtered = [
            m for m in all_metas
            if (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
            and (not query or query.lower() in m["title"].lower())
        ]
        # 정렬 (analyzed_at 기준)
        reverse = sort == "newest"
        filtered.sort(key=lambda m: m["analyzed_at"], reverse=reverse)
        # 페이지네이션
        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        items = filtered[start:end]
        # 전체 파일 기준 distinct 카테고리
        categories_all = sorted({m["category"] for m in all_metas})
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "categories": categories_all,
        }

    def get_report(self, filename: str) -> ReportFull | None:
        path = self.reports_dir / filename
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("파일 읽기 실패 %s: %s", path, e)
            return None
        fm, body = _parse_frontmatter(text)
        return {
            "filename": path.name,
            "title": str(fm.get("title") or path.stem),
            "category": str(fm.get("category") or "미분류"),
            "published": str(fm.get("published") or ""),
            "analyzed_at": str(fm.get("analyzed_at") or ""),
            "source": str(fm.get("source") or ""),
            "source_tag": str(fm.get("source_tag") or ""),
            "body": body,
        }

    def distinct_categories(self) -> list[str]:
        return sorted({m["category"] for m in self._scan()})
```

Also create `tests/webapp/store/readers/__init__.py` (empty) if not present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/store/readers/test_content_reader.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/store/readers/content.py tests/webapp/store/readers/__init__.py tests/webapp/store/readers/test_content_reader.py
git commit -m "feat(webapp): ContentReader — reports/ 디렉토리 스캔 + frontmatter 파싱"
```

---

## Task 4: Content API — GET /reports 리스트 + 상세

**Files:**
- Create: `alphapulse/webapp/api/content.py` (list + detail endpoints)
- Create: `tests/webapp/api/test_content.py`

- [ ] **Step 1: Write failing tests for GET endpoints**

Create `tests/webapp/api/test_content.py`:
```python
"""Content API — GET endpoints."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.api.content import router as content_router
from alphapulse.webapp.auth.routes import router as auth_router
from alphapulse.webapp.auth.security import hash_password
from alphapulse.webapp.config import WebAppConfig
from alphapulse.webapp.jobs.routes import router as jobs_router
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.middleware.csrf import CSRFMiddleware
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.login_attempts import LoginAttemptsRepository
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.sessions import SessionRepository
from alphapulse.webapp.store.users import UserRepository


def _write_report(
    dirpath: Path,
    filename: str,
    *,
    title: str = "테스트",
    category: str = "경제",
    published: str = "2026-04-20",
    analyzed_at: str = "2026-04-20 15:30:00",
    body: str = "본문",
) -> None:
    content = (
        f'---\ntitle: "{title}"\nsource: "https://x.y"\n'
        f'published: "{published}"\nanalyzed_at: "{analyzed_at}"\n'
        f'category: "{category}"\n---\n\n{body}\n'
    )
    (dirpath / filename).write_text(content, encoding="utf-8")


@pytest.fixture
def reports_dir(tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture
def app(webapp_db, reports_dir):
    cfg = WebAppConfig(
        session_secret="x" * 32,
        monitor_bot_token="", monitor_channel_id="",
        db_path=str(webapp_db),
    )
    app = FastAPI()
    app.state.config = cfg
    app.state.users = UserRepository(db_path=webapp_db)
    app.state.sessions = SessionRepository(db_path=webapp_db)
    app.state.login_attempts = LoginAttemptsRepository(db_path=webapp_db)
    app.state.jobs = JobRepository(db_path=webapp_db)
    app.state.job_runner = JobRunner(job_repo=app.state.jobs)
    app.state.content_reader = ContentReader(reports_dir=reports_dir)
    app.state.audit = MagicMock()
    app.state.users.create(
        email="a@x.com",
        password_hash=hash_password("long-enough-pw!"),
        role="user",
    )
    app.add_middleware(CSRFMiddleware, secret=cfg.session_secret)
    # /api/v1/csrf-token endpoint
    from fastapi import Request
    @app.get("/api/v1/csrf-token")
    async def csrf_token(request: Request):
        return {"token": request.state.csrf_token}
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(content_router)
    return app


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/csrf-token")
    token = r.json()["token"]
    c.post(
        "/api/v1/auth/login",
        json={"email": "a@x.com", "password": "long-enough-pw!"},
        headers={"x-csrf-token": token},
    )
    c.headers.update({"X-CSRF-Token": token})
    return c


def test_list_reports_empty(client):
    r = client.get("/api/v1/content/reports")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["categories"] == []


def test_list_reports_returns_items(client, reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", category="경제")
    _write_report(reports_dir, "b.md", title="글 B", category="주식")
    r = client.get("/api/v1/content/reports")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    titles = {i["title"] for i in body["items"]}
    assert titles == {"글 A", "글 B"}


def test_list_reports_category_filter_multiple(client, reports_dir):
    _write_report(reports_dir, "a.md", title="A", category="경제")
    _write_report(reports_dir, "b.md", title="B", category="주식")
    _write_report(reports_dir, "c.md", title="C", category="사회")
    r = client.get("/api/v1/content/reports?category=경제&category=주식")
    body = r.json()
    titles = {i["title"] for i in body["items"]}
    assert titles == {"A", "B"}


def test_list_reports_query(client, reports_dir):
    _write_report(reports_dir, "a.md", title="버핏의 투자")
    _write_report(reports_dir, "b.md", title="테슬라 주가")
    r = client.get("/api/v1/content/reports?q=버핏")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "버핏의 투자"


def test_list_reports_date_range(client, reports_dir):
    _write_report(reports_dir, "a.md", title="A", published="2026-03-10")
    _write_report(reports_dir, "b.md", title="B", published="2026-04-15")
    r = client.get("/api/v1/content/reports?from=20260401&to=20260430")
    body = r.json()
    titles = {i["title"] for i in body["items"]}
    assert titles == {"B"}


def test_list_reports_size_out_of_range(client):
    r = client.get("/api/v1/content/reports?size=0")
    assert r.status_code == 422
    r = client.get("/api/v1/content/reports?size=500")
    assert r.status_code == 422


def test_detail_returns_report(client, reports_dir):
    _write_report(reports_dir, "a.md", title="글 A", body="본문 내용")
    r = client.get("/api/v1/content/reports/a.md")
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "a.md"
    assert body["title"] == "글 A"
    assert "본문 내용" in body["body"]


def test_detail_404_when_missing(client):
    r = client.get("/api/v1/content/reports/missing.md")
    assert r.status_code == 404


def test_detail_rejects_path_traversal(client):
    r = client.get("/api/v1/content/reports/..%2Fetc%2Fpasswd")
    assert r.status_code == 400


def test_detail_rejects_non_md_extension(client):
    r = client.get("/api/v1/content/reports/file.txt")
    assert r.status_code == 400


def test_detail_rejects_slash_in_name(client):
    r = client.get("/api/v1/content/reports/sub%2Ffile.md")
    assert r.status_code == 400


def test_list_requires_auth(app):
    c = TestClient(app, base_url="https://testserver")
    r = c.get("/api/v1/content/reports")
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/api/test_content.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.api.content'`

- [ ] **Step 3: Implement API — list + detail (POST /run comes in Task 5)**

Create `alphapulse/webapp/api/content.py`. Note: `from` is a Python keyword so we use `alias="from"` on a `date_from` parameter.

```python
"""Content API — BlogPulse 리포트 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/content", tags=["content"])


class ReportSummary(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str = ""


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    page: int
    size: int
    total: int
    categories: list[str]


class ReportDetail(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str = ""
    body: str


class MonitorRunRequest(BaseModel):
    pass


class MonitorRunResponse(BaseModel):
    job_id: str
    reused: bool


def get_content_reader(request: Request) -> ContentReader:
    return request.app.state.content_reader


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def _validate_filename(name: str) -> str:
    """경로 조작 차단 — .md 확장자, 슬래시/점점/숨김 금지."""
    if not name.endswith(".md"):
        raise HTTPException(400, "Invalid filename — must end with .md")
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, "Invalid filename — path traversal not allowed")
    return name


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: list[str] | None = Query(None),
    date_from: str | None = Query(None, alias="from", max_length=8),
    date_to: str | None = Query(None, alias="to", max_length=8),
    q: str | None = Query(None, max_length=200),
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    result = reader.list_reports(
        categories=category,
        date_from=date_from,
        date_to=date_to,
        query=q,
        sort=sort,  # type: ignore[arg-type]
        page=page,
        size=size,
    )
    return ReportListResponse(
        items=[ReportSummary(**i) for i in result["items"]],
        page=result["page"],
        size=result["size"],
        total=result["total"],
        categories=result["categories"],
    )


@router.get("/reports/{filename}", response_model=ReportDetail)
async def get_report(
    filename: str = Path(...),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    _validate_filename(filename)
    detail = reader.get_report(filename)
    if detail is None:
        raise HTTPException(404, "Report not found")
    return ReportDetail(**detail)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/api/test_content.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add alphapulse/webapp/api/content.py tests/webapp/api/test_content.py
git commit -m "feat(webapp): Content API GET endpoints (reports list + detail)"
```

---

## Task 5: BlogMonitor 통계 반환 + Content Runner + POST /monitor/run

**Files:**
- Modify: `alphapulse/content/monitor.py` — `run_once` 가 dict 반환
- Create: `alphapulse/webapp/api/content_runner.py`
- Modify: `alphapulse/webapp/api/content.py` — POST 추가
- Modify: `tests/webapp/api/test_content.py` — POST 테스트 추가
- Create: `tests/webapp/services/test_content_runner.py`

- [ ] **Step 1: Update BlogMonitor.run_once to return summary dict**

Edit `alphapulse/content/monitor.py`. Change `run_once`:

```python
    async def run_once(self, force_latest: int = 0, send_telegram: bool = True) -> dict:
        """신규 포스트 처리.

        Returns:
            요약 dict: {processed: int, skipped: int, no_new: bool}
        """
        logger.info("모니터링 시작...")
        posts = self.detector.fetch_new_posts(force_latest=force_latest)

        if not posts:
            logger.info("새 글 없음")
            return {"processed": 0, "skipped": 0, "no_new": True}

        logger.info(f"{len(posts)}개 새 글 발견")
        target_posts, skipped = self.category_filter.filter_posts(posts)

        if not target_posts:
            logger.info("대상 카테고리 글 없음")
            for post in posts:
                self.detector.mark_seen(post["id"])
            return {"processed": 0, "skipped": len(skipped), "no_new": False}

        logger.info(f"대상 글 {len(target_posts)}개, 스킵 {len(skipped)}개")

        processed = 0
        for post in target_posts:
            try:
                ok = await self._process_post(post, send_telegram=send_telegram)
                if ok:
                    processed += 1
            except Exception as e:
                logger.error(f'글 처리 실패 "{post["title"]}": {e}')
            finally:
                self.detector.mark_seen(post["id"])

        for post in skipped:
            self.detector.mark_seen(post["id"])

        return {"processed": processed, "skipped": len(skipped), "no_new": False}
```

- [ ] **Step 2: Add BlogMonitor return-value test (existing test file sanity)**

Check if there's an existing test file for monitor.py. If yes, extend it. If not, create `tests/content/test_monitor_return.py`:
```python
"""BlogMonitor.run_once 반환값 스모크."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.content.monitor import BlogMonitor


@pytest.mark.asyncio
async def test_run_once_returns_no_new_when_empty():
    with patch("alphapulse.content.monitor.PostDetector") as PD, \
         patch("alphapulse.content.monitor.CategoryFilter"), \
         patch("alphapulse.content.monitor.BlogCrawler"), \
         patch("alphapulse.content.monitor.AnalysisOrchestrator"), \
         patch("alphapulse.content.monitor.ReportWriter"), \
         patch("alphapulse.content.monitor.TelegramNotifier"):
        PD.return_value.fetch_new_posts.return_value = []

        monitor = BlogMonitor(
            blog_id="x", state_file="/tmp/s.json",
            reports_dir="/tmp/r", gemini_api_key="k",
            telegram_bot_token="t", telegram_chat_id="c",
        )
        result = await monitor.run_once(send_telegram=False)

    assert result == {"processed": 0, "skipped": 0, "no_new": True}


@pytest.mark.asyncio
async def test_run_once_returns_counts():
    with patch("alphapulse.content.monitor.PostDetector") as PD, \
         patch("alphapulse.content.monitor.CategoryFilter") as CF, \
         patch("alphapulse.content.monitor.BlogCrawler"), \
         patch("alphapulse.content.monitor.AnalysisOrchestrator"), \
         patch("alphapulse.content.monitor.ReportWriter"), \
         patch("alphapulse.content.monitor.TelegramNotifier"):
        PD.return_value.fetch_new_posts.return_value = [
            {"id": "p1", "title": "A", "category": "경제"},
            {"id": "p2", "title": "B", "category": "스포츠"},
        ]
        CF.return_value.filter_posts.return_value = (
            [{"id": "p1", "title": "A", "category": "경제"}],  # targets
            [{"id": "p2", "title": "B", "category": "스포츠"}],  # skipped
        )

        monitor = BlogMonitor(
            blog_id="x", state_file="/tmp/s.json",
            reports_dir="/tmp/r", gemini_api_key="k",
            telegram_bot_token="t", telegram_chat_id="c",
        )
        # _process_post 를 AsyncMock 으로 override 해서 실제 처리 skip
        monitor._process_post = AsyncMock(return_value=True)
        result = await monitor.run_once(send_telegram=False)

    assert result == {"processed": 1, "skipped": 1, "no_new": False}
```

- [ ] **Step 3: Run BlogMonitor test to verify**

Run: `pytest tests/content/test_monitor_return.py -v`
Expected: PASS (2 tests)

Also run existing content tests:
Run: `pytest tests/content/ -q`
Expected: no regression (may show one existing test that asserts return None — if so, update it)

- [ ] **Step 4: Write failing test for ContentRunner**

Create `tests/webapp/services/test_content_runner.py`:
```python
"""ContentRunner — Job 어댑터 테스트."""
import asyncio
from unittest.mock import AsyncMock, patch


def test_runs_blog_monitor_and_returns_summary():
    """BlogMonitor.run_once 를 호출하고 result_ref 로 요약 문자열 반환."""
    from alphapulse.webapp.api.content_runner import run_content_monitor_async

    mock_monitor = AsyncMock()
    mock_monitor.run_once.return_value = {
        "processed": 2, "skipped": 1, "no_new": False,
    }

    progress_calls: list[tuple[int, int, str]] = []
    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.api.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        result = asyncio.run(
            run_content_monitor_async(progress_callback=on_progress),
        )

    # BlogMonitor.run_once called with send_telegram=False
    mock_monitor.run_once.assert_awaited_once_with(send_telegram=False)

    # 결과 문자열 포맷: "처리 2개, 스킵 1개"
    assert "2" in result and "1" in result
    assert progress_calls[0] == (0, 1, "BlogPulse 모니터링 시작")
    assert progress_calls[-1][0] == 1 and progress_calls[-1][1] == 1


def test_handles_no_new_posts():
    from alphapulse.webapp.api.content_runner import run_content_monitor_async

    mock_monitor = AsyncMock()
    mock_monitor.run_once.return_value = {"processed": 0, "skipped": 0, "no_new": True}
    with patch(
        "alphapulse.webapp.api.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        result = asyncio.run(
            run_content_monitor_async(progress_callback=lambda *_: None),
        )
    assert "새 글 없음" in result or "no_new" in result.lower() or "0" in result


def test_propagates_exception():
    from alphapulse.webapp.api.content_runner import run_content_monitor_async
    import pytest

    mock_monitor = AsyncMock()
    mock_monitor.run_once.side_effect = RuntimeError("crawl failed")
    with patch(
        "alphapulse.webapp.api.content_runner.BlogMonitor",
        return_value=mock_monitor,
    ):
        with pytest.raises(RuntimeError, match="crawl failed"):
            asyncio.run(
                run_content_monitor_async(progress_callback=lambda *_: None),
            )
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/webapp/services/test_content_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.webapp.api.content_runner'`

- [ ] **Step 6: Implement ContentRunner**

Create `alphapulse/webapp/api/content_runner.py`:
```python
"""ContentRunner — Job 에서 호출되는 BlogMonitor 실행 async 헬퍼.

BlogMonitor.run_once() 는 coroutine function 이므로 JobRunner 의
asyncio.to_thread 경로를 우회하고 직접 await 된다 (Task 2 에서 추가됨).
웹에서 실행되는 Job 은 텔레그램 발송을 끄고(`send_telegram=False`) 조용히 수집만.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.content.monitor import BlogMonitor


async def run_content_monitor_async(
    *,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """BlogMonitor.run_once(send_telegram=False) 실행.

    Args:
        progress_callback: Job 진행률 훅 (current, total, text).

    Returns:
        요약 문자열 (Job.result_ref 로 저장): "처리 N개, 스킵 M개"
        또는 "새 글 없음".
    """
    progress_callback(0, 1, "BlogPulse 모니터링 시작")
    monitor = BlogMonitor()
    summary = await monitor.run_once(send_telegram=False)
    if summary.get("no_new"):
        text = "새 글 없음"
    else:
        text = f"처리 {summary['processed']}개, 스킵 {summary['skipped']}개"
    progress_callback(1, 1, text)
    return text
```

- [ ] **Step 7: Run ContentRunner tests to verify**

Run: `pytest tests/webapp/services/test_content_runner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Write failing tests for POST /monitor/run**

Append to `tests/webapp/api/test_content.py`:
```python
def test_run_creates_job_and_returns_id(client, monkeypatch):
    """POST /monitor/run → BackgroundTasks 스케줄, reused=false."""
    async def fake_runner_run(self, job_id, func, **kwargs):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is False
    assert "job_id" in body


def test_run_reuses_existing_job(client, app, monkeypatch):
    """같은 kind 의 running Job 있으면 그 id 반환, reused=true."""
    app.state.jobs.create(
        job_id="existing", kind="content_monitor",
        params={}, user_id=1,
    )
    app.state.jobs.update_status("existing", "running")

    async def fake_runner_run(self, job_id, func, **kwargs):
        raise AssertionError("should not be called")
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", fake_runner_run,
    )

    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "existing"
    assert body["reused"] is True


def test_run_audit_log(client, app, monkeypatch):
    async def noop(self, *a, **kw):
        pass
    monkeypatch.setattr(
        "alphapulse.webapp.jobs.runner.JobRunner.run", noop,
    )
    r = client.post("/api/v1/content/monitor/run", json={})
    assert r.status_code == 200
    assert app.state.audit.log.called
    assert app.state.audit.log.call_args.args[0] == "webapp.content.monitor.run"
```

- [ ] **Step 9: Run tests to verify they fail**

Run: `pytest tests/webapp/api/test_content.py -v -k "run"`
Expected: FAIL — POST endpoint not yet registered

- [ ] **Step 10: Add POST endpoint to content.py**

Add to `alphapulse/webapp/api/content.py` (extend imports + add endpoint):

```python
import uuid

from fastapi import BackgroundTasks
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.api.content_runner import run_content_monitor_async


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


@router.post("/monitor/run", response_model=MonitorRunResponse)
async def run_monitor(
    body: MonitorRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    # 중복 running Job 감지 → 재사용 (kind 만으로 감지, 날짜 무관)
    existing = jobs.find_running_by_kind("content_monitor")
    if existing is not None:
        return MonitorRunResponse(job_id=existing.id, reused=True)

    job_id = str(uuid.uuid4())
    jobs.create(
        job_id=job_id, kind="content_monitor",
        params={}, user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.content.monitor.run",
            component="webapp",
            data={"user_id": user.id, "job_id": job_id},
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_content_monitor_async,
        )

    background_tasks.add_task(_run)
    return MonitorRunResponse(job_id=job_id, reused=False)
```

- [ ] **Step 11: Run tests**

Run: `pytest tests/webapp/api/test_content.py -v`
Expected: PASS (all 15 tests — 12 GET + 3 POST)

- [ ] **Step 12: Commit**

```bash
git add alphapulse/content/monitor.py alphapulse/webapp/api/content_runner.py alphapulse/webapp/api/content.py tests/content/test_monitor_return.py tests/webapp/services/test_content_runner.py tests/webapp/api/test_content.py
git commit -m "feat(webapp): Content POST /monitor/run + BlogMonitor 통계 반환 + ContentRunner"
```

---

## Task 6: main.py — ContentReader state 주입 + Router 등록

**Files:**
- Modify: `alphapulse/webapp/main.py`
- Modify: `tests/webapp/test_main.py`

- [ ] **Step 1: Write failing test**

Append to `tests/webapp/test_main.py`:
```python
def test_content_router_registered():
    """create_app 부팅 후 content 엔드포인트가 라우트에 등록된다."""
    from alphapulse.webapp.main import create_app
    app = create_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/content/reports" in routes
    assert "/api/v1/content/reports/{filename}" in routes
    assert "/api/v1/content/monitor/run" in routes


def test_content_reader_on_state():
    from alphapulse.webapp.main import create_app
    app = create_app()
    assert hasattr(app.state, "content_reader")
    assert app.state.content_reader is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webapp/test_main.py -v -k "content"`
Expected: FAIL

- [ ] **Step 3: Wire content router + content_reader state**

Edit `alphapulse/webapp/main.py`:

Add import near other API imports:
```python
from alphapulse.webapp.api.content import router as content_router
```

Add ContentReader import near other reader imports:
```python
from alphapulse.webapp.store.readers.content import ContentReader
```

In `create_app()`, after `pulse_history = PulseHistory(...)` (from Task 6 of Market Pulse plan), add:
```python
    content_reader = ContentReader(reports_dir=core.REPORTS_DIR)
```

After `app.state.pulse_history = pulse_history`, add:
```python
    app.state.content_reader = content_reader
```

After `app.include_router(market_router)`, add:
```python
    app.include_router(content_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/webapp/test_main.py -v`
Expected: PASS (new + existing)

- [ ] **Step 5: Full webapp regression**

Run: `pytest tests/webapp/ -q --tb=short`
Expected: no regression (1 pre-existing unrelated failure allowed)

- [ ] **Step 6: Commit**

```bash
git add alphapulse/webapp/main.py tests/webapp/test_main.py
git commit -m "feat(webapp): main.py 에 content router + ContentReader 상태 주입"
```

---

## Task 7: Frontend 의존성 설치

**Files:**
- Modify: `webapp-ui/package.json`
- Modify: `webapp-ui/tailwind.config.ts`

- [ ] **Step 1: Install dependencies**

Run:
```bash
cd webapp-ui && pnpm add react-markdown remark-gfm @tailwindcss/typography
```

Expected: `package.json` 업데이트, `pnpm-lock.yaml` 변경.

- [ ] **Step 2: Register Tailwind typography plugin**

Read `webapp-ui/tailwind.config.ts` and find the `plugins` array. Add `require("@tailwindcss/typography")`:

If the file uses ESM imports (`import type { Config } from 'tailwindcss'`), use dynamic require via a compatible form. Check existing file first. If it uses `module.exports`, add:

```ts
plugins: [require("@tailwindcss/typography")],
```

If it uses ESM with existing plugins array:
```ts
import typography from "@tailwindcss/typography"
// ...
plugins: [typography],
```

Pick whichever matches the file's existing style.

- [ ] **Step 3: Verify build**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/package.json webapp-ui/pnpm-lock.yaml webapp-ui/tailwind.config.ts
git commit -m "feat(webapp-ui): react-markdown + remark-gfm + @tailwindcss/typography 의존성 추가"
```

---

## Task 8: Frontend — ReportsFilterBar

**Files:**
- Create: `webapp-ui/components/domain/content/reports-filter-bar.tsx`

- [ ] **Step 1: Implement component**

Create `webapp-ui/components/domain/content/reports-filter-bar.tsx`:
```tsx
"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function ReportsFilterBar({ categories }: { categories: string[] }) {
  const router = useRouter()
  const params = useSearchParams()

  const initialSelected = new Set(params.getAll("category"))
  const [selected, setSelected] = useState<Set<string>>(initialSelected)
  const [from, setFrom] = useState(params.get("from") ?? "")
  const [to, setTo] = useState(params.get("to") ?? "")
  const [q, setQ] = useState(params.get("q") ?? "")

  const toggleCategory = (cat: string) => {
    const next = new Set(selected)
    if (next.has(cat)) next.delete(cat)
    else next.add(cat)
    setSelected(next)
  }

  const apply = () => {
    const sp = new URLSearchParams()
    selected.forEach((c) => sp.append("category", c))
    if (from) sp.set("from", from)
    if (to) sp.set("to", to)
    if (q) sp.set("q", q)
    router.push(`/content?${sp}`)
  }

  const clear = () => {
    setSelected(new Set())
    setFrom("")
    setTo("")
    setQ("")
    router.push("/content")
  }

  return (
    <div className="space-y-3 rounded border border-neutral-800 bg-neutral-900 p-4">
      <div>
        <Label className="text-xs text-neutral-400">카테고리</Label>
        <div className="mt-1 flex flex-wrap gap-2">
          {categories.length === 0 && (
            <span className="text-sm text-neutral-500">카테고리 없음</span>
          )}
          {categories.map((cat) => (
            <label key={cat} className="inline-flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={selected.has(cat)}
                onChange={() => toggleCategory(cat)}
                className="h-4 w-4"
              />
              {cat}
            </label>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <Label htmlFor="from" className="text-xs text-neutral-400">
            발행일 시작 (YYYYMMDD)
          </Label>
          <Input
            id="from" value={from}
            onChange={(e) => setFrom(e.target.value)}
            placeholder="20260301"
          />
        </div>
        <div>
          <Label htmlFor="to" className="text-xs text-neutral-400">
            발행일 종료 (YYYYMMDD)
          </Label>
          <Input
            id="to" value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="20260430"
          />
        </div>
        <div>
          <Label htmlFor="q" className="text-xs text-neutral-400">제목 검색</Label>
          <Input
            id="q" value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="검색어"
          />
        </div>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={apply}>적용</Button>
        <Button size="sm" variant="outline" onClick={clear}>초기화</Button>
      </div>
    </div>
  )
}
```

Note: `RunContentButton` (Task 11) is a separate component placed next to the page title — the filter bar doesn't need its own run button.

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/content/reports-filter-bar.tsx
git commit -m "feat(webapp-ui): ReportsFilterBar — 카테고리/날짜/검색 필터"
```

---

## Task 9: Frontend — ReportsTable + ReportSummaryRow

**Files:**
- Create: `webapp-ui/components/domain/content/report-summary-row.tsx`
- Create: `webapp-ui/components/domain/content/reports-table.tsx`

- [ ] **Step 1: Implement ReportSummaryRow**

Create `webapp-ui/components/domain/content/report-summary-row.tsx`:
```tsx
import Link from "next/link"

export type ReportSummary = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  source: string
  source_tag: string
}

export function ReportSummaryRow({ item }: { item: ReportSummary }) {
  return (
    <tr className="border-t border-neutral-800 hover:bg-neutral-900">
      <td className="px-3 py-2">
        <Link
          href={`/content/reports/${encodeURIComponent(item.filename)}`}
          className="text-blue-400 hover:underline"
        >
          {item.title}
        </Link>
      </td>
      <td className="px-3 py-2">
        <span className="inline-block rounded bg-neutral-800 px-2 py-0.5 text-xs">
          {item.category}
        </span>
      </td>
      <td className="px-3 py-2 text-sm text-neutral-400">{item.published || "-"}</td>
      <td className="px-3 py-2 text-sm text-neutral-400">{item.analyzed_at || "-"}</td>
    </tr>
  )
}
```

- [ ] **Step 2: Implement ReportsTable**

Create `webapp-ui/components/domain/content/reports-table.tsx`:
```tsx
"use client"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { ReportSummaryRow, type ReportSummary } from "./report-summary-row"
import { Button } from "@/components/ui/button"

type ListData = {
  items: ReportSummary[]
  page: number
  size: number
  total: number
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/content?${next}`
}

export function ReportsTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">
        전체 {data.total}건 · 페이지 {data.page}/{totalPages}
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2">제목</th>
            <th className="px-3 py-2">카테고리</th>
            <th className="px-3 py-2">발행일</th>
            <th className="px-3 py-2">분석시각</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => (
            <ReportSummaryRow key={i.filename} item={i} />
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex justify-center gap-1">
          {data.page > 1 ? (
            <Link href={pageHref(sp, data.page - 1)}>
              <Button size="sm" variant="outline">← 이전</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>← 이전</Button>
          )}
          <span className="px-3 py-1 text-sm">{data.page} / {totalPages}</span>
          {data.page < totalPages ? (
            <Link href={pageHref(sp, data.page + 1)}>
              <Button size="sm" variant="outline">다음 →</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>다음 →</Button>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/domain/content/reports-table.tsx webapp-ui/components/domain/content/report-summary-row.tsx
git commit -m "feat(webapp-ui): ReportsTable + ReportSummaryRow"
```

---

## Task 10: Frontend — ReportMarkdownView

**Files:**
- Create: `webapp-ui/components/domain/content/report-markdown-view.tsx`

- [ ] **Step 1: Implement component**

Create `webapp-ui/components/domain/content/report-markdown-view.tsx`:
```tsx
"use client"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export function ReportMarkdownView({ body }: { body: string }) {
  return (
    <article className="prose prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
    </article>
  )
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/components/domain/content/report-markdown-view.tsx
git commit -m "feat(webapp-ui): ReportMarkdownView — react-markdown + GFM"
```

---

## Task 11: Frontend — RunContentButton + NoReports + ContentJobProgress

**Files:**
- Create: `webapp-ui/components/domain/content/run-content-button.tsx`
- Create: `webapp-ui/components/domain/content/no-reports.tsx`
- Create: `webapp-ui/components/domain/content/content-job-progress.tsx`

- [ ] **Step 1: Create RunContentButton**

Create `webapp-ui/components/domain/content/run-content-button.tsx`:
```tsx
"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"

export function RunContentButton() {
  const router = useRouter()
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      const r = await apiMutate<{ job_id: string; reused: boolean }>(
        "/api/v1/content/monitor/run", "POST", {},
      )
      router.push(`/content/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패")
      setRunning(false)
    }
  }

  return (
    <div>
      <Button onClick={run} disabled={running}>
        {running ? "실행 중…" : "지금 실행"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </div>
  )
}
```

- [ ] **Step 2: Create NoReports**

Create `webapp-ui/components/domain/content/no-reports.tsx`:
```tsx
"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoReports({
  mode,
  onRun,
}: {
  mode: "empty" | "filtered"
  onRun?: () => void
}) {
  if (mode === "filtered") {
    return (
      <Card className="p-8 text-center text-neutral-400">
        조건에 맞는 리포트가 없습니다.
      </Card>
    )
  }
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">리포트가 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 BlogPulse 수집이 실행된 적이 없거나 대상 카테고리 글이 없었습니다.<br />
        지금 바로 수집을 시작해보세요.
      </p>
      {onRun && (
        <div className="flex justify-center">
          <Button onClick={onRun}>지금 실행</Button>
        </div>
      )}
      <p className="text-xs text-neutral-500">
        CLI: <code className="px-1 bg-neutral-800 rounded">ap content monitor</code>
      </p>
    </Card>
  )
}
```

- [ ] **Step 3: Create ContentJobProgress**

Create `webapp-ui/components/domain/content/content-job-progress.tsx`:
```tsx
"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useJobStatus } from "@/hooks/use-job-status"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function ContentJobProgress({ jobId }: { jobId: string }) {
  const router = useRouter()
  const { data: job, error } = useJobStatus(jobId)

  useEffect(() => {
    if (job?.status === "done") {
      router.replace("/content")
    }
  }, [job, router])

  if (error) return <div className="text-red-400">오류: {String(error)}</div>
  if (!job) return <Card className="p-6">로딩 중...</Card>

  const pct = (job.progress * 100).toFixed(0)

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-neutral-400">상태</p>
          <p className="text-lg font-semibold">{job.status}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-neutral-400">진행률</p>
          <p className="text-2xl font-mono">{pct}%</p>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded bg-neutral-800">
        <div className="h-full bg-green-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-sm text-neutral-400">{job.progress_text || "-"}</p>
      <p className="text-xs text-neutral-500">
        RSS + 크롤링 + AI 분석으로 포스트 당 약 30~60초 소요.
      </p>
      {job.status === "failed" && (
        <div className="space-y-2">
          <p className="text-red-400">실패: {job.error}</p>
          <Button variant="outline" onClick={() => router.push("/content")}>
            돌아가기
          </Button>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 4: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add webapp-ui/components/domain/content/run-content-button.tsx webapp-ui/components/domain/content/no-reports.tsx webapp-ui/components/domain/content/content-job-progress.tsx
git commit -m "feat(webapp-ui): RunContentButton + NoReports + ContentJobProgress"
```

---

## Task 12: Frontend — Main Page `/content` + 사이드바

**Files:**
- Modify: `webapp-ui/components/layout/sidebar.tsx`
- Create: `webapp-ui/app/(dashboard)/content/page.tsx`

- [ ] **Step 1: Add sidebar entry**

Edit `webapp-ui/components/layout/sidebar.tsx`. Insert after "시황":

```tsx
const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/market/pulse", label: "시황" },
  { href: "/content", label: "콘텐츠" },
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/risk", label: "리스크" },
  { href: "/screening", label: "스크리닝" },
  { href: "/backtest", label: "백테스트" },
  { href: "/data", label: "데이터" },
  { href: "/settings", label: "설정" },
  { href: "/audit", label: "감사" },
]
```

- [ ] **Step 2: Create SSR page**

Create `webapp-ui/app/(dashboard)/content/page.tsx`:
```tsx
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { ReportsFilterBar } from "@/components/domain/content/reports-filter-bar"
import { ReportsTable } from "@/components/domain/content/reports-table"
import { NoReports } from "@/components/domain/content/no-reports"
import { RunContentButton } from "@/components/domain/content/run-content-button"
import type { ReportSummary } from "@/components/domain/content/report-summary-row"

export const dynamic = "force-dynamic"

type Props = {
  searchParams: Promise<{
    page?: string
    category?: string | string[]
    from?: string
    to?: string
    q?: string
    sort?: string
  }>
}

export default async function ContentPage({ searchParams }: Props) {
  const sp = await searchParams
  const query = new URLSearchParams()
  if (sp.page) query.set("page", sp.page)
  const cats = Array.isArray(sp.category)
    ? sp.category
    : sp.category ? [sp.category] : []
  cats.forEach((c) => query.append("category", c))
  if (sp.from) query.set("from", sp.from)
  if (sp.to) query.set("to", sp.to)
  if (sp.q) query.set("q", sp.q)
  if (sp.sort) query.set("sort", sp.sort)

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const data = await apiFetch<{
    items: ReportSummary[]
    page: number
    size: number
    total: number
    categories: string[]
  }>(`/api/v1/content/reports?${query}`, { headers: h, cache: "no-store" })

  const hasFilters = cats.length > 0 || !!sp.from || !!sp.to || !!sp.q

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">콘텐츠</h1>
        <RunContentButton />
      </div>
      <ReportsFilterBar categories={data.categories} />
      {data.total === 0 ? (
        <NoReports mode={hasFilters ? "filtered" : "empty"} />
      ) : (
        <ReportsTable data={data} />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add webapp-ui/components/layout/sidebar.tsx webapp-ui/components/domain/content/reports-filter-bar.tsx 'webapp-ui/app/(dashboard)/content/page.tsx'
git commit -m "feat(webapp-ui): Content 메인 페이지 + 사이드바 진입점"
```

---

## Task 13: Frontend — 상세 페이지 `/content/reports/[filename]`

**Files:**
- Create: `webapp-ui/app/(dashboard)/content/reports/[filename]/page.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/app/(dashboard)/content/reports/[filename]/page.tsx`:
```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ filename: string }> }

type ReportDetail = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  source: string
  source_tag: string
  body: string
}

export default async function ReportDetailPage({ params }: Props) {
  const { filename } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<ReportDetail>(
      `/api/v1/content/reports/${encodeURIComponent(filename)}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-4">
        <Link href="/content">
          <Button variant="outline" size="sm">← 콘텐츠 목록으로</Button>
        </Link>
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">{detail.title}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-400">
            <span className="inline-block rounded bg-neutral-800 px-2 py-0.5 text-xs">
              {detail.category}
            </span>
            {detail.published && <span>발행 {detail.published}</span>}
            {detail.analyzed_at && <span>· 분석 {detail.analyzed_at}</span>}
            {detail.source && (
              <a
                href={detail.source}
                target="_blank" rel="noopener noreferrer"
                className="text-blue-400 hover:underline"
              >
                원문 →
              </a>
            )}
          </div>
        </header>
        <ReportMarkdownView body={detail.body} />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add 'webapp-ui/app/(dashboard)/content/reports/[filename]/page.tsx'
git commit -m "feat(webapp-ui): Content 상세 페이지 — 마크다운 렌더"
```

---

## Task 14: Frontend — Job 페이지 `/content/jobs/[id]`

**Files:**
- Create: `webapp-ui/app/(dashboard)/content/jobs/[id]/page.tsx`

- [ ] **Step 1: Implement**

Create `webapp-ui/app/(dashboard)/content/jobs/[id]/page.tsx`:
```tsx
import { ContentJobProgress } from "@/components/domain/content/content-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function ContentJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">BlogPulse 수집 중</h1>
      <ContentJobProgress jobId={id} />
    </div>
  )
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add 'webapp-ui/app/(dashboard)/content/jobs/[id]/page.tsx'
git commit -m "feat(webapp-ui): Content Job 진행 페이지"
```

---

## Task 15: E2E 스모크 테스트

**Files:**
- Create: `webapp-ui/e2e/content.spec.ts`

- [ ] **Step 1: Write E2E test**

Create `webapp-ui/e2e/content.spec.ts` (match the login pattern from existing `phase2-flow.spec.ts` / `market-pulse.spec.ts`):

```typescript
import { test, expect } from "@playwright/test"

test.describe("Content", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', process.env.E2E_ADMIN_EMAIL || "test@example.com")
    await page.fill('input[type="password"]', process.env.E2E_ADMIN_PASSWORD || "test-password-12!")
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 콘텐츠 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/content']")).toBeVisible()
  })

  test("/content 로드 → 리스트 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/content")
    const filterBar = page.locator("text=/카테고리/")
    const empty = page.locator("text=/리포트가 없습니다/")
    await expect(filterBar.or(empty)).toBeVisible()
  })

  test("'지금 실행' 버튼 존재", async ({ page }) => {
    await page.goto("/content")
    await expect(page.locator("button", { hasText: /지금 실행/ })).toBeVisible()
  })
})
```

- [ ] **Step 2: Verify TS**

Run: `cd webapp-ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add webapp-ui/e2e/content.spec.ts
git commit -m "test(webapp-ui): Content E2E 스모크 — 진입점 + 리스트 + 실행 버튼"
```

---

## Task 16: 최종 회귀 + 문서 링크

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 전체 pytest**

Run: `pytest tests/ -q --tb=short`
Expected: 신규 ~40개 PASS + 기존 PASS (1 pre-existing 무관 실패 허용)

- [ ] **Step 2: Ruff**

Run: `ruff check alphapulse/`
Expected: PASS

- [ ] **Step 3: Frontend build**

Run: `cd webapp-ui && pnpm build`
Expected: Next.js build 성공

- [ ] **Step 4: Add spec link to CLAUDE.md**

Edit `CLAUDE.md` under the "## Detailed Docs" section. Add:

```markdown
- Content 웹 대시보드 설계: `docs/superpowers/specs/2026-04-21-content-web-design.md`
```

Preserve the existing Market Pulse link and other entries.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — Content 웹 spec 링크 추가"
```

---

## 완료 기준 (Definition of Done)

- [ ] 백엔드 신규 테스트 모두 PASS (`tests/webapp/api/test_content.py`, `tests/webapp/services/test_content_runner.py`, `tests/webapp/store/readers/test_content_reader.py`, `tests/webapp/store/test_jobs_find_running_by_kind.py`, `tests/webapp/jobs/test_runner_coroutine.py`)
- [ ] Frontend `pnpm build` 성공
- [ ] `ruff check alphapulse/` 통과
- [ ] 사이드바 "콘텐츠" 클릭 → `/content` 렌더
- [ ] 이력 있을 때 리포트 리스트 + 필터 적용 가능
- [ ] 이력 없을 때 NoReports 렌더
- [ ] 리포트 클릭 → 마크다운 상세 페이지 렌더
- [ ] "지금 실행" → Job 페이지 이동 → 완료 시 `/content` 로 redirect
- [ ] path traversal / 비-.md 요청은 400 응답
- [ ] 기존 1100+ 테스트 모두 그린 (no regression)
