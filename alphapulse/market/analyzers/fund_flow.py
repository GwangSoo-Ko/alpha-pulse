"""증시 자금 동향 분석"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FundFlowAnalyzer:
    """고객 예탁금 + 신용잔고 분석"""

    def analyze(
        self,
        deposit_df: pd.DataFrame = None,
        credit_df: pd.DataFrame = None,
        market_cap: dict = None,
    ) -> dict:
        """
        증시 자금 동향 분석 (시총 대비 신용잔고 과열 판단 포함)

        Args:
            deposit_df: 고객 예탁금 추이
            credit_df: 신용잔고 추이
            market_cap: 시가총액 dict (KOSPI, KOSDAQ, total — 억원 단위). Optional.

        Returns:
            dict with score, details
        """
        scores = []
        details_parts = []

        # 예탁금 분석
        if deposit_df is not None and not deposit_df.empty:
            deposit_change = self._calculate_trend(deposit_df)
            deposit_score = np.clip(deposit_change * 10, -50, 50)
            scores.append(deposit_score)
            direction = "증가" if deposit_change > 0 else "감소"
            details_parts.append(f"예탁금 {direction}: {abs(deposit_change):.1f}%")

        # 신용잔고 분석
        if credit_df is not None and not credit_df.empty:
            credit_change = self._calculate_trend(credit_df)
            credit_score = np.clip(-credit_change * 10, -50, 50)
            scores.append(credit_score)

            # 시총 대비 신용잔고 비율 판단
            if market_cap and market_cap.get("total", 0) > 0:
                # 신용잔고 최신값 (억원 단위)
                credit_col = "신용잔고" if "신용잔고" in credit_df.columns else credit_df.select_dtypes(include=[np.number]).columns[0]
                latest_credit = credit_df[credit_col].iloc[0] / 100_000_000  # 원→억
                total_cap = market_cap["total"]  # 이미 억원 단위
                credit_ratio = (latest_credit / total_cap) * 100

                if credit_ratio > 0.5:
                    details_parts.append(f"신용/시총: {credit_ratio:.2f}% (과열 위험)")
                elif credit_ratio > 0.3:
                    details_parts.append(f"신용/시총: {credit_ratio:.2f}% (경계)")
                else:
                    details_parts.append(f"신용/시총: {credit_ratio:.2f}% (정상)")
            else:
                details_parts.append(f"신용잔고 변화: {credit_change:.1f}%")

        if not scores:
            return {"score": 0, "details": "데이터 없음 (T+1~2일 지연)"}

        final_score = round(float(np.mean(scores)))

        return {
            "score": np.clip(final_score, -100, 100),
            "details": " | ".join(details_parts) if details_parts else "데이터 부족",
        }

    def _calculate_trend(self, df: pd.DataFrame) -> float:
        """DataFrame의 첫 번째 수치 컬럼의 변화율(%) 계산"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return 0.0
        col = numeric_cols[0]
        values = df[col].dropna()
        if len(values) < 2:
            return 0.0
        first = values.iloc[0]
        last = values.iloc[-1]
        if first == 0:
            return 0.0
        return ((last - first) / abs(first)) * 100
