"""BacktestEngine 테스트 — 메인 시뮬레이션 루프."""

from unittest.mock import MagicMock, patch

import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import OHLCV, Order, Signal, Stock


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def sample_data(samsung):
    """5 거래일 데이터."""
    return {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
            OHLCV(date="20260409", open=74000, high=74500, low=72500, close=73000, volume=9_000_000),
            OHLCV(date="20260410", open=73000, high=73500, low=71000, close=71500, volume=15_000_000),
        ],
    }


@pytest.fixture
def mock_strategy(samsung):
    """매일 삼성전자 매수 시그널을 생성하는 모의 전략."""
    strategy = MagicMock()
    strategy.strategy_id = "test_strategy"
    strategy.generate_signals.return_value = [
        Signal(stock=samsung, score=80.0, factors={"momentum": 0.8},
               strategy_id="test_strategy"),
    ]
    strategy.should_rebalance.return_value = True
    return strategy


@pytest.fixture
def benchmark_data():
    """KOSPI 벤치마크 데이터."""
    return {
        "KOSPI": [
            OHLCV(date="20260406", open=2700, high=2720, low=2690, close=2710, volume=500_000_000),
            OHLCV(date="20260407", open=2710, high=2740, low=2700, close=2730, volume=480_000_000),
            OHLCV(date="20260408", open=2730, high=2750, low=2720, close=2740, volume=510_000_000),
            OHLCV(date="20260409", open=2740, high=2745, low=2710, close=2720, volume=490_000_000),
            OHLCV(date="20260410", open=2720, high=2725, low=2680, close=2690, volume=520_000_000),
        ],
    }


class TestBacktestConfig:
    def test_creation(self):
        """설정 객체 생성."""
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        assert config.initial_capital == 100_000_000
        assert config.benchmark == "KOSPI"


class TestBacktestResult:
    def test_creation(self):
        """결과 객체 생성."""
        result = BacktestResult(
            snapshots=[], trades=[], metrics={},
            config=BacktestConfig(
                initial_capital=100_000_000,
                start_date="20260406",
                end_date="20260410",
                cost_model=CostModel(),
            ),
        )
        assert result.snapshots == []


class TestBacktestEngine:
    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_run_returns_result(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """run()이 BacktestResult를 반환한다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert isinstance(result, BacktestResult)
        assert len(result.snapshots) == 5
        assert isinstance(result.metrics, dict)

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_snapshots_have_correct_dates(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """스냅샷 날짜가 거래일과 일치한다."""
        trading_days = ["20260406", "20260407", "20260408", "20260409", "20260410"]
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = trading_days

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        dates = [s.date for s in result.snapshots]
        assert dates == trading_days

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_initial_value_preserved(self, mock_cal_cls, sample_data, benchmark_data):
        """전략이 주문 없으면 초기 자본이 유지된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408",
        ]

        no_signal_strategy = MagicMock()
        no_signal_strategy.strategy_id = "empty"
        no_signal_strategy.generate_signals.return_value = []
        no_signal_strategy.should_rebalance.return_value = True

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260408",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[no_signal_strategy],
            order_generator=lambda signals, snap, broker: [],
        )
        result = engine.run()
        assert result.snapshots[0].total_value == 100_000_000
        assert result.snapshots[-1].total_value == 100_000_000

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_metrics_calculated(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """결과에 metrics가 포함된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert "total_return" in result.metrics
        assert "sharpe_ratio" in result.metrics
        assert "max_drawdown" in result.metrics

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_trades_recorded(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """체결 이력이 기록된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert len(result.trades) > 0

    @staticmethod
    def _simple_order_generator(signals, snapshot, broker):
        """테스트용 간단한 주문 생성기 — 매수 시그널 → MARKET 매수."""
        orders = []
        for signal in signals:
            if signal.score > 50:
                order = Order(
                    stock=signal.stock,
                    side=Side.BUY,
                    order_type="MARKET",
                    quantity=10,
                    price=None,
                    strategy_id=signal.strategy_id,
                )
                orders.append(order)
        return orders
