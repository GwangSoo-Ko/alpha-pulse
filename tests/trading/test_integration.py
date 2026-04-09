"""Trading Phase 1 통합 테스트.

Core → Data → Screening 전체 파이프라인을 검증한다.

NOTE: 개별 수집기(StockCollector, FundamentalCollector, FlowCollector, ShortCollector)는
각자의 단위 테스트에서 검증된다. 이 통합 테스트는 스크리닝 파이프라인
(유니버스 → 팩터 → 필터 → 랭킹)에 집중한다.
"""

from alphapulse.trading.data.universe import Universe
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.filter import StockFilter
from alphapulse.trading.screening.ranker import MultiFactorRanker


def test_full_screening_pipeline(trading_store):
    """데이터 → 유니버스 → 팩터 → 필터 → 랭킹 전체 흐름."""
    # 1. 유니버스 조회
    universe = Universe(trading_store)
    all_stocks = universe.get_all()
    assert len(all_stocks) == 2  # conftest에서 2종목

    # 2. 팩터 계산
    calc = FactorCalculator(trading_store)
    factor_data = {}
    for s in all_stocks:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code, lookback=20),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "flow": calc.flow(s.code, days=20),
            "volatility": calc.volatility(s.code, days=20),
        }

    # 3. 팩터 값 검증
    assert factor_data["005930"]["momentum"] > 0  # 상승
    assert factor_data["000660"]["momentum"] < 0  # 하락

    # 4. 랭킹
    ranker = MultiFactorRanker(
        weights={"momentum": 0.3, "value": 0.25, "quality": 0.2,
                 "flow": 0.15, "volatility": 0.1}
    )
    signals = ranker.rank(all_stocks, factor_data, strategy_id="multi_factor")
    assert len(signals) == 2
    assert signals[0].score >= signals[1].score
    assert signals[0].strategy_id == "multi_factor"

    # 5. 필터 (시가총액 200조 이상만)
    stock_data = {
        "005930": {"market_cap": 430e12, "avg_volume": 500e9},
        "000660": {"market_cap": 120e12, "avg_volume": 200e9},
    }
    stock_filter = StockFilter({"min_market_cap": 200e12})
    filtered = stock_filter.apply(all_stocks, stock_data)
    assert len(filtered) == 1
    assert filtered[0].code == "005930"
