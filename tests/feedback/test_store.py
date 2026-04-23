import json

import pytest

from alphapulse.core.storage.feedback import FeedbackStore


@pytest.fixture
def store(tmp_path):
    return FeedbackStore(tmp_path / "feedback.db")


def test_save_signal(store):
    store.save_signal(
        date="20260403",
        score=35.9,
        signal="매수 우위",
        indicator_scores={"investor_flow": 68, "vkospi": -10},
    )
    row = store.get("20260403")
    assert row is not None
    assert row["score"] == 35.9
    assert row["signal"] == "매수 우위"
    assert json.loads(row["indicator_scores"])["investor_flow"] == 68


def test_update_result(store):
    store.save_signal("20260403", 35.9, "매수 우위", {})
    store.update_result(
        date="20260403",
        kospi_close=2650.0,
        kospi_change_pct=1.2,
        kosdaq_close=870.0,
        kosdaq_change_pct=0.8,
        return_1d=1.2,
        hit_1d=1,
    )
    row = store.get("20260403")
    assert row["kospi_close"] == 2650.0
    assert row["return_1d"] == 1.2
    assert row["hit_1d"] == 1
    assert row["return_3d"] is None  # not yet evaluated


def test_update_analysis(store):
    store.save_signal("20260403", 35.9, "매수 우위", {})
    store.update_analysis(
        date="20260403",
        post_analysis={"reason": "외국인 매수 전환"},
        news_summary="코스피 상승, 외국인 순매수",
        blind_spots=["지정학 리스크"],
    )
    row = store.get("20260403")
    assert "외국인" in json.loads(row["post_analysis"])["reason"]
    assert "코스피" in row["news_summary"]


def test_get_recent(store):
    for i in range(5):
        store.save_signal(f"2026040{i+1}", float(i * 10), "매수", {})
    recent = store.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[0]["date"] == "20260405"  # most recent first


def test_get_pending_evaluation(store):
    store.save_signal("20260401", 35.0, "매수", {})
    store.save_signal("20260402", -20.0, "매도 우위", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.0, 1)
    pending = store.get_pending_evaluation()
    assert len(pending) == 1
    assert pending[0]["date"] == "20260402"


def test_get_yesterday(store):
    store.save_signal("20260402", -20.0, "매도 우위", {})
    store.save_signal("20260403", 35.0, "매수 우위", {})
    yesterday = store.get_yesterday()
    # Should return the second most recent (yesterday relative to latest)
    assert yesterday["date"] == "20260402"


def test_update_partial_returns(store):
    store.save_signal("20260401", 35.0, "매수", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.0, 1)
    # Later, update 3d return
    store.update_returns("20260401", return_3d=2.5, hit_3d=1)
    row = store.get("20260401")
    assert row["return_1d"] == 1.0
    assert row["return_3d"] == 2.5
    assert row["hit_3d"] == 1
    assert row["return_5d"] is None


def test_get_nonexistent(store):
    assert store.get("99991231") is None


def test_indexes_exist(store):
    """hit_1d/3d/5d 에 partial 인덱스가 생성되어야 한다."""
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        ).fetchall()
    names = {r[0] for r in rows}
    assert "idx_feedback_hit_1d" in names
    assert "idx_feedback_hit_3d" in names
    assert "idx_feedback_hit_5d" in names
