"""PostMarket 멀티에이전트 분석 테스트."""

import pytest
from unittest.mock import patch

from alphapulse.feedback.agents.orchestrator import PostMarketOrchestrator
from alphapulse.feedback.agents.blind_spot import BlindSpotAgent
from alphapulse.feedback.agents.prediction_review import PredictionReviewAgent
from alphapulse.feedback.agents.external_factor import ExternalFactorAgent
from alphapulse.feedback.agents.senior_feedback import SeniorFeedbackAgent


@pytest.fixture
def sample_signal():
    return {
        "date": "20260403",
        "score": 35.9,
        "signal": "매수 우위",
        "kospi_change_pct": 1.2,
        "indicator_scores": '{"investor_flow": 68, "vkospi": -10}',
    }


@pytest.fixture
def sample_news():
    return {
        "articles": [
            {"source": "한경", "title": "코스피 상승", "summary": "외국인 매수"}
        ]
    }


@pytest.mark.asyncio
@patch.object(BlindSpotAgent, "_call_llm", return_value="정책 이벤트 놓침")
async def test_blind_spot(mock_llm, sample_signal):
    agent = BlindSpotAgent()
    result = await agent.analyze(sample_signal, "뉴스", "정성분석")
    assert "정책" in result


@pytest.mark.asyncio
@patch.object(
    PredictionReviewAgent, "_call_llm", return_value="외국인 수급 적중, V-KOSPI 미적중"
)
async def test_prediction_review(mock_llm, sample_signal):
    agent = PredictionReviewAgent()
    result = await agent.analyze(sample_signal, "뉴스", "정성분석")
    assert "외국인" in result


@pytest.mark.asyncio
@patch.object(ExternalFactorAgent, "_call_llm", return_value="미국 고용지표 영향")
async def test_external_factor(mock_llm, sample_signal):
    agent = ExternalFactorAgent()
    result = await agent.analyze(sample_signal, "뉴스", "정성분석")
    assert "미국" in result


@pytest.mark.asyncio
@patch.object(
    SeniorFeedbackAgent,
    "_call_llm",
    return_value="종합: 외국인 매수 전환 적중. 정책 리스크 모니터링 필요.",
)
async def test_senior_feedback(mock_llm, sample_signal):
    agent = SeniorFeedbackAgent()
    result = await agent.synthesize(sample_signal, "사각지대", "예측복기", "외부변수")
    assert "종합" in result


@pytest.mark.asyncio
@patch.object(BlindSpotAgent, "_call_llm", return_value="사각지대 결과")
@patch.object(PredictionReviewAgent, "_call_llm", return_value="예측 복기 결과")
@patch.object(ExternalFactorAgent, "_call_llm", return_value="외부 변수 결과")
@patch.object(SeniorFeedbackAgent, "_call_llm", return_value="종합 피드백 결과")
async def test_orchestrator(
    mock_senior, mock_ext, mock_pred, mock_blind, sample_signal, sample_news
):
    orch = PostMarketOrchestrator()
    result = await orch.analyze(sample_signal, sample_news, ["정성분석 요약"])
    assert "blind_spots" in result
    assert "prediction_review" in result
    assert "external_factors" in result
    assert "senior_synthesis" in result
