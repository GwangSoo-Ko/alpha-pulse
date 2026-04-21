"""ScreeningRunner — Job에서 호출되는 스크리닝 실행 헬퍼.

기존 `ap trading screen` CLI 로직 추출. progress_callback으로 Job 연동.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.webapp.store.screening import ScreeningRepository


def _load_universe(market: str, store: TradingStore) -> list[Stock]:
    stocks = store.get_all_stocks()
    if market == "ALL":
        filtered = [s for s in stocks if s["market"] in ("KOSPI", "KOSDAQ")]
    elif market in ("KOSPI", "KOSDAQ"):
        filtered = [s for s in stocks if s["market"] == market]
    else:
        raise ValueError(f"unknown market: {market}")
    return [
        Stock(code=s["code"], name=s["name"], market=s["market"])
        for s in filtered
    ]


def run_screening_sync(
    *,
    market: str,
    strategy: str,
    factor_weights: dict[str, float],
    top_n: int,
    name: str,
    screening_repo: ScreeningRepository,
    user_id: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    cfg = Config()
    store = TradingStore(db_path=cfg.TRADING_DB_PATH)

    progress_callback(0, 4, "유니버스 로드")
    universe = _load_universe(market, store)

    progress_callback(1, 4, "팩터 계산")
    calc = FactorCalculator(store)
    factor_data: dict[str, dict[str, float]] = {}
    for s in universe:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "growth": calc.growth(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    progress_callback(2, 4, "랭킹")
    ranker = MultiFactorRanker(weights=factor_weights)
    ranked = ranker.rank(universe, factor_data, strategy_id=strategy)
    top = ranked[:top_n]

    progress_callback(3, 4, "저장")
    market_context = _get_market_context()
    results = [
        {
            "code": sig.stock.code,
            "name": sig.stock.name,
            "market": sig.stock.market,
            "score": round(sig.score, 2),
            "factors": sig.factors,
        }
        for sig in top
    ]
    run_id = screening_repo.save(
        name=name or f"{market}_{strategy}",
        market=market, strategy=strategy,
        factor_weights=factor_weights, top_n=top_n,
        market_context=market_context, results=results,
        user_id=user_id,
    )

    progress_callback(4, 4, "완료")
    return run_id


def _get_market_context() -> dict:
    """Market Pulse 스냅샷 획득. 실패 시 빈 dict."""
    try:
        import json

        from alphapulse.market.engine.signal_engine import SignalEngine
        from alphapulse.trading.core.adapters import PulseResultAdapter

        engine = SignalEngine()
        pulse = engine.run()
        ctx = PulseResultAdapter.to_market_context(pulse)
        # numpy/기타 비직렬화 타입을 native Python으로 변환
        return json.loads(json.dumps(ctx, default=lambda o: float(o) if hasattr(o, "__float__") else str(o)))
    except Exception:
        return {}
