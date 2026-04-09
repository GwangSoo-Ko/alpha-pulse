"""BacktestStore 테스트 — backtest.db 결과 저장."""

import json

import pytest

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import PortfolioSnapshot


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
