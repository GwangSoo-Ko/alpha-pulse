"""RecoveryManager 테스트 — 장애 복구 + DB/브로커 대사.

재시작 시 DB 스냅샷과 브로커 실제 잔고를 비교하여
불일치를 감지한다. 자동 수정은 하지 않는다.
"""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.orchestrator.recovery import RecoveryManager


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def hynix():
    return Stock(code="000660", name="SK하이닉스", market="KOSPI")


@pytest.fixture
def mock_broker():
    return MagicMock()


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def mock_alert():
    return MagicMock()


class TestReconcile:
    """DB/브로커 대사 테스트."""

    def test_positions_match(self, samsung, mock_broker, mock_store, mock_alert):
        """DB와 브로커 포지션이 일치하면 빈 경고 목록."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert warnings == []

    def test_quantity_mismatch(self, samsung, mock_broker, mock_store, mock_alert):
        """수량 불일치 시 경고를 반환한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=90, avg_price=72000,
                     current_price=73000, unrealized_pnl=0,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "005930" in warnings[0]
        assert "수량" in warnings[0]

    def test_extra_position_in_broker(self, samsung, hynix, mock_broker, mock_store, mock_alert):
        """브로커에만 있는 종목을 경고한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
            Position(stock=hynix, quantity=50, avg_price=150000,
                     current_price=155000, unrealized_pnl=250000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "000660" in warnings[0]

    def test_missing_position_in_broker(self, samsung, hynix, mock_broker, mock_store, mock_alert):
        """DB에만 있는 종목을 경고한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
            Position(stock=hynix, quantity=50, avg_price=150000,
                     current_price=155000, unrealized_pnl=250000,
                     weight=0.03, strategy_id="value"),
        ]
        broker_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = broker_positions

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert len(warnings) == 1
        assert "000660" in warnings[0]

    def test_empty_both(self, mock_broker, mock_store, mock_alert):
        """양쪽 모두 비어있으면 경고 없음."""
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = []

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        warnings = mgr.reconcile()
        assert warnings == []


class TestOnCrashRecovery:
    """재시작 복구 테스트."""

    def test_recovery_with_no_mismatch(self, samsung, mock_broker, mock_store, mock_alert):
        """불일치 없으면 정상 복구."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.0, strategy_id=""),
        ]

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
        assert result["warnings"] == []

    def test_recovery_with_mismatch_sends_alert(self, samsung, mock_broker, mock_store, mock_alert):
        """불일치 발견 시 알림을 전송한다."""
        db_positions = [
            Position(stock=samsung, quantity=100, avg_price=72000,
                     current_price=73000, unrealized_pnl=100000,
                     weight=0.05, strategy_id="momentum"),
        ]
        mock_store.get_latest_snapshot.return_value = PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=db_positions,
            total_value=100_000_000, daily_return=0, cumulative_return=0, drawdown=0,
        )
        mock_broker.get_positions.return_value = [
            Position(stock=samsung, quantity=80, avg_price=72000,
                     current_price=73000, unrealized_pnl=80000,
                     weight=0.0, strategy_id=""),
        ]

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
        assert len(result["warnings"]) == 1

    def test_recovery_no_snapshot(self, mock_broker, mock_store, mock_alert):
        """스냅샷이 없으면 경고만."""
        mock_store.get_latest_snapshot.return_value = None
        mock_broker.get_positions.return_value = []

        mgr = RecoveryManager(
            broker=mock_broker, store=mock_store, alert=mock_alert,
        )
        result = mgr.on_crash_recovery()
        assert result["recovered"] is True
