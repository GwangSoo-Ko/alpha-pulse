"""퀄리티+모멘텀 복합 전략.

퀄리티(ROE, 이익 성장)와 모멘텀을 결합 — 주간 리밸런싱.
강한 매도 우위 시 시그널 강도를 크게 축소한다.
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy._factor_helper import _compute_factor_data
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class QualityMomentumStrategy(BaseStrategy):
    """퀄리티 + 모멘텀 복합 전략.

    Attributes:
        strategy_id: "quality_momentum".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수 (기본 15).
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "quality_momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(
        self,
        ranker: MultiFactorRanker,
        config: dict,
        factor_calc=None,
    ) -> None:
        """QualityMomentumStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 15) 등.
            factor_calc: (선택) FactorCalculator.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.factor_calc = factor_calc
        self.top_n: int = config.get("top_n", 15)
        self.factor_weights: dict[str, float] = {
            "quality": 0.35,
            "momentum": 0.35,
            "flow": 0.2,
            "volatility": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """퀄리티+모멘텀 랭킹 기반 시그널을 생성한다.

        Args:
            universe: 투자 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            상위 top_n 종목의 Signal 리스트.
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")

        factor_data = _compute_factor_data(self.factor_calc, universe)
        ranked = self.ranker.rank(
            universe, factor_data, strategy_id=self.strategy_id
        )
        top_signals = ranked[: self.top_n]

        # 시장 방향에 따른 강도 조정
        dampening = self._get_dampening(pulse_signal)
        if dampening != 1.0:
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=s.score * dampening,
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info(
                "시장 상황 '%s' — 퀄리티모멘텀 시그널 강도 %.1f배",
                pulse_signal,
                dampening,
            )

        return top_signals

    @staticmethod
    def _get_dampening(pulse_signal: str) -> float:
        """시장 시그널에 따른 강도 계수를 반환한다.

        Args:
            pulse_signal: Market Pulse 시그널 레벨.

        Returns:
            강도 계수 (1.0 = 변동 없음).
        """
        dampening_map = {
            "strong_bullish": 1.0,
            "moderately_bullish": 1.0,
            "neutral": 1.0,
            "moderately_bearish": 0.5,
            "strong_bearish": 0.3,
        }
        return dampening_map.get(pulse_signal, 1.0)
