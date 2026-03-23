"""시장 체력 분석 - 업종 모멘텀, ADR, 거래량"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MarketBreadthAnalyzer:
    """업종 동향 + ADR + 거래량 분석"""

    def analyze_sector_momentum(self, sector_df: pd.DataFrame) -> dict:
        """
        업종별 모멘텀 분석

        Args:
            sector_df: DataFrame with sector performance (등락률 column)

        Returns:
            dict with score, top_sectors, bottom_sectors, details
        """
        if sector_df is None or sector_df.empty:
            return {"score": 0, "top_sectors": [], "bottom_sectors": [], "details": "데이터 없음"}

        change_col = None
        for col in ["등락률", "변동률", "수익률"]:
            if col in sector_df.columns:
                change_col = col
                break

        if change_col is None:
            return {"score": 0, "top_sectors": [], "bottom_sectors": [], "details": "등락률 데이터 없음"}

        avg_change = sector_df[change_col].mean()
        positive_ratio = (sector_df[change_col] > 0).sum() / len(sector_df)

        # 평균 등락률과 상승 업종 비율로 점수 산출
        score = np.clip(avg_change * 20 + (positive_ratio - 0.5) * 100, -100, 100)

        sorted_sectors = sector_df.sort_values(change_col, ascending=False)

        return {
            "score": round(float(score)),
            "top_sectors": sorted_sectors.head(3).to_dict("records") if len(sorted_sectors) >= 3 else [],
            "bottom_sectors": sorted_sectors.tail(3).to_dict("records") if len(sorted_sectors) >= 3 else [],
            "details": f"평균 등락률: {avg_change:.2f}% | 상승 업종 비율: {positive_ratio:.0%}",
        }

    def analyze_adr(self, ohlcv_df: pd.DataFrame) -> dict:
        """
        ADR (등락비율) + 거래량 분석

        Args:
            ohlcv_df: 전 종목 OHLCV DataFrame (등락률, 거래량 columns)

        Returns:
            dict with score, adr, details
        """
        if ohlcv_df is None or ohlcv_df.empty:
            return {"score": 0, "adr": None, "details": "데이터 없음"}

        change_col = "등락률"
        if change_col not in ohlcv_df.columns:
            return {"score": 0, "adr": None, "details": "등락률 데이터 없음"}

        advancing = (ohlcv_df[change_col] > 0).sum()
        declining = (ohlcv_df[change_col] < 0).sum()
        unchanged = (ohlcv_df[change_col] == 0).sum()

        adr = advancing / max(declining, 1)

        # ADR 기반 점수: 1.0 = 중립, >1.5 = 강한 상승, <0.5 = 강한 하락
        adr_score = np.clip((adr - 1.0) * 100, -100, 100)

        # 거래량 동반 여부 확인
        vol_col = "거래량"
        volume_note = ""
        if vol_col in ohlcv_df.columns:
            total_volume = ohlcv_df[vol_col].sum()
            volume_note = f" | 총 거래량: {total_volume:,.0f}"

        score = round(float(adr_score))

        return {
            "score": score,
            "adr": round(adr, 2),
            "advancing": int(advancing),
            "declining": int(declining),
            "unchanged": int(unchanged),
            "details": f"ADR: {adr:.2f} (상승 {advancing} / 하락 {declining} / 보합 {unchanged}){volume_note}",
        }
