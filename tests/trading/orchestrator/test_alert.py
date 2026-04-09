"""TradingAlert 테스트 — 텔레그램 매매 알림.

기존 TelegramNotifier를 mock으로 처리한다.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.orchestrator.alert import TradingAlert


@pytest.fixture
def mock_notifier():
    notifier = AsyncMock()
    notifier.send.return_value = True
    return notifier


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


class TestPreMarketAlert:
    """장전 매매 계획 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_pre_market_plan(self, mock_notifier, samsung):
        """매매 계획을 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        context = {"date": "20260409", "pulse_score": 35.2, "pulse_signal": "매수 우위"}
        orders = [
            Order(stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
                  quantity=10, price=None, strategy_id="momentum"),
        ]
        synthesis = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.72,
            allocation_adjustment={},
            stock_opinions=[],
            risk_warnings=[],
            reasoning="모멘텀 양호",
        )
        await alert.pre_market(context, orders, synthesis)
        mock_notifier.send.assert_called_once()
        call_args = mock_notifier.send.call_args
        assert "매매 계획" in call_args[1].get("title", "") or "매매 계획" in str(call_args)

    @pytest.mark.asyncio
    async def test_pre_market_no_orders(self, mock_notifier):
        """주문이 없으면 '매매 없음'을 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        context = {"date": "20260409", "pulse_score": 0}
        await alert.pre_market(context, [], None)
        mock_notifier.send.assert_called_once()


class TestExecutionAlert:
    """체결 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_execution_result(self, mock_notifier, samsung):
        """체결 결과를 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=10, price=72000, strategy_id="momentum",
        )
        result = OrderResult(
            order_id="ORD001", order=order, status="filled",
            filled_quantity=10, filled_price=72000.0,
            commission=108.0, tax=0.0, filled_at=datetime.now(),
        )
        await alert.execution(order, result)
        mock_notifier.send.assert_called_once()


class TestPostMarketAlert:
    """사후 리포트 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_daily_summary(self, mock_notifier):
        """일일 성과를 텔레그램으로 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        snapshot = PortfolioSnapshot(
            date="20260409", cash=50_000_000,
            positions=[], total_value=108_350_000,
            daily_return=0.42, cumulative_return=8.3, drawdown=-3.2,
        )
        risk_report = MagicMock()
        risk_report.summary = "VaR -2.1%, MDD -3.2%"
        await alert.post_market(snapshot, risk_report)
        mock_notifier.send.assert_called_once()


class TestRiskAlert:
    """긴급 리스크 알림 테스트."""

    @pytest.mark.asyncio
    async def test_sends_risk_warning(self, mock_notifier):
        """긴급 리스크 알림을 전송한다."""
        alert = TradingAlert(notifier=mock_notifier)
        await alert.risk_alert("드로다운 하드 리밋 도달. 포지션 50% 축소 실행.")
        mock_notifier.send.assert_called_once()
        call_args = mock_notifier.send.call_args
        assert "리스크" in str(call_args) or "긴급" in str(call_args)


class TestAlertFailureHandling:
    """알림 실패 처리 테스트."""

    @pytest.mark.asyncio
    async def test_notifier_failure_does_not_raise(self, samsung):
        """텔레그램 전송 실패해도 예외를 발생시키지 않는다."""
        mock_notifier = AsyncMock()
        mock_notifier.send.side_effect = Exception("네트워크 오류")
        alert = TradingAlert(notifier=mock_notifier)
        # 예외 없이 완료
        await alert.risk_alert("테스트 알림")


class TestWeeklyReport:
    """주간 성과 리포트 테스트."""

    @pytest.fixture
    def alert(self, mock_notifier):
        return TradingAlert(notifier=mock_notifier)

    @pytest.mark.asyncio
    async def test_weekly_report_sends(self, alert):
        """주간 리포트를 텔레그램으로 전송한다."""
        attribution = {"strategy_returns": {"topdown_etf": 0.012, "momentum": 0.008}}
        await alert.weekly_report(attribution)
        alert.notifier.send.assert_called_once()
        msg = alert.notifier.send.call_args[1].get("analysis", str(alert.notifier.send.call_args))
        assert "주간" in msg or "주간" in str(alert.notifier.send.call_args)
