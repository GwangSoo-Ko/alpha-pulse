"""StrategyAISynthesizer 테스트 — AI 전략 종합.

asyncio.run()은 CLI entry에서만 사용 (CLAUDE.md 규칙). 테스트는 pytest-asyncio를 사용한다.
"""

import json
from unittest.mock import patch

import pytest

from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)
from alphapulse.trading.strategy.ai_synthesizer import (
    STRATEGY_SYNTHESIS_PROMPT,
    StrategyAISynthesizer,
)


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def synthesizer():
    return StrategyAISynthesizer()


@pytest.fixture
def pulse_result():
    """Market Pulse 결과."""
    return {
        "date": "20260409",
        "score": 62,
        "signal": "매수 우위",
        "indicator_scores": {
            "kospi_ma_trend": 80,
            "vkospi_level": -30,
            "foreign_flow": 60,
        },
        "details": {},
    }


@pytest.fixture
def ranked_stocks(samsung):
    """팩터 스크리닝 상위 종목."""
    return [
        Signal(stock=samsung, score=85.0, factors={"momentum": 0.9, "value": 0.7},
               strategy_id="screening"),
    ]


@pytest.fixture
def strategy_signals(samsung):
    """전략별 시그널."""
    return {
        "momentum": [
            Signal(stock=samsung, score=78.0, factors={"momentum": 0.85},
                   strategy_id="momentum"),
        ],
        "value": [],
    }


@pytest.fixture
def portfolio():
    """현재 포트폴리오."""
    return PortfolioSnapshot(
        date="20260409", cash=50_000_000, positions=[],
        total_value=100_000_000, daily_return=0.5,
        cumulative_return=3.0, drawdown=-1.2,
    )


@pytest.fixture
def llm_response():
    """LLM 응답 JSON."""
    return json.dumps({
        "market_view": "글로벌 유동성 회복과 외국인 순매수 지속으로 매수 우위 판단",
        "conviction_level": 0.72,
        "allocation_adjustment": {
            "topdown_etf": 0.25,
            "momentum": 0.45,
            "value": 0.30,
        },
        "stock_opinions": [
            {
                "code": "005930",
                "name": "삼성전자",
                "action": "매수",
                "reason": "AI 반도체 수요 회복 + 외국인 순매수 전환",
                "confidence": 0.78,
            },
        ],
        "risk_warnings": ["미중 갈등 재점화 리스크"],
        "reasoning": "정량 62점 매수우위 + 외국인 3일 연속 순매수 + AI 반도체 테마 강세",
    }, ensure_ascii=False)


class TestPromptConstruction:
    def test_prompt_template_exists(self):
        """프롬프트 템플릿이 존재한다."""
        assert isinstance(STRATEGY_SYNTHESIS_PROMPT, str)
        assert len(STRATEGY_SYNTHESIS_PROMPT) > 100

    def test_build_prompt_includes_pulse(self, synthesizer, pulse_result, ranked_stocks,
                                          strategy_signals, portfolio):
        """프롬프트에 Market Pulse 정보가 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "62" in prompt  # pulse score
        assert "매수 우위" in prompt

    def test_build_prompt_includes_factors(self, synthesizer, pulse_result, ranked_stocks,
                                            strategy_signals, portfolio):
        """프롬프트에 팩터 랭킹이 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "삼성전자" in prompt
        assert "85.0" in prompt or "85" in prompt

    def test_build_prompt_includes_strategy_signals(self, synthesizer, pulse_result, ranked_stocks,
                                                     strategy_signals, portfolio):
        """프롬프트에 전략별 시그널이 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "momentum" in prompt

    def test_build_prompt_includes_content(self, synthesizer, pulse_result, ranked_stocks,
                                            strategy_signals, portfolio):
        """프롬프트에 정성 분석이 포함된다."""
        content = ["반도체 업황 회복 전망", "미국 기술주 강세"]
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            content, None, portfolio,
        )
        assert "반도체 업황 회복 전망" in prompt

    def test_build_prompt_includes_feedback(self, synthesizer, pulse_result, ranked_stocks,
                                             strategy_signals, portfolio):
        """프롬프트에 피드백 컨텍스트가 포함된다."""
        feedback = "최근 5일 적중률: 72%. 외국인 수급 지표 정확도 높음."
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], feedback, portfolio,
        )
        assert "72%" in prompt

    def test_build_prompt_includes_portfolio(self, synthesizer, pulse_result, ranked_stocks,
                                              strategy_signals, portfolio):
        """프롬프트에 현재 포트폴리오 상태가 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "100,000,000" in prompt or "100000000" in prompt


