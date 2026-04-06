"""시니어 종합 피드백 에이전트 — 3개 분석 결과를 종합하여 구조화된 피드백 생성."""

import asyncio
import logging

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

PROMPT = """당신은 CIO(최고투자책임자)입니다.
아래 3명의 분석가가 작성한 사후 분석을 종합하여 구조화된 피드백을 작성하세요.

규칙:
1. 아래 5개 섹션을 반드시 포함할 것
2. 각 섹션은 1~2문장으로 간결하게
3. 실행 가능한 구체적 제안 위주
4. 한국어로 작성

출력 형식:
[예측 성공/실패 핵심 원인]
(내용)

[놓친 변수 요약]
(내용)

[시스템 개선 제안]
(내용)

[내일 주의 포인트]
(내용)

[지표별 신뢰도 코멘트]
(내용)

=== 장 전 시그널 ===
점수: {score} ({signal})
KOSPI 변동: {kospi_change}%

=== 사각지대 분석 ===
{blind_spot}

=== 예측 복기 ===
{prediction_review}

=== 외부 변수 분석 ===
{external_factor}
"""


class SeniorFeedbackAgent:
    """3개 에이전트 결과를 종합하여 구조화된 피드백을 생성하는 시니어 에이전트."""

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
                    max_output_tokens=1536,
                    temperature=0.3,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    async def synthesize(
        self, signal: dict, blind_spot: str, prediction_review: str, external_factor: str
    ) -> str:
        """시니어 종합 피드백 생성."""
        prompt = PROMPT.format(
            score=signal.get("score", "N/A"),
            signal=signal.get("signal", "N/A"),
            kospi_change=signal.get("kospi_change_pct", "N/A"),
            blind_spot=blind_spot,
            prediction_review=prediction_review,
            external_factor=external_factor,
        )
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"SeniorFeedbackAgent 실패: {e}")
            return self._fallback(signal)

    def _fallback(self, signal: dict) -> str:
        score = signal.get("score", 0)
        signal_label = signal.get("signal", "")
        return (
            f"종합 피드백 생성 실패 (점수: {score}, {signal_label}). "
            "개별 분석 결과를 직접 확인하세요."
        )
