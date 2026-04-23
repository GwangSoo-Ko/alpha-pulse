# Content FTS5 전문 검색 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/content` 페이지에서 본문 포함 전문 검색 + 랭킹 + 하이라이트 snippet 을 지원한다. 기존 `.md` 파일 저장 구조 유지, shadow SQLite FTS5 인덱스.

**Architecture:** `ContentReader` 에 FTS5 인덱스 라이프사이클(`_init_fts_schema` / `build_index` / `upsert_index` / `search`) 추가. 앱 시작 시 mtime-diff rebuild, 파일 저장 시 incremental upsert. trigram 토크나이저로 한글 조사/어미 우회. API 응답에 `highlight: str | None` 추가. FE 테이블이 q 있을 때 하이라이트 row 렌더.

**Tech Stack:** Python 3.12 + SQLite FTS5 (trigram) + FastAPI + Next.js 15.

**Branch:** `feature/content-fts5` (spec 커밋 `d9b738d` 완료)

**Spec:** `docs/superpowers/specs/2026-04-23-content-fts5-search-design.md`

---

## File Structure

### Backend
- **Modify:** `alphapulse/core/config.py` — `CONTENT_SEARCH_DB` 속성 추가
- **Modify:** `alphapulse/webapp/store/readers/content.py`
  - 생성자 확장 (`fts_db_path` 파라미터)
  - 헬퍼 추가: `_sanitize_fts_query`, `_read_body`
  - 인스턴스 메서드 추가: `_init_fts_schema`, `build_index`, `upsert_index`, `search`
  - 기존 `list_reports(query=...)` 는 `query` 있고 FTS 가능 시 `search()` 위임
- **Modify:** `alphapulse/webapp/api/content.py` — `ReportSummary.highlight: str | None = None`
- **Modify:** `alphapulse/webapp/main.py` — `ContentReader(fts_db_path=...)` + 시작 시 `build_index()`
- **Modify:** `alphapulse/content/monitor.py` — 리포트 저장 직후 `upsert_index(filename)` 호출

### Frontend
- **Modify:** `webapp-ui/components/domain/content/report-summary-row.tsx` — `ReportSummary` 타입에 `highlight` 추가
- **Modify:** `webapp-ui/components/domain/content/reports-table.tsx` — highlight 존재 시 하이라이트 row 렌더 (React raw HTML 삽입 API 사용, 상세는 Task 9)

### 테스트
- **Create:** `tests/webapp/store/readers/test_content_search.py` — FTS5 동작 테스트
- **Modify:** `tests/webapp/api/test_content.py` — highlight 필드 회귀
- **Modify:** `webapp-ui/e2e/content.spec.ts` — 하이라이트 렌더 스모크

---

## Conventions

- 백엔드는 TDD (test first → red → green → commit)
- FE 는 `pnpm lint` + `pnpm tsc --noEmit` + E2E 로 검증 (Vitest 미도입)
- 각 Task 개별 커밋
- `ruff check alphapulse/` 통과 필수
- 인덱스 실패가 메인 기능을 중단시키지 않도록 try/except 격리

---

## Task 1: Config 확장 + `_init_fts_schema`

**Files:**
- Modify: `alphapulse/core/config.py`
- Modify: `alphapulse/webapp/store/readers/content.py`
- Create: `tests/webapp/store/readers/test_content_search.py`

Step 1.1: `alphapulse/core/config.py` 의 `Config` 클래스 내부(`self.HISTORY_DB`, `BRIEFINGS_DB`, `FEEDBACK_DB` 근처)에 다음을 추가:

```python
self.CONTENT_SEARCH_DB = self.DATA_DIR / "content_search.db"
```

(기존 패턴이 property 이면 동일 형태로 추가.)

Step 1.2: `alphapulse/webapp/store/readers/content.py` 의 `ContentReader.__init__` 변경:

```python
class ContentReader:
    def __init__(
        self,
        reports_dir,
        fts_db_path=None,
    ) -> None:
        self.reports_dir = Path(reports_dir)
        self.fts_db = Path(fts_db_path) if fts_db_path else None
        self._scan_cache = None
        self._scan_cache_mtime = None
        self._fts_available = False
        if self.fts_db is not None:
            self._init_fts_schema()

    def _init_fts_schema(self) -> None:
        """FTS5 가상 테이블 + meta 테이블 생성 (idempotent)."""
        try:
            self.fts_db.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.fts_db) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reports_meta (
                        filename TEXT PRIMARY KEY,
                        mtime REAL NOT NULL,
                        indexed_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
                        filename UNINDEXED,
                        title,
                        category,
                        body,
                        tokenize = 'trigram'
                    )
                    """
                )
            self._fts_available = True
        except sqlite3.OperationalError as e:
            logger.warning("content_search: FTS5 init failed — %s", e)
            self._fts_available = False
```

