"""PositionSizer 테스트."""

import pytest

from alphapulse.trading.core.models import Stock, StockOpinion
from alphapulse.trading.portfolio.position_sizer import PositionSizer


@pytest.fixture
def sizer():
    return PositionSizer()


class TestEqualWeight:
    def test_equal_weight_10(self, sizer):
        """10종목 균등 배분 -> 각 10%."""
        assert sizer.equal_weight(10) == pytest.approx(0.1)

    def test_equal_weight_1(self, sizer):
        """1종목 -> 100%."""
        assert sizer.equal_weight(1) == pytest.approx(1.0)


class TestVolatilityAdjusted:
    def test_basic(self, sizer):
        """변동성 낮을수록 비중 높음."""
        vols = {
            "005930": 0.20,  # 낮은 변동성 -> 높은 비중
            "035720": 0.40,  # 높은 변동성 -> 낮은 비중
        }
        weights = sizer.volatility_adjusted(vols, target_vol=0.15)
        assert weights["005930"] > weights["035720"]
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_single_stock(self, sizer):
        """1종목이면 비중 100%."""
        weights = sizer.volatility_adjusted({"005930": 0.3})
        assert weights["005930"] == pytest.approx(1.0)


class TestKelly:
    def test_positive_edge(self, sizer):
        """양의 엣지 -> 양의 비중 (half-kelly)."""
        weight = sizer.kelly(win_rate=0.6, avg_win=0.03, avg_loss=0.02)
        assert weight > 0

    def test_no_edge(self, sizer):
        """엣지 없음 -> 비중 0."""
        weight = sizer.kelly(win_rate=0.5, avg_win=0.02, avg_loss=0.02)
        assert weight == 0.0

    def test_negative_edge(self, sizer):
        """음의 엣지 -> 비중 0 (음수 방지)."""
        weight = sizer.kelly(win_rate=0.3, avg_win=0.02, avg_loss=0.03)
        assert weight == 0.0

    def test_half_kelly(self, sizer):
        """half-kelly 적용 확인."""
        # full kelly = 0.6 - 0.4/(0.04/0.02) = 0.6 - 0.2 = 0.4
        # half kelly = 0.2
        weight = sizer.kelly(win_rate=0.6, avg_win=0.04, avg_loss=0.02)
        assert weight == pytest.approx(0.2)


class TestAIAdjusted:
    def test_high_confidence_boosts(self, sizer):
        """높은 확신도 -> 비중 1.2배."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock, action="매수", reason="강세", confidence=0.8,
        )
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == pytest.approx(0.06)  # 0.05 * 1.2

    def test_low_confidence_reduces(self, sizer):
        """낮은 확신도 -> 비중 0.7배."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock, action="유지", reason="불확실", confidence=0.2,
        )
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == pytest.approx(0.035)  # 0.05 * 0.7

    def test_sell_opinion_zero(self, sizer):
        """매도 의견 -> 비중 0."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock, action="매도", reason="하락 전환", confidence=0.9,
        )
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == 0.0

    def test_max_weight_cap(self, sizer):
        """최대 비중 상한 적용."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock, action="강력매수", reason="최강", confidence=0.95,
        )
        adjusted = sizer.ai_adjusted(0.09, opinion, max_weight=0.10)
        assert adjusted <= 0.10
