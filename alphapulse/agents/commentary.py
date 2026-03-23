"""AI 시장 해설 에이전트 — Market Pulse 데이터 기반 자연어 해설 생성."""

import asyncio
import logging

from alphapulse.core.config import Config
from alphapulse.core.constants import INDICATOR_NAMES

logger = logging.getLogger(__name__)

COMMENTARY_PROMPT = """당신은 20년 경력의 시니어 투자 전략가입니다.
아래 Market Pulse 데이터를 분석하여 3~5문장의 시장 해설을 작성하세요.

규칙:
1. 핵심 수치를 반드시 인용하세요 (예: "외국인 -3.7조 매도")
2. 점수가 극단적인 지표(±80 이상)에 집중하세요
3. 상충하는 신호가 있으면 명시하세요
4. 투자 방향 제안을 포함하세요
5. 한국어로 작성하세요

{content_context}

=== Market Pulse 데이터 ===
날짜: {date}
종합 점수: {score} ({signal})

지표별 점수:
{indicators}

{details_section}
"""


class MarketCommentaryAgent:
    """AI가 Market Pulse 데이터를 읽고 자연어 시장 해설을 생성."""

    def __init__(self):
        self.config = Config()

    def _build_prompt(self, pulse_result: dict, content_summaries: list[str]) -> str:
        indicators = "\n".join(
            f"  {INDICATOR_NAMES.get(k, k)}: {v:+.0f}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )
        details_lines = []
        details = pulse_result.get("details", {})
        for key, detail in details.items():
            if isinstance(detail, dict) and "details" in detail:
                details_lines.append(f"  [{INDICATOR_NAMES.get(key, key)}] {detail['details']}")
        content_context = ""
        if content_summaries:
            content_context = "=== 최근 정성 분석 ===\n" + "\n".join(
                f"• {s}" for s in content_summaries
            )
        return COMMENTARY_PROMPT.format(
            date=pulse_result.get("date", ""),
            score=pulse_result.get("score", 0),
            signal=pulse_result.get("signal", ""),
            indicators=indicators,
            details_section="\n".join(details_lines) if details_lines else "",
            content_context=content_context,
        )

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

    async def generate(self, pulse_result: dict, content_summaries: list[str]) -> str:
        """시장 해설 생성."""
        prompt = self._build_prompt(pulse_result, content_summaries)
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"AI Commentary 생성 실패: {e}")
            return self._fallback(pulse_result)

    def _fallback(self, pulse_result: dict) -> str:
        score = pulse_result.get("score", 0)
        signal = pulse_result.get("signal", "")
        return f"Market Pulse Score {score:+.0f} ({signal}). AI 해설 생성에 실패했습니다. 지표 상세를 직접 확인하세요."
