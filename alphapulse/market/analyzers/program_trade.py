"""프로그램 매매 분석"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ProgramTradeAnalyzer:
    """프로그램 매매(차익/비차익) 분석"""

    def analyze(self, program_df: pd.DataFrame) -> dict:
        """
        프로그램 매매 방향성 분석

        Args:
            program_df: DataFrame with columns like 비차익순매수, 차익순매수

        Returns:
            dict with score, details
        """
        if program_df is None or program_df.empty:
            return {"score": 0, "details": "데이터 없음"}

        # 비차익 순매수가 핵심 지표
        non_arb_col = None
        for col in ["비차익순매수", "비차익_순매수", "순매수"]:
            if col in program_df.columns:
                non_arb_col = col
                break

        if non_arb_col is None:
            # Try to compute from available columns
            if "비차익매수" in program_df.columns and "비차익매도" in program_df.columns:
                program_df["비차익순매수"] = program_df["비차익매수"] - program_df["비차익매도"]
                non_arb_col = "비차익순매수"
            else:
                return {"score": 0, "details": "비차익거래 데이터 컬럼 없음"}

        net_value = program_df[non_arb_col].sum()

        # 1000억 단위 정규화
        hundred_billion = 100_000_000_000
        ratio = net_value / hundred_billion
        score = np.clip(ratio * 25, -100, 100)

        direction = "순매수" if net_value > 0 else "순매도"
        details = f"비차익 {direction}: {abs(net_value)/100_000_000:,.0f}억원"

        return {
            "score": round(float(score)),
            "details": details,
        }
