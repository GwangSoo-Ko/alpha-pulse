"""공매도/신용 수집기 테스트."""

import pytest

from alphapulse.trading.data.short_collector import ShortCollector


@pytest.fixture
def collector(tmp_path):
    return ShortCollector(db_path=tmp_path / "test.db")


class TestShortCollector:
    def test_save_and_get(self, collector):
        """수동 저장 + 조회 테스트 (스크래퍼 구현 전)."""
        collector.store.save_short_interest_bulk([
            ("005930", "20260409", 500_000, 10_000_000, 0.5, 100e9, 5_000_000),
        ])

        result = collector.store.get_short_interest("005930", days=1)
        assert len(result) == 1
        assert result[0]["short_ratio"] == 0.5
