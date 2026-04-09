"""상관관계 분석 + 집중도 검사.

포트폴리오 내 종목 간 상관관계를 분석하고,
높은 상관관계 집중 시 경고를 생성한다.
"""

import logging

import numpy as np
import pandas as pd

from alphapulse.trading.core.models import PortfolioSnapshot
from alphapulse.trading.risk.limits import RiskAlert

logger = logging.getLogger(__name__)

# 상관관계 집중도 경고 임계값
_CORRELATION_THRESHOLD = 0.80
# 합산 비중 임계값 (높은 상관 종목 쌍의 비중 합)
_WEIGHT_THRESHOLD = 0.40


class CorrelationAnalyzer:
    """포트폴리오 상관관계 분석기.

    종목 간 상관관계를 계산하고, 높은 상관관계 집중 리스크를 감지한다.
    """

    def calculate_correlation_matrix(
        self,
        returns_data: dict[str, np.ndarray],
    ) -> pd.DataFrame:
        """종목 간 상관관계 행렬을 계산한다.

        Args:
            returns_data: 종목코드 -> 일간 수익률 배열 매핑.

        Returns:
            상관관계 행렬 (pd.DataFrame).
        """
        codes = list(returns_data.keys())
        df = pd.DataFrame(returns_data, columns=codes)
        return df.corr()

    def check_concentration(
        self,
        portfolio: PortfolioSnapshot,
        corr_matrix: pd.DataFrame,
        corr_threshold: float = _CORRELATION_THRESHOLD,
        weight_threshold: float = _WEIGHT_THRESHOLD,
    ) -> list[RiskAlert]:
        """높은 상관관계 종목 집중도를 검사한다.

        상관계수가 corr_threshold 이상인 종목 쌍의 비중 합이
        weight_threshold를 초과하면 경고를 생성한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            corr_matrix: 상관관계 행렬.
            corr_threshold: 상관관계 경고 임계값 (기본 0.80).
            weight_threshold: 합산 비중 경고 임계값 (기본 0.40).

        Returns:
            RiskAlert 리스트.
        """
        alerts: list[RiskAlert] = []

        # 포지션 비중 매핑
        weight_map: dict[str, float] = {}
        name_map: dict[str, str] = {}
        for pos in portfolio.positions:
            weight_map[pos.stock.code] = pos.weight
            name_map[pos.stock.code] = pos.stock.name

        codes = [c for c in weight_map if c in corr_matrix.columns]

        # 모든 종목 쌍 순회
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                code_a, code_b = codes[i], codes[j]
                corr = corr_matrix.loc[code_a, code_b]
                combined_weight = weight_map[code_a] + weight_map[code_b]

                if corr >= corr_threshold and combined_weight >= weight_threshold:
                    name_a = name_map.get(code_a, code_a)
                    name_b = name_map.get(code_b, code_b)
                    alerts.append(
                        RiskAlert(
                            level="WARNING",
                            category="correlation",
                            message=(
                                f"{name_a}\u2013{name_b} 상관계수 {corr:.2f}, "
                                f"합산 비중 {combined_weight:.0%} > "
                                f"한도 {weight_threshold:.0%}"
                            ),
                            current_value=corr,
                            limit_value=corr_threshold,
                        ),
                    )

        return alerts
