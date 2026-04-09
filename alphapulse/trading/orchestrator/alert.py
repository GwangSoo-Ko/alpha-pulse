"""TradingAlert — 매매 전용 텔레그램 알림.

기존 TelegramNotifier를 재사용하여 매매 관련 알림을 전송한다.
장전 계획, 체결 결과, 일일 성과, 긴급 리스크 알림을 포맷팅한다.
"""

import logging

from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)


class TradingAlert:
    """매매 전용 텔레그램 알림.

    기존 TelegramNotifier를 래핑하여 매매 관련 메시지를 포맷팅한다.
    모든 알림 메서드는 async이며, 전송 실패 시 예외를 삼킨다.

    Attributes:
        notifier: TelegramNotifier 인스턴스 (send 메서드 필요).
    """

    def __init__(self, notifier) -> None:
        """TradingAlert를 초기화한다.

        Args:
            notifier: TelegramNotifier 인스턴스.
        """
        self.notifier = notifier

    async def pre_market(
        self,
        context: dict,
        orders: list[Order],
        synthesis: StrategySynthesis | None,
    ) -> None:
        """장전 매매 계획 알림을 전송한다.

        Args:
            context: 시장 컨텍스트 (pulse_score 등).
            orders: 승인된 주문 목록.
            synthesis: AI 종합 판단 결과 (없으면 None).
        """
        date = context.get("date", "")
        pulse_score = context.get("pulse_score", 0)
        pulse_signal = context.get("pulse_signal", "")

        if not orders:
            body = f"날짜: {date}\nMarket Pulse: {pulse_score:+.1f} ({pulse_signal})\n오늘 매매 없음"
        else:
            buy_orders = [o for o in orders if o.side == "BUY"]
            sell_orders = [o for o in orders if o.side == "SELL"]

            lines = [
                f"날짜: {date}",
                f"Market Pulse: {pulse_score:+.1f} ({pulse_signal})",
            ]
            if synthesis:
                lines.append(f"AI 확신도: {synthesis.conviction_level * 100:.0f}%")
            if buy_orders:
                buy_names = ", ".join(o.stock.name for o in buy_orders[:5])
                lines.append(f"매수 예정: {buy_names} ({len(buy_orders)}건)")
            if sell_orders:
                sell_names = ", ".join(o.stock.name for o in sell_orders[:5])
                lines.append(f"매도 예정: {sell_names} ({len(sell_orders)}건)")
            if synthesis and synthesis.risk_warnings:
                lines.append(f"리스크: {', '.join(synthesis.risk_warnings[:3])}")

            body = "\n".join(lines)

        try:
            await self.notifier.send(
                title="장전 매매 계획",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("장전 알림 전송 실패: %s", e)

    async def execution(self, order: Order, result: OrderResult) -> None:
        """체결 결과 알림을 전송한다.

        Args:
            order: 원래 주문.
            result: 체결 결과.
        """
        status_text = {
            "filled": "체결 완료",
            "partial": "부분 체결",
            "rejected": "주문 거부",
            "pending": "주문 접수",
        }.get(result.status, result.status)

        amount = result.filled_quantity * result.filled_price
        body = (
            f"{order.side} {order.stock.name} ({order.stock.code})\n"
            f"상태: {status_text}\n"
            f"체결: {result.filled_quantity}주 @ {result.filled_price:,.0f}원\n"
            f"금액: {amount:,.0f}원\n"
            f"전략: {order.strategy_id}"
        )

        try:
            await self.notifier.send(
                title=f"체결 알림 — {order.stock.name}",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("체결 알림 전송 실패: %s", e)

    async def post_market(
        self,
        snapshot: PortfolioSnapshot,
        risk_report,
    ) -> None:
        """일일 성과 리포트 알림을 전송한다.

        Args:
            snapshot: 당일 포트폴리오 스냅샷.
            risk_report: 리스크 리포트.
        """
        position_count = len(snapshot.positions)
        risk_summary = ""
        if hasattr(risk_report, "summary"):
            risk_summary = risk_report.summary

        body = (
            f"날짜: {snapshot.date}\n"
            f"총 자산: {snapshot.total_value:,.0f}원\n"
            f"일간 수익률: {snapshot.daily_return:+.2f}%\n"
            f"누적 수익률: {snapshot.cumulative_return:+.2f}%\n"
            f"MDD: {snapshot.drawdown:+.2f}%\n"
            f"보유 종목: {position_count}개\n"
            f"현금: {snapshot.cash:,.0f}원"
        )
        if risk_summary:
            body += f"\n리스크: {risk_summary}"

        try:
            await self.notifier.send(
                title="일일 성과 리포트",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("사후 리포트 알림 전송 실패: %s", e)

    async def risk_alert(self, message: str) -> None:
        """긴급 리스크 알림을 전송한다.

        Args:
            message: 리스크 경고 메시지.
        """
        try:
            await self.notifier.send(
                title="긴급 리스크 알림",
                category="risk",
                analysis=message,
                url="",
            )
        except Exception as e:
            logger.warning("리스크 알림 전송 실패: %s", e)

    async def weekly_report(self, attribution: dict) -> None:
        """주간 성과 귀속 리포트를 전송한다.

        Args:
            attribution: 전략별/팩터별 성과 귀속 딕셔너리.
        """
        lines = ["주간 성과 귀속 분석"]
        strategy_returns = attribution.get("strategy_returns", {})
        for strategy_id, ret in strategy_returns.items():
            lines.append(f"  {strategy_id}: {ret:+.2f}%")

        body = "\n".join(lines)
        try:
            await self.notifier.send(
                title="주간 성과 리포트",
                category="trading",
                analysis=body,
                url="",
            )
        except Exception as e:
            logger.warning("주간 리포트 알림 전송 실패: %s", e)
