"""예측 복기 에이전트 — 지표별 적중/미적중 분석."""

import asyncio
import logging

from alphapulse.core.config import Config

logger = logging.getLogger(__name__)

PROMPT = """당신은 퀀트 전략 검증 전문가입니다.
아래 정보를 검토하고, 어떤 지표가 맞고 어떤 지표가 틀렸는지, 왜 그런지 분석하세요.

규칙:
1. 지표별 점수와 실제 시장 결과를 비교하여 적중/미적중 판단
2. 적중한 지표의 성공 요인과 미적중 지표의 실패 원인 분석
3. 지표 간 상충 신호가 있었는지 확인
4. 향후 지표 가중치 조정에 대한 제안
5. 한국어로 간결하게 (3~5문장)

=== 장 전 시그널 ===
점수: {score} ({signal})
지표별 점수: {indicator_scores}

=== 실제 결과 ===
KOSPI: {kospi_change}%

=== 장 후 뉴스 ===
{news}

=== 장 전 정성 분석 ===
{content}
"""


class PredictionReviewAgent:
    """지표별 적중/미적중을 분석하는 에이전트."""

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
        """예측 복기 분석 실행."""
        prompt = PROMPT.format(
            score=signal.get("score", "N/A"),
            signal=signal.get("signal", "N/A"),
            indicator_scores=signal.get("indicator_scores", "N/A"),
            kospi_change=signal.get("kospi_change_pct", "N/A"),
            news=news,
            content=content,
        )
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"PredictionReviewAgent 실패: {e}")
            return self._fallback(signal)

    def _fallback(self, signal: dict) -> str:
        score = signal.get("score", 0)
        return f"예측 복기 분석 실패 (점수: {score}). 지표별 적중률을 수동으로 확인하세요."
