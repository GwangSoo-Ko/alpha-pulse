"""TradingEngine 테스트 — 일일 매매 파이프라인.

모든 서브시스템(전략, 포트폴리오, 리스크, 브로커)은 mock으로 처리한다.
run_daily()는 async 메서드이므로 pytest-asyncio를 사용한다.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, TradingMode
from alphapulse.trading.core.models import (
    Order,
    OrderResult,
    PortfolioSnapshot,
    Signal,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.orchestrator.engine import TradingEngine


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def mock_deps(samsung):
    """TradingEngine의 모든 의존성 mock."""
    deps = {
        "broker": MagicMock(),
        "data_provider": MagicMock(),
        "universe": MagicMock(),
        "screener": MagicMock(),
        "strategies": [MagicMock()],
        "allocator": MagicMock(),
        "portfolio_manager": MagicMock(),
        "risk_manager": MagicMock(),
        "ai_synthesizer": MagicMock(),
        "alert": AsyncMock(),
        "audit": MagicMock(),
        "portfolio_store": MagicMock(),
        "safeguard": None,
    }

    # 전략 mock 설정
    strategy = deps["strategies"][0]
    strategy.strategy_id = "momentum"
    strategy.should_rebalance.return_value = True
    strategy.generate_signals.return_value = [
        Signal(
            stock=samsung,
            score=75.0,
            factors={"momentum": 0.8},
            strategy_id="momentum",
        ),
    ]

    # 유니버스 mock
    deps["universe"].get_filtered.return_value = [samsung]

    # 포트폴리오 mock
    snapshot = PortfolioSnapshot(
        date="20260409",
        cash=50_000_000,
        positions=[],
        total_value=100_000_000,
        daily_return=0.0,
        cumulative_return=0.0,
        drawdown=0.0,
    )
    deps["portfolio_store"].get_latest_snapshot.return_value = snapshot

    # 포트폴리오 매니저 mock
    buy_order = Order(
        stock=samsung,
        side="BUY",
        order_type="MARKET",
        quantity=10,
        price=None,
        strategy_id="momentum",
        reason="팩터 상위",
    )
    deps["portfolio_manager"].update_target.return_value = MagicMock()
    deps["portfolio_manager"].generate_orders.return_value = [buy_order]

    # 리스크 매니저 mock
    risk_decision = MagicMock()
    risk_decision.action = RiskAction.APPROVE
    risk_decision.adjusted_quantity = None
    deps["risk_manager"].check_order.return_value = risk_decision
    deps["risk_manager"].drawdown_mgr = MagicMock()
    deps["risk_manager"].drawdown_mgr.check.return_value = DrawdownAction.NORMAL
    deps["risk_manager"].daily_report.return_value = MagicMock()

    # 브로커 mock
    deps["broker"].submit_order.return_value = OrderResult(
        order_id="ORD001",
        order=buy_order,
        status="filled",
        filled_quantity=10,
        filled_price=72000.0,
        commission=108.0,
        tax=0.0,
        filled_at=datetime.now(),
    )
    deps["broker"].get_positions.return_value = []

    # AI 합성 mock
    synthesis = StrategySynthesis(
        market_view="매수 우위",
        conviction_level=0.72,
        allocation_adjustment={"momentum": 1.0},
        stock_opinions=[],
        risk_warnings=[],
        reasoning="모멘텀 양호",
    )
    deps["ai_synthesizer"].synthesize = AsyncMock(return_value=synthesis)

    # 알로케이터 mock
    deps["allocator"].adjust_by_market_regime.return_value = {"momentum": 1.0}

    return deps


class TestTradingEngineInit:
    """TradingEngine 초기화 테스트."""

    def test_creates_with_mode(self, mock_deps):
        """TradingMode로 초기화한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        assert engine.mode == TradingMode.PAPER

    def test_live_mode_requires_safeguard(self, mock_deps):
        """LIVE 모드에서 safeguard가 None이면 ValueError."""
        mock_deps["safeguard"] = None
        with pytest.raises(ValueError, match="실매매 모드에서 safeguard"):
            TradingEngine(mode=TradingMode.LIVE, **mock_deps)

    def test_live_mode_with_safeguard(self, mock_deps):
        """LIVE 모드에서 safeguard가 있으면 정상 생성."""
        mock_deps["safeguard"] = MagicMock()
        mock_deps["safeguard"].check_live_allowed.return_value = True
        mock_deps["safeguard"].confirm_live_start.return_value = True
        engine = TradingEngine(mode=TradingMode.LIVE, **mock_deps)
        assert engine.mode == TradingMode.LIVE

    def test_live_mode_calls_confirm(self, mock_deps):
        """LIVE 모드에서 check_live_allowed + confirm_live_start 모두 호출."""
        mock_deps["safeguard"] = MagicMock()
        mock_deps["safeguard"].check_live_allowed.return_value = True
        mock_deps["safeguard"].confirm_live_start.return_value = True
        TradingEngine(mode=TradingMode.LIVE, **mock_deps)
        mock_deps["safeguard"].check_live_allowed.assert_called_once()
        mock_deps["safeguard"].confirm_live_start.assert_called_once()


