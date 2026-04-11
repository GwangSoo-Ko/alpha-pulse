"""전략 공용 factor 계산 헬퍼.

FactorCalculator가 주입되었으면 universe에 대해 factor_data 매핑을 계산하고,
주입되지 않았으면 빈 dict를 반환한다 (테스트에서 ranker를 mock할 때 사용).
"""

from __future__ import annotations

import logging

from alphapulse.trading.core.models import Stock

logger = logging.getLogger(__name__)

# 공통 기본 팩터 세트 (MultiFactorRanker가 percentile 정규화 시 사용)
_DEFAULT_FACTORS: tuple[str, ...] = (
    "momentum",
    "value",
    "quality",
    "growth",
    "flow",
    "volatility",
)


def _compute_factor_data(
    factor_calc,
    universe: list[Stock],
) -> dict[str, dict]:
    """종목코드 → 팩터 dict 매핑을 생성한다.

    Args:
        factor_calc: FactorCalculator 인스턴스 또는 None.
        universe: 대상 종목 리스트.

    Returns:
        {code: {factor_name: value}} 또는 factor_calc=None이면 빈 dict.
    """
    if factor_calc is None:
        return {}

    factor_data: dict[str, dict] = {}
    for stock in universe:
        row: dict[str, float] = {}
        for name in _DEFAULT_FACTORS:
            method = getattr(factor_calc, name, None)
            if not callable(method):
                continue
            try:
                row[name] = method(stock.code)
            except Exception as e:
                logger.debug("팩터 %s(%s) 계산 실패: %s", name, stock.code, e)
        if row:
            factor_data[stock.code] = row
    return factor_data
