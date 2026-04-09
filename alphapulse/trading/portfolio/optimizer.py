"""포트폴리오 최적화.

평균-분산(Markowitz), 리스크 패리티, 최소 분산 최적화를 제공한다.
scipy.optimize를 사용한다.
"""

import logging

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """수학적 포트폴리오 최적화.

    세 가지 최적화 방법을 제공하며, 시장 상황에 따라 자동 선택한다.
    """

    def mean_variance(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        max_weight: float = 1.0,
        risk_free_rate: float = 0.035,
    ) -> np.ndarray:
        """마코위츠 평균-분산 최적화 (최대 샤프 비율).

        Args:
            expected_returns: 종목별 기대수익률 벡터.
            cov_matrix: 공분산 행렬.
            max_weight: 종목당 최대 비중.
            risk_free_rate: 무위험 이자율 (연).

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = len(expected_returns)
        if n == 1:
            return np.array([1.0])

        def neg_sharpe(w):
            port_ret = w @ expected_returns
            port_vol = np.sqrt(w @ cov_matrix @ w)
            if port_vol < 1e-10:
                return 0.0
            return -(port_ret - risk_free_rate) / port_vol

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, max_weight)] * n
        x0 = np.ones(n) / n

        result = minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("평균-분산 최적화 실패 -> 균등 배분")
        return np.ones(n) / n

    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """리스크 패리티 최적화.

        각 종목의 리스크 기여도를 균등화한다.

        Args:
            cov_matrix: 공분산 행렬.

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = cov_matrix.shape[0]
        if n == 1:
            return np.array([1.0])

        def risk_parity_obj(w):
            sigma_p = np.sqrt(w @ cov_matrix @ w)
            if sigma_p < 1e-10:
                return 0.0
            marginal = cov_matrix @ w
            risk_contrib = w * marginal / sigma_p
            target_rc = sigma_p / n
            return np.sum((risk_contrib - target_rc) ** 2)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.01, 1.0)] * n
        x0 = np.ones(n) / n

        result = minimize(
            risk_parity_obj,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("리스크 패리티 최적화 실패 -> 균등 배분")
        return np.ones(n) / n

    def min_variance(self, cov_matrix: np.ndarray) -> np.ndarray:
        """최소 분산 포트폴리오.

        포트폴리오 전체 변동성을 최소화한다.

        Args:
            cov_matrix: 공분산 행렬.

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = cov_matrix.shape[0]
        if n == 1:
            return np.array([1.0])

        def portfolio_variance(w):
            return w @ cov_matrix @ w

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * n
        x0 = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("최소 분산 최적화 실패 -> 균등 배분")
        return np.ones(n) / n

    def select_method(self, market_context: dict) -> str:
        """시장 상황에 따라 최적화 방법을 자동 선택한다.

        Args:
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            최적화 방법 문자열 ("mean_variance" | "risk_parity" | "min_variance").
        """
        signal = market_context.get("pulse_signal", "neutral")

        if signal in ("strong_bullish", "moderately_bullish"):
            return "mean_variance"
        elif signal in ("strong_bearish",):
            return "min_variance"
        else:
            return "risk_parity"
