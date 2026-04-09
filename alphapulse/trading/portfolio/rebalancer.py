"""포트폴리오 리밸런서.

목표 비중과 현재 포트폴리오의 차이를 주문으로 변환한다.
매도 -> 매수 순서로 정렬하여 자금을 확보한다.
"""

import logging

from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Stock

logger = logging.getLogger(__name__)


class Rebalancer:
    """목표 포트폴리오와 현재 포트폴리오의 차이를 주문으로 변환한다.

    Attributes:
        min_trade_amount: 최소 거래금액 (이하 무시).
    """

    def __init__(self, min_trade_amount: float = 100_000) -> None:
        """Rebalancer를 초기화한다.

        Args:
            min_trade_amount: 최소 거래금액 (원). 이하 차이는 무시.
        """
        self.min_trade_amount = min_trade_amount

    def generate_orders(
        self,
        target_weights: dict[str, float],
        current: PortfolioSnapshot,
        prices: dict[str, float],
        strategy_id: str,
    ) -> list[Order]:
        """현재 -> 목표 차이를 주문 리스트로 변환한다.

        Args:
            target_weights: 종목코드 -> 목표 비중 매핑.
            current: 현재 포트폴리오 스냅샷.
            prices: 종목코드 -> 현재가 매핑.
            strategy_id: 전략 ID.

        Returns:
            Order 리스트 (매도 먼저, 매수 나중).
        """
        total_value = current.total_value
        if total_value <= 0:
            return []

        # 현재 포지션 매핑
        current_holdings: dict[str, dict] = {}
        for pos in current.positions:
            current_holdings[pos.stock.code] = {
                "stock": pos.stock,
                "quantity": pos.quantity,
                "weight": pos.weight,
            }

        sell_orders: list[Order] = []
        buy_orders: list[Order] = []

        # 1. 매도 주문: 현재 보유 중이나 목표에 없거나 비중 감소
        for code, holding in current_holdings.items():
            target_w = target_weights.get(code, 0.0)
            current_w = holding["weight"]
            diff_w = target_w - current_w
            price = prices.get(code, 0)

            if price <= 0:
                continue

            diff_amount = diff_w * total_value
            if diff_amount < -self.min_trade_amount:
                sell_qty = int(abs(diff_amount) / price)
                if target_w == 0.0:
                    sell_qty = holding["quantity"]  # 전량 매도
                if sell_qty > 0:
                    sell_orders.append(
                        Order(
                            stock=holding["stock"],
                            side=Side.SELL,
                            order_type=OrderType.MARKET,
                            quantity=sell_qty,
                            price=None,
                            strategy_id=strategy_id,
                            reason=f"리밸런싱: {current_w:.1%} -> {target_w:.1%}",
                        ),
                    )

        # 2. 매수 주문: 목표에 있으나 미보유이거나 비중 증가
        for code, target_w in target_weights.items():
            current_w = current_holdings.get(code, {}).get("weight", 0.0)
            diff_w = target_w - current_w
            price = prices.get(code, 0)

            if price <= 0:
                continue

            diff_amount = diff_w * total_value
            if diff_amount > self.min_trade_amount:
                buy_qty = int(diff_amount / price)
                if buy_qty > 0:
                    stock = current_holdings.get(code, {}).get(
                        "stock",
                        Stock(code=code, name=code, market="KOSPI"),
                    )
                    buy_orders.append(
                        Order(
                            stock=stock,
                            side=Side.BUY,
                            order_type=OrderType.MARKET,
                            quantity=buy_qty,
                            price=None,
                            strategy_id=strategy_id,
                            reason=f"리밸런싱: {current_w:.1%} -> {target_w:.1%}",
                        ),
                    )

        # 매도 먼저 -> 매수 나중 (자금 확보)
        return sell_orders + buy_orders
