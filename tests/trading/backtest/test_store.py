"""BacktestStore 테스트 — backtest.db 결과 저장."""

import json

import pytest

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, OrderResult, PortfolioSnapshot, Stock


@pytest.fixture
def store(tmp_path):
    """임시 DB로 초기화된 BacktestStore."""
    db_path = tmp_path / "backtest.db"
    return BacktestStore(str(db_path))


@pytest.fixture
def sample_result():
    """간단한 백테스트 결과."""
    config = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260406",
        end_date="20260410",
        cost_model=CostModel(slippage_model="none"),
        benchmark="KOSPI",
    )
    snapshots = [
        PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260407", cash=95_000_000, positions=[],
            total_value=101_500_000, daily_return=1.5,
            cumulative_return=1.5, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260408", cash=93_000_000, positions=[],
            total_value=103_000_000, daily_return=1.48,
            cumulative_return=3.0, drawdown=0.0,
        ),
    ]
    metrics = {
        "total_return": 3.0,
        "sharpe_ratio": 1.5,
        "max_drawdown": -2.0,
    }
    return BacktestResult(
        snapshots=snapshots,
        trades=[],
        metrics=metrics,
        config=config,
    )


class TestBacktestStore:
    def test_save_run_returns_run_id(self, store, sample_result):
        """저장 시 run_id를 반환한다."""
        run_id = store.save_run(sample_result, name="테스트 실행")
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_get_run(self, store, sample_result):
        """저장된 실행을 조회한다."""
        run_id = store.save_run(sample_result, name="테스트 실행")
        run = store.get_run(run_id)
        assert run is not None
        assert run["name"] == "테스트 실행"
        assert run["start_date"] == "20260406"
        assert run["end_date"] == "20260410"

    def test_get_run_metrics(self, store, sample_result):
        """저장된 지표를 조회한다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        metrics = json.loads(run["metrics"])
        assert metrics["total_return"] == 3.0
        assert metrics["sharpe_ratio"] == 1.5

    def test_get_run_not_found(self, store):
        """존재하지 않는 run_id는 None."""
        assert store.get_run("nonexistent") is None

    def test_list_runs(self, store, sample_result):
        """실행 목록을 조회한다."""
        store.save_run(sample_result, name="실행1")
        store.save_run(sample_result, name="실행2")
        runs = store.list_runs()
        assert len(runs) == 2

    def test_list_runs_empty(self, store):
        """실행 없으면 빈 리스트."""
        assert store.list_runs() == []

    def test_save_snapshots(self, store, sample_result):
        """스냅샷이 저장된다."""
        run_id = store.save_run(sample_result, name="스냅샷 테스트")
        snapshots = store.get_snapshots(run_id)
        assert len(snapshots) == 3
        assert snapshots[0]["date"] == "20260406"
        assert snapshots[-1]["total_value"] == 103_000_000

    def test_delete_run(self, store, sample_result):
        """실행을 삭제한다."""
        run_id = store.save_run(sample_result)
        store.delete_run(run_id)
        assert store.get_run(run_id) is None
        assert store.get_snapshots(run_id) == []

    def test_get_initial_and_final_value(self, store, sample_result):
        """초기/최종 자산이 올바르게 저장된다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        assert run["initial_capital"] == 100_000_000
        assert run["final_value"] == 103_000_000

    def test_save_strategies_and_allocations(self, store, sample_result):
        """전략 목록과 배분이 저장/조회된다."""
        strategies = ["momentum", "value"]
        allocations = {"momentum": 0.6, "value": 0.4}
        run_id = store.save_run(
            sample_result, name="전략 테스트",
            strategies=strategies, allocations=allocations,
        )
        run = store.get_run(run_id)
        assert json.loads(run["strategies"]) == ["momentum", "value"]
        assert json.loads(run["allocations"]) == {"momentum": 0.6, "value": 0.4}

    def test_default_strategies_and_allocations(self, store, sample_result):
        """strategies/allocations 미지정 시 빈 기본값이 저장된다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        assert json.loads(run["strategies"]) == []
        assert json.loads(run["allocations"]) == {}


def _make_trades():
    """테스트용 체결 이력 (2건 라운드트립)."""
    stock = Stock(code="005930", name="삼성전자", market="KOSPI")
    buy = Order(stock=stock, side="BUY", order_type="MARKET",
                quantity=100, price=None, strategy_id="momentum")
    sell = Order(stock=stock, side="SELL", order_type="MARKET",
                 quantity=100, price=None, strategy_id="momentum")
    return [
        OrderResult(
            order_id="b1", order=buy, status="filled",
            filled_quantity=100, filled_price=72000,
            commission=108, tax=0, trade_date="20260406",
        ),
        OrderResult(
            order_id="s1", order=sell, status="filled",
            filled_quantity=100, filled_price=74000,
            commission=111, tax=1332, trade_date="20260408",
        ),
        OrderResult(
            order_id="b2", order=buy, status="filled",
            filled_quantity=100, filled_price=73000,
            commission=110, tax=0, trade_date="20260409",
        ),
        OrderResult(
            order_id="s2", order=sell, status="filled",
            filled_quantity=100, filled_price=71000,
            commission=107, tax=1278, trade_date="20260410",
        ),
    ]


class TestTradeStorage:
    """거래 기록 저장/조회 테스트."""

    def test_trades_saved(self, store, sample_result):
        """체결 기록이 DB에 저장된다."""
        sample_result.trades = _make_trades()
        run_id = store.save_run(sample_result)
        trades = store.get_trades(run_id)
        assert len(trades) == 4
        assert trades[0]["code"] == "005930"
        assert trades[0]["side"] == "BUY"

    def test_round_trips_saved(self, store, sample_result):
        """라운드트립이 DB에 저장된다."""
        sample_result.trades = _make_trades()
        run_id = store.save_run(sample_result)
        rts = store.get_round_trips(run_id)
        assert len(rts) == 2

    def test_round_trip_fields(self, store, sample_result):
        """라운드트립에 상세 필드가 있다."""
        sample_result.trades = _make_trades()
        run_id = store.save_run(sample_result)
        rts = store.get_round_trips(run_id)
        rt = rts[0]
        assert rt["code"] == "005930"
        assert rt["buy_date"] == "20260406"
        assert rt["sell_date"] == "20260408"
        assert rt["buy_price"] == 72000
        assert rt["sell_price"] == 74000
        assert rt["holding_days"] == 2
        assert rt["pnl"] > 0
        assert rt["return_pct"] > 0

    def test_losing_round_trip(self, store, sample_result):
        """패배 라운드트립의 PnL이 음수다."""
        sample_result.trades = _make_trades()
        run_id = store.save_run(sample_result)
        rts = store.get_round_trips(run_id)
        loser = rts[1]  # 73000 -> 71000
        assert loser["pnl"] < 0
        assert loser["return_pct"] < 0

    def test_empty_trades(self, store, sample_result):
        """거래 없으면 빈 리스트."""
        run_id = store.save_run(sample_result)
        assert store.get_trades(run_id) == []
        assert store.get_round_trips(run_id) == []

    def test_delete_cleans_trades(self, store, sample_result):
        """삭제 시 거래/라운드트립도 삭제된다."""
        sample_result.trades = _make_trades()
        run_id = store.save_run(sample_result)
        store.delete_run(run_id)
        assert store.get_trades(run_id) == []
        assert store.get_round_trips(run_id) == []


def _make_result_with_positions():
    """포지션이 포함된 백테스트 결과."""
    from alphapulse.trading.core.models import Position

    stock1 = Stock(code="005930", name="삼성전자", market="KOSPI")
    stock2 = Stock(code="000660", name="SK하이닉스", market="KOSPI")
    config = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260406",
        end_date="20260408",
        cost_model=CostModel(slippage_model="none"),
    )
    snapshots = [
        PortfolioSnapshot(
            date="20260406", cash=90_000_000,
            positions=[
                Position(stock=stock1, quantity=100, avg_price=72000,
                         current_price=73000, unrealized_pnl=100000,
                         weight=0.073, strategy_id="momentum"),
            ],
            total_value=100_300_000, daily_return=0.3,
            cumulative_return=0.3, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260407", cash=80_000_000,
            positions=[
                Position(stock=stock1, quantity=100, avg_price=72000,
                         current_price=74000, unrealized_pnl=200000,
                         weight=0.074, strategy_id="momentum"),
                Position(stock=stock2, quantity=50, avg_price=120000,
                         current_price=121000, unrealized_pnl=50000,
                         weight=0.060, strategy_id="value"),
            ],
            total_value=101_250_000, daily_return=0.95,
            cumulative_return=1.25, drawdown=0.0,
        ),
    ]
    return BacktestResult(
        snapshots=snapshots, trades=[], metrics={"total_return": 1.25},
        config=config,
    )


class TestPositionStorage:
    """종목별 보유 포지션 저장/조회 테스트."""

    def test_positions_saved(self, store):
        """일별 포지션이 DB에 저장된다."""
        result = _make_result_with_positions()
        run_id = store.save_run(result)
        positions = store.get_positions(run_id)
        assert len(positions) == 3

    def test_positions_by_date(self, store):
        """특정 날짜의 포지션만 조회한다."""
        result = _make_result_with_positions()
        run_id = store.save_run(result)
        pos = store.get_positions(run_id, date="20260407")
        assert len(pos) == 2
        codes = {p["code"] for p in pos}
        assert codes == {"005930", "000660"}

    def test_positions_by_code(self, store):
        """특정 종목의 전 기간 포지션을 조회한다."""
        result = _make_result_with_positions()
        run_id = store.save_run(result)
        pos = store.get_positions(run_id, code="005930")
        assert len(pos) == 2

    def test_position_fields(self, store):
        """포지션에 필수 필드가 있다."""
        result = _make_result_with_positions()
        run_id = store.save_run(result)
        pos = store.get_positions(run_id, date="20260406")
        p = pos[0]
        assert p["code"] == "005930"
        assert p["quantity"] == 100
        assert p["avg_price"] == 72000
        assert p["current_price"] == 73000
        assert p["unrealized_pnl"] == 100000
        assert p["strategy_id"] == "momentum"

    def test_delete_cleans_positions(self, store):
        """삭제 시 포지션도 삭제된다."""
        result = _make_result_with_positions()
        run_id = store.save_run(result)
        store.delete_run(run_id)
        assert store.get_positions(run_id) == []

    def test_no_positions(self, store, sample_result):
        """포지션 없는 스냅샷은 빈 리스트."""
        run_id = store.save_run(sample_result)
        assert store.get_positions(run_id) == []
