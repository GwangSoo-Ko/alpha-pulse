"""백테스트 엔진 — 시간 순서대로 전략 파이프라인 시뮬레이션.

거래일을 순회하며 데이터 피드 전진 → 시그널 생성 → 주문 생성 → 체결 → 스냅샷 저장.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.metrics import BacktestMetrics
from alphapulse.trading.backtest.sim_broker import SimBroker
from alphapulse.trading.core.calendar import KRXCalendar
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, OrderResult, PortfolioSnapshot, Signal


@dataclass
class BacktestConfig:
    """백테스트 설정.

    Attributes:
        initial_capital: 초기 투자금 (원).
        start_date: 시작일 (YYYYMMDD).
        end_date: 종료일 (YYYYMMDD).
        cost_model: 거래 비용 모델.
        benchmark: 벤치마크 코드 (기본 KOSPI).
        use_ai: AI 종합 판단 사용 여부 (기본 False).
        risk_free_rate: 무위험 이자율 (연율, 기본 3.5%).
    """

    initial_capital: float
    start_date: str
    end_date: str
    cost_model: CostModel
    benchmark: str = "KOSPI"
    use_ai: bool = False
    risk_free_rate: float = 0.035


@dataclass
class BacktestResult:
    """백테스트 결과.

    Attributes:
        snapshots: 일별 포트폴리오 스냅샷 목록.
        trades: 체결 이력.
        metrics: 성과 지표 딕셔너리.
        config: 백테스트 설정.
    """

    snapshots: list[PortfolioSnapshot]
    trades: list[OrderResult]
    metrics: dict
    config: BacktestConfig


class BacktestEngine:
    """백테스트 엔진.

    거래일을 순회하며 전략 파이프라인을 시뮬레이션한다.
    데이터 피드, 전략, 주문 생성기를 주입받아 동작한다.

    **설계 의도 (Phase 3 Simplification):**
    이 엔진은 order_generator callable을 주입받아 시그널 → 주문 변환을 외부에 위임한다.
    이는 의도적인 단순화이다. Phase 3에서는 PortfolioManager, RiskManager 없이도
    백테스트 루프 자체를 독립적으로 테스트할 수 있게 한다. Phase 4 (TradingEngine)에서
    PortfolioManager.rebalance() → RiskManager.check_order() → order 생성 파이프라인을
    order_generator로 주입하여 완전한 통합을 달성한다.

    Attributes:
        config: 백테스트 설정.
        data_feed: 히스토리 데이터 피드.
        broker: 시뮬레이션 브로커.
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_feed: HistoricalDataFeed,
        strategies: list,
        order_generator: Callable[
            [list[Signal], PortfolioSnapshot, SimBroker], list[Order]
        ],
    ) -> None:
        """초기화.

        Args:
            config: 백테스트 설정.
            data_feed: 히스토리 데이터 피드.
            strategies: 전략 리스트 (Strategy Protocol 구현체).
            order_generator: 시그널 → 주문 변환 함수.
        """
        self.config = config
        self.data_feed = data_feed
        self.strategies = strategies
        self.order_generator = order_generator
        self.broker = SimBroker(
            cost_model=config.cost_model,
            data_feed=data_feed,
            initial_cash=config.initial_capital,
        )
        self._calendar = KRXCalendar()
        self._metrics_calc = BacktestMetrics()

    def run(self) -> BacktestResult:
        """백테스트를 실행한다.

        거래일을 순회하며:
        1. data_feed.advance_to(date) — 미래 데이터 차단.
        2. 전략별 시그널 생성.
        3. 주문 생성 → SimBroker 체결.
        4. 일별 스냅샷 저장.

        Returns:
            BacktestResult (스냅샷, 체결 이력, 성과 지표).
        """
        trading_days = self._calendar.trading_days_between(
            self.config.start_date,
            self.config.end_date,
        )

        snapshots: list[PortfolioSnapshot] = []

        for date in trading_days:
            self.data_feed.advance_to(date)

            # 전략별 시그널 수집
            all_signals: list[Signal] = []
            for strategy in self.strategies:
                if strategy.should_rebalance("", date, {}):
                    signals = strategy.generate_signals([], {})
                    all_signals.extend(signals)

            # 현재 스냅샷 생성 (주문 전)
            snapshot = self._take_snapshot(date, snapshots)

            # 주문 생성 및 체결
            orders = self.order_generator(all_signals, snapshot, self.broker)
            for order in orders:
                self.broker.submit_order(order)

            # 체결 후 최종 스냅샷
            final_snapshot = self._take_snapshot(date, snapshots)
            snapshots.append(final_snapshot)

        # 벤치마크 수익률 계산
        benchmark_returns = self._get_benchmark_returns(trading_days)

        # 성과 지표 계산
        metrics = self._metrics_calc.calculate(
            snapshots,
            benchmark_returns,
            risk_free_rate=self.config.risk_free_rate,
            trades=self.broker.trade_log,
        )

        return BacktestResult(
            snapshots=snapshots,
            trades=self.broker.trade_log,
            metrics=metrics,
            config=self.config,
        )

    def _take_snapshot(
        self, date: str, prev_snapshots: list[PortfolioSnapshot]
    ) -> PortfolioSnapshot:
        """현재 포트폴리오 스냅샷을 생성한다."""
        balance = self.broker.get_balance()
        total_value = balance["total_value"]

        if prev_snapshots:
            prev_value = prev_snapshots[-1].total_value
            daily_return = (
                (total_value - prev_value) / prev_value * 100
                if prev_value > 0
                else 0.0
            )
        else:
            daily_return = 0.0

        initial = self.config.initial_capital
        cumulative_return = (total_value - initial) / initial * 100

        peak = max(
            [s.total_value for s in prev_snapshots] + [initial, total_value]
        )
        drawdown = -(peak - total_value) / peak * 100 if peak > 0 else 0.0

        return PortfolioSnapshot(
            date=date,
            cash=balance["cash"],
            positions=self.broker.get_positions(),
            total_value=total_value,
            daily_return=round(daily_return, 4),
            cumulative_return=round(cumulative_return, 4),
            drawdown=round(drawdown, 4),
        )

    def _get_benchmark_returns(self, trading_days: list[str]) -> np.ndarray:
        """벤치마크 일간 수익률 배열을 생성한다."""
        prices = []
        for date in trading_days:
            self.data_feed.advance_to(date)
            bar = self.data_feed.get_bar(self.config.benchmark)
            if bar:
                prices.append(bar.close)
            else:
                prices.append(prices[-1] if prices else 0)

        if len(prices) < 2:
            return np.array([0.0])

        prices_arr = np.array(prices, dtype=float)
        returns = np.diff(prices_arr) / prices_arr[:-1]
        return returns
