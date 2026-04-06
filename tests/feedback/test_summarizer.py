import json
import pytest
from alphapulse.feedback.summarizer import FeedbackSummarizer
from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator


@pytest.fixture
def store(tmp_path):
    return FeedbackStore(tmp_path / "feedback.db")


@pytest.fixture
def summarizer(store):
    evaluator = FeedbackEvaluator(store=store)
    return FeedbackSummarizer(store=store, evaluator=evaluator)


def _seed(store, n=10):
    for i in range(n):
        date = f"2026040{i+1}" if i < 9 else f"202604{i+1}"
        score = 40.0 if i % 2 == 0 else -30.0
        signal = "매수 우위" if score > 0 else "매도 우위"
        indicators = {"investor_flow": 80, "vkospi": -50}
        store.save_signal(date, score, signal, indicators)
        ret = 1.0 if score > 0 else -1.0
        hit = 1 if i < 7 else 0
        if i >= 7:
            ret = -ret
        store.update_result(date, 2650+i, ret, 870, 0.5, ret, hit)


def test_generate_ai_context(summarizer, store):
    _seed(store)
    ctx = summarizer.generate_ai_context(days=30)
    assert isinstance(ctx, str)
    assert "적중률" in ctx
    assert "지표별 신뢰도" in ctx


def test_generate_ai_context_empty(summarizer):
    ctx = summarizer.generate_ai_context(days=30)
    assert "데이터 부족" in ctx or ctx == ""


def test_format_daily_result(summarizer, store):
    store.save_signal("20260403", 35.0, "매수 우위", {})
    store.update_result("20260403", 2650, 1.2, 870, 0.8, 1.2, 1)
    row = store.get("20260403")
    msg = summarizer.format_daily_result(row)
    assert "매수 우위" in msg
    assert "1.2" in msg or "+1.2" in msg
    assert "✅" in msg


def test_format_daily_result_miss(summarizer, store):
    store.save_signal("20260403", 35.0, "매수 우위", {})
    store.update_result("20260403", 2600, -0.5, 860, -0.3, -0.5, 0)
    row = store.get("20260403")
    msg = summarizer.format_daily_result(row)
    assert "❌" in msg


def test_format_daily_result_none(summarizer):
    msg = summarizer.format_daily_result(None)
    assert msg == "" or "없음" in msg


def test_format_weekly_summary(summarizer, store):
    _seed(store)
    msg = summarizer.format_weekly_summary()
    assert "주간" in msg
    assert "적중률" in msg
