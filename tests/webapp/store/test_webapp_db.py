"""webapp.db 스키마/초기화 테스트."""
import sqlite3

from alphapulse.webapp.store.webapp_db import init_webapp_db


class TestInitWebAppDb:
    def test_creates_all_tables(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        names = {r[0] for r in rows}
        assert names == {
            "users", "sessions", "jobs", "login_attempts", "alert_log", "settings",
            "risk_report_cache", "screening_runs", "notifications",
        }

    def test_users_has_tenant_id_column(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            cols = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = {c[1] for c in cols}
        assert "tenant_id" in col_names

    def test_idempotent(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        init_webapp_db(db)

    def test_wal_mode_enabled(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_indexes_created(self, tmp_path):
        db = tmp_path / "w.db"
        init_webapp_db(db)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name LIKE 'idx_%'"
            ).fetchall()
        names = {r[0] for r in rows}
        assert "idx_users_email" in names
        assert "idx_sessions_expires" in names
        assert "idx_jobs_status" in names
        assert "idx_settings_category" in names
        assert "idx_screening_user" in names
