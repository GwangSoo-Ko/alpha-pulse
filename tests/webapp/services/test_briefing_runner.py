"""BriefingRunner — Job 어댑터 테스트."""
import asyncio
from unittest.mock import AsyncMock, patch


def test_runs_orchestrator_and_returns_saved_date():
    """run_briefing_async 가 orchestrator 호출 + pulse_result.date 반환."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.return_value = {
        "pulse_result": {"date": "20260421", "score": 42.0, "signal": "neutral"},
        "synthesis": "요약",
    }

    progress_calls: list[tuple[int, int, str]] = []
    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        result = asyncio.run(
            run_briefing_async(date="20260421", progress_callback=on_progress),
        )

    mock_orch.run_async.assert_awaited_once_with(date="20260421", send_telegram=False)
    assert result == "20260421"
    assert progress_calls[0] == (0, 1, "브리핑 실행 중 (3~10분 소요, 브라우저 닫아도 계속)")
    assert progress_calls[-1][0] == 1 and progress_calls[-1][1] == 1
    assert "20260421" in progress_calls[-1][2]


def test_passes_none_date_to_orchestrator():
    """date=None 이면 orchestrator 가 오늘 날짜로 처리."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.return_value = {
        "pulse_result": {"date": "20260422", "score": 10.0, "signal": "neutral"},
    }
    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        result = asyncio.run(
            run_briefing_async(date=None, progress_callback=lambda *_: None),
        )
    mock_orch.run_async.assert_awaited_once_with(date=None, send_telegram=False)
    assert result == "20260422"


def test_propagates_exception():
    """orchestrator 예외는 그대로 raise (JobRunner 가 failed 마킹)."""
    from alphapulse.webapp.services.briefing_runner import run_briefing_async

    mock_orch = AsyncMock()
    mock_orch.run_async.side_effect = RuntimeError("gemini unavailable")

    import pytest
    with patch(
        "alphapulse.webapp.services.briefing_runner.BriefingOrchestrator",
        return_value=mock_orch,
    ):
        with pytest.raises(RuntimeError, match="gemini unavailable"):
            asyncio.run(
                run_briefing_async(date="20260421", progress_callback=lambda *_: None),
            )
