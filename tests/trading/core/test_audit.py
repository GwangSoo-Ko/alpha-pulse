"""감사 추적 로거 테스트."""

import json

import pytest

from alphapulse.trading.core.audit import AuditLogger
from alphapulse.trading.core.enums import TradingMode


@pytest.fixture
def audit(tmp_path):
    return AuditLogger(db_path=tmp_path / "test_audit.db")


class TestAuditLogger:
    def test_log_and_query(self, audit):
        """이벤트를 기록하고 조회한다."""
        audit.log("signal", "momentum_strategy",
                   {"stock": "005930", "score": 75},
                   mode=TradingMode.BACKTEST)

        results = audit.query()
        assert len(results) == 1
        assert results[0]["event_type"] == "signal"
        assert results[0]["component"] == "momentum_strategy"
        data = json.loads(results[0]["data"])
        assert data["stock"] == "005930"

    def test_query_by_event_type(self, audit):
        """이벤트 유형으로 필터링한다."""
        audit.log("signal", "comp1", {"a": 1}, mode=TradingMode.PAPER)
        audit.log("order", "comp2", {"b": 2}, mode=TradingMode.PAPER)
        audit.log("signal", "comp3", {"c": 3}, mode=TradingMode.PAPER)

        signals = audit.query(event_type="signal")
        assert len(signals) == 2

        orders = audit.query(event_type="order")
        assert len(orders) == 1

    def test_query_by_date_range(self, audit):
        """날짜 범위로 필터링한다."""
        audit.log("signal", "comp1", {"a": 1}, mode=TradingMode.LIVE)
        results = audit.query(start="20260101", end="20261231")
        assert len(results) == 1

    def test_empty_query(self, audit):
        """레코드 없으면 빈 리스트."""
        assert audit.query() == []

    def test_mode_stored(self, audit):
        """실행 모드가 저장된다."""
        audit.log("order", "broker", {"id": "123"}, mode=TradingMode.LIVE)
        results = audit.query()
        assert results[0]["mode"] == "live"
