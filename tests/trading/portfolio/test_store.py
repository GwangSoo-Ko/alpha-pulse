"""PortfolioStore 테스트."""

import json

import pytest

from alphapulse.trading.portfolio.store import PortfolioStore


@pytest.fixture
def store(tmp_path):
    return PortfolioStore(tmp_path / "portfolio.db")


class TestSnapshots:
    def test_save_and_get(self, store):
        """스냅샷 저장 및 조회."""
        positions = [
            {"code": "005930", "quantity": 100, "avg_price": 72000,
             "weight": 0.5, "strategy_id": "momentum"},
        ]
        store.save_snapshot(
            date="20260409", mode="paper", cash=5_000_000,
            total_value=12_200_000, positions=positions,
            daily_return=0.5, cumulative_return=8.3, drawdown=-2.1,
        )

        snap = store.get_snapshot("20260409", mode="paper")
        assert snap is not None
        assert snap["cash"] == 5_000_000
        assert snap["total_value"] == 12_200_000
        assert snap["daily_return"] == 0.5
        parsed = json.loads(snap["positions"])
        assert len(parsed) == 1
        assert parsed[0]["code"] == "005930"

    def test_get_snapshots_range(self, store):
        """기간별 스냅샷 조회."""
        for i, date in enumerate(["20260407", "20260408", "20260409"]):
            store.save_snapshot(
                date=date, mode="paper", cash=5_000_000,
                total_value=10_000_000 + i * 100_000,
                positions=[], daily_return=0.1 * i,
                cumulative_return=0.3 * i, drawdown=0.0,
            )

        snaps = store.get_snapshots("20260407", "20260409", mode="paper")
        assert len(snaps) == 3
        assert snaps[0]["date"] == "20260407"
        assert snaps[2]["date"] == "20260409"

    def test_get_missing_snapshot(self, store):
        """존재하지 않는 스냅샷 → None."""
        assert store.get_snapshot("20260409", mode="paper") is None


class TestOrders:
    def test_save_and_get(self, store):
        """주문 저장 및 조회."""
        store.save_order(
            order_id="ORD001", mode="paper", date="20260409",
            stock_code="005930", stock_name="삼성전자",
            side="BUY", order_type="MARKET", quantity=100, price=72000,
            strategy_id="momentum", reason="리밸런싱",
            status="filled", filled_quantity=100, filled_price=72000,
            commission=1080, tax=0,
        )

        orders = store.get_orders("20260409", mode="paper")
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORD001"
        assert orders[0]["status"] == "filled"

    def test_get_orders_empty(self, store):
        assert store.get_orders("20260409", mode="paper") == []


class TestTrades:
    def test_save_and_get(self, store):
        """거래 저장 및 조회."""
        store.save_trade(
            trade_id="TRD001", order_id="ORD001", mode="paper",
            date="20260409", stock_code="005930", side="BUY",
            quantity=100, price=72000, commission=1080, tax=0,
            strategy_id="momentum", realized_pnl=0,
        )

        trades = store.get_trades("20260409", mode="paper")
        assert len(trades) == 1
        assert trades[0]["trade_id"] == "TRD001"


class TestAttribution:
    def test_save_and_get(self, store):
        """성과 귀속 저장 및 조회."""
        store.save_attribution(
            date="20260409", mode="paper",
            strategy_returns={"momentum": 0.012, "value": -0.003},
            factor_returns={"momentum_factor": 0.009},
            sector_returns={"반도체": 0.005},
        )

        attr = store.get_attribution("20260409", mode="paper")
        assert attr is not None
        parsed = json.loads(attr["strategy_returns"])
        assert parsed["momentum"] == 0.012
