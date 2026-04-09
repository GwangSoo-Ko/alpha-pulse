"""멀티전략 자금 배분기.

Market Pulse + AI 종합 판단에 따라 전략별 자금을 동적 배분한다.
"""

import logging

from alphapulse.trading.core.models import StrategySynthesis

logger = logging.getLogger(__name__)

# AI 확신도 최소 임계값 — 이 이하면 AI 조정 무시
_MIN_AI_CONVICTION = 0.3

# AI 배분 가중치 (규칙 기반과의 블렌딩)
_AI_BLEND_WEIGHT = 0.4


class StrategyAllocator:
    """멀티전략 간 자금 배분 관리자.

    Attributes:
        base_allocations: 기본 배분 비율 (합계 1.0).
        current_allocations: 현재 적용 중인 배분 비율.
    """

    def __init__(self, base_allocations: dict[str, float]) -> None:
        """StrategyAllocator를 초기화한다.

        Args:
            base_allocations: 전략ID → 배분비율 딕셔너리 (합계 1.0).
        """
        self.base_allocations = dict(base_allocations)
        self.current_allocations = dict(base_allocations)

    def get_allocations(self) -> dict[str, float]:
        """현재 배분 비율을 반환한다."""
        return dict(self.current_allocations)

    def get_capital(self, strategy_id: str, total_capital: float) -> float:
        """전략별 할당 가능 자금을 반환한다.

        Args:
            strategy_id: 전략 ID.
            total_capital: 총 투자 자본.

        Returns:
            해당 전략에 배분된 자금 (원).
        """
        ratio = self.current_allocations.get(strategy_id, 0)
        return total_capital * ratio

    def adjust_by_market_regime(
        self,
        pulse_score: float,
        ai_synthesis: StrategySynthesis | None,
    ) -> dict[str, float]:
        """시장 상황에 따라 배분을 동적 조정한다.

        Args:
            pulse_score: Market Pulse 점수 (-100 ~ +100).
            ai_synthesis: AI 종합 판단 결과 (없으면 None).

        Returns:
            조정된 배분 비율 딕셔너리 (합계 1.0).
        """
        # 1단계: 규칙 기반 조정
        adjusted = self._rule_based_adjustment(pulse_score)

        # 2단계: AI 종합 판단 반영
        if (
            ai_synthesis is not None
            and ai_synthesis.conviction_level >= _MIN_AI_CONVICTION
            and ai_synthesis.allocation_adjustment
        ):
            ai_alloc = ai_synthesis.allocation_adjustment
            # 규칙 기반과 AI 제안의 가중 평균
            for key in adjusted:
                if key in ai_alloc:
                    rule_val = adjusted[key]
                    ai_val = ai_alloc[key]
                    adjusted[key] = (
                        rule_val * (1 - _AI_BLEND_WEIGHT)
                        + ai_val * _AI_BLEND_WEIGHT
                    )
            logger.info(
                "AI 종합 판단 반영 (확신도: %.2f)", ai_synthesis.conviction_level
            )

        # 정규화 (합계 = 1.0)
        adjusted = self._normalize(adjusted)
        self.current_allocations = adjusted
        return dict(adjusted)

    def update_allocations(self, new_allocations: dict[str, float]) -> None:
        """배분 비율을 직접 갱신한다.

        Args:
            new_allocations: 새 배분 비율 (합계 1.0).
        """
        self.current_allocations = dict(new_allocations)

    def _rule_based_adjustment(
        self, pulse_score: float
    ) -> dict[str, float]:
        """규칙 기반 배분 조정을 수행한다.

        Args:
            pulse_score: Market Pulse 점수 (-100 ~ +100).

        Returns:
            조정된 배분 딕셔너리.
        """
        adjusted = dict(self.base_allocations)

        etf_key = "topdown_etf"
        stock_keys = [k for k in adjusted if k != etf_key]

        if pulse_score > 50:
            # 강한 매수 → 종목 전략 비중 증가
            shift = 0.10
            adjusted[etf_key] = max(adjusted[etf_key] - shift, 0.10)
            bonus = shift / len(stock_keys) if stock_keys else 0
            for k in stock_keys:
                adjusted[k] += bonus
        elif pulse_score < -50:
            # 강한 매도 → ETF 비중 증가
            shift = 0.15
            adjusted[etf_key] = min(adjusted[etf_key] + shift, 0.60)
            penalty = shift / len(stock_keys) if stock_keys else 0
            for k in stock_keys:
                adjusted[k] = max(adjusted[k] - penalty, 0.05)
        elif -10 <= pulse_score <= 10:
            # 중립 → 밸류 비중 약간 증가
            if "value" in adjusted:
                shift = 0.05
                adjusted["value"] += shift
                for k in stock_keys:
                    if k != "value":
                        adjusted[k] -= shift / (len(stock_keys) - 1)

        return adjusted

    @staticmethod
    def _normalize(allocations: dict[str, float]) -> dict[str, float]:
        """배분 비율을 정규화하여 합계 1.0으로 만든다."""
        total = sum(allocations.values())
        if total <= 0:
            n = len(allocations)
            return {k: 1.0 / n for k in allocations}
        return {k: v / total for k, v in allocations.items()}
