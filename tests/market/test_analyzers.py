"""분석기 모듈 테스트"""
import pandas as pd
import pytest

from alphapulse.market.analyzers.fund_flow import FundFlowAnalyzer
from alphapulse.market.analyzers.investor_flow import InvestorFlowAnalyzer
from alphapulse.market.analyzers.macro_monitor import MacroMonitorAnalyzer
from alphapulse.market.analyzers.market_breadth import MarketBreadthAnalyzer
from alphapulse.market.analyzers.program_trade import ProgramTradeAnalyzer


@pytest.fixture
def sample_ohlcv_df():
    """전 종목 OHLCV 샘플 (ADR 계산용)"""
    return pd.DataFrame({
        "시가": [70000, 130000, 400000, 800000, 200000],
        "고가": [71000, 132000, 410000, 810000, 205000],
        "저가": [69000, 128000, 395000, 790000, 198000],
        "종가": [70500, 131000, 405000, 805000, 203000],
        "거래량": [1000000, 500000, 200000, 100000, 300000],
        "등락률": [1.5, -0.8, 2.1, -1.2, 0.5],
    }, index=["005930", "000660", "373220", "207940", "005380"])


class TestInvestorFlowAnalyzer:
    def setup_method(self):
        self.analyzer = InvestorFlowAnalyzer()

    def test_analyze_flow_bullish(self):
        """외국인+기관 모두 순매수 -> 양의 점수"""
        df = pd.DataFrame({
            "기관합계": [500_000_000_000, 300_000_000_000],
            "외국인합계": [400_000_000_000, 200_000_000_000],
            "개인": [-900_000_000_000, -500_000_000_000],
            "기타법인": [0, 0],
        })
        result = self.analyzer.analyze_flow(df)
        assert result["score"] > 0
        assert result["foreign_net"] > 0
        assert result["institutional_net"] > 0

    def test_analyze_flow_bearish(self):
        """외국인+기관 모두 순매도 -> 음의 점수"""
        df = pd.DataFrame({
            "기관합계": [-500_000_000_000, -300_000_000_000],
            "외국인합계": [-400_000_000_000, -200_000_000_000],
            "개인": [900_000_000_000, 500_000_000_000],
            "기타법인": [0, 0],
        })
        result = self.analyzer.analyze_flow(df)
        assert result["score"] < 0

    def test_analyze_flow_empty(self):
        """빈 데이터 -> 점수 0"""
        result = self.analyzer.analyze_flow(pd.DataFrame())
        assert result["score"] == 0

    def test_spot_futures_aligned_buy(self):
        """현선물 매수 방향 일치"""
        spot = pd.DataFrame({"외국인합계": [100, 200]})
        futures = pd.DataFrame({"외국인합계": [50, 100]})
        result = self.analyzer.analyze_spot_futures_alignment(spot, futures)
        assert result["score"] > 0
        assert result["aligned"] is True

    def test_spot_futures_misaligned(self):
        """현선물 방향 불일치"""
        spot = pd.DataFrame({"외국인합계": [100, 200]})
        futures = pd.DataFrame({"외국인합계": [-50, -100]})
        result = self.analyzer.analyze_spot_futures_alignment(spot, futures)
        assert result["score"] == 0
        assert result["aligned"] is False


class TestProgramTradeAnalyzer:
    def setup_method(self):
        self.analyzer = ProgramTradeAnalyzer()

    def test_analyze_net_buy(self):
        """비차익 순매수 -> 양의 점수"""
        df = pd.DataFrame({"비차익순매수": [500_000_000_000]})
        result = self.analyzer.analyze(df)
        assert result["score"] > 0

    def test_analyze_empty(self):
        result = self.analyzer.analyze(pd.DataFrame())
        assert result["score"] == 0


class TestMarketBreadthAnalyzer:
    def setup_method(self):
        self.analyzer = MarketBreadthAnalyzer()

    def test_adr_bullish(self, sample_ohlcv_df):
        """상승 종목이 많으면 양의 점수"""
        # sample has 3 positive, 2 negative
        result = self.analyzer.analyze_adr(sample_ohlcv_df)
        assert result["adr"] > 1.0
        assert result["score"] > 0

    def test_adr_empty(self):
        result = self.analyzer.analyze_adr(pd.DataFrame())
        assert result["score"] == 0

    def test_sector_momentum(self):
        df = pd.DataFrame({
            "업종명": ["전기전자", "화학", "금융"],
            "등락률": [2.5, -0.5, 1.0],
        })
        result = self.analyzer.analyze_sector_momentum(df)
        assert result["score"] > 0


class TestFundFlowAnalyzer:
    def setup_method(self):
        self.analyzer = FundFlowAnalyzer()

    def test_analyze_no_data(self):
        result = self.analyzer.analyze()
        assert result["score"] == 0

    def test_analyze_deposit_increase(self):
        deposit = pd.DataFrame({"예탁금": [50000, 51000, 52000]})
        result = self.analyzer.analyze(deposit_df=deposit)
        assert result["score"] > 0


class TestMacroMonitorAnalyzer:
    def setup_method(self):
        self.analyzer = MacroMonitorAnalyzer()

    def test_exchange_rate_won_strength(self):
        """원화 강세(환율 하락) -> 양의 점수"""
        df = pd.DataFrame({"Close": [1350.0, 1340.0, 1330.0]})
        result = self.analyzer.analyze_exchange_rate(df)
        assert result["score"] > 0

    def test_exchange_rate_won_weakness(self):
        """원화 약세(환율 상승) -> 음의 점수"""
        df = pd.DataFrame({"Close": [1300.0, 1320.0, 1350.0]})
        result = self.analyzer.analyze_exchange_rate(df)
        assert result["score"] < 0

    def test_vkospi_stable(self):
        """V-KOSPI 15~20: 안정 구간"""
        df = pd.DataFrame({"Close": [18.5]})
        result = self.analyzer.analyze_vkospi(df)
        assert result["score"] > 0
        assert result["level"] == "안정"

    def test_vkospi_fear(self):
        """V-KOSPI 25~35: 공포"""
        df = pd.DataFrame({"Close": [30.0]})
        result = self.analyzer.analyze_vkospi(df)
        assert result["score"] < 0

    def test_vkospi_extreme_contrarian(self):
        """V-KOSPI >50: 패닉 → 역투자 관점으로 점수 완화"""
        df = pd.DataFrame({"Close": [60.0]})
        result = self.analyzer.analyze_vkospi(df)
        assert result["score"] > -50  # 공포(-50)보다 점수가 높아야 함

    def test_global_markets_positive(self):
        indices = {
            "SP500": pd.DataFrame({"Close": [5000, 5050]}),
            "NASDAQ": pd.DataFrame({"Close": [16000, 16200]}),
        }
        result = self.analyzer.analyze_global_markets(indices)
        assert result["score"] > 0

    def test_interest_rate_diff(self):
        us = pd.DataFrame({"rate": [4.5]})
        kr = pd.DataFrame({"rate": [3.5]})
        result = self.analyzer.analyze_interest_rate_diff(us, kr)
        assert result["score"] < 0  # 미국이 높으면 부정적
        assert result["diff"] == 1.0
