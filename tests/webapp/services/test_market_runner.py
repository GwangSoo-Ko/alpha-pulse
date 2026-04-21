"""run_market_pulse_sync 테스트 — SignalEngine 모킹."""
from unittest.mock import MagicMock, patch


def test_runs_engine_and_returns_date():
    """SignalEngine.run 을 호출하고 저장된 date 를 반환한다."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260420",
        "score": 42.0,
        "signal": "moderately_bullish",
        "indicator_scores": {"investor_flow": 50.0},
        "details": {},
    }

    progress_calls: list[tuple[int, int, str]] = []

    def on_progress(current: int, total: int, text: str) -> None:
        progress_calls.append((current, total, text))

    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        result_date = run_market_pulse_sync(
            date="20260420",
            progress_callback=on_progress,
        )

    assert result_date == "20260420"
    mock_engine.run.assert_called_once_with(date="20260420")
    assert progress_calls[0] == (0, 1, "시황 분석 실행 중")
    assert progress_calls[-1] == (1, 1, "완료")


def test_passes_none_date_to_engine():
    """date=None 이면 SignalEngine 이 직전 거래일을 자동 선택한다."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.return_value = {
        "date": "20260420", "score": 10.0, "signal": "neutral",
        "indicator_scores": {}, "details": {},
    }
    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        run_market_pulse_sync(date=None, progress_callback=lambda *_: None)

    mock_engine.run.assert_called_once_with(date=None)


def test_propagates_engine_exception():
    """SignalEngine.run 예외 그대로 raise (JobRunner 가 failed 로 마킹)."""
    from alphapulse.webapp.services.market_runner import run_market_pulse_sync

    mock_engine = MagicMock()
    mock_engine.run.side_effect = RuntimeError("fetch failed")

    import pytest
    with patch(
        "alphapulse.webapp.services.market_runner.SignalEngine",
        return_value=mock_engine,
    ):
        with pytest.raises(RuntimeError, match="fetch failed"):
            run_market_pulse_sync(date="20260420", progress_callback=lambda *_: None)
