"""ContentReader FTS5 검색 인덱스 테스트."""

import sqlite3

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
    # 재생성 — IF NOT EXISTS 덕분에 에러 없이 재진입
    reader = ContentReader(reports_dir=tmp_path, fts_db_path=fts_db)
    assert reader._fts_available is True
