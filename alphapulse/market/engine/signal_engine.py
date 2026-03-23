"""종합 시그널 엔진"""

import logging
from datetime import datetime

import pandas as pd

from alphapulse.core.config import Config
from alphapulse.market.collectors.pykrx_collector import PykrxCollector
from alphapulse.market.collectors.fdr_collector import FdrCollector
from alphapulse.market.collectors.krx_scraper import KrxScraper
from alphapulse.market.collectors.fred_collector import FredCollector
from alphapulse.market.collectors.investing_scraper import InvestingScraper
from alphapulse.market.analyzers.investor_flow import InvestorFlowAnalyzer
from alphapulse.market.analyzers.program_trade import ProgramTradeAnalyzer
from alphapulse.market.analyzers.market_breadth import MarketBreadthAnalyzer
from alphapulse.market.analyzers.fund_flow import FundFlowAnalyzer
from alphapulse.market.analyzers.macro_monitor import MacroMonitorAnalyzer
from alphapulse.market.engine.scoring import calculate_weighted_score
from alphapulse.core.storage import DataCache, PulseHistory

logger = logging.getLogger(__name__)


class SignalEngine:
    """모든 분석기를 종합하여 Market Pulse Score 산출"""

    def __init__(self, cache: DataCache | None = None, history: PulseHistory | None = None):
        self.config = Config()
        self.cache = cache or DataCache(str(self.config.CACHE_DB))
        self.history = history or PulseHistory(str(self.config.HISTORY_DB))

        # 수집기
        self.pykrx = PykrxCollector(cache=self.cache)
        self.fdr = FdrCollector(cache=self.cache)
        self.krx = KrxScraper(cache=self.cache)
        self.fred = FredCollector(cache=self.cache)
        self.investing = InvestingScraper(cache=self.cache)

        # 분석기
        self.investor_analyzer = InvestorFlowAnalyzer()
        self.program_analyzer = ProgramTradeAnalyzer()
        self.breadth_analyzer = MarketBreadthAnalyzer()
        self.fund_analyzer = FundFlowAnalyzer()
        self.macro_analyzer = MacroMonitorAnalyzer()

    def run(self, date: str | None = None, period: str = "daily") -> dict:
        """
        종합 시황 분석 실행

        Args:
            date: 분석 대상 날짜 (YYYYMMDD). None이면 오늘.
            period: 분석 기간 ('daily', 'weekly', 'monthly')

        Returns:
            dict with: score, signal, indicator_scores, details
        """
        if date:
            target_date = self.config.parse_date(date)
        else:
            # 기본값: 직전 거래일 (장 전 분석 기준)
            target_date = self.config.get_prev_trading_day()

        # 기간 설정
        period_days = {"daily": 5, "weekly": 5, "monthly": 20}.get(period, 5)
        start_date = self.config.get_date_str(period_days)

        logger.info(f"시황 분석 시작: {target_date} (기간: {start_date}~{target_date})")

        indicator_scores = {}
        details = {}

        # 1. 투자자 수급 (20%) — 직전 거래일 기준 + 5일 추세
        try:
            # 일별 추세 데이터(웹 크롤링)를 메인 소스로 사용
            # — 네이버 모바일 API trend는 당일(장중) 데이터를 반환하므로
            #   장전 분석 시 불완전할 수 있음
            trend_df = self.krx.get_investor_trend_daily(days=10)
            if trend_df is not None and not trend_df.empty and "외국인" in trend_df.columns:
                # 일별 추세 데이터를 수급 분석 형식으로 변환 (최근 1일 = 직전 거래일)
                latest = trend_df.head(1)
                trading_df = pd.DataFrame([{
                    "외국인합계": latest["외국인"].iloc[0] * 100_000_000,
                    "기관합계": latest["기관합계"].iloc[0] * 100_000_000,
                }])
            else:
                # 웹 크롤링 실패 시 네이버 모바일 API 폴백
                trading_df = self.pykrx.get_investor_trading(start_date, target_date)
                trend_df = None
            flow_result = self.investor_analyzer.analyze_flow(trading_df, trend_df=trend_df)
            indicator_scores["investor_flow"] = flow_result["score"]
            details["investor_flow"] = flow_result
        except Exception as e:
            logger.warning(f"투자자 수급 분석 실패: {e}")
            indicator_scores["investor_flow"] = None
            details["investor_flow"] = {"score": None, "details": f"분석 실패: {e}"}

        # 2. 선물 베이시스 (15%) — 현선물 괴리율로 시장 심리 판단
        try:
            basis = self.investing.get_futures_basis()
            if basis and "basis_pct" in basis:
                basis_pct = basis["basis_pct"]
                # 베이시스 기반 점수: 프리미엄(양수)=강세, 디스카운트(음수)=약세
                import numpy as np
                score = int(np.clip(basis_pct * 50, -100, 100))
                signal = "프리미엄(강세)" if basis_pct > 0 else "디스카운트(약세)"
                date_info = f" ({basis['date']})" if "date" in basis else ""
                align_result = {
                    "score": score,
                    "basis_pct": basis_pct,
                    "details": f"베이시스: {basis_pct:+.2f}% ({signal}) | 선물 {basis['futures_price']:.2f} / 현물 {basis['spot_price']:.2f}{date_info}",
                }
            else:
                align_result = {"score": 0, "details": "선물 베이시스 데이터 없음"}
            indicator_scores["spot_futures_align"] = align_result["score"]
            details["spot_futures_align"] = align_result
        except Exception as e:
            logger.warning(f"선물 베이시스 분석 실패: {e}")
            indicator_scores["spot_futures_align"] = None
            details["spot_futures_align"] = {"score": None, "details": f"분석 실패: {e}"}

        # 3. 프로그램 매매 (10%)
        try:
            program_df = self.krx.get_program_trading(target_date)
            program_result = self.program_analyzer.analyze(program_df)
            indicator_scores["program_trade"] = program_result["score"]
            details["program_trade"] = program_result
        except Exception as e:
            logger.warning(f"프로그램 매매 분석 실패: {e}")
            indicator_scores["program_trade"] = None
            details["program_trade"] = {"score": None, "details": f"분석 실패: {e}"}

        # 4. 업종 모멘텀 (10%)
        try:
            # 네이버 금융 업종별 등락률 우선, pykrx 폴백
            sector_df = self.krx.get_sector_performance()
            if sector_df.empty:
                sector_df = self.pykrx.get_sector_performance(start_date, target_date)
            sector_result = self.breadth_analyzer.analyze_sector_momentum(sector_df)
            indicator_scores["sector_momentum"] = sector_result["score"]
            details["sector_momentum"] = sector_result
        except Exception as e:
            logger.warning(f"업종 모멘텀 분석 실패: {e}")
            indicator_scores["sector_momentum"] = None
            details["sector_momentum"] = {"score": None, "details": f"분석 실패: {e}"}

        # 5. 환율 (10%)
        try:
            fx_df = self.fdr.get_exchange_rate(start_date, target_date)
            fx_result = self.macro_analyzer.analyze_exchange_rate(fx_df)
            indicator_scores["exchange_rate"] = fx_result["score"]
            details["exchange_rate"] = fx_result
        except Exception as e:
            logger.warning(f"환율 분석 실패: {e}")
            indicator_scores["exchange_rate"] = None
            details["exchange_rate"] = {"score": None, "details": f"분석 실패: {e}"}

        # 6. V-KOSPI (10%)
        try:
            # investing.com 우선, 네이버 금융 폴백
            vkospi_df = self.investing.get_vkospi()
            if vkospi_df.empty:
                vkospi_df = self.krx.get_vkospi(start_date, target_date)
            vkospi_result = self.macro_analyzer.analyze_vkospi(vkospi_df)
            indicator_scores["vkospi"] = vkospi_result["score"]
            details["vkospi"] = vkospi_result
        except Exception as e:
            logger.warning(f"V-KOSPI 분석 실패: {e}")
            indicator_scores["vkospi"] = None
            details["vkospi"] = {"score": None, "details": f"분석 실패: {e}"}

        # 7. 한미 금리차 (5%)
        try:
            us_rate = self.fred.get_us_treasury_10y(start_date, target_date)
            # 한국 금리: FDR → FRED 폴백 (FRED 한국 금리는 월간이므로 90일 범위로 조회)
            kr_rate = self.fdr.get_bond_yields_kr(start_date, target_date)
            if kr_rate.empty:
                wide_start = self.config.get_date_str(90)
                kr_rate = self.fred.get_kr_long_term_rate(wide_start, target_date)
            rate_result = self.macro_analyzer.analyze_interest_rate_diff(us_rate, kr_rate)
            indicator_scores["interest_rate_diff"] = rate_result["score"]
            details["interest_rate_diff"] = rate_result
        except Exception as e:
            logger.warning(f"금리차 분석 실패: {e}")
            indicator_scores["interest_rate_diff"] = None
            details["interest_rate_diff"] = {"score": None, "details": f"분석 실패: {e}"}

        # 8. 글로벌 시장 (15%) — 미국 선물 실시간 포함
        try:
            indices = self.fdr.get_global_indices(start_date, target_date)
            us_futures = None
            try:
                us_futures = self.investing.get_us_futures()
            except Exception:
                pass
            global_result = self.macro_analyzer.analyze_global_markets(indices, us_futures=us_futures)
            indicator_scores["global_market"] = global_result["score"]
            details["global_market"] = global_result
        except Exception as e:
            logger.warning(f"글로벌 시장 분석 실패: {e}")
            indicator_scores["global_market"] = None
            details["global_market"] = {"score": None, "details": f"분석 실패: {e}"}

        # 9. 증시 자금 (5%) — 시총 대비 신용잔고 비율 포함
        try:
            deposit_df = self.krx.get_deposit(start_date, target_date)
            credit_df = self.krx.get_credit_balance(start_date, target_date)
            market_cap = None
            if not deposit_df.empty:
                try:
                    market_cap = self.krx.get_total_market_cap()
                except Exception:
                    pass
            fund_result = self.fund_analyzer.analyze(deposit_df, credit_df, market_cap=market_cap)
            indicator_scores["fund_flow"] = fund_result["score"]
            details["fund_flow"] = fund_result
        except Exception as e:
            logger.warning(f"자금 동향 분석 실패: {e}")
            indicator_scores["fund_flow"] = None
            details["fund_flow"] = {"score": None, "details": f"분석 실패: {e}"}

        # 10. ADR + 거래량 (5%)
        try:
            ohlcv_df = self.pykrx.get_market_ohlcv(target_date)
            adr_result = self.breadth_analyzer.analyze_adr(ohlcv_df)
            indicator_scores["adr_volume"] = adr_result["score"]
            details["adr_volume"] = adr_result
        except Exception as e:
            logger.warning(f"ADR 분석 실패: {e}")
            indicator_scores["adr_volume"] = None
            details["adr_volume"] = {"score": None, "details": f"분석 실패: {e}"}

        # 종합 점수 산출
        final_score, signal = calculate_weighted_score(indicator_scores)

        # 이력 저장 (numpy 타입을 Python 네이티브로 변환)
        try:
            serializable_scores = {
                k: float(v) for k, v in indicator_scores.items() if v is not None
            }
            self.history.save(target_date, final_score, signal, {
                "indicator_scores": serializable_scores,
                "period": period,
            })
        except Exception as e:
            logger.warning(f"이력 저장 실패: {e}")

        return {
            "date": target_date,
            "period": period,
            "score": final_score,
            "signal": signal,
            "indicator_scores": indicator_scores,
            "details": details,
        }
