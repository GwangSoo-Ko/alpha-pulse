"""Trading 데이터 모델 테스트."""

from datetime import datetime

from alphapulse.trading.core.models import (
    OHLCV,
    Order,
    OrderResult,
    PortfolioSnapshot,
    Position,
    RiskAlert,
    RiskDecision,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)


class TestStock:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        assert stock.code == "005930"
        assert stock.name == "삼성전자"
        assert stock.market == "KOSPI"
        assert stock.sector == ""

    def test_frozen(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        try:
            stock.code = "000660"
            assert False, "frozen dataclass should raise"
        except AttributeError:
            pass

    def test_equality(self):
        s1 = Stock(code="005930", name="삼성전자", market="KOSPI")
        s2 = Stock(code="005930", name="삼성전자", market="KOSPI")
        assert s1 == s2

    def test_with_sector(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")
        assert stock.sector == "반도체"


class TestOHLCV:
    def test_creation(self):
        bar = OHLCV(
            date="20260409",
            open=72000,
            high=73000,
            low=71500,
            close=72500,
            volume=10_000_000,
        )
        assert bar.close == 72500
        assert bar.market_cap == 0

    def test_with_market_cap(self):
        bar = OHLCV(
            date="20260409",
            open=72000,
            high=73000,
            low=71500,
            close=72500,
            volume=10_000_000,
            market_cap=430_000_000_000_000,
        )
        assert bar.market_cap == 430_000_000_000_000


class TestPosition:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        pos = Position(
            stock=stock,
            quantity=100,
            avg_price=72000,
            current_price=73000,
            unrealized_pnl=100000,
            weight=0.05,
            strategy_id="momentum",
        )
        assert pos.quantity == 100
        assert pos.strategy_id == "momentum"


class TestOrder:
    def test_market_order(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        order = Order(
            stock=stock,
            side="BUY",
            order_type="MARKET",
            quantity=100,
            price=None,
            strategy_id="momentum",
        )
        assert order.price is None
        assert order.reason == ""

    def test_limit_order_with_reason(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        order = Order(
            stock=stock,
            side="SELL",
            order_type="LIMIT",
            quantity=50,
            price=73000,
            strategy_id="value",
            reason="리밸런싱",
        )
        assert order.price == 73000
        assert order.reason == "리밸런싱"


class TestSignal:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        signal = Signal(
            stock=stock,
            score=75.0,
            factors={"momentum": 0.8, "value": 0.3},
            strategy_id="momentum",
        )
        assert signal.score == 75.0
        assert isinstance(signal.timestamp, datetime)


class TestPortfolioSnapshot:
    def test_creation(self):
        snap = PortfolioSnapshot(
            date="20260409",
            cash=50_000_000,
            positions=[],
            total_value=100_000_000,
            daily_return=0.5,
            cumulative_return=8.3,
            drawdown=-2.1,
        )
        assert snap.total_value == 100_000_000
        assert snap.positions == []


class TestStrategySynthesis:
    def test_creation(self):
        syn = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.72,
            allocation_adjustment={"topdown_etf": 0.3},
            stock_opinions=[],
            risk_warnings=["변동성 확대"],
            reasoning="외국인 순매수 지속",
        )
        assert syn.conviction_level == 0.72


class TestStockOpinion:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock,
            action="매수",
            reason="외국인 수급 전환",
            confidence=0.8,
        )
        assert opinion.action == "매수"


class TestOrderResult:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        order = Order(
            stock=stock,
            side="BUY",
            order_type="MARKET",
            quantity=100,
            price=None,
            strategy_id="momentum",
        )
        result = OrderResult(
            order_id="ORD001",
            order=order,
            status="filled",
            filled_quantity=100,
            filled_price=72000,
            commission=1080,
            tax=0,
            filled_at=datetime(2026, 4, 9, 10, 0),
        )
        assert result.order_id == "ORD001"
        assert result.status == "filled"
        assert result.filled_quantity == 100


class TestRiskDecision:
    def test_creation(self):
        decision = RiskDecision(
            action="APPROVE",
            reason="리스크 한도 내",
            adjusted_quantity=None,
        )
        assert decision.action == "APPROVE"
        assert decision.adjusted_quantity is None

    def test_reduce_size(self):
        decision = RiskDecision(
            action="REDUCE_SIZE",
            reason="집중도 초과",
            adjusted_quantity=50,
        )
        assert decision.action == "REDUCE_SIZE"
        assert decision.adjusted_quantity == 50


class TestRiskAlert:
    def test_creation(self):
        alert = RiskAlert(
            level="WARNING",
            category="drawdown",
            message="드로다운 -8% 도달",
            current_value=8.0,
            limit_value=10.0,
        )
        assert alert.level == "WARNING"
        assert alert.category == "drawdown"
        assert alert.current_value == 8.0