Step 1.3: `tests/webapp/store/readers/test_content_search.py` 신규 생성:

```python
"""ContentReader FTS5 검색 인덱스 테스트."""

import sqlite3
from pathlib import Path

from alphapulse.webapp.store.readers.content import ContentReader


def test_init_creates_fts_schema_when_fts_db_path_given(tmp_path):
    fts_db = tmp_path / "content_search.db"
    reader = ContentReader(reports_dir=tmp_path, fts_db_path=fts_db)
    assert reader._fts_available is True
    with sqlite3.connect(fts_db) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "reports_meta" in tables
    assert "reports_fts" in tables


def test_init_without_fts_db_path_leaves_fts_unavailable(tmp_path):
    reader = ContentReader(reports_dir=tmp_path)
    assert reader._fts_available is False
    assert reader.fts_db is None


def test_init_is_idempotent(tmp_path):
    fts_db = tmp_path / "content_search.db"
    ContentReader(reports_dir=tmp_path, fts_db_path=fts_db)
    reader = ContentReader(reports_dir=tmp_path, fts_db_path=fts_db)
    assert reader._fts_available is True
```

Step 1.4: Run `pytest tests/webapp/store/readers/test_content_search.py -v`. Expect: 3 passed (구현이 함께 포함됐으므로 바로 green).

Step 1.5: 린트 + 커밋.

```bash
ruff check alphapulse/core/config.py alphapulse/webapp/store/readers/content.py tests/webapp/store/readers/test_content_search.py
git add alphapulse/core/config.py alphapulse/webapp/store/readers/content.py tests/webapp/store/readers/test_content_search.py
git commit -m "feat(content): Config.CONTENT_SEARCH_DB + ContentReader FTS5 스키마 초기화"
```

---

## Task 2: `_sanitize_fts_query` + `_read_body` 헬퍼

**Files:**
- Modify: `alphapulse/webapp/store/readers/content.py`
- Modify: `tests/webapp/store/readers/test_content_search.py`

Step 2.1: 테스트 추가 (append to `tests/webapp/store/readers/test_content_search.py`):

```python
from alphapulse.webapp.store.readers.content import (
    _sanitize_fts_query,
    _read_body,
)


class TestSanitizeFtsQuery:
    def test_empty_returns_empty(self):
        assert _sanitize_fts_query("") == ""
        assert _sanitize_fts_query(None) == ""
        assert _sanitize_fts_query("   ") == ""

    def test_basic_query_wrapped_in_phrase(self):
        assert _sanitize_fts_query("삼성전자") == '"삼성전자"'

    def test_strips_fts5_special_chars(self):
        assert _sanitize_fts_query('"AI" OR (반도체*)') == '"AI  OR   반도체 "'

    def test_all_special_becomes_empty(self):
        assert _sanitize_fts_query('"*:()') == ""


class TestReadBody:
    def test_strips_frontmatter(self, tmp_path):
        p = tmp_path / "report.md"
        p.write_text(
            '---\ntitle: "T"\ncategory: "C"\n---\n\n본문 내용입니다.\n두번째 줄.\n',
            encoding="utf-8",
        )
        body = _read_body(p)
        assert "본문 내용입니다" in body
        assert "두번째 줄" in body
        assert "title:" not in body

    def test_no_frontmatter_returns_full_text(self, tmp_path):
        p = tmp_path / "plain.md"
        p.write_text("그냥 본문.", encoding="utf-8")
        assert _read_body(p) == "그냥 본문."

    def test_missing_file_returns_empty(self, tmp_path):
        assert _read_body(tmp_path / "missing.md") == ""
```

Step 2.2: Red — `pytest ... -k "Sanitize or ReadBody"`. Expect FAIL (import error).

Step 2.3: 구현 — 모듈 상단에 `import re` 가 없으면 추가. 클래스 밖 (모듈 레벨) 에 두 함수 추가:

