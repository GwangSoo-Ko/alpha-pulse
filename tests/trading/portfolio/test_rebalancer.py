"""Rebalancer 테스트."""

import pytest

from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.portfolio.rebalancer import Rebalancer


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def hynix():
    return Stock(code="000660", name="SK하이닉스", market="KOSPI")


@pytest.fixture
def kakao():
    return Stock(code="035720", name="카카오", market="KOSPI")


@pytest.fixture
def rebalancer():
    return Rebalancer(min_trade_amount=100_000)


class TestGenerateOrders:
    def test_buy_new_stock(self, rebalancer, samsung):
        """신규 종목 매수 주문 생성."""
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.50}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.BUY
        assert orders[0].stock.code == "005930"
        assert orders[0].quantity > 0

    def test_sell_removed_stock(self, rebalancer, samsung):
        """목표에서 빠진 종목 전량 매도."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=73000, unrealized_pnl=100000,
            weight=0.50, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[pos], total_value=12_300_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {}  # 삼성전자 빠짐
        prices = {"005930": 73000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 100

    def test_rebalance_increase(self, rebalancer, samsung):
        """비중 증가 -> 추가 매수."""
        pos = Position(
            stock=samsung, quantity=50, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.36, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=6_400_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.70}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.BUY

    def test_sells_before_buys(self, rebalancer, samsung, hynix, kakao):
        """매도 주문이 매수 주문보다 먼저 온다 (자금 확보)."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.72, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=2_800_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.30, "000660": 0.40}
        prices = {"005930": 72000, "000660": 180000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        sell_indices = [i for i, o in enumerate(orders) if o.side == Side.SELL]
        buy_indices = [i for i, o in enumerate(orders) if o.side == Side.BUY]
        if sell_indices and buy_indices:
            assert max(sell_indices) < min(buy_indices)

    def test_skip_small_trades(self, rebalancer, samsung):
        """최소 거래금액 미만 차이는 무시."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.72, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=2_800_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        # 목표 비중이 현재와 거의 동일 -> 거래 불필요
        target_weights = {"005930": 0.72}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 0

    def test_empty_targets_sells_all(self, rebalancer, samsung):
        """빈 목표 -> 전량 매도."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=1.0, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=0,
            positions=[pos], total_value=7_200_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )

        orders = rebalancer.generate_orders(
            target_weights={},
            current=current,
            prices={"005930": 72000},
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 100
