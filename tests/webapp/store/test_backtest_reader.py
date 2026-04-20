"""BacktestReader — 기존 BacktestStore 래핑 어댑터."""
import json
import time
import uuid

import pytest

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.store.readers.backtest import BacktestReader


def _seed_run(store, name="t", total_return=5.0):
    run_id = str(uuid.uuid4())
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT INTO runs (run_id, name, strategies, allocations,
                start_date, end_date, initial_capital, final_value,
                benchmark, params, metrics, created_at)
            VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                100000000, 105000000, 'KOSPI', '{}', ?, ?)""",
            (
                run_id, name,
                json.dumps({
                    "total_return": total_return,
                    "sharpe_ratio": 1.1,
                    "max_drawdown": -2.0,
                }),
                time.time(),
            ),
        )
    return run_id


@pytest.fixture
def reader(tmp_path):
    store = BacktestStore(db_path=tmp_path / "backtest.db")
    return BacktestReader(db_path=tmp_path / "backtest.db"), store


class TestBacktestReader:
    def test_list_runs_empty(self, reader):
        r, _ = reader
        page = r.list_runs(page=1, size=20)
        assert page.total == 0
        assert page.items == []

    def test_list_runs_paginates(self, reader):
        r, store = reader
        for i in range(25):
            _seed_run(store, name=f"r{i}", total_return=i)
        page = r.list_runs(page=1, size=10)
        assert page.total == 25
        assert len(page.items) == 10
        assert page.page == 1
        assert page.size == 10
        page2 = r.list_runs(page=3, size=10)
        assert len(page2.items) == 5

    def test_list_runs_filter_name(self, reader):
        r, store = reader
        _seed_run(store, name="momentum-bt")
        _seed_run(store, name="value-bt")
        page = r.list_runs(page=1, size=20, name_contains="momentum")
        assert page.total == 1
        assert "momentum" in page.items[0].name

    def test_resolve_by_prefix(self, reader):
        r, store = reader
        rid = _seed_run(store, name="x")
        run = r.resolve_run(rid[:8])
        assert run is not None
        assert run.run_id == rid

    def test_get_run_full_includes_metrics(self, reader):
        r, store = reader
        rid = _seed_run(store, name="x", total_return=7.5)
        full = r.get_run_full(rid)
        assert full is not None
        assert full.metrics["total_return"] == 7.5

    def test_not_found(self, reader):
        r, _ = reader
        assert r.resolve_run("aaaaaaaa") is None
        assert r.get_run_full("aaaaaaaa") is None