```python
def _sanitize_fts_query(raw):
    """사용자 입력을 FTS5 MATCH 로 안전하게 변환.

    특수문자 `"`, `*`, `:`, `(`, `)` 를 공백으로 치환 후 phrase 로 감싼다.
    빈 문자열이면 "" 반환.
    """
    cleaned = re.sub(r'["\*\:\(\)]', ' ', raw or "").strip()
    if not cleaned:
        return ""
    return f'"{cleaned}"'


def _read_body(path):
    """`.md` 파일에서 frontmatter(`---...---`) 를 제거한 본문을 반환."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    if not text.startswith("---"):
        return text
    rest = text[3:]
    close_idx = rest.find("\n---")
    if close_idx < 0:
        return text
    after = rest[close_idx + len("\n---"):]
    return after.lstrip("\r\n")
```

Step 2.4: Green — 9 passed.

Step 2.5: 커밋 `feat(content): _sanitize_fts_query + _read_body 헬퍼`.

---

## Task 3: `upsert_index` 메서드

**Files:** `alphapulse/webapp/store/readers/content.py`, `tests/webapp/store/readers/test_content_search.py`

Step 3.1: 테스트 추가 (append):

```python
import time


def _write_report(dir_path, name, title="제목", category="테스트", body="본문 내용"):
    (dir_path / name).write_text(
        f'---\ntitle: "{title}"\ncategory: "{category}"\npublished: "2026-04-01"\nanalyzed_at: "2026-04-02T10:00"\n---\n\n{body}\n',
        encoding="utf-8",
    )


