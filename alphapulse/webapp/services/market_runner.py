"""MarketRunner — Job 에서 호출되는 Market Pulse 실행 헬퍼.

SignalEngine.run() 을 sync 로 호출하고 progress_callback 으로 Job 진행률을 기록.
저장은 SignalEngine 내부의 PulseHistory.save 가 담당 → 여기선 저장된 date 만 반환.
"""

from __future__ import annotations

from typing import Callable

from alphapulse.market.engine.signal_engine import SignalEngine


def run_market_pulse_sync(
    *,
    date: str | None,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """SignalEngine 을 실행하고 저장된 날짜를 반환한다.

    Args:
        date: YYYYMMDD 또는 None(= 직전 거래일).
        progress_callback: Job 진행률 훅. (current, total, text).

    Returns:
        실제 저장된 날짜 (YYYYMMDD).
    """
    progress_callback(0, 1, "시황 분석 실행 중")
    engine = SignalEngine()
    result = engine.run(date=date)
    progress_callback(1, 1, "완료")
    return result["date"]
