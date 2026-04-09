"""전략별 유니버스 선택.

전략마다 다른 투자 유니버스를 적용한다 (ETF 전략은 ETF만, 종목 전략은 주식만 등).
"""

from alphapulse.trading.core.models import Stock


class UniverseSelector:
    """전략 ID에 따라 적절한 종목 유니버스를 선택한다."""

    def __init__(self, strategy_configs: dict[str, dict] | None = None) -> None:
        self.strategy_configs = strategy_configs or {}

    def select(
        self,
        strategy_id: str,
        all_stocks: list[Stock],
        stock_data: dict[str, dict],
    ) -> list[Stock]:
        """전략 설정에 맞는 종목 유니버스를 반환한다."""
        config = self.strategy_configs.get(strategy_id, {})
        include_markets = config.get("include_markets")
        min_market_cap = config.get("min_market_cap")
        min_avg_volume = config.get("min_avg_volume")

        result = []
        for s in all_stocks:
            if include_markets and s.market not in include_markets:
                continue
            data = stock_data.get(s.code, {})
            if min_market_cap and data.get("market_cap", 0) < min_market_cap:
                continue
            if min_avg_volume and data.get("avg_volume", 0) < min_avg_volume:
                continue
            result.append(s)
        return result
