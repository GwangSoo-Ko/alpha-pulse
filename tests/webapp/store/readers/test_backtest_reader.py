"""BacktestReader.list_runs sort/dir 테스트."""
from __future__ import annotations

import json
import sqlite3

import pytest

from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.webapp.store.readers.backtest import BacktestReader


@pytest.fixture
def reader(tmp_path):
    db = tmp_path / "backtest.db"
    BacktestStore(db_path=db)  # schema 생성
    return BacktestReader(db_path=db)


def _seed(reader, *, run_id: str, name: str, created_at: float, final_return: float,
          start_date: str = "20260101", end_date: str = "20260301"):
    """테스트용 run 직접 삽입."""
    with sqlite3.connect(reader.db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, name, strategies, start_date, end_date, "
            "initial_capital, final_value, benchmark, created_at, metrics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, name, json.dumps(["momentum"]),
                start_date, end_date,
                10_000_000.0, 10_000_000.0, "KOSPI",
                created_at,
                json.dumps({"final_return": final_return}),
            ),
        )


def test_list_runs_sort_by_name_asc(reader):
    _seed(reader, run_id="r-alpha", name="alpha", created_at=100.0, final_return=5.0)
    _seed(reader, run_id="r-bravo", name="bravo", created_at=200.0, final_return=3.0)
    page = reader.list_runs(page=1, size=10, sort="name", dir="asc")
    names = [r.name for r in page.items]
    assert names == ["alpha", "bravo"]


def test_list_runs_sort_by_final_return_desc(reader):
    _seed(reader, run_id="r-low", name="low", created_at=100.0, final_return=1.0)
    _seed(reader, run_id="r-high", name="high", created_at=200.0, final_return=10.0)
    _seed(reader, run_id="r-mid", name="mid", created_at=300.0, final_return=5.0)
    page = reader.list_runs(page=1, size=10, sort="final_return", dir="desc")
    names = [r.name for r in page.items]
    assert names == ["high", "mid", "low"]


def test_list_runs_sort_default_is_created_at_desc(reader):
    _seed(reader, run_id="r-first", name="first", created_at=100.0, final_return=5.0)
    _seed(reader, run_id="r-second", name="second", created_at=200.0, final_return=3.0)
    page = reader.list_runs(page=1, size=10)  # default sort/dir
    names = [r.name for r in page.items]
    assert names == ["second", "first"]


def test_list_runs_sort_invalid_falls_back(reader):
    _seed(reader, run_id="r-first", name="first", created_at=100.0, final_return=5.0)
    _seed(reader, run_id="r-second", name="second", created_at=200.0, final_return=3.0)
    page = reader.list_runs(page=1, size=10, sort="hacker; DROP TABLE x;", dir="desc")
    names = [r.name for r in page.items]
    # 기본 created_at DESC 로 fallback
    assert names == ["second", "first"]
