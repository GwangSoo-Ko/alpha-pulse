"""RiskReportCacheRepository."""
import time

import pytest

from alphapulse.webapp.store.risk_cache import RiskReportCacheRepository


@pytest.fixture
def cache(webapp_db):
    return RiskReportCacheRepository(db_path=webapp_db)


class TestRiskCache:
    def test_miss_returns_none(self, cache):
        assert cache.get("20260420|paper|100000000") is None

    def test_put_and_get(self, cache):
        cache.put(
            key="20260420|paper|100000000",
            report={"var_95": -2.5, "cvar_95": -3.1, "drawdown_status": "NORMAL"},
            stress={"2020_covid": -10.5, "flash_crash": -15.0},
        )
        got = cache.get("20260420|paper|100000000")
        assert got is not None
        assert got.report["var_95"] == -2.5
        assert got.stress["2020_covid"] == -10.5

    def test_put_overwrites(self, cache):
        cache.put(
            key="K", report={"var_95": -1.0}, stress={},
        )
        cache.put(
            key="K", report={"var_95": -2.0}, stress={},
        )
        got = cache.get("K")
        assert got.report["var_95"] == -2.0

    def test_computed_at_recent(self, cache):
        cache.put(key="K", report={}, stress={})
        got = cache.get("K")
        assert time.time() - got.computed_at < 2

    def test_snapshot_key_helper(self):
        key = RiskReportCacheRepository.snapshot_key(
            date="20260420", mode="paper", total_value=100_000_000.5,
        )
        assert key == "20260420|paper|100000000"
