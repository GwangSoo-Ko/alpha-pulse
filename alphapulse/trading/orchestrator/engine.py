"""TradingEngine — 일일 매매 파이프라인 오케스트레이터.

5단계 파이프라인:
1. 데이터 수집
2. 분석 (전략 시그널 + AI 종합 판단)
3. 포트폴리오 (목표 산출 + 리스크 체크 + 장전 알림)
4. 실행 (주문 제출 + 체결 알림)
5. 사후 관리 (드로다운 체크 + 일일 리포트)

run_daily()는 async 메서드이다 (AI 합성이 async).
CLI entry에서만 이벤트 루프를 시작하여 호출한다.
"""

import logging
from datetime import datetime

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, TradingMode
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)


class TradingEngine:
    """전체 매매 파이프라인 오케스트레이터.

    전략, 포트폴리오, 리스크, 브로커를 통합하여
    일일 매매 사이클을 실행한다.

    Attributes:
        mode: 실행 모드 (BACKTEST, PAPER, LIVE).
        broker: Broker Protocol 구현체.
        strategies: 전략 목록.
    """

    def __init__(
        self,
        mode: TradingMode,
        broker,
        data_provider,
        universe,
        screener,
        strategies: list,
        allocator,
        portfolio_manager,
        risk_manager,
        ai_synthesizer,
        alert,
        audit,
        portfolio_store,
        safeguard=None,
    ) -> None:
        """TradingEngine을 초기화한다.

        Args:
            mode: 실행 모드.
            broker: Broker Protocol 구현체.
            data_provider: 데이터 소스.
            universe: 투자 유니버스 관리자.
            screener: 멀티팩터 랭커.
            strategies: 전략 목록.
            allocator: 멀티전략 배분기.
            portfolio_manager: 포트폴리오 관리자.
            risk_manager: 리스크 매니저.
            ai_synthesizer: AI 전략 종합기 (async).
            alert: TradingAlert 인스턴스 (async).
            audit: AuditLogger 인스턴스.
            portfolio_store: 포트폴리오 저장소.
            safeguard: TradingSafeguard (LIVE 모드 필수).

        Raises:
            ValueError: LIVE 모드에서 safeguard가 None인 경우.
        """
        if mode == TradingMode.LIVE and safeguard is None:
            raise ValueError(
                "실매매 모드에서 safeguard는 필수입니다. "
                "TradingSafeguard 인스턴스를 전달하세요."
            )

        self.mode = mode
        self.broker = broker
        self.data_provider = data_provider
        self.universe = universe
        self.screener = screener
        self.strategies = strategies
        self.allocator = allocator
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.ai_synthesizer = ai_synthesizer
        self.alert = alert
        self.audit = audit
        self.portfolio_store = portfolio_store
        self.safeguard = safeguard

        # 이중 안전장치 (spec 섹션 10): env 스위치 + 터미널 확인
        if mode == TradingMode.LIVE:
            safeguard.check_live_allowed()
            safeguard.confirm_live_start(broker.client.account_no)

    async def run_daily(self, date: str | None = None) -> dict:
        """일일 매매 사이클을 실행한다 — 5 Phase.

        Args:
            date: 기준 날짜 (YYYYMMDD). None이면 오늘.

        Returns:
            실행 결과 요약 딕셔너리.
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        logger.info("=== 일일 매매 사이클 시작: %s (모드: %s) ===", date, self.mode)

        # ── Phase 1: 데이터 수집 ──
        logger.info("Phase 1: 데이터 수집")
        try:
            self.data_provider.refresh()
        except Exception as e:
            logger.error("데이터 수집 실패: %s", e)
            self.audit.log_error("data_provider", e, {"date": date})

        # ── Phase 2: 분석 ──
        logger.info("Phase 2: 분석")
        filtered_universe = self.universe.get_filtered()
        market_context = self._get_market_context(date)

        strategy_signals: dict[str, list] = {}
        for strategy in self.strategies:
            if strategy.should_rebalance(date, date, market_context):
                signals = strategy.generate_signals(filtered_universe, market_context)
                strategy_signals[strategy.strategy_id] = signals
                logger.info(
                    "전략 %s: %d개 시그널", strategy.strategy_id, len(signals)
                )

        # AI 종합 판단
        ai_synthesis = await self._run_ai_synthesis(
            market_context,
            strategy_signals,
            date,
        )

        # ── Phase 3: 포트폴리오 ──
        logger.info("Phase 3: 포트폴리오")
        current_snapshot = self._get_current_snapshot(date)

        self.allocator.adjust_by_market_regime(
            market_context.get("pulse_score", 0),
            ai_synthesis,
        )

        target = self.portfolio_manager.update_target(
            strategy_signals,
            ai_synthesis,
            self.allocator,
            current_snapshot,
        )
        orders = self.portfolio_manager.generate_orders(target, current_snapshot)

        # 리스크 체크
        approved_orders: list[Order] = []
        for order in orders:
            decision = self.risk_manager.check_order(order, current_snapshot)
            self.audit.log_risk_decision(order, decision)

            if decision.action == RiskAction.APPROVE:
                approved_orders.append(order)
            elif decision.action == RiskAction.REDUCE_SIZE:
                order.quantity = decision.adjusted_quantity
                approved_orders.append(order)
            else:
                logger.info(
                    "주문 거부: %s %s — %s",
                    order.stock.code,
                    order.side,
                    decision.reason if hasattr(decision, "reason") else "",
                )

        # 장전 알림
        try:
            await self.alert.pre_market(
                market_context, approved_orders, ai_synthesis
            )
        except Exception as e:
            logger.warning("장전 알림 실패: %s", e)

        # ── Phase 4: 실행 ──
        logger.info("Phase 4: 실행 (%d건)", len(approved_orders))
        execution_results = []
        for order in approved_orders:
            try:
                result = self.broker.submit_order(order)
                self.audit.log_order(order, result)
                execution_results.append(result)
                try:
                    await self.alert.execution(order, result)
                except Exception as e:
                    logger.warning("체결 알림 실패: %s", e)
            except Exception as e:
                logger.error(
                    "주문 실행 실패: %s %s — %s", order.stock.code, order.side, e
                )
                self.audit.log_error("broker", e, {"order": str(order)})

        # ── Phase 5: 사후 관리 ──
        logger.info("Phase 5: 사후 관리")
        snapshot = self._take_snapshot(date)
        self.portfolio_store.save_snapshot(snapshot, self.mode)

        # 드로다운 체크
        dd_action = self.risk_manager.drawdown_mgr.check(snapshot)
        if dd_action == DrawdownAction.DELEVERAGE:
            logger.warning("드로다운 하드 리밋 도달 — 포지션 축소 실행")
            deleverage_orders = (
                self.risk_manager.drawdown_mgr.generate_deleverage_orders(snapshot)
            )
            for dl_order in deleverage_orders:
                try:
                    dl_result = self.broker.submit_order(dl_order)
                    self.audit.log_order(dl_order, dl_result)
                except Exception as e:
                    logger.error("디레버리징 실행 실패: %s", e)
            try:
                await self.alert.risk_alert(
                    "드로다운 하드 리밋 도달. 포지션 50% 축소 실행."
                )
            except Exception as e:
                logger.warning("리스크 알림 실패: %s", e)

        # 일일 리포트
        risk_report = self.risk_manager.daily_report(snapshot)
        try:
            await self.alert.post_market(snapshot, risk_report)
        except Exception as e:
            logger.warning("사후 알림 실패: %s", e)

        logger.info("=== 일일 매매 사이클 완료: %s ===", date)

        return {
            "date": date,
            "mode": self.mode,
            "signals": len(strategy_signals),
            "orders_submitted": len(execution_results),
            "drawdown_action": (
                dd_action.value if hasattr(dd_action, "value") else str(dd_action)
            ),
        }

    async def _run_ai_synthesis(
        self,
        market_context: dict,
        strategy_signals: dict,
        date: str,
    ) -> StrategySynthesis | None:
        """AI 종합 판단을 실행한다. 실패 시 None 반환.

        Returns:
            StrategySynthesis 또는 None (실패 시).
        """
        try:
            current_snapshot = self._get_current_snapshot(date)
            synthesis = await self.ai_synthesizer.synthesize(
                pulse_result=market_context,
                ranked_stocks=[],
                strategy_signals=strategy_signals,
                content_summaries=[],
                feedback_context=None,
                current_portfolio=current_snapshot,
            )
            logger.info(
                "AI 종합 판단 완료: 확신도 %.1f%%", synthesis.conviction_level * 100
            )
            return synthesis
        except Exception as e:
            logger.warning("AI 종합 판단 실패: %s — fallback 진행", e)
            self.audit.log_error("ai_synthesizer", e, {"date": date})
            return None

    def _get_market_context(self, date: str) -> dict:
        """시장 컨텍스트를 수집한다.

        Returns:
            시장 컨텍스트 딕셔너리.
        """
        try:
            return self.data_provider.get_market_context(date)
        except Exception:
            return {"date": date, "pulse_score": 0}

    def _get_current_snapshot(self, date: str) -> PortfolioSnapshot:
        """현재 포트폴리오 스냅샷을 조회한다.

        Returns:
            최신 포트폴리오 스냅샷. 없으면 초기 스냅샷.
        """
        snapshot = self.portfolio_store.get_latest_snapshot()
        if snapshot is None:
            return PortfolioSnapshot(
                date=date,
                cash=0,
                positions=[],
                total_value=0,
                daily_return=0.0,
                cumulative_return=0.0,
                drawdown=0.0,
            )
        return snapshot

    def _take_snapshot(self, date: str) -> PortfolioSnapshot:
        """현재 브로커 상태를 기반으로 스냅샷을 생성한다.

        Returns:
            현재 포트폴리오 스냅샷.
        """
        try:
            positions = self.broker.get_positions()
            balance = self.broker.get_balance()
            cash_str = "0"
            if isinstance(balance, dict):
                output = balance.get("output", balance)
                cash_str = output.get("dnca_tot_amt", "0")
            cash = float(cash_str)
            total_positions_value = sum(
                p.current_price * p.quantity for p in positions
            )
            total_value = cash + total_positions_value
        except Exception as e:
            logger.warning("스냅샷 생성 실패: %s — 이전 스냅샷 사용", e)
            return self._get_current_snapshot(date)

        prev = self._get_current_snapshot(date)
        daily_return = (
            (total_value - prev.total_value) / prev.total_value * 100
            if prev.total_value > 0
            else 0.0
        )

        return PortfolioSnapshot(
            date=date,
            cash=cash,
            positions=positions,
            total_value=total_value,
            daily_return=daily_return,
            cumulative_return=prev.cumulative_return + daily_return,
            drawdown=prev.drawdown,  # DrawdownManager가 별도 관리
        )
