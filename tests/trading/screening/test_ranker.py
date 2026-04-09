"""멀티팩터 랭킹 테스트."""

import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker


@pytest.fixture
def factor_data():
    """종목별 팩터 원시값 (FactorCalculator 출력 형식)."""
    return {
        "005930": {"momentum": 5.4, "value": 8.0, "quality": 15.2, "flow": 400e9, "volatility": 25.0},
        "000660": {"momentum": -3.0, "value": 12.5, "quality": 12.0, "flow": -600e9, "volatility": 35.0},
        "035720": {"momentum": 2.0, "value": 5.0, "quality": 10.0, "flow": 100e9, "volatility": 40.0},
    }


@pytest.fixture
def stocks():
    return [
        Stock(code="005930", name="삼성전자", market="KOSPI"),
        Stock(code="000660", name="SK하이닉스", market="KOSPI"),
        Stock(code="035720", name="카카오", market="KOSPI"),
    ]


class TestMultiFactorRanker:
    def test_rank_returns_sorted(self, stocks, factor_data):
        """점수 내림차순 정렬."""
        ranker = MultiFactorRanker(
            weights={"momentum": 0.3, "value": 0.3, "quality": 0.2, "flow": 0.1, "volatility": 0.1}
        )
        signals = ranker.rank(stocks, factor_data, strategy_id="test")

        assert len(signals) == 3
        # 점수 내림차순 확인
        assert signals[0].score >= signals[1].score >= signals[2].score

    def test_rank_signal_fields(self, stocks, factor_data):
        """Signal 필드가 올바르게 설정된다."""
        ranker = MultiFactorRanker(
            weights={"momentum": 0.5, "value": 0.5}
        )
        signals = ranker.rank(stocks, factor_data, strategy_id="momentum")

        for sig in signals:
            assert sig.strategy_id == "momentum"
            assert -100 <= sig.score <= 100
            assert "momentum" in sig.factors
            assert "value" in sig.factors

    def test_rank_with_missing_factor(self, stocks):
        """팩터 데이터 누락 시 해당 종목은 0점 처리."""
        factor_data = {
            "005930": {"momentum": 5.0},
            "000660": {"momentum": -3.0},
            # 035720은 아예 없음
        }
        ranker = MultiFactorRanker(weights={"momentum": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        assert len(signals) == 3

    def test_rank_single_stock(self, factor_data):
        """종목 1개일 때도 동작한다."""
        stocks = [Stock(code="005930", name="삼성전자", market="KOSPI")]
        ranker = MultiFactorRanker(weights={"momentum": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        assert len(signals) == 1

    def test_volatility_inverse_scoring(self, stocks, factor_data):
        """변동성은 역순 — 낮을수록 높은 점수."""
        ranker = MultiFactorRanker(weights={"volatility": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        # 삼성(25%) < SK(35%) < 카카오(40%) → 삼성 점수 최고
        assert signals[0].stock.code == "005930"
