"""백테스트 기본 주문 생성기.

전략 시그널을 받아 포트폴리오 목표를 산출하고,
리스크 검증을 거쳐 주문 리스트를 반환한다.
"""

import logging

from alphapulse.trading.core.enums import OrderType, RiskAction, Side
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    Signal,
)

logger = logging.getLogger(__name__)


def make_default_order_generator(
    top_n: int = 20,
    initial_capital: float = 100_000_000,
):
    """간단한 기본 주문 생성기를 반환한다.

    전략 시그널 상위 N종목을 균등 비중으로 매수하는 naive rebalancing.
    백테스트 초기 검증용으로 사용한다.

    Args:
        top_n: 각 전략에서 상위 몇 종목을 매수할지.
        initial_capital: 기준 자본. 포지션 사이즈 계산용.

    Returns:
        order_generator 함수 (signals, snapshot, broker) → list[Order].
    """

    def order_generator(
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        broker,
    ) -> list[Order]:
        """시그널을 주문으로 변환한다 (naive equal-weight).

        Args:
            signals: 모든 전략의 시그널 리스트.
            snapshot: 현재 포트폴리오 스냅샷.
            broker: 브로커 (가격 조회용, SimBroker).

        Returns:
            주문 리스트.
        """
        if not signals:
            return []

        # 시그널 점수 내림차순 정렬, 상위 N개 선택
        sorted_signals = sorted(signals, key=lambda s: s.score, reverse=True)
        top_signals = sorted_signals[:top_n]

        if not top_signals:
            return []

        # 균등 비중
        per_weight = 1.0 / len(top_signals)
        total_value = snapshot.total_value if snapshot.total_value > 0 else initial_capital
        per_position_value = total_value * per_weight

        orders: list[Order] = []
        # 현재 보유 종목 맵 (quick lookup)
        held = {p.stock.code: p for p in snapshot.positions}
        target_codes = {s.stock.code for s in top_signals}

        # 1. 매도: 보유 중인데 타깃이 아닌 종목
        for pos in snapshot.positions:
            if pos.stock.code not in target_codes and pos.quantity > 0:
                orders.append(
                    Order(
                        stock=pos.stock,
                        side=Side.SELL,
                        order_type=OrderType.MARKET,
                        quantity=pos.quantity,
                        price=None,
                        strategy_id="backtest_default",
                        reason="리밸런싱 매도",
                    )
                )

        # 2. 매수: 타깃인데 보유하지 않거나 비중 미달
        for sig in top_signals:
            current_qty = held[sig.stock.code].quantity if sig.stock.code in held else 0

            # 현재 가격 조회
            price = _get_price(broker, sig.stock.code)
            if price is None or price <= 0:
                continue

            target_qty = int(per_position_value / price)
            if target_qty <= current_qty:
                continue  # 이미 충분

            buy_qty = target_qty - current_qty
            if buy_qty <= 0:
                continue

            orders.append(
                Order(
                    stock=sig.stock,
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=buy_qty,
                    price=None,
                    strategy_id=sig.strategy_id or "backtest_default",
                    reason=f"점수 {sig.score:.1f}",
                )
            )

        return orders

    return order_generator


def make_risk_checked_order_generator(
    portfolio_manager,
    risk_manager,
    top_n: int = 20,
):
    """PortfolioManager + RiskManager를 사용한 주문 생성기.

    포트폴리오 매니저가 목표 포트폴리오를 산출하고, 리스크 매니저가
    각 주문을 검증하는 완전한 파이프라인.

    Args:
        portfolio_manager: PortfolioManager 인스턴스.
        risk_manager: RiskManager 인스턴스.
        top_n: 전략당 상위 N종목.

    Returns:
        order_generator 함수.
    """
    default_gen = make_default_order_generator(top_n=top_n)

    def order_generator(
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        broker,
    ) -> list[Order]:
        # 기본 생성기로 raw 주문 생성
        raw_orders = default_gen(signals, snapshot, broker)

        # 리스크 검증
        approved: list[Order] = []
        for order in raw_orders:
            try:
                decision = risk_manager.check_order(order, snapshot)
                if decision.action == RiskAction.APPROVE:
                    approved.append(order)
                elif decision.action == RiskAction.REDUCE_SIZE:
                    if decision.adjusted_quantity and decision.adjusted_quantity > 0:
                        order.quantity = decision.adjusted_quantity
                        approved.append(order)
                # REJECT: 스킵
            except Exception as e:
                logger.debug("리스크 체크 예외 (통과 처리): %s", e)
                approved.append(order)

        return approved

    return order_generator


def _get_price(broker, code: str) -> float | None:
    """브로커 또는 브로커의 data_feed에서 현재 가격을 조회한다."""
    # SimBroker에 execution_prices가 있으면 사용
    prices = getattr(broker, "execution_prices", None)
    if isinstance(prices, dict) and code in prices:
        return prices[code]

    # get_current_price 메서드가 있으면 사용
    get_price = getattr(broker, "get_current_price", None)
    if callable(get_price):
        try:
            return get_price(code)
        except Exception:
            pass

    # SimBroker는 data_feed를 가지고 있음 — get_latest_price / get_bar 사용
    data_feed = getattr(broker, "data_feed", None)
    if data_feed is not None:
        get_latest = getattr(data_feed, "get_latest_price", None)
        if callable(get_latest):
            try:
                price = get_latest(code)
                if price is not None:
                    return price
            except Exception:
                pass
        get_bar = getattr(data_feed, "get_bar", None)
        if callable(get_bar):
            try:
                bar = get_bar(code)
                if bar is not None:
                    return getattr(bar, "close", None)
            except Exception:
                pass

    return None
