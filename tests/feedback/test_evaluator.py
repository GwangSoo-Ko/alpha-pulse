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
