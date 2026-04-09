"""리스크 한도 정의.

절대 위반 불가 제약 조건과 리스크 판정 결과 데이터 클래스.
"""

from dataclasses import dataclass

from alphapulse.trading.core.enums import RiskAction


@dataclass
class RiskLimits:
    """절대 위반 불가 리스크 제약 조건.

    AI, 전략, 사용자 모두 오버라이드 불가.
    Config(.env)에서 로드하여 코드 수정 없이 튜닝 가능하다.

    Attributes:
        max_position_weight: 종목당 최대 비중.
        max_sector_weight: 섹터당 최대 비중.
        max_etf_leverage: 레버리지/인버스 ETF 최대 비중.
        max_total_exposure: 총 노출도 상한.
        max_drawdown_soft: 소프트 드로다운 한도 (경고).
        max_drawdown_hard: 하드 드로다운 한도 (강제 축소).
        max_daily_loss: 일간 최대 손실 한도.
        min_cash_ratio: 최소 현금 비율.
        max_single_order_pct: 단일 주문 총자산 비율 상한.
        max_order_to_volume: 주문량/일평균 거래량 비율 상한.
        max_portfolio_var_95: 95% VaR 상한.
    """

    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    max_etf_leverage: float = 0.20
    max_total_exposure: float = 1.0
    max_drawdown_soft: float = 0.10
    max_drawdown_hard: float = 0.15
    max_daily_loss: float = 0.03
    min_cash_ratio: float = 0.05
    max_single_order_pct: float = 0.05
    max_order_to_volume: float = 0.10
    max_portfolio_var_95: float = 0.03


@dataclass
class RiskDecision:
    """리스크 검증 결과.

    Attributes:
        action: 검증 결과 (APPROVE | REDUCE_SIZE | REJECT).
        reason: 사유.
        adjusted_quantity: REDUCE_SIZE일 때 조정된 수량.
    """

    action: RiskAction
    reason: str
    adjusted_quantity: int | None


@dataclass
class RiskAlert:
    """리스크 경고.

    Attributes:
        level: 경고 수준 ("INFO" | "WARNING" | "CRITICAL").
        category: 카테고리 ("drawdown" | "concentration" | "var" | "liquidity").
        message: 경고 메시지.
        current_value: 현재값.
        limit_value: 한도값.
    """

    level: str
    category: str
    message: str
    current_value: float
    limit_value: float
