"""사각지대 분석 에이전트 — 현 시스템이 놓친 요인 식별."""

import asyncio
import logging

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

PROMPT = """당신은 투자 시스템 감사관입니다.
아래 정보를 검토하고, 현재 시스템이 놓친 시장 영향 요인을 식별하세요.

규칙:
1. 현재 시스템의 11개 지표가 커버하지 못하는 요인에 집중
2. 정치 이벤트, 규제 변화, 실적 발표, 지정학 등 비정량 요인
3. 구체적으로 어떤 이벤트/변수가 시장에 영향을 줬는지 명시
4. 시스템 개선을 위한 새 지표 후보 제안
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


class BlindSpotAgent:
    """현 시스템이 놓친 시장 영향 요인을 식별하는 에이전트."""

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
        """사각지대 분석 실행."""
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
            logger.error(f"BlindSpotAgent 실패: {e}")
            return self._fallback(signal)

    def _fallback(self, signal: dict) -> str:
        score = signal.get("score", 0)
        return f"사각지대 분석 실패 (점수: {score}). 비정량 요인을 수동으로 확인하세요."
