"""탑다운 ETF 전략.

Market Pulse Score → ETF 포지션 결정.
시그널 레벨 변경 시에만 리밸런싱 (SIGNAL_DRIVEN).
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

# ETF 코드 매핑 (이름 → 코드)
_ETF_CODES = {
    "KODEX 레버리지": "122630",
    "KODEX 200": "069500",
    "KODEX 단기채권": "153130",
    "KODEX 인버스": "114800",
    "KODEX 200선물인버스2X": "252670",
}


class TopDownETFStrategy(BaseStrategy):
    """Market Pulse Score 기반 탑다운 ETF 전략.

    시장 시그널 레벨에 따라 공격/방어 ETF 비중을 결정한다.

    Attributes:
        ETF_MAP: 시그널 레벨별 ETF 비중 매핑.
    """

    strategy_id = "topdown_etf"
    rebalance_freq = RebalanceFreq.SIGNAL_DRIVEN

    ETF_MAP: dict[str, dict[str, float]] = {
        "strong_bullish": {"KODEX 레버리지": 0.7, "KODEX 200": 0.3},
        "moderately_bullish": {"KODEX 200": 0.8, "KODEX 단기채권": 0.2},
        "neutral": {"KODEX 단기채권": 0.5, "KODEX 200": 0.3},
        "moderately_bearish": {"KODEX 인버스": 0.5, "KODEX 단기채권": 0.3},
        "strong_bearish": {
            "KODEX 200선물인버스2X": 0.4,
            "KODEX 단기채권": 0.3,
        },
    }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """Market Pulse 시그널에 따라 ETF 매매 시그널을 생성한다.

        Args:
            universe: ETF 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            ETF별 목표 비중을 점수로 변환한 Signal 리스트.
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")
        pulse_score = market_context.get("pulse_score", 0)

        etf_weights = self.ETF_MAP.get(pulse_signal, self.ETF_MAP["neutral"])
        if pulse_signal not in self.ETF_MAP:
            logger.warning("알 수 없는 시그널 '%s' → neutral 폴백", pulse_signal)

        # 유니버스에서 코드 → Stock 매핑 생성
        code_to_stock = {s.code: s for s in universe}

        signals = []
        for etf_name, weight in etf_weights.items():
            code = _ETF_CODES.get(etf_name)
            if code is None or code not in code_to_stock:
                continue
            # 비중을 점수(-100~+100)로 변환: 비중 * pulse_score 방향성
            direction = 1.0 if pulse_score >= 0 else -1.0
            score = weight * 100 * direction
            # 인버스 ETF는 방향 반전
            if "인버스" in etf_name:
                score = weight * 100 * (-direction)
            signals.append(
                Signal(
                    stock=code_to_stock[code],
                    score=abs(score),
                    factors={"pulse_signal": pulse_signal, "weight": weight},
                    strategy_id=self.strategy_id,
                )
            )

        signals.sort(key=lambda s: s.score, reverse=True)
        return signals

    def should_rebalance_signal_driven(
        self,
        prev_signal: str,
        curr_signal: str,
    ) -> bool:
        """시그널 레벨이 변경되었을 때만 리밸런싱한다.

        Args:
            prev_signal: 이전 시그널 레벨.
            curr_signal: 현재 시그널 레벨.

        Returns:
            레벨이 변경되었으면 True.
        """
        return prev_signal != curr_signal
