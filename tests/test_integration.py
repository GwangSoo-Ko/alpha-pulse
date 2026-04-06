"""AlphaPulse 통합 테스트 — 전체 파이프라인 E2E."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from alphapulse.cli import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_cli_market_pulse_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["market", "pulse", "--help"])
    assert result.exit_code == 0
    assert "--date" in result.output


def test_cli_content_monitor_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "monitor", "--help"])
    assert result.exit_code == 0
    assert "--daemon" in result.output


def test_cli_briefing_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["briefing", "--help"])
    assert result.exit_code == 0


def test_cli_commentary_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["commentary", "--help"])
    assert result.exit_code == 0


def test_cli_cache_clear():
    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear"])
    assert result.exit_code == 0


@patch("alphapulse.briefing.orchestrator.SignalEngine")
def test_briefing_orchestrator_e2e(mock_engine_cls, tmp_path):
    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260323", "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100, "global_market": -47,
            "sector_momentum": -100, "program_trade": -100,
            "exchange_rate": -22, "vkospi": -10,
            "adr_volume": -93, "spot_futures_align": -100,
            "interest_rate_diff": -19, "fund_flow": 50,
        },
        "details": {},
    }
    mock_engine_cls.return_value = mock_engine

    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    result = orch.run(send_telegram=False)
    assert result["pulse_result"]["score"] == -63
    assert isinstance(result["content_summaries"], list)


def test_formatter_quantitative_e2e():
    from alphapulse.briefing.formatter import BriefingFormatter
    formatter = BriefingFormatter()
    html = formatter.format_quantitative({
        "date": "20260323", "score": -63, "signal": "강한 매도",
        "indicator_scores": {"investor_flow": -100, "global_market": -47},
        "details": {},
    })
    assert "📊" in html
    assert "정량 리포트" in html


def test_formatter_synthesis_e2e():
    from alphapulse.briefing.formatter import BriefingFormatter
    formatter = BriefingFormatter()
    html = formatter.format_synthesis(
        pulse_result={"score": -63, "signal": "강한 매도", "date": "20260323",
                      "indicator_scores": {}, "details": {}},
        content_summaries=["[메르] 트럼프 관세"],
        commentary="방어적 전략 권고",
    )
    assert "📋" in html
    assert "종합 리포트" in html


def test_feedback_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["feedback", "--help"])
    assert result.exit_code == 0
    assert "evaluate" in result.output
    assert "report" in result.output
    assert "indicators" in result.output
    assert "history" in result.output


def test_feedback_store_integration(tmp_path):
    from alphapulse.core.storage.feedback import FeedbackStore
    store = FeedbackStore(tmp_path / "fb.db")
    store.save_signal("20260403", 35.0, "매수 우위", {"investor_flow": 68})
    store.update_result("20260403", 2650, 1.2, 870, 0.8, 1.2, 1)
    row = store.get("20260403")
    assert row["hit_1d"] == 1

    from alphapulse.feedback.evaluator import FeedbackEvaluator
    evaluator = FeedbackEvaluator(store=store)
    rates = evaluator.get_hit_rates(30)
    assert rates["hit_rate_1d"] == 1.0

    from alphapulse.feedback.summarizer import FeedbackSummarizer
    summarizer = FeedbackSummarizer(store=store, evaluator=evaluator)
    msg = summarizer.format_daily_result(row)
    assert "✅" in msg
