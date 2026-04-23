"""BriefingStore — briefings.db 테이블 스토리지."""
import pytest

from alphapulse.core.storage.briefings import BriefingStore


@pytest.fixture
def store(tmp_path):
    return BriefingStore(db_path=tmp_path / "briefings.db")


def test_get_returns_none_when_empty(store):
    assert store.get("20260421") is None


def test_save_then_get_roundtrip(store):
    payload = {
        "pulse_result": {"date": "20260421", "score": 42.0, "signal": "moderately_bullish"},
        "synthesis": "요약 테스트",
        "news": {"articles": [{"title": "기사 1"}]},
    }
    store.save("20260421", payload)
    got = store.get("20260421")
    assert got is not None
    assert got["date"] == "20260421"
    assert got["payload"] == payload
    assert got["created_at"] > 0


def test_save_upsert_overwrites(store):
    store.save("20260421", {"v": 1})
    store.save("20260421", {"v": 2})
    got = store.get("20260421")
    assert got["payload"] == {"v": 2}


def test_get_recent_sorted_date_desc(store):
    store.save("20260419", {"i": 1})
    store.save("20260421", {"i": 3})
    store.save("20260420", {"i": 2})
    items = store.get_recent(days=30)
    assert [x["date"] for x in items] == ["20260421", "20260420", "20260419"]


def test_get_recent_limits_to_days(store):
    for i in range(5):
        store.save(f"2026041{i}", {"i": i})
    items = store.get_recent(days=3)
    assert len(items) == 3


def test_save_sanitizes_numpy_scalars(store):
    """numpy float 같은 비-JSON 타입도 sanitize 되어야 함."""
    class FakeNpFloat:
        def __float__(self) -> float:
            return 42.5
    payload = {"score": FakeNpFloat()}
    store.save("20260421", payload)
    got = store.get("20260421")
    # Round-trip 후 float 로 변환됨
    assert got["payload"]["score"] == 42.5


def test_save_sanitizes_unknown_objects_to_str(store):
    class Obj:
        def __repr__(self) -> str:
            return "custom-obj"
    payload = {"weird": Obj()}
    store.save("20260421", payload)
    got = store.get("20260421")
    assert got["payload"]["weird"] == "custom-obj"


def test_list_summaries_returns_only_summary_fields(store):
    payload = {
        "pulse_result": {"score": 62.5, "signal": "매수 우위"},
        "commentary": "x",
        "synthesis": "y",
        "daily_result_msg": "m",
        "news": {"articles": []},
    }
    store.save(date="20260420", payload=payload)
    result = store.list_summaries(limit=10)
    assert len(result) == 1
    row = result[0]
    assert row["date"] == "20260420"
    assert row["score"] == 62.5
    assert row["signal"] == "매수 우위"
    assert row["has_synthesis"] is True
    assert row["has_commentary"] is True
    assert "created_at" in row
    # payload 전체가 포함되지 않아야 한다
    assert "payload" not in row
    assert "news" not in row


def test_list_summaries_paginates_with_offset(store):
    for i in range(5):
        store.save(date=f"2026041{i}", payload={"pulse_result": {"score": float(i), "signal": "중립"}})
    page1 = store.list_summaries(limit=2, offset=0)
    page2 = store.list_summaries(limit=2, offset=2)
    page3 = store.list_summaries(limit=2, offset=4)
    assert [r["date"] for r in page1] == ["20260414", "20260413"]  # DESC
    assert [r["date"] for r in page2] == ["20260412", "20260411"]
    assert [r["date"] for r in page3] == ["20260410"]


def test_list_summaries_has_synthesis_false_when_missing(store):
    store.save(date="20260420", payload={"pulse_result": {"score": 0.0, "signal": "중립"}})
    result = store.list_summaries(limit=10)
    assert result[0]["has_synthesis"] is False
    assert result[0]["has_commentary"] is False


def test_get_recent_offset(store):
    for i in range(5):
        store.save(date=f"2026041{i}", payload={"test": i})
    first = store.get_recent(days=3, offset=0)
    second = store.get_recent(days=3, offset=3)
    assert [r["date"] for r in first] == ["20260414", "20260413", "20260412"]
    assert [r["date"] for r in second] == ["20260411", "20260410"]
