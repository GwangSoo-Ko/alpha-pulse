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
