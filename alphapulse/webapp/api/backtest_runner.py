"""Backtest 실행 헬퍼 — CLI의 backtest_run 로직을 함수로 추출.

progress_callback을 받아 JobRunner에서 진행률 훅으로 주입 가능.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
)
from alphapulse.trading.backtest.order_gen import (
    make_default_order_generator,
)
from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.backtest.store_feed import TradingStoreDataFeed
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.momentum import MomentumStrategy
from alphapulse.trading.strategy.quality_momentum import (
    QualityMomentumStrategy,
)
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy
from alphapulse.trading.strategy.value import ValueStrategy

_STRATEGY_MAP = {
    "momentum": MomentumStrategy,
    "value": ValueStrategy,
    "quality_momentum": QualityMomentumStrategy,
    "topdown_etf": TopDownETFStrategy,
}


def run_backtest_sync(
    *,
    strategy: str,
    start: str,
    end: str,
    capital: int,
    market: str,
    top: int,
    name: str,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """백테스트를 동기 실행하고 DB에 저장. run_id 반환."""
    if strategy not in _STRATEGY_MAP:
        raise ValueError(
            f"unknown strategy: {strategy}. "
            f"Available: {list(_STRATEGY_MAP)}"
        )
    if not end:
        end = datetime.now().strftime("%Y%m%d")
    if not start:
        start = (
            datetime.now() - timedelta(days=3 * 365)
        ).strftime("%Y%m%d")

    cfg = Config()
    db_path = cfg.TRADING_DB_PATH
    data_feed = TradingStoreDataFeed(db_path=db_path, market=market)
    if not data_feed.codes:
        raise ValueError(f"No market data for {market}")

    ranker = MultiFactorRanker(weights={
        "momentum": 0.25, "flow": 0.25, "value": 0.20,
        "quality": 0.15, "growth": 0.10, "volatility": 0.05,
    })
    strat_cls = _STRATEGY_MAP[strategy]
    factor_calc = FactorCalculator(data_feed.store)
    try:
        strat = strat_cls(
            ranker=ranker, factor_calc=factor_calc,
            config={"top_n": top},
        )
    except TypeError:
        strat = strat_cls(config={"top_n": top})

    cost_model = CostModel(
        commission_rate=cfg.BACKTEST_COMMISSION,
        tax_rate_stock=cfg.BACKTEST_TAX,
    )
    order_gen = make_default_order_generator(
        top_n=top, initial_capital=capital,
    )
    bt_config = BacktestConfig(
        initial_capital=capital,
        start_date=start, end_date=end,
        cost_model=cost_model,
    )
    engine = BacktestEngine(
        config=bt_config,
        data_feed=data_feed,
        strategies=[strat],
        order_generator=order_gen,
    )

    def _hook(current: int, total: int, date: str = "") -> None:
        progress_callback(current, total, date)

    result = engine.run(progress_callback=_hook)
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")
    run_id = bt_store.save_run(
        result, name=name or f"{strategy}_{start}_{end}",
        strategies=[strategy],
    )
    return run_id
