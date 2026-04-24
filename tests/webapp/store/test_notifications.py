"""NotificationStore 단위 테스트."""

from __future__ import annotations

import time

import pytest

from alphapulse.webapp.store.notifications import (
    DEDUP_WINDOW_SECONDS,
    NotificationStore,
)
from alphapulse.webapp.store.webapp_db import init_webapp_db


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "webapp.db"
    init_webapp_db(db)
    return NotificationStore(db_path=db)


def test_add_inserts_row(store):
    nid = store.add(
        kind="job", level="info", title="제목", body="본문", link="/a",
    )
    assert nid is not None and nid > 0
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["title"] == "제목"
    assert rows[0]["is_read"] == 0


def test_add_rejects_invalid_kind(store):
    nid = store.add(kind="unknown", level="info", title="x")
    assert nid is None
    assert store.list_recent() == []


def test_add_rejects_invalid_level(store):
    nid = store.add(kind="job", level="debug", title="x")
    assert nid is None


def test_add_dedups_same_kind_link_within_1min(store):
    first = store.add(kind="job", level="info", title="A", link="/x")
    second = store.add(kind="job", level="info", title="B", link="/x")
    assert first is not None
    assert second is None
    assert len(store.list_recent()) == 1


def test_add_allows_same_kind_different_link(store):
    a = store.add(kind="job", level="info", title="A", link="/x")
    b = store.add(kind="job", level="info", title="B", link="/y")
    assert a is not None and b is not None
    assert len(store.list_recent()) == 2


def test_add_allows_same_kind_no_link(store):
    a = store.add(kind="pulse", level="info", title="A", link=None)
    b = store.add(kind="pulse", level="info", title="B", link=None)
    assert a is not None and b is not None


def test_list_recent_orders_desc(store):
    a = store.add(kind="job", level="info", title="first", link="/1")
    time.sleep(0.01)
    b = store.add(kind="job", level="info", title="second", link="/2")
    rows = store.list_recent()
    assert rows[0]["id"] == b
    assert rows[1]["id"] == a


def test_list_recent_respects_limit(store):
    for i in range(5):
        store.add(kind="job", level="info", title=f"n{i}", link=f"/l{i}")
    rows = store.list_recent(limit=3)
    assert len(rows) == 3


def test_list_recent_filters_retention_cutoff(store, monkeypatch):
    # 31일 전 레코드 직접 삽입
    import sqlite3
    old = time.time() - 31 * 86400
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "INSERT INTO notifications (kind, level, title, created_at) "
            "VALUES ('job', 'info', 'old', ?)",
            (old,),
        )
    store.add(kind="job", level="info", title="new", link="/new")
    rows = store.list_recent()
    titles = [r["title"] for r in rows]
    assert "new" in titles
    assert "old" not in titles


def test_unread_count_counts_only_is_read_zero(store):
    a = store.add(kind="job", level="info", title="a", link="/a")
    store.add(kind="job", level="info", title="b", link="/b")
    store.mark_read(a)
    assert store.unread_count() == 1


def test_mark_read_returns_true_on_success(store):
    nid = store.add(kind="job", level="info", title="t", link="/t")
    assert store.mark_read(nid) is True
    rows = store.list_recent()
    assert rows[0]["is_read"] == 1


def test_mark_read_returns_false_on_missing_id(store):
    assert store.mark_read(99999) is False


def test_mark_all_read_returns_affected_count(store):
    store.add(kind="job", level="info", title="a", link="/a")
    store.add(kind="job", level="info", title="b", link="/b")
    affected = store.mark_all_read()
    assert affected == 2
    assert store.unread_count() == 0


def test_dedup_window_constant_is_60(store):
    assert DEDUP_WINDOW_SECONDS == 60
