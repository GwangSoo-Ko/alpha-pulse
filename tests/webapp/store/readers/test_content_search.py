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
