"""E2E 통합 테스트 — TradingStoreDataFeed → BacktestEngine → PortfolioStore.

실제 파일시스템 + SQLite store를 사용하여 백테스트 파이프라인이
크래시 없이 일별 스냅샷을 생성하는지 검증한다.
"""

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestEngine
from alphapulse.trading.backtest.order_gen import make_default_order_generator
from alphapulse.trading.backtest.store_feed import TradingStoreDataFeed
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.momentum import MomentumStrategy


def test_backtest_runs_end_to_end(trading_store, tmp_path):
    """TradingStore + HistoricalDataFeed → BacktestEngine → 스냅샷까지."""
    # store는 conftest에서 삼성/SK 2종목 + 20영업일 OHLCV를 보유
    db_path = trading_store.db_path

    data_feed = TradingStoreDataFeed(
        db_path=db_path,
        codes=["005930", "000660"],
    )
    # 벤치마크 코드(KOSPI)가 feed에 없어도 엔진이 폴백해야 함 - 임시로 삼성 사용
    cfg = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260401",
        end_date="20260420",
        cost_model=CostModel(),
        benchmark="005930",
    )

    # 모멘텀 전략 1개만 실행
    ranker = MultiFactorRanker(
        weights={
            "momentum": 0.6,
            "flow": 0.3,
            "volatility": 0.1,
        }
    )
    factor_calc = FactorCalculator(trading_store)
    strategy = MomentumStrategy(
        ranker=ranker,
        config={"top_n": 2},
        factor_calc=factor_calc,
    )

    order_gen = make_default_order_generator(top_n=2, initial_capital=100_000_000)

    engine = BacktestEngine(
        config=cfg,
        data_feed=data_feed,
        strategies=[strategy],
        order_generator=order_gen,
    )

    result = engine.run()

    # 최소한의 무결성 검증
    assert result is not None
    assert len(result.snapshots) > 0, "스냅샷이 하나 이상 생성되어야 함"
    first = result.snapshots[0]
    last = result.snapshots[-1]
    assert first.date < last.date or first.date == last.date
    assert last.total_value > 0
    assert isinstance(result.metrics, dict)


def test_factory_builds_engine_without_crash(monkeypatch, tmp_path):
    """팩토리가 config 기반으로 엔진을 조립할 수 있어야 함 (KIS 키 모킹)."""
    # KIS 키가 없으면 RuntimeError를 발생시킨다
    monkeypatch.setenv("KIS_APP_KEY", "dummy")
    monkeypatch.setenv("KIS_APP_SECRET", "dummy")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "0000")
    monkeypatch.setenv("KIS_IS_PAPER", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    from alphapulse.core.config import Config
    from alphapulse.trading.core.enums import TradingMode
    from alphapulse.trading.orchestrator.factory import build_trading_engine

    cfg = Config()
    engine = build_trading_engine(TradingMode.PAPER, cfg=cfg)

    # 필수 컬래버레이터 바인딩 확인
    assert engine.broker is not None
    assert engine.data_provider is not None
    assert engine.universe is not None
    assert engine.portfolio_manager is not None
    assert engine.risk_manager is not None
    assert engine.portfolio_store is not None
    assert len(engine.strategies) >= 3  # momentum, value, topdown_etf
    assert engine.mode == TradingMode.PAPER
    # LIVE 모드가 아니므로 safeguard는 None
    assert engine.safeguard is None
