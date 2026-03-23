"""스토리지 계층 테스트

DataCache 및 PulseHistory의 CRUD, TTL, 직렬화를 검증한다.
"""

import time

import pandas as pd
import pytest

from alphapulse.core.storage.cache import DataCache
from alphapulse.core.storage.history import PulseHistory


# ── DataCache 테스트 ──────────────────────────────────────────────


class TestDataCache:
    """DataCache CRUD 및 TTL 테스트."""

    def test_set_and_get_roundtrip(self, tmp_path: object) -> None:
        """DataFrame 저장 후 조회하면 동일한 데이터가 반환된다."""
        cache = DataCache(tmp_path / "test_cache.db")
        df = pd.DataFrame(
            {"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]}
        )
        cache.set("test_key", df)

        result = cache.get("test_key")
        assert result is not None
        pd.testing.assert_frame_equal(result, df)

    def test_get_missing_key_returns_none(self, tmp_path: object) -> None:
        """존재하지 않는 키를 조회하면 None을 반환한다."""
        cache = DataCache(tmp_path / "test_cache.db")
        assert cache.get("nonexistent") is None

    def test_get_with_zero_ttl_never_expires(self, tmp_path: object) -> None:
        """ttl_minutes=0이면 만료되지 않는다."""
        cache = DataCache(tmp_path / "test_cache.db")
        df = pd.DataFrame({"value": [42]})
        cache.set("permanent", df)

        result = cache.get("permanent", ttl_minutes=0)
        assert result is not None
        pd.testing.assert_frame_equal(result, df)

    def test_get_expired_returns_none(self, tmp_path: object) -> None:
        """TTL이 지나면 None을 반환한다."""
        cache = DataCache(tmp_path / "test_cache.db")
        df = pd.DataFrame({"value": [1]})
        cache.set("expiring", df)

        # 0.001분 = 0.06초, sleep(0.1)이면 만료
        time.sleep(0.1)
        result = cache.get("expiring", ttl_minutes=0.001)
        assert result is None

    def test_set_upsert_overwrites(self, tmp_path: object) -> None:
        """같은 키로 다시 저장하면 데이터가 갱신된다."""
        cache = DataCache(tmp_path / "test_cache.db")
        df1 = pd.DataFrame({"value": [1]})
        df2 = pd.DataFrame({"value": [2]})

        cache.set("key", df1)
        cache.set("key", df2)

        result = cache.get("key")
        assert result is not None
        pd.testing.assert_frame_equal(result, df2)

    def test_clear_removes_all(self, tmp_path: object) -> None:
        """clear() 호출 시 모든 캐시가 삭제된다."""
        cache = DataCache(tmp_path / "test_cache.db")
        cache.set("a", pd.DataFrame({"v": [1]}))
        cache.set("b", pd.DataFrame({"v": [2]}))

        cache.clear()

        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_expired_removes_old_entries(self, tmp_path: object) -> None:
        """clear_expired()는 TTL 초과 항목만 삭제한다."""
        cache = DataCache(tmp_path / "test_cache.db")
        cache.set("old", pd.DataFrame({"v": [1]}))

        time.sleep(0.1)
        cache.set("new", pd.DataFrame({"v": [2]}))

        # 0.001분 = 0.06초, old는 만료, new는 유효
        cache.clear_expired(ttl_minutes=0.001)

        assert cache.get("old") is None
        result = cache.get("new")
        assert result is not None
        assert result["v"].iloc[0] == 2

    def test_roundtrip_with_datetime_index(self, tmp_path: object) -> None:
        """DatetimeIndex를 가진 DataFrame도 왕복 직렬화된다."""
        cache = DataCache(tmp_path / "test_cache.db")
        dates = pd.date_range("2026-03-09", periods=3, freq="B")
        df = pd.DataFrame({"price": [100, 200, 300]}, index=dates)

        cache.set("datetime_df", df)
        result = cache.get("datetime_df")

        assert result is not None
        assert len(result) == 3
        assert list(result["price"]) == [100, 200, 300]


# ── PulseHistory 테스트 ───────────────────────────────────────────


class TestPulseHistory:
    """PulseHistory CRUD 및 범위 조회 테스트."""

    @pytest.fixture()
    def history(self, tmp_path: object) -> PulseHistory:
        """테스트용 PulseHistory 인스턴스를 생성한다."""
        return PulseHistory(tmp_path / "test_history.db")

    @pytest.fixture()
    def sample_details(self) -> dict:
        """샘플 세부 점수 딕셔너리."""
        return {
            "investor_flow": 15.0,
            "spot_futures_align": 8.0,
            "program_trade": 5.0,
        }

    def test_save_and_get(
        self, history: PulseHistory, sample_details: dict
    ) -> None:
        """저장 후 조회하면 동일한 데이터가 반환된다."""
        history.save("20260313", 45.5, "매수 우위", sample_details)

        result = history.get("20260313")
        assert result is not None
        assert result["date"] == "20260313"
        assert result["score"] == 45.5
        assert result["signal"] == "매수 우위"
        assert result["details"] == sample_details
        assert isinstance(result["created_at"], float)

    def test_get_missing_date_returns_none(
        self, history: PulseHistory
    ) -> None:
        """존재하지 않는 날짜를 조회하면 None을 반환한다."""
        assert history.get("99991231") is None

    def test_save_upsert_overwrites(
        self, history: PulseHistory, sample_details: dict
    ) -> None:
        """같은 날짜로 다시 저장하면 데이터가 갱신된다."""
        history.save("20260313", 45.5, "매수 우위", sample_details)
        history.save("20260313", -30.0, "매도 우위", {"updated": True})

        result = history.get("20260313")
        assert result is not None
        assert result["score"] == -30.0
        assert result["signal"] == "매도 우위"
        assert result["details"] == {"updated": True}

    def test_get_range(
        self, history: PulseHistory, sample_details: dict
    ) -> None:
        """날짜 범위로 조회하면 해당 기간의 이력이 반환된다."""
        dates = ["20260309", "20260310", "20260311", "20260312", "20260313"]
        for i, d in enumerate(dates):
            history.save(d, float(i * 10), "signal", sample_details)

        results = history.get_range("20260310", "20260312")
        assert len(results) == 3
        assert results[0]["date"] == "20260310"
        assert results[1]["date"] == "20260311"
        assert results[2]["date"] == "20260312"

    def test_get_range_empty(self, history: PulseHistory) -> None:
        """범위에 데이터가 없으면 빈 리스트를 반환한다."""
        results = history.get_range("20260101", "20260131")
        assert results == []

    def test_get_recent(
        self, history: PulseHistory, sample_details: dict
    ) -> None:
        """get_recent()는 최근 N건을 날짜 내림차순으로 반환한다."""
        dates = ["20260309", "20260310", "20260311", "20260312", "20260313"]
        for i, d in enumerate(dates):
            history.save(d, float(i * 10), "signal", sample_details)

        results = history.get_recent(days=3)
        assert len(results) == 3
        # 내림차순 확인
        assert results[0]["date"] == "20260313"
        assert results[1]["date"] == "20260312"
        assert results[2]["date"] == "20260311"

    def test_get_recent_fewer_than_requested(
        self, history: PulseHistory, sample_details: dict
    ) -> None:
        """데이터가 요청 건수보다 적으면 있는 만큼만 반환한다."""
        history.save("20260313", 50.0, "signal", sample_details)

        results = history.get_recent(days=30)
        assert len(results) == 1
        assert results[0]["date"] == "20260313"

    def test_details_korean_preserved(self, history: PulseHistory) -> None:
        """한글 세부 정보가 직렬화/역직렬화 후 보존된다."""
        details = {"투자자 동향": 15.0, "선물/현물 정렬": 8.0}
        history.save("20260313", 23.0, "중립", details)

        result = history.get("20260313")
        assert result is not None
        assert result["details"] == details
