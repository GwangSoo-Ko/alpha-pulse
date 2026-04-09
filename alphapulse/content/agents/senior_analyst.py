import asyncio
import logging

from google import genai

from alphapulse.content.agents.topic_classifier import TOPIC_LABELS
from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

_config = Config()

SENIOR_PROMPT_TEMPLATE = """당신은 20년 경력의 시니어 자산운용 전문가이자 수석 애널리스트입니다.
자산 투자, 운용, 배분에 대한 깊은 전문성을 보유하고 있습니다.

아래 블로그 글에 대해 여러 전문가들이 각자의 관점에서 분석한 결과를 종합하여,
최종 인사이트 보고서를 작성해주세요.

## 원문 제목: {title}

## 원문 내용 (요약):
{content}

---

## 전문가 분석 결과

{specialist_analyses}

---

위 전문가 분석들을 종합하여 아래 형식의 최종 보고서를 작성해주세요:

## 핵심 요약
- 3~5문장으로 글의 핵심과 시장 영향을 종합 요약

## 전문가 분석 종합
각 전문가의 핵심 의견을 간결하게 정리

## 크로스 자산 시사점
- 여러 자산군에 걸친 연쇄 영향 분석
- 자산 간 상관관계 관점의 인사이트

## 포트폴리오 전략 제안
- 현 상황에서의 자산배분 방향성
- 비중 확대/축소 추천 자산군
- 헤지 전략 제안

## 주요 리스크
- 종합적 리스크 요인 정리
- 시나리오별 영향 (베이스/불/베어 케이스)

## 모니터링 포인트
- 향후 주시해야 할 지표/이벤트 3~5개

## 관련 키워드
- 핵심 키워드 5~10개를 태그 형태로 나열
"""


class SeniorAnalyst:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or _config.GEMINI_API_KEY
        self.model_name = model or _config.GEMINI_MODEL
        self.max_retries = _config.MAX_RETRIES
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    async def synthesize(self, title: str, content: str,
                         specialist_results: dict[str, str]) -> str:
        prompt = self._build_prompt(title, content, specialist_results)

        for attempt in range(self.max_retries):
            try:
                result = await self._call_llm(prompt)
                logger.info("시니어 분석가 종합 보고서 생성 완료")
                return result
            except Exception as e:
                logger.warning(f"시니어 분석 실패 ({attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(3)

        logger.error("시니어 분석 최종 실패, 전문가 분석 취합 보고서로 대체")
        return self._format_fallback(title, specialist_results)

    async def _call_llm(self, prompt: str) -> str:
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
        )
        return response.text

    def _build_prompt(self, title: str, content: str,
                      specialist_results: dict[str, str]) -> str:
        content_truncated = content[:3000]

        analyses_text = ""
        for topic, analysis in specialist_results.items():
            label = TOPIC_LABELS.get(topic, topic)
            analyses_text += f"### [{label}] 전문가 분석\n{analysis}\n\n"

        if not analyses_text:
            analyses_text = "(전문가 분석 없음)\n"

        return SENIOR_PROMPT_TEMPLATE.format(
            title=title,
            content=content_truncated,
            specialist_analyses=analyses_text,
        )

    def _format_fallback(self, title: str, specialist_results: dict[str, str]) -> str:
        sections = [f"## 종합 보고서: {title}\n"]
        sections.append("*시니어 분석가 API 호출 실패로 전문가 분석 취합본을 제공합니다.*\n")

        for topic, analysis in specialist_results.items():
            label = TOPIC_LABELS.get(topic, topic)
            sections.append(f"### [{label}] 전문가 분석\n{analysis}\n")

        return "\n".join(sections)
