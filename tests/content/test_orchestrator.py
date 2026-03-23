import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from alphapulse.content.agents.orchestrator import AnalysisOrchestrator


@pytest.fixture
def orchestrator():
    return AnalysisOrchestrator(api_key="test")


@pytest.mark.asyncio
async def test_analyze_full_pipeline(orchestrator):
    with patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock,
                      return_value=["us_stock", "bond"]) as mock_classify, \
         patch("alphapulse.content.agents.orchestrator.get_specialists_for_topics") as mock_get_specs, \
         patch.object(orchestrator.senior, "synthesize", new_callable=AsyncMock,
                      return_value="## 종합 보고서\n최종 분석") as mock_synth:

        mock_spec1 = MagicMock()
        mock_spec1.topic = "us_stock"
        mock_spec1.analyze = AsyncMock(return_value="미국 주식 분석")
        mock_spec2 = MagicMock()
        mock_spec2.topic = "bond"
        mock_spec2.analyze = AsyncMock(return_value="채권 분석")
        mock_get_specs.return_value = [mock_spec1, mock_spec2]

        result = await orchestrator.analyze("미국 금리", "연준이 금리를...")

        mock_classify.assert_called_once()
        assert mock_spec1.analyze.called
        assert mock_spec2.analyze.called
        mock_synth.assert_called_once()
        assert "종합 보고서" in result


@pytest.mark.asyncio
async def test_analyze_no_specialists(orchestrator):
    """When classifier returns topics but no valid specialists found"""
    with patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock,
                      return_value=["unknown_topic"]) as mock_classify, \
         patch("alphapulse.content.agents.orchestrator.get_specialists_for_topics",
               return_value=[]), \
         patch.object(orchestrator.senior, "synthesize", new_callable=AsyncMock,
                      return_value="## 종합 보고서\n분석") as mock_synth:

        result = await orchestrator.analyze("제목", "내용")
        # Should still call senior with empty specialist results
        mock_synth.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_specialist_partial_failure(orchestrator):
    """One specialist fails, others succeed"""
    with patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock,
                      return_value=["us_stock", "forex"]), \
         patch("alphapulse.content.agents.orchestrator.get_specialists_for_topics") as mock_get_specs, \
         patch.object(orchestrator.senior, "synthesize", new_callable=AsyncMock,
                      return_value="## 종합\n결과") as mock_synth:

        mock_spec1 = MagicMock()
        mock_spec1.topic = "us_stock"
        mock_spec1.analyze = AsyncMock(return_value="미국 분석 성공")
        mock_spec2 = MagicMock()
        mock_spec2.topic = "forex"
        mock_spec2.analyze = AsyncMock(return_value="(분석 실패)")  # fallback from specialist
        mock_get_specs.return_value = [mock_spec1, mock_spec2]

        result = await orchestrator.analyze("제목", "내용")
        # Both results should be passed to senior
        call_args = mock_synth.call_args
        specialist_results = call_args[0][2]  # 3rd positional arg
        assert "us_stock" in specialist_results
        assert "forex" in specialist_results


@pytest.mark.asyncio
async def test_analyze_total_failure_fallback(orchestrator):
    """When classifier itself fails catastrophically"""
    with patch.object(orchestrator.classifier, "classify", new_callable=AsyncMock,
                      side_effect=Exception("total failure")):

        result = await orchestrator.analyze("제목", "본문 내용")
        assert isinstance(result, str)
        assert len(result) > 0  # Should return some fallback
