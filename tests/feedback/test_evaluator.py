import pytest

from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator


@pytest.fixture
def store(tmp_path):
    return FeedbackStore(tmp_path / "feedback.db")


@pytest.fixture
def evaluator(store):
    return FeedbackEvaluator(store=store)


def _seed_data(store, n=10):
    """시드 데이터 생성: 교대로 bullish/bearish, 70% 적중률"""
    for i in range(n):
        date = f"2026040{i+1}" if i < 9 else f"202604{i+1}"
        score = 40.0 if i % 2 == 0 else -30.0
        signal = "매수 우위" if score > 0 else "매도 우위"
        indicators = {"investor_flow": 80 if i % 3 == 0 else 20, "vkospi": -50}
        store.save_signal(date, score, signal, indicators)
        # 70% hit rate: first 7 correct, last 3 wrong
        if i < 7:
            ret = 1.0 if score > 0 else -1.0  # correct direction
        else:
            ret = -1.0 if score > 0 else 1.0  # wrong direction
        store.update_result(date, 2650 + i, ret, 870, 0.5, ret, 1 if i < 7 else 0)


def test_get_hit_rates(evaluator, store):
    _seed_data(store, 10)
    rates = evaluator.get_hit_rates(days=30)
    assert "hit_rate_1d" in rates
    assert 0 <= rates["hit_rate_1d"] <= 1.0
    assert rates["total_evaluated"] == 10


def test_get_hit_rates_empty(evaluator):
    rates = evaluator.get_hit_rates(days=30)
    assert rates["total_evaluated"] == 0


def test_get_indicator_accuracy(evaluator, store):
    _seed_data(store, 10)
    accuracy = evaluator.get_indicator_accuracy(days=30)
    assert "investor_flow" in accuracy
    assert "vkospi" in accuracy


def test_get_correlation(evaluator, store):
    _seed_data(store, 10)
    corr = evaluator.get_correlation(days=30)
    assert isinstance(corr, float) or corr is None
    if corr is not None:
        assert -1.0 <= corr <= 1.0


def test_get_correlation_insufficient_data(evaluator, store):
    store.save_signal("20260401", 35.0, "매수", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.0, 1)
    corr = evaluator.get_correlation(days=30)
    # Too few data points for meaningful correlation
    assert corr is None


def test_get_hit_rate_trend_empty_returns_empty_list(evaluator):
    result = evaluator.get_hit_rate_trend(days=30)
    assert result == []


def test_get_hit_rate_trend_returns_dates_ascending(evaluator, store):
    _seed_data(store, 10)
    result = evaluator.get_hit_rate_trend(days=30)
    dates = [p["date"] for p in result]
    assert dates == sorted(dates)


def test_get_hit_rate_trend_computes_rolling_7d_average(evaluator, store):
    # 14일 데이터, 앞 7일 hit=1, 뒤 7일 hit=0
    for i in range(14):
        date = "20260401" if i == 0 else f"202604{i+1:02d}"
        store.save_signal(date, 40.0, "매수 우위", {})
        hit = 1 if i < 7 else 0
        store.update_result(date, 2650 + i, 1.0, 870, 0.5, 1.0, hit)
    result = evaluator.get_hit_rate_trend(days=30, window=7)
    # 7번째 (index 6) 시점: 앞 7개(i=0..6) 모두 hit=1 → 1.0
    # 14번째 (index 13): 앞 7개(i=7..13) 모두 hit=0 → 0.0
    assert len(result) == 14
    assert result[6]["rolling_hit_rate_1d"] == 1.0
    assert result[13]["rolling_hit_rate_1d"] == 0.0


def test_get_hit_rate_trend_returns_null_when_window_has_no_evaluated(evaluator, store):
    # 평가되지 않은(return_1d=None) 레코드만 존재
    for i in range(5):
        store.save_signal(f"202604{i+1:02d}", 40.0, "매수 우위", {})
    result = evaluator.get_hit_rate_trend(days=30)
    assert len(result) == 5
    assert all(p["rolling_hit_rate_1d"] is None for p in result)


def test_get_score_return_points_empty_returns_empty_list(evaluator):
    assert evaluator.get_score_return_points(days=30) == []


def test_get_score_return_points_filters_null_return_1d(evaluator, store):
    # 2건 평가, 1건 미평가
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    store.save_signal("20260402", -30.0, "매도 우위", {})
    store.update_result("20260402", 2640, -0.4, 870, 0.1, -0.8, 1)
    store.save_signal("20260403", 20.0, "매수 우위", {})  # not evaluated
    result = evaluator.get_score_return_points(days=30)
    assert len(result) == 2
    dates = {p["date"] for p in result}
    assert dates == {"20260401", "20260402"}


