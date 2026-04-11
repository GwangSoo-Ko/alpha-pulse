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

    # 재무 시계열 (시계열 팩터 테스트용)
    # 삼성: 분기마다 매출/이익 성장
    # SK: 매출은 비슷, 이익 감소
    # 형식: (code, period, period_type, is_estimate,
    #        revenue, operating_profit, net_income,
    #        operating_margin, net_margin,
    #        roe, debt_ratio, quick_ratio, reserve_ratio,
    #        eps, per, bps, pbr, dps, div_yield, div_payout)
    samsung_ts = [
        ("005930", "2024.06", "quarterly", 0,
         700000.0, 50000.0, 40000.0, 7.14, 5.71, 8.5, 28.0, None, None,
         700.0, 12.0, 50000.0, 1.2, None, None, None),
        ("005930", "2024.09", "quarterly", 0,
         750000.0, 60000.0, 50000.0, 8.0, 6.67, 9.0, 28.5, None, None,
         800.0, 12.5, 51000.0, 1.25, None, None, None),
        ("005930", "2024.12", "quarterly", 0,
         800000.0, 70000.0, 60000.0, 8.75, 7.5, 9.5, 29.0, None, None,
         900.0, 13.0, 52000.0, 1.3, None, None, None),
        ("005930", "2025.03", "quarterly", 0,
         850000.0, 80000.0, 70000.0, 9.41, 8.24, 10.0, 29.5, None, None,
         1000.0, 13.5, 53000.0, 1.35, None, None, None),
        ("005930", "2025.06", "quarterly", 0,
         900000.0, 90000.0, 80000.0, 10.0, 8.89, 10.5, 30.0, None, None,
         1100.0, 14.0, 54000.0, 1.4, None, None, None),
        ("005930", "2024.12", "annual", 0,
         3000000.0, 250000.0, 200000.0, 8.33, 6.67, 9.5, 29.0, None, None,
         3000.0, 13.0, 52000.0, 1.3, None, None, None),
    ]
    hynix_ts = [
        ("000660", "2024.06", "quarterly", 0,
         200000.0, 50000.0, 40000.0, 25.0, 20.0, 12.0, 35.0, None, None,
         500.0, 8.0, 60000.0, 1.0, None, None, None),
        ("000660", "2024.09", "quarterly", 0,
         200000.0, 45000.0, 35000.0, 22.5, 17.5, 11.5, 35.0, None, None,
         470.0, 8.5, 60500.0, 1.05, None, None, None),
        ("000660", "2024.12", "quarterly", 0,
         200000.0, 40000.0, 30000.0, 20.0, 15.0, 11.0, 35.0, None, None,
         440.0, 9.0, 61000.0, 1.1, None, None, None),
        ("000660", "2025.03", "quarterly", 0,
         200000.0, 35000.0, 25000.0, 17.5, 12.5, 10.5, 35.0, None, None,
         410.0, 9.5, 61500.0, 1.15, None, None, None),
        ("000660", "2025.06", "quarterly", 0,
         200000.0, 30000.0, 20000.0, 15.0, 10.0, 10.0, 35.0, None, None,
         380.0, 10.0, 62000.0, 1.2, None, None, None),
        ("000660", "2024.12", "annual", 0,
         800000.0, 175000.0, 130000.0, 21.88, 16.25, 11.5, 35.0, None, None,
         1820.0, 8.5, 60500.0, 1.05, None, None, None),
    ]
    store.save_fundamentals_timeseries_bulk(samsung_ts + hynix_ts)

    return store
