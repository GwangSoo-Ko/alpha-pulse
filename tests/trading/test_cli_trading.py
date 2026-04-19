"""Trading CLI 명령 테스트.

Click CliRunner로 CLI 명령을 테스트한다.
실제 서브시스템은 mock으로 처리한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from alphapulse.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestTradingRun:
    """ap trading run 명령 테스트."""

    @patch("alphapulse.trading.orchestrator.engine.TradingEngine")
    def test_run_paper_mode(self, mock_engine_cls, runner):
        """paper 모드로 1회 실행한다."""
        mock_engine = MagicMock()
        mock_engine.run_daily = AsyncMock(return_value={"status": "ok"})
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(cli, ["trading", "run", "--mode", "paper"])
        assert "paper" in result.output.lower() or result.exit_code == 0

    @patch("alphapulse.trading.orchestrator.engine.TradingEngine")
    def test_run_default_mode(self, mock_engine_cls, runner):
        """기본 모드(paper)로 실행 가능하다."""
        mock_engine = MagicMock()
        mock_engine.run_daily = AsyncMock(return_value={"status": "ok"})
        mock_engine_cls.return_value = mock_engine

        # mode에 기본값 "paper"가 있으므로 통과
        result = runner.invoke(cli, ["trading", "run"])
        assert "paper" in result.output.lower() or result.exit_code == 0


class TestTradingStatus:
    """ap trading status 명령 테스트."""

    def test_status_command(self, runner):
        """시스템 상태를 출력한다."""
        result = runner.invoke(cli, ["trading", "status"])
        assert result.exit_code == 0


class TestTradingReconcile:
    """ap trading reconcile 명령 테스트."""

    def test_reconcile_no_kis_key(self, runner):
        """KIS_APP_KEY가 없으면 안내 메시지를 출력한다."""
        result = runner.invoke(cli, ["trading", "reconcile"])
        assert result.exit_code == 0
        assert "KIS_APP_KEY" in result.output


def _seed_run(store, name="test", total_return=0.0, sharpe=0.0) -> str:
    """테스트용 백테스트 결과를 DB에 저장한다."""
    import json
    import sqlite3
    import time
    import uuid

    run_id = str(uuid.uuid4())
    metrics = json.dumps({
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": -3.0,
    })
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT INTO runs (run_id, name, strategies, allocations,
                start_date, end_date, initial_capital, final_value,
                benchmark, params, metrics, created_at)
            VALUES (?, ?, '["momentum"]', '{}', '20240101', '20241231',
                    100000000, 105000000, 'KOSPI', '{}', ?, ?)""",
            (run_id, name, metrics, time.time()),
        )
    return run_id


class TestBacktestGroup:
    """ap trading backtest 서브커맨드 테스트."""

    def test_backtest_no_subcommand_shows_help(self, runner):
        """서브커맨드 없이 실행하면 사용법을 출력한다."""
        result = runner.invoke(cli, ["trading", "backtest"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "list" in result.output

    def test_backtest_list_empty(self, runner, tmp_path):
        """결과가 없으면 안내 메시지를 출력한다."""
        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(cli, ["trading", "backtest", "list"])
        assert result.exit_code == 0
        assert "없습니다" in result.output

    def test_backtest_list_shows_runs(self, runner, tmp_path):
        """저장된 결과 목록을 표시한다."""
        from alphapulse.trading.backtest.store import BacktestStore

        store = BacktestStore(db_path=tmp_path / "backtest.db")
        _seed_run(store, name="momentum_test", total_return=5.5)

        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(cli, ["trading", "backtest", "list"])
        assert result.exit_code == 0
        assert "momentum_test" in result.output

    def test_backtest_report_not_found(self, runner, tmp_path):
        """존재하지 않는 run_id면 안내 메시지."""
        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli, ["trading", "backtest", "report", "nonexist"]
            )
        assert result.exit_code == 0
        assert "찾을 수 없습니다" in result.output

    def test_backtest_report_by_prefix(self, runner, tmp_path):
        """run_id 접두사로 리포트를 조회한다."""
        from alphapulse.trading.backtest.store import BacktestStore

        store = BacktestStore(db_path=tmp_path / "backtest.db")
        run_id = _seed_run(store, name="value_bt", total_return=3.2)
        prefix = run_id[:8]

        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli, ["trading", "backtest", "report", prefix]
            )
        assert result.exit_code == 0
        assert "value_bt" in result.output
        assert "3.2" in result.output

    def test_backtest_compare(self, runner, tmp_path):
        """두 결과를 비교한다."""
        from alphapulse.trading.backtest.store import BacktestStore

        store = BacktestStore(db_path=tmp_path / "backtest.db")
        id1 = _seed_run(store, name="A", total_return=5.0, sharpe=1.2)
        id2 = _seed_run(store, name="B", total_return=-2.0, sharpe=-0.3)

        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli,
                ["trading", "backtest", "compare", id1[:8], id2[:8]],
            )
        assert result.exit_code == 0
        assert "비교" in result.output
        assert "5.00" in result.output
        assert "-2.00" in result.output

    def test_backtest_compare_not_found(self, runner, tmp_path):
        """존재하지 않는 run_id면 안내 메시지."""
        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli, ["trading", "backtest", "compare", "aaa", "bbb"]
            )
        assert result.exit_code == 0
        assert "찾을 수 없습니다" in result.output

    def test_backtest_trades_not_found(self, runner, tmp_path):
        """존재하지 않는 run_id면 안내 메시지."""
        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli, ["trading", "backtest", "trades", "nonexist"]
            )
        assert result.exit_code == 0
        assert "찾을 수 없습니다" in result.output

    def test_backtest_trades_empty(self, runner, tmp_path):
        """거래 없으면 안내 메시지."""
        from alphapulse.trading.backtest.store import BacktestStore

        store = BacktestStore(db_path=tmp_path / "backtest.db")
        run_id = _seed_run(store, name="no_trades")

        with patch("alphapulse.core.config.Config") as mock_cfg:
            mock_cfg.return_value.DATA_DIR = tmp_path
            result = runner.invoke(
                cli, ["trading", "backtest", "trades", run_id[:8]]
            )
        assert result.exit_code == 0
        assert "없습니다" in result.output