class TestRunDaily:
    """run_daily() 5단계 파이프라인 테스트."""

    @pytest.mark.asyncio
    async def test_full_pipeline_executes(self, mock_deps):
        """5단계 파이프라인이 순서대로 실행된다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # Phase 1: 데이터 수집
        mock_deps["data_provider"].refresh.assert_called_once()

        # Phase 2: 분석
        mock_deps["strategies"][0].should_rebalance.assert_called_once()
        mock_deps["strategies"][0].generate_signals.assert_called_once()
        mock_deps["ai_synthesizer"].synthesize.assert_called_once()

        # Phase 3: 포트폴리오
        mock_deps["portfolio_manager"].update_target.assert_called_once()
        mock_deps["portfolio_manager"].generate_orders.assert_called_once()
        mock_deps["risk_manager"].check_order.assert_called_once()

        # Phase 4: 실행
        mock_deps["broker"].submit_order.assert_called_once()

        # Phase 5: 사후 관리
        mock_deps["alert"].post_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_rejected_order_not_submitted(self, mock_deps):
        """리스크 거부된 주문은 브로커에 전달하지 않는다."""
        risk_decision = MagicMock()
        risk_decision.action = RiskAction.REJECT
        mock_deps["risk_manager"].check_order.return_value = risk_decision

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["broker"].submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_risk_reduce_size(self, mock_deps, samsung):
        """리스크 축소된 주문은 수량을 조정하여 전달한다."""
        risk_decision = MagicMock()
        risk_decision.action = RiskAction.REDUCE_SIZE
        risk_decision.adjusted_quantity = 5
        mock_deps["risk_manager"].check_order.return_value = risk_decision

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        submitted_order = mock_deps["broker"].submit_order.call_args[0][0]
        assert submitted_order.quantity == 5

    @pytest.mark.asyncio
    async def test_drawdown_deleverage(self, mock_deps):
        """드로다운 하드 리밋 도달 시 디레버리징 주문을 실행한다."""
        mock_deps["risk_manager"].drawdown_mgr.check.return_value = (
            DrawdownAction.DELEVERAGE
        )
        deleverage_order = Order(
            stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
            side="SELL",
            order_type="MARKET",
            quantity=50,
            price=None,
            strategy_id="risk",
            reason="드로다운 디레버리징",
        )
        mock_deps[
            "risk_manager"
        ].drawdown_mgr.generate_deleverage_orders.return_value = [
            deleverage_order,
        ]

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # 기본 주문 + 디레버리징 주문
        assert mock_deps["broker"].submit_order.call_count >= 2
        mock_deps["alert"].risk_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_strategy_no_rebalance_skipped(self, mock_deps):
        """리밸런싱 시점이 아닌 전략은 시그널 생성을 건너뛴다."""
        mock_deps["strategies"][0].should_rebalance.return_value = False
        mock_deps["portfolio_manager"].generate_orders.return_value = []

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["strategies"][0].generate_signals.assert_not_called()

    @pytest.mark.asyncio
    async def test_ai_synthesis_failure_uses_fallback(self, mock_deps):
        """AI 종합 판단 실패 시 fallback으로 진행한다."""
        mock_deps["ai_synthesizer"].synthesize = AsyncMock(
            side_effect=Exception("LLM 오류"),
        )

        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        # fallback으로 진행하므로 포트폴리오 단계까지 도달
        mock_deps["portfolio_manager"].update_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_market_alert_sent(self, mock_deps):
        """Phase 3 완료 후 장전 알림을 전송한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["alert"].pre_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_alert_per_order(self, mock_deps):
        """각 주문 체결마다 알림을 전송한다."""
        engine = TradingEngine(mode=TradingMode.PAPER, **mock_deps)
        await engine.run_daily(date="20260409")

        mock_deps["alert"].execution.assert_called_once()
