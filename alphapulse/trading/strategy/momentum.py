"""모멘텀 전략.

상위 모멘텀 종목 롱 — 주간 리밸런싱.
시장 시그널이 매도 우위 이하면 시그널 강도를 축소한다.
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

_BEARISH_SIGNALS = {"moderately_bearish", "strong_bearish"}


class MomentumStrategy(BaseStrategy):
    """모멘텀 팩터 기반 종목 선정 전략.

    Attributes:
        strategy_id: "momentum".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수.
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, ranker: MultiFactorRanker, config: dict) -> None:
        """MomentumStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 20) 등.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.top_n: int = config.get("top_n", 20)
        self.factor_weights: dict[str, float] = {
            "momentum": 0.6,
            "flow": 0.3,
            "volatility": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """모멘텀 상위 종목 시그널을 생성한다.

        Args:
            universe: 투자 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            상위 top_n 종목의 Signal 리스트 (점수순).
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")

        # 랭커로 종목 점수 산출
        ranked = self.ranker.rank(universe, strategy_id=self.strategy_id)

        # 상위 N 선정
        top_signals = ranked[: self.top_n]

        # 매도 우위 시 강도 축소 (0.5배)
        if pulse_signal in _BEARISH_SIGNALS:
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=s.score * 0.5,
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info("매도 우위 — 모멘텀 시그널 강도 0.5배 축소")

        return top_signals