class TestSynthesizeSuccess:
    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_returns_strategy_synthesis(self, mock_llm, synthesizer,
                                                    pulse_result, ranked_stocks,
                                                    strategy_signals, portfolio,
                                                    llm_response):
        """synthesize()가 StrategySynthesis를 반환한다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.72

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_market_view(self, mock_llm, synthesizer,
                                            pulse_result, ranked_stocks,
                                            strategy_signals, portfolio,
                                            llm_response):
        """market_view가 올바르게 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "유동성" in result.market_view

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_stock_opinions(self, mock_llm, synthesizer,
                                               pulse_result, ranked_stocks,
                                               strategy_signals, portfolio,
                                               llm_response):
        """종목별 의견이 StockOpinion으로 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert len(result.stock_opinions) == 1
        assert isinstance(result.stock_opinions[0], StockOpinion)
        assert result.stock_opinions[0].action == "매수"

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_allocation(self, mock_llm, synthesizer,
                                           pulse_result, ranked_stocks,
                                           strategy_signals, portfolio,
                                           llm_response):
        """전략 배분 조정이 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "momentum" in result.allocation_adjustment
        assert result.allocation_adjustment["momentum"] == 0.45

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_risk_warnings(self, mock_llm, synthesizer,
                                              pulse_result, ranked_stocks,
                                              strategy_signals, portfolio,
                                              llm_response):
        """리스크 경고가 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert len(result.risk_warnings) >= 1
        assert "미중" in result.risk_warnings[0]


class TestFallback:
    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_fallback_on_llm_failure(self, mock_llm, synthesizer,
                                      pulse_result, ranked_stocks,
                                      strategy_signals, portfolio):
        """LLM 실패 시 _fallback()이 호출된다."""
        mock_llm.side_effect = Exception("API Error")
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.5
        assert "실패" in result.risk_warnings[0] or "실패" in result.reasoning

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_fallback_on_invalid_json(self, mock_llm, synthesizer,
                                       pulse_result, ranked_stocks,
                                       strategy_signals, portfolio):
        """잘못된 JSON 응답 시 _fallback()이 호출된다."""
        mock_llm.return_value = "이것은 유효하지 않은 JSON입니다"
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.5

    def test_fallback_returns_valid_synthesis(self, synthesizer, strategy_signals):
        """_fallback()이 유효한 StrategySynthesis를 반환한다."""
        result = synthesizer._fallback(strategy_signals)
        assert isinstance(result, StrategySynthesis)
        assert 0.0 <= result.conviction_level <= 1.0
        assert isinstance(result.allocation_adjustment, dict)
        assert isinstance(result.stock_opinions, list)
        assert isinstance(result.risk_warnings, list)


class TestParseResponse:
    def test_parse_valid_json(self, synthesizer, llm_response):
        """올바른 JSON을 파싱한다."""
        result = synthesizer._parse_response(llm_response)
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.72

    def test_parse_json_in_markdown_block(self, synthesizer, llm_response):
        """마크다운 코드 블록 안의 JSON도 파싱한다."""
        wrapped = f"```json\n{llm_response}\n```"
        result = synthesizer._parse_response(wrapped)
        assert isinstance(result, StrategySynthesis)

    def test_parse_invalid_json_raises(self, synthesizer):
        """잘못된 JSON은 ValueError를 발생시킨다."""
        with pytest.raises(ValueError):
            synthesizer._parse_response("not json")
