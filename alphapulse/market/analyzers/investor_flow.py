"""투자자 수급 분석"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class InvestorFlowAnalyzer:
    """투자자별 수급 분석 및 현선물 방향 일치 판단"""

    def analyze_flow(self, trading_df: pd.DataFrame, trend_df: pd.DataFrame = None) -> dict:
        """
        투자자별 수급 강도 분석 (다일치 추세 포함)

        Args:
            trading_df: 당일 투자자별 매매동향 (columns: 기관합계, 외국인합계)
            trend_df: 일별 추세 데이터 (columns: 외국인, 기관합계, 날짜별 억원 단위). Optional.

        Returns:
            dict with keys: score, foreign_net, institutional_net, trend, details
        """
        if trading_df is None or trading_df.empty:
            return {"score": 0, "foreign_net": 0, "institutional_net": 0, "details": "데이터 없음"}

        # 당일 또는 누적 외국인/기관 순매수
        foreign_net = trading_df["외국인합계"].sum()
        institutional_net = trading_df["기관합계"].sum()
        combined = foreign_net + institutional_net

        # 정규화 (1조 기준)
        trillion = 1_000_000_000_000
        ratio = combined / trillion
        score = np.clip(ratio * 50, -100, 100)

        # 외국인+기관 방향 일치 보너스
        if foreign_net > 0 and institutional_net > 0:
            score = min(score * 1.2, 100)
        elif foreign_net < 0 and institutional_net < 0:
            score = max(score * 1.2, -100)

        details = []
        details.append(f"외국인: {foreign_net/100_000_000:,.0f}억")
        details.append(f"기관: {institutional_net/100_000_000:,.0f}억")

        # 다일치 추세 분석 (외국인/기관 각각)
        trend_info = ""
        if trend_df is not None and not trend_df.empty and "외국인" in trend_df.columns:
            n = len(trend_df)
            if n >= 3:
                days_5 = min(n, 5)
                foreign_5d = trend_df["외국인"].head(days_5).sum()
                inst_5d = trend_df["기관합계"].head(days_5).sum()

                # 외국인/기관 각각 추세 판단: 최근 3일 vs 이전 3일
                recent = trend_df.head(3)
                prev = trend_df.iloc[3:6] if n >= 6 else trend_df.tail(min(3, n - 3))

                def _trend_label(recent_series, prev_df, col):
                    recent_avg = recent_series[col].mean()
                    if len(prev_df) > 0 and col in prev_df.columns:
                        prev_avg = prev_df[col].mean()
                        if recent_avg > 0 and prev_avg <= 0:
                            return "매수전환"
                        elif recent_avg > 0:
                            return "매수지속"
                        elif recent_avg <= 0 and prev_avg > 0:
                            return "매도전환"
                        else:
                            return "매도지속"
                    return "매수" if recent_avg > 0 else "매도"

                f_trend = _trend_label(recent, prev, "외국인")
                i_trend = _trend_label(recent, prev, "기관합계")
                trend_info = f"외국인 {f_trend} / 기관 {i_trend}"

                details.append(f"5일: 외국인 {foreign_5d:,.0f}억({f_trend}) 기관 {inst_5d:,.0f}억({i_trend})")

        return {
            "score": round(float(score)),
            "foreign_net": foreign_net,
            "institutional_net": institutional_net,
            "trend": trend_info,
            "details": " | ".join(details),
        }

    def analyze_spot_futures_alignment(
        self, spot_df: pd.DataFrame, futures_df: pd.DataFrame
    ) -> dict:
        """
        현선물 방향 일치 분석

        Args:
            spot_df: 현물 투자자별 매매동향
            futures_df: 선물 투자자별 매매동향

        Returns:
            dict with keys: score (-100~100), aligned (bool), details
        """
        if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
            return {"score": 0, "aligned": None, "details": "데이터 없음"}

        # 외국인 현물/선물 방향 비교
        foreign_spot = spot_df["외국인합계"].sum()
        foreign_futures = futures_df["외국인합계"].sum() if "외국인합계" in futures_df.columns else 0

        foreign_aligned = (foreign_spot > 0 and foreign_futures > 0) or \
                         (foreign_spot < 0 and foreign_futures < 0)

        if foreign_aligned:
            # 방향 일치 = 강한 신호
            if foreign_spot > 0:
                score = 80  # 매수 방향 일치
            else:
                score = -80  # 매도 방향 일치
        else:
            # 방향 불일치 = 전환 경고, 중립쪽으로
            score = 0

        details = f"외국인 현물 {'매수' if foreign_spot > 0 else '매도'} / 선물 {'매수' if foreign_futures > 0 else '매도'} → {'일치' if foreign_aligned else '불일치'}"

        return {
            "score": score,
            "aligned": bool(foreign_aligned),
            "details": details,
        }

    def get_top_stocks(self, trading_by_ticker: pd.DataFrame, n: int = 10) -> dict:
        """외국인/기관 순매수 상위 종목"""
        if trading_by_ticker is None or trading_by_ticker.empty:
            return {"top_buy": [], "top_sell": []}

        sorted_df = trading_by_ticker.sort_values("순매수", ascending=False)
        top_buy = sorted_df.head(n)
        top_sell = sorted_df.tail(n).sort_values("순매수")

        return {
            "top_buy": top_buy.to_dict("records") if not top_buy.empty else [],
            "top_sell": top_sell.to_dict("records") if not top_sell.empty else [],
        }
