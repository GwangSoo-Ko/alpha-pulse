"""리스크 매니저.

모든 리스크 체크를 통합하는 중앙 관리자.
주문 실행 전 검증, 포트폴리오 전체 점검, 일일 리포트를 담당한다.
"""

import logging

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot
from alphapulse.trading.risk.correlation import CorrelationAnalyzer
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskAlert, RiskDecision, RiskLimits
from alphapulse.trading.risk.report import RiskReport, RiskReportGenerator
from alphapulse.trading.risk.stress_test import StressTest
from alphapulse.trading.risk.var import VaRCalculator

logger = logging.getLogger(__name__)


class RiskManager:
    """모든 리스크 체크 통합 관리자.

    Attributes:
        limits: 리스크 한도.
        var_calc: VaR 계산기.
        drawdown_mgr: 드로다운 관리자.
        correlation_analyzer: 상관관계 분석기.
        stress_test: 스트레스 테스트.
        report_gen: 리포트 생성기.
    """

    def __init__(
        self,
        limits: RiskLimits,
        var_calc: VaRCalculator,
        drawdown_mgr: DrawdownManager,
    ) -> None:
        """RiskManager를 초기화한다.

        Args:
            limits: 리스크 한도 설정.
            var_calc: VaR 계산기.
            drawdown_mgr: 드로다운 관리자.
        """
        self.limits = limits
        self.var_calc = var_calc
        self.drawdown_mgr = drawdown_mgr
        self.correlation_analyzer = CorrelationAnalyzer()
        self.stress_test = StressTest()
        self.report_gen = RiskReportGenerator()

    def check_order(
        self,
        order: Order,
        portfolio: PortfolioSnapshot,
    ) -> RiskDecision:
        """주문 실행 전 리스크를 검증한다.

        RiskChecker Protocol에 맞춰 prices 파라미터 없이 동작한다.
        가격 정보는 포트폴리오의 포지션 데이터 또는 주문의 price 필드에서 조회한다.

        검증 순서:
        1. 일간 손실 한도
        2. 드로다운 상태 (WARN이면 매수 거부)
        3. 최소 현금 비율
        4. 종목 비중 한도
        5. 단일 주문 금액 한도

        Args:
            order: 검증할 주문.
            portfolio: 현재 포트폴리오.

        Returns:
            RiskDecision (APPROVE | REDUCE_SIZE | REJECT).
        """
        # 1. 일간 손실 한도 체크
        if abs(portfolio.daily_return) >= self.limits.max_daily_loss * 100:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason=f"일간 손실 한도 초과: {portfolio.daily_return:.1f}% "
                       f"(한도: {self.limits.max_daily_loss * 100:.1f}%)",
                adjusted_quantity=None,
            )

        # 2. 드로다운 상태 체크
        dd_action = self.drawdown_mgr.check(portfolio)
        if dd_action == DrawdownAction.WARN and order.side == Side.BUY:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason="드로다운 경고 상태 — 신규 매수 중단",
                adjusted_quantity=None,
            )
        if dd_action == DrawdownAction.DELEVERAGE and order.side == Side.BUY:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason="드로다운 한도 초과 — 디레버리징 모드",
                adjusted_quantity=None,
            )

        # 매도 주문은 추가 검증 없이 승인
        if order.side == Side.SELL:
            return RiskDecision(
                action=RiskAction.APPROVE,
                reason="매도 주문 승인",
                adjusted_quantity=None,
            )

        # 3. 최소 현금 비율 체크
        if portfolio.total_value > 0:
            cash_ratio = portfolio.cash / portfolio.total_value
            if cash_ratio < self.limits.min_cash_ratio:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=f"최소 현금 비율 미달: {cash_ratio:.1%} "
                           f"(한도: {self.limits.min_cash_ratio:.1%})",
                    adjusted_quantity=None,
                )

        # 4. 종목 비중 한도 체크
        # 가격: 주문 price, 포지션 current_price, 순서로 조회
        price = order.price or 0
        if price == 0:
            for pos in portfolio.positions:
                if pos.stock.code == order.stock.code:
                    price = pos.current_price
                    break
        if price > 0 and portfolio.total_value > 0:
            # 현재 보유량 + 주문량
            current_qty = 0
            for pos in portfolio.positions:
                if pos.stock.code == order.stock.code:
                    current_qty = pos.quantity
                    break
            new_value = (current_qty + order.quantity) * price
            new_weight = new_value / portfolio.total_value

            if new_weight > self.limits.max_position_weight:
                # 비중 한도 내로 수량 축소
                max_value = portfolio.total_value * self.limits.max_position_weight
                max_qty = int(max_value / price) - current_qty
                if max_qty <= 0:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        reason=f"종목 비중 한도 초과: {new_weight:.1%} "
                               f"(한도: {self.limits.max_position_weight:.1%})",
                        adjusted_quantity=None,
                    )
                return RiskDecision(
                    action=RiskAction.REDUCE_SIZE,
                    reason=f"종목 비중 한도 → 수량 축소: {order.quantity} → {max_qty}",
                    adjusted_quantity=max_qty,
                )

        # 5. 단일 주문 금액 한도
        if price > 0 and portfolio.total_value > 0:
            order_amount = order.quantity * price
            order_pct = order_amount / portfolio.total_value
            if order_pct > self.limits.max_single_order_pct:
                max_amount = portfolio.total_value * self.limits.max_single_order_pct
                max_qty = int(max_amount / price)
                if max_qty <= 0:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        reason=f"단일 주문 한도 초과: {order_pct:.1%}",
                        adjusted_quantity=None,
                    )
                return RiskDecision(
                    action=RiskAction.REDUCE_SIZE,
                    reason=f"단일 주문 한도 → 수량 축소: {order.quantity} → {max_qty}",
                    adjusted_quantity=max_qty,
                )

        return RiskDecision(
            action=RiskAction.APPROVE,
            reason="모든 한도 이내",
            adjusted_quantity=None,
        )

    def check_portfolio(
        self,
        portfolio: PortfolioSnapshot,
    ) -> list[RiskAlert]:
        """포트폴리오 전체 리스크를 점검한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            RiskAlert 리스트.
        """
        alerts: list[RiskAlert] = []

        # 섹터 집중도
        alerts.extend(
            self.report_gen.check_concentration_alerts(
                portfolio,
                max_sector_weight=self.limits.max_sector_weight,
            )
        )

        # 종목 집중도
        for pos in portfolio.positions:
            if pos.weight > self.limits.max_position_weight:
                alerts.append(
                    RiskAlert(
                        level="WARNING",
                        category="concentration",
                        message=f"{pos.stock.name} 비중 {pos.weight:.0%} > "
                                f"한도 {self.limits.max_position_weight:.0%}",
                        current_value=pos.weight,
                        limit_value=self.limits.max_position_weight,
                    )
                )

        # 드로다운 경고
        dd_action = self.drawdown_mgr.check(portfolio)
        if dd_action != DrawdownAction.NORMAL:
            alerts.append(
                RiskAlert(
                    level="CRITICAL" if dd_action == DrawdownAction.DELEVERAGE else "WARNING",
                    category="drawdown",
                    message=f"드로다운 상태: {dd_action.value}",
                    current_value=abs(portfolio.drawdown) / 100,
                    limit_value=self.limits.max_drawdown_soft,
                )
            )

        return alerts

    def daily_report(
        self,
        portfolio: PortfolioSnapshot,
        returns_history: list[float] | None = None,
    ) -> RiskReport:
        """일일 리스크 리포트를 생성한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            returns_history: 일간 수익률 이력 (VaR 계산용).

        Returns:
            RiskReport.
        """
        import numpy as np

        dd_action = self.drawdown_mgr.check(portfolio)

        var_95 = 0.0
        cvar_95 = 0.0
        if returns_history and len(returns_history) >= 20:
            arr = np.array(returns_history)
            var_95 = self.var_calc.historical_var(arr, confidence=0.95)
            cvar_95 = self.var_calc.cvar(arr, confidence=0.95)

        stress_results = self.stress_test.run_all(portfolio)

        return self.report_gen.generate(
            portfolio=portfolio,
            drawdown_status=dd_action.value,
            var_95=var_95,
            cvar_95=cvar_95,
            stress_results=stress_results,
            max_sector_weight=self.limits.max_sector_weight,
        )
