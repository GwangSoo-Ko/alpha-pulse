"""투자 제외 필터.

NOTE: stock_data는 외부에서 주입한다 (테스트 용이성 위한 의도적 설계 결정. spec은 내부 조회).
"""

from alphapulse.trading.core.models import Stock


class StockFilter:
    """시가총액, 거래량, 섹터 기준으로 종목을 필터링한다."""

    def __init__(self, config: dict) -> None:
        self.min_market_cap = config.get("min_market_cap")
        self.min_avg_volume = config.get("min_avg_volume")
        self.exclude_sectors = set(config.get("exclude_sectors", []))

    def apply(self, stocks: list[Stock], stock_data: dict[str, dict]) -> list[Stock]:
        """필터 조건을 통과한 종목 리스트를 반환한다."""
        result = []
        for s in stocks:
            data = stock_data.get(s.code, {})
            if self.min_market_cap is not None:
                if data.get("market_cap", 0) < self.min_market_cap:
                    continue
            if self.min_avg_volume is not None:
                if data.get("avg_volume", 0) < self.min_avg_volume:
                    continue
            if s.sector in self.exclude_sectors:
                continue
            result.append(s)
        return result
