"""BacktestReport 테스트 — 터미널 + HTML 출력."""

import os

import pytest

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
from alphapulse.trading.backtest.report import BacktestReport
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import PortfolioSnapshot


@pytest.fixture
def sample_result():
    """간단한 백테스트 결과."""
    snapshots = [
        PortfolioSnapshot(
            date="20260406", cash=90_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260407", cash=89_000_000, positions=[],
            total_value=101_000_000, daily_return=1.0,
            cumulative_return=1.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260408", cash=88_000_000, positions=[],
            total_value=102_500_000, daily_return=1.49,
            cumulative_return=2.5, drawdown=0.0,
        ),
    ]
    config = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260406",
        end_date="20260408",
        cost_model=CostModel(slippage_model="none"),
        benchmark="KOSPI",
    )
    metrics = {
        "total_return": 2.5,
        "cagr": 15.3,
        "volatility": 12.5,
        "max_drawdown": -3.2,
        "max_drawdown_duration": 3,
        "sharpe_ratio": 1.22,
        "sortino_ratio": 1.85,
        "calmar_ratio": 4.78,
        "total_trades": 10,
        "win_rate": 65.0,
        "profit_factor": 1.95,
        "avg_win": 150000,
        "avg_loss": 80000,
        "turnover": 3.2,
        "benchmark_return": 1.8,
        "excess_return": 0.7,
        "beta": 0.85,
        "alpha": 5.2,
        "information_ratio": 0.92,
        "tracking_error": 8.5,
        "downside_deviation": 8.0,
    }
    return BacktestResult(
        snapshots=snapshots,
        trades=[],
        metrics=metrics,
        config=config,
    )


@pytest.fixture
def reporter():
    return BacktestReport()


class TestTerminalReport:
    def test_to_terminal_returns_string(self, reporter, sample_result):
        """터미널 리포트가 문자열을 반환한다."""
        output = reporter.to_terminal(sample_result)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_terminal_contains_key_metrics(self, reporter, sample_result):
        """터미널 리포트에 핵심 지표가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "2.5" in output  # total_return
        assert "1.22" in output  # sharpe
        assert "-3.2" in output  # max_drawdown
        assert "65.0" in output  # win_rate

    def test_terminal_contains_period_info(self, reporter, sample_result):
        """기간 정보가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "20260406" in output
        assert "20260408" in output

    def test_terminal_contains_benchmark_info(self, reporter, sample_result):
        """벤치마크 비교 정보가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "0.85" in output  # beta
        assert "KOSPI" in output


class TestHTMLReport:
    def test_to_html_returns_string(self, reporter, sample_result):
        """HTML 리포트가 문자열을 반환한다."""
        html = reporter.to_html(sample_result)
        assert isinstance(html, str)
        assert "<html" in html

    def test_html_contains_metrics(self, reporter, sample_result):
        """HTML에 지표가 포함된다."""
        html = reporter.to_html(sample_result)
        assert "2.5" in html
        assert "1.22" in html

    def test_save_html(self, reporter, sample_result, tmp_path):
        """HTML 파일을 저장한다."""
        output_path = tmp_path / "report.html"
        reporter.save_html(sample_result, str(output_path))
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<html" in content
        assert "2.5" in content

    def test_html_contains_equity_data(self, reporter, sample_result):
        """HTML에 자산 곡선 데이터가 포함된다."""
        html = reporter.to_html(sample_result)
        assert "100000000" in html or "100,000,000" in html
