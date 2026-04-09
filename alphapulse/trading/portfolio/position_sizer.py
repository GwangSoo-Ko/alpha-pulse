"""포지션 사이징.

종목당 투자 비중을 결정하는 다양한 방법을 제공한다.
"""

import logging

from alphapulse.trading.core.models import StockOpinion

logger = logging.getLogger(__name__)


class PositionSizer:
    """종목당 투자 비중 결정 도구.

    균등 배분, 변동성 조정, 켈리 기준, AI 조정을 지원한다.
    """

    def equal_weight(self, n_stocks: int) -> float:
        """균등 배분 비중을 계산한다.

        Args:
            n_stocks: 종목 수.

        Returns:
            종목당 비중 (0~1).
        """
        if n_stocks <= 0:
            return 0.0
        return 1.0 / n_stocks

    def volatility_adjusted(
        self,
        volatilities: dict[str, float],
        target_vol: float = 0.15,
    ) -> dict[str, float]:
        """변동성 역수 비중을 계산한다.

        변동성이 낮을수록 비중이 높아진다.

        Args:
            volatilities: 종목코드 -> 연 변동성 매핑.
            target_vol: 포트폴리오 목표 변동성 (참조용).

        Returns:
            종목코드 -> 비중 매핑 (합계 1.0).
        """
        inv_vols = {}
        for code, vol in volatilities.items():
            inv_vols[code] = 1.0 / vol if vol > 0 else 0.0

        total = sum(inv_vols.values())
        if total <= 0:
            n = len(volatilities)
            return {k: 1.0 / n for k in volatilities} if n > 0 else {}

        return {k: v / total for k, v in inv_vols.items()}

    def kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """켈리 기준 최적 비중을 계산한다 (half-kelly).

        Args:
            win_rate: 승률 (0~1).
            avg_win: 평균 수익 (양수).
            avg_loss: 평균 손실 (양수).

        Returns:
            최적 투자 비중 (0 이상, half-kelly).
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        kelly_fraction = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        return max(0.0, kelly_fraction * 0.5)

    def ai_adjusted(
        self,
        base_weight: float,
        opinion: StockOpinion,
        max_weight: float = 0.10,
    ) -> float:
        """AI 확신도를 반영하여 비중을 조정한다.

        Args:
            base_weight: 기본 비중 (0~1).
            opinion: AI 종목별 의견.
            max_weight: 최대 허용 비중.

        Returns:
            조정된 비중 (0~max_weight).
        """
        if opinion.action in ("매도", "강력매도"):
            return 0.0

        if opinion.confidence > 0.7:
            adjusted = base_weight * 1.2
        elif opinion.confidence < 0.3:
            adjusted = base_weight * 0.7
        else:
            adjusted = base_weight

        return min(adjusted, max_weight)
