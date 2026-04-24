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


@pytest.mark.asyncio
async def test_run_async_emits_notification_on_save_success(
    tmp_path, monkeypatch,
):
    """Store.save 성공 시 notification_store.add 가 호출된다."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("FEEDBACK_ENABLED", "false")
    notif_store = MagicMock()
    orch = BriefingOrchestrator(
        reports_dir=str(tmp_path),
        notification_store=notif_store,
    )
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 75.0, "signal": "bullish",
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
            store_cls.return_value.save = MagicMock()
            await orch.run_async(date="20260421", send_telegram=False)

    assert notif_store.add.call_count == 1
    kwargs = notif_store.add.call_args.kwargs
    assert kwargs["kind"] == "briefing"
    assert kwargs["level"] == "info"
    assert "브리핑" in kwargs["title"]
    assert "20260421" in kwargs["link"]


@pytest.mark.asyncio
async def test_run_async_no_notification_when_save_fails(
    tmp_path, monkeypatch,
):
    """Store.save 실패 시 notification_store.add 가 호출되지 않는다."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("FEEDBACK_ENABLED", "false")
    notif_store = MagicMock()
    orch = BriefingOrchestrator(
        reports_dir=str(tmp_path),
        notification_store=notif_store,
    )
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 0.0, "signal": "neutral",
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
            await orch.run_async(date="20260421", send_telegram=False)

    notif_store.add.assert_not_called()


@pytest.mark.asyncio
async def test_run_async_resilient_to_notification_error(
    tmp_path, monkeypatch,
):
    """notification_store.add 가 예외 내도 run_async 는 정상 완료된다."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("FEEDBACK_ENABLED", "false")
    notif_store = MagicMock()
    notif_store.add.side_effect = RuntimeError("notif broken")

    orch = BriefingOrchestrator(
        reports_dir=str(tmp_path),
        notification_store=notif_store,
    )
    orch.config.BRIEFINGS_DB = tmp_path / "briefings.db"

    fake_pulse = {
        "date": "20260421", "score": 0.0, "signal": "neutral",
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
            store_cls.return_value.save = MagicMock()
            result = await orch.run_async(
                date="20260421", send_telegram=False,
            )

    assert result is not None
    assert result["pulse_result"]["date"] == "20260421"
