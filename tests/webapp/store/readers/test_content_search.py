"""ContentReader FTS5 검색 인덱스 테스트."""

import sqlite3

from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.readers.content import (
    _sanitize_fts_query,
    _read_body,
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
