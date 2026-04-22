"""BriefingOrchestrator — run_async 완료 후 BriefingStore.save 호출 검증."""
from unittest.mock import AsyncMock, patch

import pytest

from alphapulse.briefing.orchestrator import BriefingOrchestrator


@pytest.mark.asyncio
async def test_run_async_saves_to_briefing_store(tmp_path, monkeypatch):
    """run_async 정상 완료 시 BriefingStore.save 가 호출되어야 한다."""
    monkeypatch.setenv("FEEDBACK_ENABLED", "false")

    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 42.0, "signal": "moderately_bullish",
        "indicator_scores": {}, "details": {},
    }

    with patch.object(orch, "run_quantitative", return_value=fake_pulse), \
         patch("alphapulse.briefing.orchestrator.TelegramNotifier") as notifier, \
         patch("alphapulse.agents.commentary.MarketCommentaryAgent") as cm_cls, \
         patch("alphapulse.agents.synthesis.SeniorSynthesisAgent") as synth_cls:
        notifier.return_value._send_message = AsyncMock()
        cm_cls.return_value.generate = AsyncMock(return_value="comm-text")
        synth_cls.return_value.synthesize = AsyncMock(return_value="synth-text")

        with patch(
            "alphapulse.briefing.orchestrator.BriefingStore",
        ) as store_cls:
            store_instance = store_cls.return_value
            result = await orch.run_async(date="20260421", send_telegram=False)

    # Store 생성 + save 호출 확인
    assert store_cls.called
    assert store_instance.save.called
    save_args = store_instance.save.call_args
    assert save_args.args[0] == "20260421"   # date
    saved_payload = save_args.args[1]
    assert saved_payload["pulse_result"] == fake_pulse
    assert "commentary" in saved_payload
    assert "synthesis" in saved_payload
    # run_async 자체는 정상 완료 (기존 반환값 유지)
    assert result["pulse_result"] == fake_pulse


@pytest.mark.asyncio
async def test_run_async_tolerates_save_failure(tmp_path, monkeypatch):
    """Store.save 가 예외 내도 run_async 는 완료돼야 한다 (기존 흐름 보호)."""
    monkeypatch.setenv("FEEDBACK_ENABLED", "false")

    orch = BriefingOrchestrator(reports_dir=str(tmp_path))
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 42.0, "signal": "neutral",
        "indicator_scores": {}, "details": {},
    }
    with patch.object(orch, "run_quantitative", return_value=fake_pulse), \
         patch("alphapulse.briefing.orchestrator.TelegramNotifier") as notifier, \
         patch("alphapulse.agents.commentary.MarketCommentaryAgent") as cm_cls, \
         patch("alphapulse.agents.synthesis.SeniorSynthesisAgent") as synth_cls:
        notifier.return_value._send_message = AsyncMock()
        cm_cls.return_value.generate = AsyncMock(return_value="c")
        synth_cls.return_value.synthesize = AsyncMock(return_value="s")
        with patch(
            "alphapulse.briefing.orchestrator.BriefingStore",
        ) as store_cls:
            store_cls.return_value.save.side_effect = RuntimeError("disk full")
            # 예외 bubble 되지 않아야 함
            result = await orch.run_async(date="20260421", send_telegram=False)
    assert result is not None
    assert result["pulse_result"]["date"] == "20260421"
