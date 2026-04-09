"""AI 전략 종합 — LLM 기반 최종 전략 판단.

정량(Market Pulse, 팩터 랭킹, 전략 시그널) + 정성(콘텐츠 분석) + 피드백을
Google Gemini LLM으로 종합하여 최종 전략 배분 및 종목 의견을 도출한다.

기존 에이전트 패턴 동일: asyncio.to_thread(), try/except, _fallback().
"""

import asyncio
import json
import logging
import re

from alphapulse.core.config import Config
from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)

STRATEGY_SYNTHESIS_PROMPT = """당신은 20년 경력의 수석 투자 전략가입니다.
아래 다섯 가지 입력을 종합하여 최종 전략 판단을 JSON으로 출력하세요.

핵심 규칙:
1. 정량 데이터(Market Pulse, 팩터 분석)를 기본으로 하되 정성 분석과 상충하면 양쪽 근거 명시
2. conviction_level 0.3 미만이면 현금 비중 상향 권고
3. 리스크 경고는 반드시 1개 이상 포함
4. 모든 판단에 구체적 수치 근거를 인용
5. 한국어로 작성

=== 1. 시장 상황 (Market Pulse) ===
날짜: {date}
종합 점수: {pulse_score} ({pulse_signal})
지표별 상세:
{indicator_details}

=== 2. 팩터 분석 (상위 종목 랭킹) ===
{factor_rankings}

=== 3. 전략별 시그널 ===
{strategy_signals}

=== 4. 정성 분석 (콘텐츠) ===
{content_summaries}

=== 5. 과거 성과 피드백 ===
{feedback_context}

=== 현재 포트폴리오 ===
총 자산: {total_value}원
현금: {cash}원
일간 수익률: {daily_return}%
누적 수익률: {cumulative_return}%
드로다운: {drawdown}%

출력 형식 (반드시 유효한 JSON):
{{
  "market_view": "시장 전체 판단 요약 (2~3문장)",
  "conviction_level": 0.0~1.0,
  "allocation_adjustment": {{"topdown_etf": 0.0~1.0, "momentum": 0.0~1.0, "value": 0.0~1.0}},
  "stock_opinions": [
    {{"code": "종목코드", "name": "종목명", "action": "강력매수|매수|유지|축소|매도", "reason": "근거", "confidence": 0.0~1.0}}
  ],
  "risk_warnings": ["경고1", "경고2"],
  "reasoning": "판단 근거 (3~5문장)"
}}
"""


