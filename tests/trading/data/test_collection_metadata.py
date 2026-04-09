"""데이터 수집 메타데이터 테스트."""
import pytest

from alphapulse.trading.data.collection_metadata import CollectionMetadata


@pytest.fixture
def meta(tmp_path):
    return CollectionMetadata(tmp_path / "test.db")


class TestCollectionMetadata:
    def test_get_last_date_empty(self, meta):
        assert meta.get_last_date("KOSPI", "ohlcv") is None

    def test_set_and_get(self, meta):
        meta.set_last_date("KOSPI", "ohlcv", "20260409")
        assert meta.get_last_date("KOSPI", "ohlcv") == "20260409"

    def test_update_existing(self, meta):
        meta.set_last_date("KOSPI", "ohlcv", "20260408")
        meta.set_last_date("KOSPI", "ohlcv", "20260409")
        assert meta.get_last_date("KOSPI", "ohlcv") == "20260409"

    def test_different_markets(self, meta):
        meta.set_last_date("KOSPI", "ohlcv", "20260409")
        meta.set_last_date("KOSDAQ", "ohlcv", "20260408")
        assert meta.get_last_date("KOSPI", "ohlcv") == "20260409"
        assert meta.get_last_date("KOSDAQ", "ohlcv") == "20260408"

    def test_get_all_status(self, meta):
        meta.set_last_date("KOSPI", "ohlcv", "20260409")
        meta.set_last_date("KOSPI", "fundamentals", "20260409")
        status = meta.get_all_status()
        assert len(status) == 2
        assert status[0]["market"] == "KOSPI"
