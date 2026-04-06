"""외부 변수 분석 에이전트 — 글로벌/거시 요인 식별."""

import asyncio
import logging

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

PROMPT = """당신은 글로벌 매크로 전략가입니다.
아래 정보를 검토하고, 시장에 영향을 준 외부 요인을 식별하세요.

규칙:
1. 미국 정책, 지정학, 경제 이벤트, 실적 시즌, 글로벌 유동성 등 외부 요인에 집중
2. 해당 외부 요인이 KOSPI에 미친 구체적 영향 경로 설명
3. 현 시스템이 이 요인을 포착할 수 있었는지 평가
4. 향후 모니터링 포인트 제안
5. 한국어로 간결하게 (3~5문장)

=== 장 전 시그널 ===
점수: {score} ({signal})

=== 실제 결과 ===
KOSPI: {kospi_change}%

=== 장 후 뉴스 ===
{news}

=== 장 전 정성 분석 ===
{content}
"""


class ExternalFactorAgent:
    """글로벌/거시 외부 요인을 식별하는 에이전트."""

    def __init__(self):
        self.config = Config()

    async def _call_llm(self, prompt: str) -> str:
        """LLM 호출 (sync API를 thread에서 실행하여 이벤트 루프 블로킹 방지)."""
        from google import genai

        def _sync_call():
            client = genai.Client(api_key=self.config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=1024,
                    temperature=0.3,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    async def analyze(self, signal: dict, news: str, content: str) -> str:
        """외부 변수 분석 실행."""
        prompt = PROMPT.format(
            score=signal.get("score", "N/A"),
            signal=signal.get("signal", "N/A"),
            kospi_change=signal.get("kospi_change_pct", "N/A"),
            news=news,
            content=content,
        )
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"ExternalFactorAgent 실패: {e}")
            return self._fallback(signal)

    def _fallback(self, signal: dict) -> str:
        score = signal.get("score", 0)
        return f"외부 변수 분석 실패 (점수: {score}). 글로벌 매크로 요인을 수동으로 확인하세요."
