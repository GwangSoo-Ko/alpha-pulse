import pytest
from unittest.mock import patch
from alphapulse.agents.synthesis import SeniorSynthesisAgent


@pytest.fixture
def sample_pulse():
    return {
        "date": "20260323", "score": -63, "signal": "강한 매도",
        "indicator_scores": {"investor_flow": -100, "fund_flow": 50},
        "details": {},
    }


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_with_content(mock_llm, sample_pulse):
    mock_llm.return_value = "외국인 매도와 관세 이슈가 결합되어 방어적 전략이 필요합니다."
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(
        sample_pulse,
        content_summaries=["[메르] 트럼프 관세 3차 확대"],
        commentary="외국인 대규모 매도 지속",
    )
    assert "방어적" in result


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_without_content(mock_llm, sample_pulse):
    mock_llm.return_value = "정량 데이터만으로 판단: 수급 극도 악화."
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(sample_pulse, content_summaries=[], commentary="수급 악화")
    assert len(result) > 0


@pytest.mark.asyncio
@patch("alphapulse.agents.synthesis.SeniorSynthesisAgent._call_llm")
async def test_synthesize_fallback(mock_llm, sample_pulse):
    mock_llm.side_effect = Exception("API Error")
    agent = SeniorSynthesisAgent()
    result = await agent.synthesize(sample_pulse, [], None)
    assert result is not None
    assert "Market Pulse" in result


def test_build_prompt(sample_pulse):
    agent = SeniorSynthesisAgent()
    prompt = agent._build_prompt(sample_pulse, ["[메르] 관세 분석"], "외국인 매도")
    assert "-63" in prompt
    assert "강한 매도" in prompt
    assert "관세 분석" in prompt


def test_build_prompt_with_feedback(sample_pulse):
    agent = SeniorSynthesisAgent()
    feedback = "=== 피드백 === V-KOSPI 신뢰도 낮음"
    prompt = agent._build_prompt(sample_pulse, [], None, feedback_context=feedback)
    assert "V-KOSPI 신뢰도" in prompt


def test_build_prompt_no_content(sample_pulse):
    agent = SeniorSynthesisAgent()
    prompt = agent._build_prompt(sample_pulse, [], None)
    assert "정량 데이터만으로 판단" in prompt or "정성 분석 없음" in prompt
