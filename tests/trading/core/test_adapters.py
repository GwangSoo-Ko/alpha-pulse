"""기존 시스템 어댑터 테스트."""

from alphapulse.trading.core.adapters import PulseResultAdapter


class TestPulseResultAdapter:
    def test_to_market_context(self):
        """SignalEngine 결과를 market_context로 변환한다."""
        pulse_result = {
            "date": "20260409",
            "score": 35.2,
            "signal": "매수 우위 (Moderately Bullish)",
            "indicator_scores": {
                "investor_flow": 42,
                "vkospi": -25,
            },
            "details": {
                "investor_flow": {"score": 42, "foreign_net": 3000},
            },
            "period": "daily",
        }

        ctx = PulseResultAdapter.to_market_context(pulse_result)

        assert ctx["date"] == "20260409"
        assert ctx["pulse_score"] == 35.2
        assert ctx["pulse_signal"] == "매수 우위 (Moderately Bullish)"
        assert ctx["indicator_scores"]["investor_flow"] == 42
        assert "details" in ctx

    def test_to_feedback_context(self):
        """피드백 평가 결과를 문자열로 변환한다."""
        hit_rates = {
            "hit_rate_1d": 0.65,
            "hit_rate_3d": 0.60,
            "hit_rate_5d": 0.58,
            "total_evaluated": 20,
        }

        result = PulseResultAdapter.to_feedback_context(hit_rates, correlation=0.42)

        assert "65.0%" in result
        assert "0.42" in result
        assert "20건" in result

    def test_to_feedback_context_insufficient_data(self):
        """평가 데이터 부족 시 안내 문자열."""
        hit_rates = {"total_evaluated": 0}
        result = PulseResultAdapter.to_feedback_context(hit_rates, correlation=None)
        assert "부족" in result or "없" in result
