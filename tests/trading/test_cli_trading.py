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
