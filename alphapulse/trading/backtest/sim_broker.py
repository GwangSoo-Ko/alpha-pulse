"""시뮬레이션 브로커 — 가상 체결 엔진.

Broker Protocol을 구현하여 백테스트에서 사용한다.
MARKET 주문은 당일 종가, LIMIT 주문은 고가/저가 범위로 체결 여부를 결정한다.
"""

import uuid
from datetime import datetime

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, OrderResult, Position, Stock


class SimBroker:
    """가상 체결 브로커.

    내부에 현금과 포지션 상태를 관리하며, 데이터 피드에서 가격을 가져와 체결한다.
    CostModel을 통해 수수료, 세금, 슬리피지를 반영한다.

    Attributes:
        cash: 보유 현금 (원).
        trade_log: 체결 이력 (OrderResult 리스트).
    """

    def __init__(self, cost_model: CostModel, data_feed: HistoricalDataFeed,
                 initial_cash: float) -> None:
        """초기화.

        Args:
            cost_model: 거래 비용 모델.
            data_feed: 히스토리 데이터 피드.
            initial_cash: 초기 투자금 (원).
        """
        self.cost_model = cost_model
        self.data_feed = data_feed
        self.cash: float = initial_cash
        self._positions: dict[str, dict] = {}  # code → {stock, quantity, avg_price, strategy_id}
        self.trade_log: list[OrderResult] = []
        self.current_date: str = ""

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 체결한다.

        MARKET: 당일 종가로 체결 (보수적 가정).
        LIMIT 매수: 저가 <= 지정가이면 지정가로 체결.
        LIMIT 매도: 고가 >= 지정가이면 지정가로 체결.

        Args:
            order: 매매 주문.

        Returns:
            체결 결과.
        """
        bar = self.data_feed.get_bar(order.stock.code)
        if bar is None:
            return self._rejected(order, "당일 데이터 없음")

        if order.side == Side.BUY:
            return self._execute_buy(order, bar)
        else:
            return self._execute_sell(order, bar)

    def cancel_order(self, order_id: str) -> bool:
        """주문 취소 (SimBroker는 즉시 체결이므로 항상 False)."""
        return False

    def get_balance(self) -> dict:
        """잔고 정보를 반환한다."""
        positions_value = sum(
            p["quantity"] * self.data_feed.get_latest_price(code)
            for code, p in self._positions.items()
        )
        return {
            "cash": self.cash,
            "positions_value": positions_value,
            "total_value": self.cash + positions_value,
        }

    def get_positions(self) -> list[Position]:
        """보유 포지션 목록을 반환한다."""
        result = []
        for code, p in self._positions.items():
            current_price = self.data_feed.get_latest_price(code)
            pnl = (current_price - p["avg_price"]) * p["quantity"]
            total = self.get_balance()["total_value"]
            weight = (p["quantity"] * current_price) / total if total > 0 else 0.0
            result.append(Position(
                stock=p["stock"],
                quantity=p["quantity"],
                avg_price=p["avg_price"],
                current_price=current_price,
                unrealized_pnl=pnl,
                weight=weight,
                strategy_id=p["strategy_id"],
            ))
        return result

    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태를 조회한다."""
        for trade in self.trade_log:
            if trade.order_id == order_id:
                return trade
        return self._rejected(
            Order(stock=Stock(code="", name="", market=""),
                  side=Side.BUY, order_type=OrderType.MARKET,
                  quantity=0, price=None, strategy_id=""),
            "주문 없음",
        )

    def _execute_buy(self, order: Order, bar) -> OrderResult:
        """매수 체결 로직."""
        fill_price = self._determine_fill_price(order, bar)
        if fill_price is None:
            return self._rejected(order, "LIMIT 미체결 (저가 > 지정가)")

        slippage_pct = self.cost_model.estimate_slippage(order, bar.volume)
        adjusted_price = fill_price * (1 + slippage_pct)

        total_amount = order.quantity * adjusted_price
        commission = self.cost_model.calculate_commission(total_amount)
        total_cost = total_amount + commission

        if total_cost > self.cash:
            return self._rejected(order, "현금 부족")

        self.cash -= total_cost
        self._update_position_buy(order, adjusted_price)

        result = OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="filled",
            filled_quantity=order.quantity,
            filled_price=adjusted_price,
            commission=commission,
            tax=0.0,
            filled_at=datetime.now(),
            trade_date=self.current_date,
        )
        self.trade_log.append(result)
        return result

    def _execute_sell(self, order: Order, bar) -> OrderResult:
        """매도 체결 로직."""
        pos = self._positions.get(order.stock.code)
        if pos is None or pos["quantity"] < order.quantity:
            return self._rejected(order, "보유 수량 부족")

        fill_price = self._determine_fill_price(order, bar)
        if fill_price is None:
            return self._rejected(order, "LIMIT 미체결 (고가 < 지정가)")

        slippage_pct = self.cost_model.estimate_slippage(order, bar.volume)
        adjusted_price = fill_price * (1 - slippage_pct)

        total_amount = order.quantity * adjusted_price
        is_etf = order.stock.market == "ETF"
        commission = self.cost_model.calculate_commission(total_amount)
        tax = self.cost_model.calculate_tax(total_amount, is_etf=is_etf)

        self.cash += total_amount - commission - tax
        self._update_position_sell(order)

        result = OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="filled",
            filled_quantity=order.quantity,
            filled_price=adjusted_price,
            commission=commission,
            tax=tax,
            filled_at=datetime.now(),
            trade_date=self.current_date,
        )
        self.trade_log.append(result)
        return result

    def _determine_fill_price(self, order: Order, bar) -> float | None:
        """체결가를 결정한다.

        MARKET: 종가.
        LIMIT 매수: 저가 <= 지정가이면 지정가, 아니면 None.
        LIMIT 매도: 고가 >= 지정가이면 지정가, 아니면 None.
        """
        if order.order_type == OrderType.MARKET:
            return bar.close

        if order.side == Side.BUY:
            if bar.low <= order.price:
                return order.price
            return None
        else:
            if bar.high >= order.price:
                return order.price
            return None

    def _update_position_buy(self, order: Order, fill_price: float) -> None:
        """매수로 포지션을 갱신한다."""
        code = order.stock.code
        if code in self._positions:
            pos = self._positions[code]
            total_qty = pos["quantity"] + order.quantity
            pos["avg_price"] = (
                (pos["avg_price"] * pos["quantity"] + fill_price * order.quantity)
                / total_qty
            )
            pos["quantity"] = total_qty
        else:
            self._positions[code] = {
                "stock": order.stock,
                "quantity": order.quantity,
                "avg_price": fill_price,
                "strategy_id": order.strategy_id,
            }

    def _update_position_sell(self, order: Order) -> None:
        """매도로 포지션을 갱신한다."""
        code = order.stock.code
        pos = self._positions[code]
        pos["quantity"] -= order.quantity
        if pos["quantity"] == 0:
            del self._positions[code]

    @staticmethod
    def _rejected(order: Order, reason: str) -> OrderResult:
        """거부 결과를 생성한다."""
        return OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="rejected",
            filled_quantity=0,
            filled_price=0.0,
            commission=0.0,
            tax=0.0,
            filled_at=None,
        )
