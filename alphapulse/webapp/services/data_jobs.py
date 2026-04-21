"""Data Jobs — 기존 데이터 수집 모듈의 Job wrapper.

collect_all은 제공하지 않는다 (리소스 보호). CLI(`ap trading data collect`)에서만.

Signature adaptations vs. plan
-------------------------------
- FundamentalCollector.collect() → returns None (not dict). We report market only.
- WisereportCollector.collect_static_batch() → returns dict[str, dict] (not list).
  len(results) still works correctly.
- ShortCollector.collect(code, start, end) → loops top codes; each call just logs
  (actual async collection requires collect_async). Codes resolved via TradingStore.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from alphapulse.core.config import Config
from alphapulse.trading.data.bulk_collector import BulkCollector
from alphapulse.trading.data.fundamental_collector import FundamentalCollector
from alphapulse.trading.data.short_collector import ShortCollector
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.wisereport_collector import WisereportCollector


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def run_data_update(
    *,
    markets: list[str],
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """BulkCollector.update()를 호출하여 증분 업데이트를 수행한다.

    BulkProgress 이벤트를 Job (current, total, text) 튜플로 브릿지하여
    webapp UI 에 phase/market/code 실시간 진행률을 전달한다.

    Args:
        markets: 대상 시장 목록 (예: ["KOSPI", "KOSDAQ"]).
        progress_callback: (current, total, text) 콜백.

    Returns:
        JSON 문자열 — 시장별 수집 결과 리스트.
    """
    from alphapulse.trading.data.bulk_collector import BulkProgress

    cfg = Config()
    collector = BulkCollector(db_path=cfg.TRADING_DB_PATH)

    # 전체 진척률: 시장 × phase 5 × phase 내 비율 → 0.0 ~ 1.0
    # Job progress 는 (current, total) 정수 페어이므로 1000 배율 사용
    SCALE = 1000

    def _bridge(p: BulkProgress) -> None:
        total_steps = p.markets_total * p.phases_total
        steps_done = (p.market_idx - 1) * p.phases_total + (p.phase_idx - 1)
        phase_frac = p.current / p.total if p.total > 0 else 1.0
        overall_num = int((steps_done + phase_frac) * SCALE)
        overall_den = total_steps * SCALE

        text = (
            f"[{p.market}] [{p.phase_idx}/{p.phases_total}] "
            f"{p.phase_label} · {p.current}/{p.total}"
        )
        if p.detail:
            text += f" · {p.detail}"
        progress_callback(overall_num, overall_den, text)

    progress_callback(0, 1, "증분 업데이트 시작")
    results = collector.update(markets=markets, progress_callback=_bridge)
    progress_callback(1, 1, "완료")
    payload = [
        {
            "market": r.market,
            "ohlcv_count": r.ohlcv_count,
            "fundamentals_count": r.fundamentals_count,
            "flow_count": r.flow_count,
            "wisereport_count": r.wisereport_count,
            "skipped": r.skipped,
            "elapsed_seconds": r.elapsed_seconds,
        }
        for r in results
    ]
    return json.dumps(payload, ensure_ascii=False)


def run_data_collect_financials(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """FundamentalCollector.collect()를 호출하여 재무제표를 수집한다.

    FundamentalCollector.collect() returns None; result is reported by market.
    Collector 내부 per-code progress_callback 을 Job UI 로 전달한다.

    Args:
        market: 대상 시장 (KOSPI / KOSDAQ).
        top: 상위 종목 수 (collector 내부에서 전 종목 수집하므로 참고용).
        progress_callback: (current, total, text) 콜백.

    Returns:
        JSON 문자열 — {"market": ..., "status": "ok"}.
    """
    cfg = Config()
    collector = FundamentalCollector(db_path=cfg.TRADING_DB_PATH)
    progress_callback(0, 1, f"{market} 재무제표 수집 시작")
    counter = [0]

    def _cb(code: str) -> None:
        counter[0] += 1
        # 총 개수를 모르므로 current+1 을 total 로 사용 → UI 는 진행 중 표시
        progress_callback(counter[0], counter[0] + 1, f"{market} · {code}")

    today = _today()
    collector.collect(date=today, market=market, progress_callback=_cb)
    progress_callback(1, 1, "완료")
    return json.dumps({"market": market, "status": "ok"}, ensure_ascii=False)


def run_data_collect_wisereport(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """WisereportCollector.collect_static_batch()로 wisereport 정적 데이터를 수집한다.

    Collector 내부 per-code progress_callback 을 Job UI 로 전달한다.

    Args:
        market: 대상 시장 (KOSPI / KOSDAQ).
        top: 상위 종목 수.
        progress_callback: (current, total, text) 콜백.

    Returns:
        JSON 문자열 — {"market": ..., "collected": N}.
    """
    cfg = Config()
    store = TradingStore(db_path=cfg.TRADING_DB_PATH)
    stocks = store.get_all_stocks()
    codes = [s["code"] for s in stocks if s["market"] == market][:top]
    collector = WisereportCollector(db_path=cfg.TRADING_DB_PATH)
    total = len(codes) or 1
    progress_callback(0, total, f"{market} wisereport 수집 시작 ({total}종목)")
    counter = [0]

    def _cb(code: str) -> None:
        counter[0] += 1
        progress_callback(counter[0], total, f"{market} · {code}")

    today = _today()
    # collect_static_batch returns dict[str, dict] — use len() for count
    results = collector.collect_static_batch(
        codes, today, progress_callback=_cb,
    )
    progress_callback(total, total, "완료")
    return json.dumps(
        {"market": market, "collected": len(results)}, ensure_ascii=False,
    )


def run_data_collect_short(
    *,
    market: str,
    top: int,
    progress_callback: Callable[[int, int, str], None],
) -> str:
    """ShortCollector.collect()를 종목별로 호출하여 공매도 수집 작업을 큐잉한다.

    ShortCollector.collect(code, start, end) is a sync stub that logs a
    message directing users to collect_async(). This wrapper resolves the
    top codes for the given market and calls collect() per code so that the
    sync Job layer records the attempt.

    Args:
        market: 대상 시장 (KOSPI / KOSDAQ).
        top: 상위 종목 수.
        progress_callback: (current, total, text) 콜백.

    Returns:
        JSON 문자열 — {"market": ..., "queued": N}.
    """
    cfg = Config()
    store = TradingStore(db_path=cfg.TRADING_DB_PATH)
    stocks = store.get_all_stocks()
    codes = [s["code"] for s in stocks if s["market"] == market][:top]
    collector = ShortCollector(db_path=cfg.TRADING_DB_PATH)
    today = _today()
    progress_callback(0, len(codes) or 1, "공매도 수집 중")
    for i, code in enumerate(codes, 1):
        collector.collect(code, today, today)
        progress_callback(i, len(codes) or 1, f"{code} 처리")
    progress_callback(len(codes) or 1, len(codes) or 1, "완료")
    return json.dumps(
        {"market": market, "queued": len(codes)}, ensure_ascii=False,
    )
