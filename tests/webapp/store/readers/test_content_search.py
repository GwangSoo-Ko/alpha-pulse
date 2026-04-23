"""ContentReader FTS5 검색 인덱스 테스트."""

import sqlite3
import time

from alphapulse.webapp.store.readers.content import (
    ContentReader,
    _read_body,
    _sanitize_fts_query,
)


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
    # 재생성 — IF NOT EXISTS 덕분에 에러 없이 재진입
    reader = ContentReader(reports_dir=tmp_path, fts_db_path=fts_db)
    assert reader._fts_available is True


class TestSanitizeFtsQuery:
    def test_empty_returns_empty(self):
        assert _sanitize_fts_query("") == ""
        assert _sanitize_fts_query(None) == ""
        assert _sanitize_fts_query("   ") == ""

    def test_basic_query_wrapped_in_phrase(self):
        assert _sanitize_fts_query("삼성전자") == '"삼성전자"'

    def test_strips_fts5_special_chars(self):
        # ", *, :, (, ) 는 공백으로 치환되고 전체 phrase wrap
        # ' "AI" OR (반도체*) '  →  replace special chars →  ' AI  OR  반도체  '
        # strip →  'AI  OR  반도체'  →  wrap →  '"AI  OR  반도체"'
        assert _sanitize_fts_query('"AI" OR (반도체*)') == '"AI  OR  반도체"'

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
        assert "category:" not in body

    def test_no_frontmatter_returns_full_text(self, tmp_path):
        p = tmp_path / "plain.md"
        p.write_text("그냥 본문.", encoding="utf-8")
        assert _read_body(p) == "그냥 본문."

    def test_missing_file_returns_empty(self, tmp_path):
        assert _read_body(tmp_path / "missing.md") == ""


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
        reader = ContentReader(reports_dir=tmp_path)  # fts_db_path 없음
        reader.upsert_index("whatever.md")  # 예외 없이 조용히 반환


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
