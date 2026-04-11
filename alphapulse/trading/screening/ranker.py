"""멀티팩터 종목 랭킹.

팩터별 percentile 정규화 → 가중 합산 → 종합 점수 산출.
"""

from datetime import datetime

from alphapulse.trading.core.models import Signal, Stock

# 높을수록 좋은 팩터 vs 낮을수록 좋은 팩터
# 주의: factors.py의 일부 메서드는 이미 역수로 반환 (예: quality_debt_ratio)
#       그런 경우 여기에 추가하지 않는다.
# raw 부채비율, downside_vol을 직접 사용할 때만 inverse 처리.
_INVERSE_FACTORS = {
    "volatility",
    "downside_vol",
    "debt_ratio_raw",  # 명시적으로 raw 부채비율 (선택적)
}


class MultiFactorRanker:
    """멀티팩터 종합 랭킹.

    Attributes:
        weights: 팩터별 가중치 딕셔너리 (합계 1.0 권장).
    """

    def __init__(self, weights: dict[str, float]) -> None:
        self.weights = weights

    def rank(
        self,
        stocks: list[Stock],
        factor_data: dict[str, dict],
        strategy_id: str,
    ) -> list[Signal]:
        """종목별 종합 점수를 계산하고 내림차순 정렬한다.

        Args:
            stocks: 대상 종목 리스트.
            factor_data: 종목코드 → {팩터명: 원시값} 매핑.
            strategy_id: 전략 ID.

        Returns:
            점수 내림차순 Signal 리스트.
        """
        factor_names = list(self.weights.keys())

        # 1. 팩터별 percentile 계산
        percentiles = self._calculate_percentiles(stocks, factor_data, factor_names)

        # 2. 가중 합산 → 종합 점수 (-100 ~ +100)
        signals = []
        for s in stocks:
            code_pcts = percentiles.get(s.code, {})
            total_weight = 0
            weighted_sum = 0

            factor_scores = {}
            for factor in factor_names:
                pct = code_pcts.get(factor)
                if pct is None:
                    continue
                w = self.weights[factor]
                weighted_sum += pct * w
                total_weight += w
                factor_scores[factor] = round(pct, 1)

            if total_weight > 0:
                # 0~100 percentile → -100~+100 스케일
                raw_score = weighted_sum / total_weight
                score = (raw_score - 50) * 2
            else:
                score = 0

            score = max(-100, min(100, round(score, 1)))

            signals.append(
                Signal(
                    stock=s,
                    score=score,
                    factors=factor_scores,
                    strategy_id=strategy_id,
                    timestamp=datetime.now(),
                )
            )

        signals.sort(key=lambda sig: sig.score, reverse=True)
        return signals

    def _calculate_percentiles(
        self,
        stocks: list[Stock],
        factor_data: dict[str, dict],
        factor_names: list[str],
    ) -> dict[str, dict[str, float]]:
        """팩터별 percentile(0~100)을 계산한다.

        Args:
            stocks: 종목 리스트.
            factor_data: 팩터 원시값.
            factor_names: 계산할 팩터 이름 목록.

        Returns:
            종목코드 → {팩터명: percentile} 매핑.
        """
        result: dict[str, dict[str, float]] = {s.code: {} for s in stocks}

        for factor in factor_names:
            # 해당 팩터의 값이 있는 종목만 수집
            values: list[tuple[str, float]] = []
            for s in stocks:
                data = factor_data.get(s.code, {})
                val = data.get(factor)
                if val is not None:
                    values.append((s.code, val))

            if not values:
                continue

            # 정렬 (inverse 팩터는 역순)
            reverse = factor not in _INVERSE_FACTORS
            sorted_vals = sorted(values, key=lambda x: x[1], reverse=reverse)

            # percentile 할당 (순위 기반)
            n = len(sorted_vals)
            for rank_idx, (code, _) in enumerate(sorted_vals):
                if n == 1:
                    pct = 50.0
                else:
                    pct = (1 - rank_idx / (n - 1)) * 100
                result[code][factor] = pct

        return result