def test_get_score_return_points_returns_all_four_fields(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.update_result("20260401", 2650, 1.0, 870, 0.5, 1.5, 1)
    result = evaluator.get_score_return_points(days=30)
    assert len(result) == 1
    p = result[0]
    assert p["date"] == "20260401"
    assert p["score"] == 40.0
    assert p["return_1d"] == 1.5
    assert p["signal"] == "매수 우위"


def test_get_indicator_heatmap_empty_returns_empty_list(evaluator):
    assert evaluator.get_indicator_heatmap(days=30) == []


def test_get_indicator_heatmap_skips_none_scores(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위",
                      {"investor_flow": 80, "vkospi": None, "fund_flow": -30})
    result = evaluator.get_indicator_heatmap(days=30)
    indicators = {c["indicator"] for c in result}
    assert indicators == {"investor_flow", "fund_flow"}


def test_get_indicator_heatmap_flat_cells(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {"investor_flow": 80})
    store.save_signal("20260402", -30.0, "매도 우위", {"investor_flow": -60, "vkospi": 50})
    result = evaluator.get_indicator_heatmap(days=30)
    assert len(result) == 3  # 1 + 2
    # 각 cell shape 확인
    for c in result:
        assert set(c.keys()) == {"date", "indicator", "score"}


def test_get_indicator_heatmap_score_is_float(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {"investor_flow": 80})
    result = evaluator.get_indicator_heatmap(days=30)
    assert isinstance(result[0]["score"], float)
    assert result[0]["score"] == 80.0


def test_get_signal_breakdown_empty_returns_empty_list(evaluator):
    assert evaluator.get_signal_breakdown(days=30) == []


def test_get_signal_breakdown_groups_by_signal(evaluator, store):
    # 3건 "매수 우위" (2건 hit=1, 1건 hit=0), 2건 "매도 우위" (둘 다 hit=1)
    for i, (sig, hit) in enumerate([
        ("매수 우위", 1), ("매수 우위", 1), ("매수 우위", 0),
        ("매도 우위", 1), ("매도 우위", 1),
    ]):
        date = f"202604{i+1:02d}"
        store.save_signal(date, 40.0 if "매수" in sig else -30.0, sig, {})
        store.update_result(date, 2650, 0.5, 870, 0.1, 0.3, hit)
    result = evaluator.get_signal_breakdown(days=30)
    by_signal = {r["signal"]: r for r in result}
    assert by_signal["매수 우위"]["count"] == 3
    assert by_signal["매수 우위"]["hit_rate_1d"] == pytest.approx(2 / 3, abs=0.01)
    assert by_signal["매도 우위"]["count"] == 2
    assert by_signal["매도 우위"]["hit_rate_1d"] == 1.0


def test_get_signal_breakdown_null_when_all_unevaluated(evaluator, store):
    store.save_signal("20260401", 40.0, "매수 우위", {})
    store.save_signal("20260402", 40.0, "매수 우위", {})
    result = evaluator.get_signal_breakdown(days=30)
    assert len(result) == 1
    assert result[0]["signal"] == "매수 우위"
    assert result[0]["count"] == 2
    assert result[0]["hit_rate_1d"] is None
    assert result[0]["hit_rate_3d"] is None
    assert result[0]["hit_rate_5d"] is None


def test_evaluator_caches_store_get_recent(evaluator, store, monkeypatch):
    """동일 limit 으로 get_* 메서드 여러 번 호출 시 store.get_recent 은 1회만 호출."""
    _seed_data(store, 5)
    call_count = {"n": 0}
    original = store.get_recent

    def counting(*args, **kwargs):
        call_count["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "get_recent", counting)

    evaluator.get_hit_rates(days=30)
    evaluator.get_hit_rates(days=30)   # cache hit
    evaluator.get_correlation(days=30)  # cache hit (same limit)
    evaluator.get_hit_rate_trend(days=30)  # cache hit

    assert call_count["n"] == 1


def test_evaluator_cache_separate_per_limit(evaluator, store, monkeypatch):
    """다른 limit 은 별도 캐시 키로 동작한다."""
    _seed_data(store, 30)
    call_count = {"n": 0}
    original = store.get_recent

    def counting(*args, **kwargs):
        call_count["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "get_recent", counting)

    evaluator.get_hit_rates(days=7)
    evaluator.get_hit_rates(days=30)
    evaluator.get_hit_rates(days=7)   # cache hit for limit=7

    assert call_count["n"] == 2  # 7일과 30일 각 1회