class TestUpsertIndex:
    def test_upsert_inserts_new_row(self, tmp_path):
        _write_report(tmp_path, "a.md", title="삼성전자", body="반도체 호황")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.upsert_index("a.md")
        with sqlite3.connect(reader.fts_db) as conn:
            conn.row_factory = sqlite3.Row
            meta_rows = conn.execute("SELECT * FROM reports_meta").fetchall()
            assert len(meta_rows) == 1
            assert meta_rows[0]["filename"] == "a.md"
            fts_rows = conn.execute(
                "SELECT filename, title, body FROM reports_fts"
            ).fetchall()
            assert len(fts_rows) == 1
            assert fts_rows[0]["title"] == "삼성전자"
            assert "반도체 호황" in fts_rows[0]["body"]

    def test_upsert_replaces_existing_row(self, tmp_path):
        _write_report(tmp_path, "a.md", title="원본")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.upsert_index("a.md")
        _write_report(tmp_path, "a.md", title="수정됨", body="새 본문")
        time.sleep(0.01)
        reader.upsert_index("a.md")
        with sqlite3.connect(reader.fts_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM reports_meta").fetchall()
            assert len(rows) == 1
            fts = conn.execute("SELECT title, body FROM reports_fts").fetchall()
            assert fts[0]["title"] == "수정됨"
            assert "새 본문" in fts[0]["body"]

    def test_upsert_noop_when_file_missing(self, tmp_path):
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.upsert_index("ghost.md")
        with sqlite3.connect(reader.fts_db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM reports_meta").fetchone()[0] == 0

    def test_upsert_noop_when_fts_unavailable(self, tmp_path):
        reader = ContentReader(reports_dir=tmp_path)
        reader.upsert_index("whatever.md")  # 예외 없이 조용히 반환
```

Step 3.2: Red — FAIL, upsert_index 미존재.

Step 3.3: 구현 — `ContentReader` 에 메서드 추가. 상단 import 에 `import time` 없으면 추가:

```python
    def upsert_index(self, filename: str) -> None:
        """단일 파일을 FTS5 인덱스에 반영 (upsert)."""
        if not self._fts_available or self.fts_db is None:
            return
        path = self.reports_dir / filename
        if not path.is_file():
            return
        meta = _meta_from_file(path)
        body = _read_body(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        with sqlite3.connect(self.fts_db) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "DELETE FROM reports_fts WHERE filename = ?", (filename,)
                )
                conn.execute(
                    "DELETE FROM reports_meta WHERE filename = ?", (filename,)
                )
                conn.execute(
                    "INSERT INTO reports_fts (filename, title, category, body) "
                    "VALUES (?, ?, ?, ?)",
                    (filename, meta["title"], meta["category"], body),
                )
                conn.execute(
                    "INSERT INTO reports_meta (filename, mtime, indexed_at) "
                    "VALUES (?, ?, ?)",
                    (filename, mtime, time.time()),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
```

Step 3.4: Green — 13 passed.

Step 3.5: 커밋 `feat(content): ContentReader.upsert_index`.

---

## Task 4: `build_index` (mtime-diff rebuild)

**Files:** 동일.

Step 4.1: 테스트 추가:

```python
class TestBuildIndex:
    def test_build_indexes_all_files_on_empty_db(self, tmp_path):
        _write_report(tmp_path, "a.md")
        _write_report(tmp_path, "b.md")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        stats = reader.build_index()
        assert stats == {"added": 2, "updated": 0, "removed": 0}
        with sqlite3.connect(reader.fts_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM reports_meta").fetchone()[0]
            assert count == 2

    def test_build_noop_when_all_up_to_date(self, tmp_path):
        _write_report(tmp_path, "a.md")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.build_index()
        stats = reader.build_index()
        assert stats == {"added": 0, "updated": 0, "removed": 0}

    def test_build_detects_mtime_change(self, tmp_path):
        _write_report(tmp_path, "a.md", title="원본")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.build_index()
        time.sleep(0.01)
        _write_report(tmp_path, "a.md", title="수정됨")
        stats = reader.build_index()
        assert stats["updated"] == 1
        with sqlite3.connect(reader.fts_db) as conn:
            title = conn.execute(
                "SELECT title FROM reports_fts WHERE filename='a.md'"
            ).fetchone()[0]
            assert title == "수정됨"

    def test_build_removes_deleted_files(self, tmp_path):
        _write_report(tmp_path, "a.md")
        _write_report(tmp_path, "b.md")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.build_index()
        (tmp_path / "b.md").unlink()
        stats = reader.build_index()
        assert stats["removed"] == 1
        with sqlite3.connect(reader.fts_db) as conn:
            names = {r[0] for r in conn.execute("SELECT filename FROM reports_meta").fetchall()}
            assert names == {"a.md"}

    def test_build_noop_when_dir_missing(self, tmp_path):
        reader = ContentReader(reports_dir=tmp_path / "missing", fts_db_path=tmp_path / "s.db")
        stats = reader.build_index()
        assert stats == {"added": 0, "updated": 0, "removed": 0}

    def test_build_noop_when_fts_unavailable(self, tmp_path):
        reader = ContentReader(reports_dir=tmp_path)
        stats = reader.build_index()
        assert stats == {"added": 0, "updated": 0, "removed": 0}
```

Step 4.2: Red.

Step 4.3: 구현:

```python
    def build_index(self) -> dict:
        """디스크와 FTS5 인덱스를 mtime 기반으로 동기화."""
        if not self._fts_available or self.fts_db is None:
            return {"added": 0, "updated": 0, "removed": 0}
        if not self.reports_dir.is_dir():
            return {"added": 0, "updated": 0, "removed": 0}

        disk: dict[str, float] = {}
        for entry in self.reports_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix != ".md" or entry.name.startswith("."):
                continue
            try:
                disk[entry.name] = entry.stat().st_mtime
            except OSError:
                continue

        with sqlite3.connect(self.fts_db) as conn:
            rows = conn.execute(
                "SELECT filename, mtime FROM reports_meta"
            ).fetchall()
        db = {r[0]: r[1] for r in rows}

        added = [n for n in disk if n not in db]
        updated = [n for n in disk if n in db and db[n] != disk[n]]
        removed = [n for n in db if n not in disk]

        for name in added + updated:
            try:
                self.upsert_index(name)
            except Exception as e:
                logger.warning("build_index upsert failed for %s: %s", name, e)

        if removed:
            with sqlite3.connect(self.fts_db) as conn:
                conn.executemany(
                    "DELETE FROM reports_fts WHERE filename = ?",
                    [(n,) for n in removed],
                )
                conn.executemany(
                    "DELETE FROM reports_meta WHERE filename = ?",
                    [(n,) for n in removed],
                )

        return {"added": len(added), "updated": len(updated), "removed": len(removed)}
```

Step 4.4: Green — 19 passed.

Step 4.5: 커밋 `feat(content): ContentReader.build_index (mtime-diff rebuild)`.

---

## Task 5: `search` 메서드

**Files:** 동일.

Step 5.1: 테스트 추가:

```python
class TestSearch:
    def _setup(self, tmp_path, files):
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        for f in files:
            _write_report(tmp_path, f["name"], title=f["title"],
                          category=f.get("category", "테스트"),
                          body=f.get("body", ""))
        reader.build_index()
        return reader

    def test_search_matches_title(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "삼성전자 분석", "body": "반도체 업황"},
            {"name": "b.md", "title": "애플 실적", "body": "아이폰 판매량"},
        ])
        result = reader.search(q="삼성전자", categories=None, date_from=None, date_to=None, page=1, size=20)
        filenames = [i["filename"] for i in result["items"]]
        assert "a.md" in filenames and "b.md" not in filenames

    def test_search_matches_body(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "제목1", "body": "반도체 호황 지속"},
            {"name": "b.md", "title": "제목2", "body": "자동차 수출 확대"},
        ])
        result = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=1, size=20)
        assert [i["filename"] for i in result["items"]] == ["a.md"]

    def test_search_trigram_matches_korean_with_particles(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "뉴스", "body": "삼성전자가 실적을 발표했다"},
        ])
        result = reader.search(q="삼성전자", categories=None, date_from=None, date_to=None, page=1, size=20)
        assert len(result["items"]) == 1

    def test_search_returns_highlight_with_mark_tags(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "분석", "body": "반도체 시장 전망"},
        ])
        result = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=1, size=20)
        hl = result["items"][0]["highlight"]
        assert "<mark>" in hl and "</mark>" in hl

    def test_search_sanitizes_special_chars(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "AI 테마", "body": "분석"},
        ])
        result = reader.search(q='"AI"*', categories=None, date_from=None, date_to=None, page=1, size=20)
        assert len(result["items"]) == 1

    def test_search_empty_q_returns_empty_items(self, tmp_path):
        reader = self._setup(tmp_path, [{"name": "a.md", "title": "제목"}])
        result = reader.search(q="", categories=None, date_from=None, date_to=None, page=1, size=20)
        assert result["items"] == [] and result["total"] == 0

    def test_search_filters_by_category_after_fts(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "삼성전자", "category": "기업", "body": ""},
            {"name": "b.md", "title": "삼성전자", "category": "시장", "body": ""},
        ])
        result = reader.search(q="삼성전자", categories=["기업"], date_from=None, date_to=None, page=1, size=20)
        assert [i["filename"] for i in result["items"]] == ["a.md"]

    def test_search_sorts_by_bm25_rank(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "일반", "body": "반도체 얘기 약간"},
            {"name": "b.md", "title": "반도체 주도주", "body": "짧음"},
        ])
        result = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=1, size=20)
        assert result["items"][0]["filename"] == "b.md"

    def test_search_paginates(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": f"f{i}.md", "title": "반도체", "body": f"본문{i}"} for i in range(5)
        ])
        page1 = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=1, size=2)
        page2 = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=2, size=2)
        page3 = reader.search(q="반도체", categories=None, date_from=None, date_to=None, page=3, size=2)
        assert len(page1["items"]) == 2 and len(page2["items"]) == 2 and len(page3["items"]) == 1
        assert page1["total"] == 5

    def test_search_returns_all_categories(self, tmp_path):
        reader = self._setup(tmp_path, [
            {"name": "a.md", "title": "a", "category": "기업"},
            {"name": "b.md", "title": "b", "category": "시장"},
        ])
        result = reader.search(q="a", categories=None, date_from=None, date_to=None, page=1, size=20)
        assert set(result["categories"]) == {"기업", "시장"}
