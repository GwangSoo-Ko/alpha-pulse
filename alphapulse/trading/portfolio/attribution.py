"""성과 귀속 분석.

전략별, 섹터별 수익 기여도를 분석한다.
"""

import logging

from alphapulse.trading.core.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class PerformanceAttribution:
    """수익률 원천 분석.

    전략별, 섹터별 수익 기여도를 산출한다.
    """

    def strategy_attribution(
        self,
        prev_snapshot: PortfolioSnapshot,
        curr_snapshot: PortfolioSnapshot,
    ) -> dict[str, float]:
        """전략별 수익 기여도를 산출한다.

        Args:
            prev_snapshot: 전일 스냅샷.
            curr_snapshot: 금일 스냅샷.

        Returns:
            전략ID → 수익 기여도(%) 매핑.
        """
        prev_total = prev_snapshot.total_value
        if prev_total <= 0:
            return {}

        # 전일 포지션 매핑: code → (price, weight, strategy)
        prev_map: dict[str, dict] = {}
        for pos in prev_snapshot.positions:
            prev_map[pos.stock.code] = {
                "price": pos.current_price,
                "weight": pos.weight,
                "strategy_id": pos.strategy_id,
            }

        # 전략별 수익 기여도 집계
        strategy_returns: dict[str, float] = {}
        for pos in curr_snapshot.positions:
            code = pos.stock.code
            strategy = pos.strategy_id
            prev = prev_map.get(code)
            if prev is None or prev["price"] <= 0:
                continue

            stock_return = (pos.current_price - prev["price"]) / prev["price"]
            contribution = prev["weight"] * stock_return * 100  # %

            strategy_returns[strategy] = (
                strategy_returns.get(strategy, 0.0) + contribution
            )

        return strategy_returns

    def sector_attribution(
        self,
        prev_snapshot: PortfolioSnapshot,
        curr_snapshot: PortfolioSnapshot,
    ) -> dict[str, float]:
        """섹터별 수익 기여도를 산출한다.

        Args:
            prev_snapshot: 전일 스냅샷.
            curr_snapshot: 금일 스냅샷.

        Returns:
            섹터명 → 수익 기여도(%) 매핑.
        """
        prev_total = prev_snapshot.total_value
        if prev_total <= 0:
            return {}

        prev_map: dict[str, dict] = {}
        for pos in prev_snapshot.positions:
            prev_map[pos.stock.code] = {
                "price": pos.current_price,
                "weight": pos.weight,
                "sector": pos.stock.sector,
            }

        sector_returns: dict[str, float] = {}
        for pos in curr_snapshot.positions:
            code = pos.stock.code
            prev = prev_map.get(code)
            if prev is None or prev["price"] <= 0:
                continue

            sector = prev["sector"] or "기타"
            stock_return = (pos.current_price - prev["price"]) / prev["price"]
            contribution = prev["weight"] * stock_return * 100

            sector_returns[sector] = (
                sector_returns.get(sector, 0.0) + contribution
            )

        return sector_returns
