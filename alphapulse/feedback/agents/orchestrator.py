"""사후 분석 멀티에이전트 오케스트레이터."""

import asyncio
import logging

from alphapulse.feedback.agents.blind_spot import BlindSpotAgent
from alphapulse.feedback.agents.prediction_review import PredictionReviewAgent
from alphapulse.feedback.agents.external_factor import ExternalFactorAgent
from alphapulse.feedback.agents.senior_feedback import SeniorFeedbackAgent

logger = logging.getLogger(__name__)


class PostMarketOrchestrator:
    """사후 분석 파이프라인: 3 agents parallel -> senior synthesis."""

    def __init__(self):
        self.blind_spot = BlindSpotAgent()
        self.prediction_review = PredictionReviewAgent()
        self.external_factor = ExternalFactorAgent()
        self.senior = SeniorFeedbackAgent()

    async def analyze(
        self, signal: dict, news: dict, content_summaries: list[str]
    ) -> dict:
        """사후 분석 파이프라인 실행.

        Stage 1: 3개 전문 에이전트 병렬 실행
        Stage 2: 시니어 에이전트가 결과 종합
        """
        news_text = "\n".join(
            f"- [{a.get('source', '')}] {a.get('title', '')}: {a.get('summary', '')}"
            for a in news.get("articles", [])[:5]
        )
        content_text = (
            "\n".join(content_summaries[:3]) if content_summaries else "정성 분석 없음"
        )

        # Stage 1: 3 agents in parallel
        blind_spot_result, prediction_result, external_result = await asyncio.gather(
            self.blind_spot.analyze(signal, news_text, content_text),
            self.prediction_review.analyze(signal, news_text, content_text),
            self.external_factor.analyze(signal, news_text, content_text),
        )

        # Stage 2: Senior synthesis
        senior_result = await self.senior.synthesize(
            signal=signal,
            blind_spot=blind_spot_result,
            prediction_review=prediction_result,
            external_factor=external_result,
        )

        return {
            "blind_spots": blind_spot_result,
            "prediction_review": prediction_result,
            "external_factors": external_result,
            "senior_synthesis": senior_result,
        }
