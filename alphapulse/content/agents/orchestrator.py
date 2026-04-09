import asyncio
import logging

from alphapulse.content.agents.senior_analyst import SeniorAnalyst
from alphapulse.content.agents.specialists import get_specialists_for_topics
from alphapulse.content.agents.topic_classifier import TopicClassifier
from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_config = Config()


class AnalysisOrchestrator:
    """
    멀티에이전트 분석 오케스트레이터.
    기존 GeminiAnalyzer와 동일한 인터페이스: analyze(title, content) -> str
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or _config.GEMINI_API_KEY
        self.model = model or _config.GEMINI_MODEL
        self.classifier = TopicClassifier(api_key=self.api_key, model=self.model)
        self.senior = SeniorAnalyst(api_key=self.api_key, model=self.model)

    async def analyze(self, title: str, content: str) -> str:
        try:
            return await self._run_pipeline(title, content)
        except Exception as e:
            logger.error(f"분석 파이프라인 전체 실패: {e}")
            return self._generate_fallback(title, content)

    async def _run_pipeline(self, title: str, content: str) -> str:
        # Step 1: 주제 분류
        logger.info("Step 1: 주제 분류 시작")
        topics = await self.classifier.classify(title, content)
        logger.info(f"분류된 주제: {topics}")

        # Step 2: 전문가 병렬 분석
        logger.info(f"Step 2: 전문가 분석 시작 ({len(topics)}개 분야)")
        specialists = get_specialists_for_topics(topics, api_key=self.api_key, model=self.model)

        specialist_results = {}
        if specialists:
            analyses = await asyncio.gather(
                *[s.analyze(title, content) for s in specialists],
                return_exceptions=True,
            )
            for specialist, result in zip(specialists, analyses):
                if isinstance(result, Exception):
                    logger.error(f"[{specialist.name}] 분석 예외: {result}")
                    specialist_results[specialist.topic] = f"(분석 중 오류 발생: {result})"
                else:
                    specialist_results[specialist.topic] = result

        logger.info(f"전문가 분석 완료: {list(specialist_results.keys())}")

        # Step 3: 시니어 분석가 종합
        logger.info("Step 3: 시니어 분석가 종합 시작")
        final_report = await self.senior.synthesize(title, content, specialist_results)

        return final_report

    def _generate_fallback(self, title: str, content: str) -> str:
        preview = content[:1000]
        return f"""## 핵심 요약
(멀티에이전트 분석 파이프라인 실패 — 원문 미리보기로 대체)

## 제목: {title}

## 원문 미리보기
{preview}

---
*분석 파이프라인 오류로 자동 생성된 기본 보고서입니다.*
"""
