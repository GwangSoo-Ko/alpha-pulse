import pytest
from unittest.mock import patch, AsyncMock
from alphapulse.agents.commentary import MarketCommentaryAgent


@pytest.fixture
def sample_pulse_result():
    return {
        "date": "20260323",
        "score": -63,
        "signal": "강한 매도 (Strong Bearish)",
        "indicator_scores": {
            "investor_flow": -100, "global_market": -47,
            "sector_momentum": -100, "program_trade": -100,
            "exchange_rate": -22, "vkospi": -10,
            "adr_volume": -93, "spot_futures_align": -100,
            "interest_rate_diff": -19, "fund_flow": 50,
        },
        "details": {
            "investor_flow": {"foreign_net": -36755, "institution_net": -38162},
        },
    }


def test_build_prompt(sample_pulse_result):
    agent = MarketCommentaryAgent()
    prompt = agent._build_prompt(sample_pulse_result, [])
    assert "-63" in prompt
    assert "강한 매도" in prompt


def test_build_prompt_with_content(sample_pulse_result):
    agent = MarketCommentaryAgent()
    content = ["[메르] 트럼프 관세 3차 확대 시나리오 분석"]
    prompt = agent._build_prompt(sample_pulse_result, content)
    assert "트럼프 관세" in prompt


@pytest.mark.asyncio
@patch("alphapulse.agents.commentary.MarketCommentaryAgent._call_llm")
async def test_generate(mock_llm, sample_pulse_result):
    mock_llm.return_value = "외국인 대규모 매도(-3.7조)와 프로그램 순매도가 동시 출현하며 수급이 극도로 악화되었습니다."
    agent = MarketCommentaryAgent()
    result = await agent.generate(sample_pulse_result, [])
    assert "매도" in result
    assert len(result) > 50


@pytest.mark.asyncio
@patch("alphapulse.agents.commentary.MarketCommentaryAgent._call_llm")
async def test_generate_fallback_on_failure(mock_llm, sample_pulse_result):
    mock_llm.side_effect = Exception("API Error")
    agent = MarketCommentaryAgent()
    result = await agent.generate(sample_pulse_result, [])
    assert result is not None
    assert len(result) > 0
