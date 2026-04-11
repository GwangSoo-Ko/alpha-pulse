"""밸류 전략.

저평가 + 퀄리티 복합 — 주간 리밸런싱.
중립 시장에서 강도가 증가한다 (불확실성 시 가치주 선호).
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy._factor_helper import _compute_factor_data
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class ValueStrategy(BaseStrategy):
    """저평가 + 퀄리티 복합 전략.

    Attributes:
        strategy_id: "value".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수 (기본 15).
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "value"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(
        self,
        ranker: MultiFactorRanker,
        config: dict,
        factor_calc=None,
    ) -> None:
        """ValueStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 15) 등.
            factor_calc: (선택) FactorCalculator. 있으면 factor_data를 계산.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.factor_calc = factor_calc
        self.top_n: int = config.get("top_n", 15)
        self.factor_weights: dict[str, float] = {
            "value": 0.4,
            "quality": 0.3,
            "momentum": 0.2,
            "flow": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """밸류 랭킹 기반 시그널을 생성한다.

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

        # 중립 시장 → 밸류 전략 강도 1.2배 (불확실성 시 가치주 선호)
        if pulse_signal == "neutral":
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=min(s.score * 1.2, 100.0),
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info("중립 시장 — 밸류 시그널 강도 1.2배 증가")

        return top_signals
