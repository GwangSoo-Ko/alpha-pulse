from unittest.mock import MagicMock, patch

import pytest

from alphapulse.briefing.orchestrator import BriefingOrchestrator


@pytest.fixture
def mock_pulse_result():
    return {
        "date": "20260323",
        "period": "daily",
        "score": -63,
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


def test_orchestrator_init():
    orch = BriefingOrchestrator()
    assert orch is not None


@patch("alphapulse.briefing.orchestrator.SignalEngine")
def test_run_quantitative(mock_engine_cls, mock_pulse_result):
    mock_engine = MagicMock()
    mock_engine.run.return_value = mock_pulse_result
    mock_engine_cls.return_value = mock_engine
    orch = BriefingOrchestrator()
    result = orch.run_quantitative()
    assert result["score"] == -63
    mock_engine.run.assert_called_once()


def test_collect_recent_content(tmp_path):
    report = tmp_path / "20260323_150000_경제_test.md"
    report.write_text("---\ntitle: Test\n---\n## 핵심 요약\nTest summary content")
    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    summaries = orch.collect_recent_content(hours=24)
    assert len(summaries) >= 1


def test_collect_recent_content_empty(tmp_path):
    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    summaries = orch.collect_recent_content(hours=24)
    assert summaries == []