```

Step 5.2: Red.

Step 5.3: 구현:

```python
    def search(
        self,
        *,
        q,
        categories,
        date_from,
        date_to,
        page,
        size,
    ) -> dict:
        """FTS5 기반 검색 + 메타 필터 + rank 정렬 + 페이지네이션."""
        all_metas = self._scan()
        categories_all = sorted({m["category"] for m in all_metas})
        q_sanitized = _sanitize_fts_query(q)
        if not q_sanitized or not self._fts_available or self.fts_db is None:
            return {
                "items": [], "total": 0, "page": page, "size": size,
                "categories": categories_all,
            }

        try:
            with sqlite3.connect(self.fts_db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT
                        filename,
                        snippet(reports_fts, 3, '<mark>', '</mark>', '…', 16) AS highlight,
                        bm25(reports_fts) AS rank
                    FROM reports_fts
                    WHERE reports_fts MATCH ?
                    ORDER BY rank
                    """,
                    (q_sanitized,),
                ).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning("content_search MATCH failed for %r: %s", q, e)
            rows = []

        match_by_name = {r["filename"]: dict(r) for r in rows}
        filtered = [
            m for m in all_metas
            if m["filename"] in match_by_name
            and (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
        ]
        filtered.sort(key=lambda m: match_by_name[m["filename"]]["rank"])
        total = len(filtered)
        start = (page - 1) * size
        items = [
            {**m, "highlight": match_by_name[m["filename"]]["highlight"]}
            for m in filtered[start:start + size]
        ]
        return {
            "items": items, "total": total, "page": page, "size": size,
            "categories": categories_all,
        }
```

Step 5.4: Green — 29 passed (19 + 10).

Step 5.5: 커밋 `feat(content): ContentReader.search — FTS5 MATCH + rank + paginate`.

---

## Task 6: `list_reports` → `search()` 위임

**Files:** 동일.

Step 6.1: 테스트 추가:

```python
class TestListReportsIntegration:
    def test_list_reports_with_query_uses_fts(self, tmp_path):
        _write_report(tmp_path, "a.md", title="비관련", body="반도체 호황")
        _write_report(tmp_path, "b.md", title="그냥", body="다른 내용")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.build_index()
        result = reader.list_reports(query="반도체")
        filenames = [i["filename"] for i in result["items"]]
        assert filenames == ["a.md"]
        assert result["items"][0].get("highlight") is not None

    def test_list_reports_without_query_no_highlight(self, tmp_path):
        _write_report(tmp_path, "a.md", title="제목")
        reader = ContentReader(reports_dir=tmp_path, fts_db_path=tmp_path / "s.db")
        reader.build_index()
        result = reader.list_reports()
        for item in result["items"]:
            assert item.get("highlight") is None or "highlight" not in item

    def test_list_reports_without_fts_db_falls_back_to_substring(self, tmp_path):
        _write_report(tmp_path, "a.md", title="삼성전자 분석")
        _write_report(tmp_path, "b.md", title="다른 뉴스")
        reader = ContentReader(reports_dir=tmp_path)
        result = reader.list_reports(query="삼성")
        filenames = [i["filename"] for i in result["items"]]
        assert "a.md" in filenames and "b.md" not in filenames
```

Step 6.2: Red.

Step 6.3: 구현 — 기존 `list_reports` 메서드 body 상단에 분기 추가:

```python
    def list_reports(
        self,
        *,
        categories=None,
        date_from=None,
        date_to=None,
        query=None,
        sort="newest",
        page=1,
        size=20,
    ):
        # FTS 가능 + query 있으면 search() 로 위임
        if query and self._fts_available:
            return self.search(
                q=query, categories=categories,
                date_from=date_from, date_to=date_to,
                page=page, size=size,
            )

        # 기존 substring 경로 (변경 없음)
        all_metas = self._scan()
        filtered = [
            m for m in all_metas
            if (not categories or m["category"] in categories)
            and _date_in_range(m["published"], date_from, date_to)
            and (not query or query.lower() in m["title"].lower())
        ]
        reverse = sort == "newest"
        filtered.sort(key=lambda m: m["analyzed_at"], reverse=reverse)
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

Step 6.4: Green — 전체 store readers 회귀 포함 통과.

Step 6.5: 커밋 `feat(content): list_reports → query 있으면 search() 위임`.

---

## Task 7: API `ReportSummary.highlight` 필드 추가

**Files:**
- Modify: `alphapulse/webapp/api/content.py`
- Modify: `tests/webapp/api/test_content.py`

Step 7.1: 기존 fixture/엔드포인트 확인:

```bash
cat tests/webapp/api/test_content.py | head -80
grep -n "class ReportSummary\|@router.get" alphapulse/webapp/api/content.py
```

기존 fixture 가 `reports_dir` 만 구성하고 있다면, FTS 가능하도록 `fts_db_path=tmp_path / "s.db"` 추가한 reader 를 주입하도록 fixture 확장.

Step 7.2: 테스트 추가 (기존 fixture 이름에 맞춰 조정). 대략적 구조:

```python
def test_list_reports_with_q_includes_highlight(client, content_reports_dir, content_reader):
    # seed: 본문에 '반도체' 포함
    (content_reports_dir / "a.md").write_text(
        '---\ntitle: "분석"\ncategory: "시장"\npublished: "2026-04-01"\nanalyzed_at: "2026-04-02T10:00"\n---\n\n반도체 시장 전망\n',
        encoding="utf-8",
    )
    content_reader.build_index()
    r = client.get("/api/v1/content/reports?q=반도체")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert "<mark>" in (item.get("highlight") or "")


def test_list_reports_without_q_no_highlight(client, content_reports_dir, content_reader):
    (content_reports_dir / "a.md").write_text(
        '---\ntitle: "분석"\ncategory: "시장"\npublished: "2026-04-01"\nanalyzed_at: "2026-04-02T10:00"\n---\n\n본문\n',
        encoding="utf-8",
    )
    content_reader.build_index()
    r = client.get("/api/v1/content/reports")
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item.get("highlight") is None
```

기존 fixture 가 다른 이름이면 맞춰 사용. FTS 가능 reader 구성이 기존 fixture 에 없으면 fixture 를 확장하거나 테스트 내부에서 직접 구성.

Step 7.3: Red.

Step 7.4: 구현 — `ReportSummary` 모델에 `highlight: str | None = None` 추가. 엔드포인트 반환 매핑에 `highlight=i.get("highlight")` 추가:

```python
class ReportSummary(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    highlight: str | None = None
```

엔드포인트 변경 예:

```python
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

Step 7.5: Green + 회귀.

Step 7.6: 커밋 `feat(webapp): /content/reports 응답 highlight 필드 추가`.

---

## Task 8: 앱 시작 시 build_index + monitor.py 저장 시 upsert

**Files:**
- Modify: `alphapulse/webapp/main.py`
- Modify: `alphapulse/content/monitor.py`

Step 8.1: `webapp/main.py` — `content_reader` 생성 라인을 확장:

```python
content_reader = ContentReader(
    reports_dir=core.REPORTS_DIR,
    fts_db_path=core.CONTENT_SEARCH_DB,
)
try:
    stats = content_reader.build_index()
    logger.info("content_search index built: %s", stats)
except Exception as e:
    logger.warning("content_search index build failed: %s", e)
```

Step 8.2: `content/monitor.py` — `reporter.save(...)` 호출부에서 반환된 `filepath.name` 을 reader 에 전달:

```bash
grep -n "reporter.save\|self.reporter.save" alphapulse/content/monitor.py
```

해당 호출 직후 추가:

```python
try:
    from alphapulse.webapp.store.readers.content import ContentReader
    ContentReader(
        reports_dir=self.reporter.reports_dir,
        fts_db_path=_cfg.CONTENT_SEARCH_DB,
    ).upsert_index(filepath.name)
except Exception as e:
    logger.warning("content_search upsert failed for %s: %s", filepath.name, e)
```

`_cfg` 가 module-level Config 인스턴스로 이미 존재. 없으면 `from alphapulse.core.config import Config; Config()` 로 대체.

Step 8.3: 회귀:

```bash
pytest tests/webapp/ tests/content/ tests/feedback/ -q --tb=short 2>&1 | tail -5
```

Step 8.4: 커밋 `feat(content): 앱 시작 build_index + 저장 시 upsert_index`.

---

## Task 9: FE ReportsTable 하이라이트 row

**Files:**
- Modify: `webapp-ui/components/domain/content/report-summary-row.tsx`
- Modify: `webapp-ui/components/domain/content/reports-table.tsx`

Step 9.1: `report-summary-row.tsx` 의 `ReportSummary` 타입에 `highlight` 필드 추가:

```tsx
export type ReportSummary = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  highlight?: string | null
}
```

Step 9.2: `reports-table.tsx` — body 에서 각 item 렌더 시 highlight 존재 시 colspan row 삽입.

현재 테이블 body 구조를 먼저 확인:

```bash
cat webapp-ui/components/domain/content/reports-table.tsx
```

기존 패턴에 맞춰 highlight row 를 추가. 예시 (실제 구조에 맞게 조정):

```tsx
{data.items.map((item) => (
  <Fragment key={item.filename}>
    <tr className="border-t border-neutral-800 hover:bg-neutral-900">
      {/* 기존 컬럼 4개 */}
    </tr>
    {item.highlight ? (
      <tr>
        <td colSpan={4} className="px-3 pb-2 text-xs text-neutral-400">
          <HighlightSnippet html={item.highlight} />
        </td>
      </tr>
    ) : null}
  </Fragment>
))}
```

`HighlightSnippet` 은 동일 파일 또는 보조 파일에서 React 의 raw HTML 삽입 API 로 `<mark>` 태그만 포함된 snippet 을 렌더. XSS 평가: 서버 통제 콘텐츠 (스펙 §4.5) — 신뢰 경계 내.

```tsx
function HighlightSnippet({ html }: { html: string }) {
  return (
    <span
      className="[&_mark]:bg-yellow-700/40 [&_mark]:text-yellow-200 [&_mark]:rounded [&_mark]:px-0.5"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
```

Step 9.3: 린트 + tsc + 빌드:

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep "reports-table\|report-summary-row" || echo "no errors"
pnpm build 2>&1 | tail -5
```

Step 9.4: 커밋 `feat(webapp-ui): ReportsTable 검색 결과 하이라이트 row 추가`.

---

## Task 10: Playwright E2E 스모크

**Files:** `webapp-ui/e2e/content.spec.ts`

Step 10.1: 기존 describe 블록에 테스트 추가:

```typescript
test("검색어 입력 → 결과 있으면 mark 태그 렌더", async ({ page }) => {
  await page.goto("/content?q=%EB%B0%98%EB%8F%84%EC%B2%B4") // 반도체
  const empty = page.getByText(/결과가 없습니다|리포트가 없습니다/)
  const isEmpty = await empty.isVisible().catch(() => false)
  test.skip(isEmpty, "검색 결과 없음 — 스모크 스킵")
  await expect(page.locator("mark").first()).toBeVisible()
})
```

실제 empty 문구는 `webapp-ui/components/domain/content/no-reports.tsx` 에서 확인하여 정확한 텍스트로 조정.

Step 10.2: 린트 + 커밋 `test(webapp-ui): Content 검색 하이라이트 E2E 스모크`.

---

## Task 11: 전체 CI Gate 검증

Step 11.1: `pytest tests/ -x -q --tb=short | tail -5` → 1304+ passed.

Step 11.2: `ruff check alphapulse/` → clean.

Step 11.3: `pnpm lint && pnpm build` → success.

Step 11.4: 검증 통과 시 병합 단계 (커밋 없음).

---

## Spec Coverage 체크

- [x] §2 데이터 모델 → Task 1
- [x] §3.1 ContentReader __init__/_init_fts_schema → Task 1
- [x] §3.2 search → Task 5
- [x] §3.3 _sanitize_fts_query → Task 2
- [x] §3.4 build_index → Task 4
- [x] §3.5 upsert_index → Task 3
- [x] §3.6 _read_body → Task 2
- [x] §4.1 Config.CONTENT_SEARCH_DB → Task 1
- [x] §4.2 main.py startup hook → Task 8
- [x] §4.3 monitor.py 저장 시 upsert → Task 8
- [x] §4.4 ReportSummary.highlight → Task 7
- [x] §4.5 FE 하이라이트 row → Task 9
- [x] §5 에러 처리 → Task 1/3/4/5/8 내부
- [x] §6.1 단위 테스트 → Task 1-6
- [x] §6.2 API 회귀 → Task 7
- [x] §6.3 E2E → Task 10
- [x] §7 CI Gate → Task 11

## Implementation Notes

1. **Task 순서 엄격**: 1 → 2 → 3 → 4 (3 사용) → 5 (2 사용) → 6 (5 사용) → 7 → 8 → 9 → 10 → 11.
2. **Task 2 의 `_read_body`**: 기존 `_parse_frontmatter` 와 독립. 단순 split 으로 의존 최소화.
3. **Task 5 rank 정렬은 Python**: FTS5 가 rank 반환, Python 이 category/date 후필터 + sort + paginate. 1000건 규모엔 충분.
4. **Task 8 monitor 통합**: monitor 가 async 환경이더라도 ContentReader 는 sync. `Config()` 로 DB 경로만 주입.
5. **Task 9 FE**: React raw HTML 삽입 API 사용. Spec §4.5 에서 위험 평가 완료. 향후 `.md` 출처가 확장되면 DOMPurify 도입.
6. **Fallback**: FTS5 미지원 SQLite 에서도 `list_reports` 기존 substring 경로 그대로 동작.