class StrategyAISynthesizer:
    """정량 + 정성 분석을 LLM으로 종합하여 최종 전략 판단.

    Google Gemini API를 asyncio.to_thread()로 호출한다.
    LLM 실패 시 _fallback()으로 규칙 기반 안전 실행.
    """

    def __init__(self) -> None:
        """초기화."""
        self.config = Config()

    async def synthesize(
        self,
        pulse_result: dict,
        ranked_stocks: list[Signal],
        strategy_signals: dict[str, list[Signal]],
        content_summaries: list[str],
        feedback_context: str | None,
        current_portfolio: PortfolioSnapshot,
    ) -> StrategySynthesis:
        """AI 종합 판단을 생성한다.

        Args:
            pulse_result: Market Pulse 11개 지표 결과.
            ranked_stocks: 팩터 스크리닝 상위 종목 시그널.
            strategy_signals: 전략별 시그널 딕셔너리.
            content_summaries: 정성 분석 결과 요약 리스트.
            feedback_context: 적중률/피드백 텍스트 (선택).
            current_portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            StrategySynthesis 데이터클래스.
        """
        prompt = self._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            content_summaries, feedback_context, current_portfolio,
        )
        try:
            response = await self._call_llm(prompt)
            return self._parse_response(response)
        except Exception:
            logger.exception("AI 전략 종합 실패")
            return self._fallback(strategy_signals)

    def _build_prompt(
        self,
        pulse_result: dict,
        ranked_stocks: list[Signal],
        strategy_signals: dict[str, list[Signal]],
        content_summaries: list[str],
        feedback_context: str | None,
        current_portfolio: PortfolioSnapshot,
    ) -> str:
        """LLM 프롬프트를 구성한다.

        5가지 입력 카테고리를 구조화된 프롬프트로 조합한다.
        """
        # 1. 지표 상세
        indicator_details = "\n".join(
            f"  {k}: {v:+.0f}" if isinstance(v, (int, float)) else f"  {k}: {v}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )
        if not indicator_details:
            indicator_details = "  (지표 데이터 없음)"

        # 2. 팩터 랭킹
        if ranked_stocks:
            factor_lines = []
            for i, sig in enumerate(ranked_stocks[:20], 1):
                factors_str = ", ".join(f"{k}={v:.2f}" for k, v in sig.factors.items())
                factor_lines.append(
                    f"  {i}. {sig.stock.name}({sig.stock.code}) "
                    f"점수={sig.score:.1f} [{factors_str}]"
                )
            factor_rankings = "\n".join(factor_lines)
        else:
            factor_rankings = "  (팩터 분석 결과 없음)"

        # 3. 전략별 시그널
        strategy_lines = []
        for strat_id, signals in strategy_signals.items():
            if signals:
                top = signals[:5]
                names = ", ".join(f"{s.stock.name}({s.score:.0f})" for s in top)
                strategy_lines.append(f"  {strat_id}: {len(signals)}종목 — 상위: {names}")
            else:
                strategy_lines.append(f"  {strat_id}: 시그널 없음")
        strategy_signals_text = "\n".join(strategy_lines) if strategy_lines else "  (전략 시그널 없음)"

        # 4. 정성 분석
        if content_summaries:
            content_text = "\n".join(f"  - {s}" for s in content_summaries)
        else:
            content_text = "  (정성 분석 없음 — 정량 데이터만으로 판단)"

        # 5. 피드백
        feedback_text = feedback_context if feedback_context else "  (피드백 데이터 없음)"

        return STRATEGY_SYNTHESIS_PROMPT.format(
            date=pulse_result.get("date", ""),
            pulse_score=pulse_result.get("score", 0),
            pulse_signal=pulse_result.get("signal", ""),
            indicator_details=indicator_details,
            factor_rankings=factor_rankings,
            strategy_signals=strategy_signals_text,
            content_summaries=content_text,
            feedback_context=feedback_text,
            total_value=f"{current_portfolio.total_value:,.0f}",
            cash=f"{current_portfolio.cash:,.0f}",
            daily_return=f"{current_portfolio.daily_return:.2f}",
            cumulative_return=f"{current_portfolio.cumulative_return:.2f}",
            drawdown=f"{current_portfolio.drawdown:.2f}",
        )

    async def _call_llm(self, prompt: str) -> str:
        """asyncio.to_thread()로 sync genai API를 호출한다.

        Args:
            prompt: LLM 프롬프트.

        Returns:
            LLM 응답 텍스트.
        """
        from google import genai

        def _sync_call():
            client = genai.Client(api_key=self.config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=4096,
                    temperature=0.2,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    def _parse_response(self, response: str) -> StrategySynthesis:
        """LLM 응답을 StrategySynthesis로 파싱한다.

        JSON 응답을 파싱하여 구조화된 데이터클래스로 변환한다.
        마크다운 코드 블록 내부 JSON도 처리한다.

        Args:
            response: LLM 응답 텍스트.

        Returns:
            StrategySynthesis 데이터클래스.

        Raises:
            ValueError: 유효하지 않은 JSON.
        """
        # 마크다운 코드 블록 제거
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답 JSON 파싱 실패: {e}") from e

        # StockOpinion 변환
        stock_opinions = []
        for op in data.get("stock_opinions", []):
            stock = Stock(
                code=op.get("code", ""),
                name=op.get("name", ""),
                market="KOSPI",  # 기본값
            )
            stock_opinions.append(StockOpinion(
                stock=stock,
                action=op.get("action", "유지"),
                reason=op.get("reason", ""),
                confidence=float(op.get("confidence", 0.5)),
            ))

        return StrategySynthesis(
            market_view=data.get("market_view", ""),
            conviction_level=float(data.get("conviction_level", 0.5)),
            allocation_adjustment=data.get("allocation_adjustment", {}),
            stock_opinions=stock_opinions,
            risk_warnings=data.get("risk_warnings", []),
            reasoning=data.get("reasoning", ""),
        )

    def _fallback(self, strategy_signals: dict[str, list[Signal]]) -> StrategySynthesis:
        """LLM 실패 시 규칙 기반 기본 판단.

        정량 시그널만으로 보수적인 기본값을 반환한다.

        Args:
            strategy_signals: 전략별 시그널.

        Returns:
            StrategySynthesis (기본 보수적 배분).
        """
        # 전략별 균등 배분
        strategy_ids = list(strategy_signals.keys()) if strategy_signals else []
        if strategy_ids:
            equal_weight = round(1.0 / len(strategy_ids), 2)
            allocation = {sid: equal_weight for sid in strategy_ids}
        else:
            allocation = {}

        return StrategySynthesis(
            market_view="AI 분석 불가 — 정량 시그널 기반 실행",
            conviction_level=0.5,
            allocation_adjustment=allocation,
            stock_opinions=[],
            risk_warnings=["AI 종합 판단 실패. 규칙 기반으로 실행됨."],
            reasoning="LLM 호출 실패로 정량 시그널만 사용",
        )
