"""SimBroker 테스트 — 가상 체결 엔진."""

import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.sim_broker import SimBroker
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import OHLCV, Order, Stock


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def kodex200():
    return Stock(code="069500", name="KODEX 200", market="ETF")


@pytest.fixture
def sample_feed():
    """5일치 데이터를 가진 HistoricalDataFeed."""
    data = {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
        ],
        "069500": [
            OHLCV(date="20260406", open=35000, high=35500, low=34800, close=35200, volume=5_000_000),
            OHLCV(date="20260407", open=35200, high=36000, low=35000, close=35800, volume=6_000_000),
            OHLCV(date="20260408", open=35800, high=36200, low=35500, close=35900, volume=5_500_000),
        ],
    }
    feed = HistoricalDataFeed(data)
    return feed


@pytest.fixture
def broker(sample_feed):
    """기본 SimBroker (슬리피지 없음)."""
    cost_model = CostModel(slippage_model="none")
    return SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=100_000_000)


class TestSimBrokerInit:
    def test_initial_cash(self, broker):
        """초기 현금이 설정된다."""
        assert broker.cash == 100_000_000

    def test_initial_no_positions(self, broker):
        """초기 포지션은 비어있다."""
        assert broker.get_positions() == []

    def test_get_balance(self, broker):
        """잔고 조회."""
        balance = broker.get_balance()
        assert balance["cash"] == 100_000_000
        assert balance["total_value"] == 100_000_000
        assert balance["positions_value"] == 0


class TestMarketOrder:
    def test_buy_market_executes_at_close(self, broker, samsung, sample_feed):
        """MARKET 매수 — 당일 종가로 체결."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "filled"
        assert result.filled_price == 72500  # 당일 종가
        assert result.filled_quantity == 100
        assert result.commission > 0

    def test_buy_reduces_cash(self, broker, samsung, sample_feed):
        """매수 후 현금이 감소한다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        expected_cost = 100 * 72500  # 7,250,000
        assert broker.cash < 100_000_000
        assert broker.cash < 100_000_000 - expected_cost + 1  # 수수료까지

    def test_buy_creates_position(self, broker, samsung, sample_feed):
        """매수 후 포지션이 생성된다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].stock.code == "005930"
        assert positions[0].quantity == 100

    def test_sell_market_executes_at_close(self, broker, samsung, sample_feed):
        """MARKET 매도 — 당일 종가로 체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "filled"
        assert result.filled_price == 73500  # 20260407 종가
        assert result.filled_quantity == 100

    def test_sell_removes_position(self, broker, samsung, sample_feed):
        """전량 매도 후 포지션이 제거된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(sell)
        assert broker.get_positions() == []

    def test_sell_tax_on_stock(self, broker, samsung, sample_feed):
        """주식 매도 시 세금이 부과된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.tax > 0  # 주식 매도세 존재

    def test_sell_etf_no_tax(self, broker, kodex200, sample_feed):
        """ETF 매도 시 세금이 면제된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=kodex200, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=kodex200, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.tax == 0


class TestLimitOrder:
    def test_buy_limit_filled_when_low_hits(self, broker, samsung, sample_feed):
        """매수 LIMIT — 저가 <= 지정가이면 체결."""
        sample_feed.advance_to("20260406")
        # 20260406 저가 71500, 지정가 72000 → 체결
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=100, price=72000, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "filled"
        assert result.filled_price == 72000  # 지정가로 체결

    def test_buy_limit_rejected_when_low_above(self, broker, samsung, sample_feed):
        """매수 LIMIT — 저가 > 지정가이면 미체결."""
        sample_feed.advance_to("20260406")
        # 20260406 저가 71500, 지정가 71000 → 미체결
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=100, price=71000, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "rejected"
        assert result.filled_quantity == 0

    def test_sell_limit_filled_when_high_hits(self, broker, samsung, sample_feed):
        """매도 LIMIT — 고가 >= 지정가이면 체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        # 20260406 고가 73000, 지정가 73000 → 체결
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.LIMIT,
            quantity=100, price=73000, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "filled"
        assert result.filled_price == 73000

    def test_sell_limit_rejected_when_high_below(self, broker, samsung, sample_feed):
        """매도 LIMIT — 고가 < 지정가이면 미체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        # 20260406 고가 73000, 지정가 74000 → 미체결
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.LIMIT,
            quantity=100, price=74000, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"
        assert result.filled_quantity == 0


class TestEdgeCases:
    def test_insufficient_cash_rejected(self, sample_feed):
        """현금 부족 시 매수 거부."""
        cost_model = CostModel(slippage_model="none")
        broker = SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=1_000_000)
        sample_feed.advance_to("20260406")
        order = Order(
            stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
            side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        # 72500 * 100 = 7,250,000 > 1,000,000
        assert result.status == "rejected"

    def test_sell_more_than_held_rejected(self, broker, samsung, sample_feed):
        """보유 수량 초과 매도 거부."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=200, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"

    def test_sell_nonexistent_position_rejected(self, broker, samsung, sample_feed):
        """미보유 종목 매도 거부."""
        sample_feed.advance_to("20260406")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"

    def test_no_bar_data_rejected(self, broker, sample_feed):
        """당일 데이터 없는 종목 주문 거부."""
        sample_feed.advance_to("20260406")
        unknown = Stock(code="999999", name="없는종목", market="KOSPI")
        order = Order(
            stock=unknown, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=10, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "rejected"

    def test_multiple_buys_accumulate(self, broker, samsung, sample_feed):
        """동일 종목 복수 매수 시 포지션이 누적된다."""
        sample_feed.advance_to("20260406")
        for _ in range(3):
            order = Order(
                stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
                quantity=50, price=None, strategy_id="test",
            )
            broker.submit_order(order)
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].quantity == 150

    def test_partial_sell(self, broker, samsung, sample_feed):
        """일부 매도 시 남은 수량이 유지된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=30, price=None, strategy_id="test",
        )
        broker.submit_order(sell)
        positions = broker.get_positions()
        assert positions[0].quantity == 70

    def test_trade_log(self, broker, samsung, sample_feed):
        """체결 이력이 기록된다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        assert len(broker.trade_log) == 1
        assert broker.trade_log[0].order.stock.code == "005930"


class TestSlippage:
    def test_slippage_applied_to_buy(self, sample_feed, samsung):
        """매수 시 슬리피지가 가격에 가산된다."""
        cost_model = CostModel(slippage_model="fixed")
        broker = SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=100_000_000)
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        # fixed 슬리피지: 종가 * (1 + slippage) → 72500보다 높아야
        assert result.filled_price >= 72500


class TestProtocolConformance:
    def test_implements_broker_protocol(self, broker):
        """SimBroker가 Broker Protocol을 구현한다."""
        from alphapulse.trading.core.interfaces import Broker

        assert isinstance(broker, Broker)
