"""Senior Synthesis Agent — 정량+정성 리포트를 소스로 종합 판단."""

import asyncio
import logging

from alphapulse.core.config import Config
from alphapulse.core.constants import INDICATOR_NAMES

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """당신은 20년 경력의 수석 투자 전략가(Senior Synthesis Agent)입니다.
아래 정량 분석과 정성 분석을 종합하여 투자 판단을 제시하세요.

핵심 규칙:
1. 정량 데이터와 정성 분석이 모두 있으면: 맥락을 연결하여 종합 판단
2. 정성 분석이 없으면: 정량 데이터만으로 시장 해설
3. 정량/정성이 상충하면: 상충 사실을 명시하고 양쪽 근거를 제시
4. 구체적 수치를 반드시 인용
5. 투자 방향 제안 포함
6. 한국어로 작성

{feedback_context}
=== 정량 분석 (Market Pulse) ===
날짜: {date}
종합 점수: {score} ({signal})
지표:
{indicators}

{commentary_section}

{content_section}

위 데이터를 종합하여 5~8문장의 종합 판단을 작성하세요.
마지막에 한 줄 투자 제안을 포함하세요.
"""


class SeniorSynthesisAgent:
    """정량 리포트 + 정성 리포트를 소스로 참조하여 맥락 기반 종합 판단."""

    def __init__(self):
        self.config = Config()

    def _build_prompt(self, pulse_result: dict, content_summaries: list[str],
                      commentary: str | None,
                      feedback_context: str | None = None) -> str:
        indicators = "\n".join(
            f"  {INDICATOR_NAMES.get(k, k)}: {v:+.0f}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )
        commentary_section = ""
        if commentary:
            commentary_section = f"=== AI 시장 해설 ===\n{commentary}"

        content_section = ""
        if content_summaries:
            content_section = "=== 최근 정성 분석 ===\n" + "\n".join(
                f"• {s}" for s in content_summaries
            )
        else:
            content_section = "=== 정성 분석 없음 — 정량 데이터만으로 판단 ==="

        feedback_block = ""
        if feedback_context:
            feedback_block = f"\n{feedback_context}\n"

        return SYNTHESIS_PROMPT.format(
            date=pulse_result.get("date", ""),
            score=pulse_result.get("score", 0),
            signal=pulse_result.get("signal", ""),
            indicators=indicators,
            commentary_section=commentary_section,
            content_section=content_section,
            feedback_context=feedback_block,
        )

    async def _call_llm(self, prompt: str) -> str:
        from google import genai

        def _sync_call():
            client = genai.Client(api_key=self.config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.3,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    async def synthesize(self, pulse_result: dict, content_summaries: list[str],
                         commentary: str | None,
                         feedback_context: str | None = None) -> str:
        """종합 판단 생성."""
        prompt = self._build_prompt(pulse_result, content_summaries, commentary,
                                    feedback_context=feedback_context)
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"종합 판단 생성 실패: {e}")
            return self._fallback(pulse_result, content_summaries)

    def _fallback(self, pulse_result: dict, content_summaries: list[str]) -> str:
        score = pulse_result.get("score", 0)
        signal = pulse_result.get("signal", "")
        content_note = f" 최근 정성 분석 {len(content_summaries)}건 참고." if content_summaries else ""
        return f"Market Pulse {score:+.0f} ({signal}).{content_note} AI 종합 판단 생성에 실패했습니다."
