"""포트폴리오 데이터 모델.

TargetPortfolio -- 목표 포트폴리오를 표현하는 데이터 클래스.
"""

from dataclasses import dataclass, field


@dataclass
class TargetPortfolio:
    """목표 포트폴리오.

    PortfolioManager.update_target()의 반환 타입.

    Attributes:
        date: 기준 날짜 (YYYYMMDD).
        positions: 종목코드 -> 목표 비중 매핑.
        cash_weight: 현금 비중 (0~1).
        strategy_allocations: 전략ID -> 자금 배분 비율 매핑.
    """

    date: str
    positions: dict[str, float] = field(default_factory=dict)  # code -> target weight
    cash_weight: float = 0.0
    strategy_allocations: dict[str, float] = field(
        default_factory=dict,
    )  # strategy_id -> capital allocation
