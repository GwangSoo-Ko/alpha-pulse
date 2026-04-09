"""VaR(Value at Risk) / CVaR 계산기.

포트폴리오 손실 위험을 측정한다.
Historical, Parametric(분산-공분산), CVaR(Expected Shortfall)을 지원한다.
"""

import numpy as np
from scipy.stats import norm


class VaRCalculator:
    """포트폴리오 VaR/CVaR 계산기."""

    def historical_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """과거 수익률 분포 기반 Historical VaR.

        Args:
            returns: 일간 수익률 배열.
            confidence: 신뢰수준 (0~1, 기본 0.95).

        Returns:
            VaR 값 (양수, 손실 크기).
        """
        percentile = (1 - confidence) * 100
        return float(-np.percentile(returns, percentile))

    def parametric_var(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """분산-공분산 기반 파라메트릭 VaR (정규분포 가정).

        Args:
            weights: 종목별 비중 벡터.
            cov_matrix: 공분산 행렬.
            confidence: 신뢰수준.

        Returns:
            VaR 값 (양수).
        """
        portfolio_vol = float(np.sqrt(weights @ cov_matrix @ weights))
        z_score = norm.ppf(confidence)
        return portfolio_vol * z_score

    def cvar(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """Conditional VaR (Expected Shortfall).

        VaR를 초과하는 손실의 평균 — 꼬리 리스크를 반영한다.

        Args:
            returns: 일간 수익률 배열.
            confidence: 신뢰수준.

        Returns:
            CVaR 값 (양수, 손실 크기).
        """
        var = self.historical_var(returns, confidence)
        tail_losses = returns[returns <= -var]
        if len(tail_losses) == 0:
            return var
        return float(-tail_losses.mean())
