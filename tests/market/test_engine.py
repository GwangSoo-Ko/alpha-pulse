"""시그널 엔진 및 스코어링 테스트"""

from alphapulse.market.engine.scoring import calculate_weighted_score, normalize_score


class TestNormalizeScore:
    def test_within_range(self):
        assert normalize_score(50) == 50

    def test_above_max(self):
        assert normalize_score(150) == 100

    def test_below_min(self):
        assert normalize_score(-150) == -100

    def test_zero(self):
        assert normalize_score(0) == 0


class TestCalculateWeightedScore:
    def test_all_positive(self):
        scores = {
            "investor_flow": 80,
            "spot_futures_align": 80,
            "program_trade": 60,
            "sector_momentum": 50,
            "exchange_rate": 40,
            "vkospi": 30,
            "interest_rate_diff": 20,
            "global_market": 60,
            "fund_flow": 30,
            "adr_volume": 40,
        }
        score, label = calculate_weighted_score(scores)
        assert score > 0
        assert "매수" in label or "Bullish" in label

    def test_all_negative(self):
        scores = {
            "investor_flow": -80,
            "spot_futures_align": -80,
            "program_trade": -60,
            "sector_momentum": -50,
            "exchange_rate": -40,
            "vkospi": -30,
            "interest_rate_diff": -20,
            "global_market": -60,
            "fund_flow": -30,
            "adr_volume": -40,
        }
        score, label = calculate_weighted_score(scores)
        assert score < 0
        assert "매도" in label or "Bearish" in label

    def test_mixed_neutral(self):
        scores = {
            "investor_flow": 10,
            "spot_futures_align": -10,
            "program_trade": 5,
            "sector_momentum": -5,
            "exchange_rate": 0,
            "vkospi": 0,
            "interest_rate_diff": 0,
            "global_market": 0,
            "fund_flow": 0,
            "adr_volume": 0,
        }
        score, label = calculate_weighted_score(scores)
        assert -19 <= score <= 19
        assert "중립" in label or "Neutral" in label

    def test_with_none_values_redistributes_weights(self):
        """N/A 지표 제외 시 가중치 재배분"""
        scores = {
            "investor_flow": 80,
            "spot_futures_align": None,
            "program_trade": None,
            "sector_momentum": None,
            "exchange_rate": None,
            "vkospi": None,
            "interest_rate_diff": None,
            "global_market": None,
            "fund_flow": None,
            "adr_volume": None,
        }
        score, label = calculate_weighted_score(scores)
        # investor_flow만 있으면 그 점수가 100% 반영
        assert score == 80.0

    def test_empty_scores(self):
        score, label = calculate_weighted_score({})
        assert score == 0.0
        assert "중립" in label or "Neutral" in label

    def test_strong_bullish_threshold(self):
        scores = {k: 100 for k in [
            "investor_flow", "spot_futures_align", "program_trade",
            "sector_momentum", "exchange_rate", "vkospi",
            "interest_rate_diff", "global_market", "fund_flow", "adr_volume",
        ]}
        score, label = calculate_weighted_score(scores)
        assert score >= 60
        assert "강한 매수" in label or "Strong Bullish" in label
