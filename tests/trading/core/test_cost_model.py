"""거래 비용 모델 테스트."""

import pytest

from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, Stock


@pytest.fixture
def model():
    return CostModel()


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def kodex200():
    return Stock(code="069500", name="KODEX 200", market="ETF")


class TestCommission:
    def test_default_rate(self, model):
        """기본 수수료율 0.015%."""
        assert model.calculate_commission(10_000_000) == pytest.approx(1500)

    def test_custom_rate(self):
        model = CostModel(commission_rate=0.0003)
        assert model.calculate_commission(10_000_000) == pytest.approx(3000)


class TestTax:
    def test_stock_sell_tax(self, model):
        """주식 매도세 0.18%."""
        assert model.calculate_tax(10_000_000, is_etf=False) == pytest.approx(18000)

    def test_etf_no_tax(self, model):
        """ETF는 매도세 면제."""
        assert model.calculate_tax(10_000_000, is_etf=True) == 0


class TestSlippage:
    def test_no_slippage_model(self):
        model = CostModel(slippage_model="none")
        order = Order(stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
                       side="BUY", order_type="MARKET", quantity=100,
                       price=72000, strategy_id="test")
        assert model.estimate_slippage(order, avg_volume=1_000_000) == 0.0

    def test_small_order_no_slippage(self, model, samsung):
        """거래대금 1% 미만 → 슬리피지 0."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=10, price=72000, strategy_id="test")
        # 주문: 720,000원 / 일평균: 72,000,000,000원 < 1%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.0

    def test_medium_order_slippage(self, model, samsung):
        """거래대금 1~5% → 0.1% 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=20_000, price=72000, strategy_id="test")
        # 주문: 1,440,000,000원 / 일평균: 72,000,000,000원 = 2%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.001

    def test_large_order_slippage(self, model, samsung):
        """거래대금 5%+ → 0.3% 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100_000, price=72000, strategy_id="test")
        # 주문: 7,200,000,000원 / 일평균: 72,000,000,000원 = 10%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.003

    def test_zero_volume_max_slippage(self, model, samsung):
        """거래량 없으면 최대 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        result = model.estimate_slippage(order, avg_volume=0)
        assert result == 0.003


class TestTotalCost:
    def test_buy_order(self, model, samsung):
        """매수 → 수수료만, 세금 없음."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        cost = model.total_cost(order, filled_price=72000,
                                 is_etf=False, avg_volume=1_000_000)
        assert cost["commission"] == pytest.approx(1080)  # 7,200,000 * 0.00015
        assert cost["tax"] == 0

    def test_sell_stock(self, model, samsung):
        """주식 매도 → 수수료 + 세금."""
        order = Order(stock=samsung, side="SELL", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        cost = model.total_cost(order, filled_price=72000,
                                 is_etf=False, avg_volume=1_000_000)
        assert cost["commission"] == pytest.approx(1080)
        assert cost["tax"] == pytest.approx(12960)  # 7,200,000 * 0.0018

    def test_sell_etf_no_tax(self, model, kodex200):
        """ETF 매도 → 수수료만, 세금 면제."""
        order = Order(stock=kodex200, side="SELL", order_type="MARKET",
                       quantity=100, price=35000, strategy_id="test")
        cost = model.total_cost(order, filled_price=35000,
                                 is_etf=True, avg_volume=500_000)
        assert cost["tax"] == 0
