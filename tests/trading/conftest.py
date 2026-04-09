"""Trading 모듈 공유 테스트 픽스처."""

import pytest

from alphapulse.trading.data.store import TradingStore


@pytest.fixture
def trading_store(tmp_path):
    """OHLCV + 재무 + 수급 데이터가 미리 로드된 TradingStore."""
    store = TradingStore(tmp_path / "test.db")

    # 종목
    store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
    store.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)

    # OHLCV (20일치 시뮬레이션 — 삼성전자는 상승, SK하이닉스는 하락)
    samsung_prices = [70000 + i * 200 for i in range(20)]  # 70000 → 73800
    hynix_prices = [190000 - i * 300 for i in range(20)]   # 190000 → 184300
    dates = [f"202604{d:02d}" for d in range(1, 21)]

    samsung_ohlcv = []
    hynix_ohlcv = []
    for i, date in enumerate(dates):
        sp = samsung_prices[i]
        samsung_ohlcv.append(
            ("005930", date, sp - 500, sp + 500, sp - 800, sp, 10_000_000, 430e12)
        )
        hp = hynix_prices[i]
        hynix_ohlcv.append(
            ("000660", date, hp - 1000, hp + 1000, hp - 1500, hp, 3_000_000, 120e12)
        )

    store.save_ohlcv_bulk(samsung_ohlcv + hynix_ohlcv)

    # 재무제표
    store.save_fundamental("005930", "20260331", per=12.5, pbr=1.3,
                           roe=15.2, dividend_yield=2.1)
    store.save_fundamental("000660", "20260331", per=8.0, pbr=1.0,
                           roe=12.0, dividend_yield=1.5)

    # 수급 (삼성: 외국인 순매수, SK: 외국인 순매도)
    samsung_flow = [
        ("005930", date, 50e9 if i % 2 == 0 else -10e9, 20e9, -70e9, 55.0)
        for i, date in enumerate(dates)
    ]
    hynix_flow = [
        ("000660", date, -30e9, -10e9, 40e9, 30.0)
        for date in dates
    ]
    store.save_investor_flow_bulk(samsung_flow + hynix_flow)

    # 공매도 (삼성: 감소 추세, SK: 증가 추세)
    samsung_short = [
        ("005930", date, 500_000 - i * 20_000, 10_000_000 - i * 200_000,
         0.5 - i * 0.02, 100e9, 5_000_000)
        for i, date in enumerate(dates)
    ]
    hynix_short = [
        ("000660", date, 300_000 + i * 15_000, 8_000_000 + i * 150_000,
         0.3 + i * 0.01, 80e9, 4_000_000)
        for i, date in enumerate(dates)
    ]
    store.save_short_interest_bulk(samsung_short + hynix_short)

    return store
