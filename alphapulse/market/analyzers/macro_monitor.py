"""매크로 환경 분석"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MacroMonitorAnalyzer:
    """환율, V-KOSPI, 금리차, 글로벌 시장 분석"""

    def analyze_exchange_rate(self, fx_df: pd.DataFrame) -> dict:
        """
        환율(USD/KRW) 추세 + 변동성 분석
        - 방향: 원화 강세(환율 하락) = 긍정, 약세(환율 상승) = 부정
        - 변동성: 급격한 변동 = 불확실성 증가 = 추가 감점

        Returns:
            dict with score (-100~100), details
        """
        if fx_df is None or fx_df.empty:
            return {"score": 0, "details": "환율 데이터 없음"}

        close_col = "Close" if "Close" in fx_df.columns else fx_df.columns[0]
        values = fx_df[close_col].dropna()

        if len(values) < 2:
            return {"score": 0, "details": "환율 데이터 부족"}

        # 방향 점수
        change_pct = ((values.iloc[-1] - values.iloc[0]) / values.iloc[0]) * 100
        direction_score = np.clip(-change_pct * 30, -100, 100)

        # 변동성 페널티 (일간 변화율의 표준편차)
        daily_changes = values.pct_change().dropna()
        volatility = daily_changes.std() * 100 if len(daily_changes) > 1 else 0

        if volatility > 1.0:
            vol_penalty = -20
            vol_level = "급등"
        elif volatility > 0.5:
            vol_penalty = -10
            vol_level = "확대"
        else:
            vol_penalty = 0
            vol_level = "정상"

        score = np.clip(direction_score + vol_penalty, -100, 100)

        direction = "강세" if change_pct < 0 else "약세"
        current = values.iloc[-1]

        vol_note = f" | 변동성: {volatility:.2f}% ({vol_level})" if vol_penalty != 0 else ""

        return {
            "score": round(float(score)),
            "current_rate": float(current),
            "volatility": round(volatility, 3),
            "details": f"USD/KRW {current:,.1f} (원화 {direction}, {change_pct:+.2f}%){vol_note}",
        }

    def analyze_vkospi(self, vkospi_df: pd.DataFrame) -> dict:
        """
        V-KOSPI 수준 분석 (역투자 신호 포함)

        구간별 해석:
        - <15: 과열/안일 → 시장 과열 경고 (부정)
        - 15~20: 안정 → 긍정
        - 20~25: 경계 시작 → 약간 부정
        - 25~35: 공포 → 부정적이나 역투자 접근 가능
        - >35: 극단적 공포 → 단기 부정이나 역투자 매수 기회

        Returns:
            dict with score, level, details
        """
        if vkospi_df is None or vkospi_df.empty:
            return {"score": 0, "level": None, "details": "V-KOSPI 데이터 없음"}

        close_col = "Close" if "Close" in vkospi_df.columns else vkospi_df.columns[0]
        current = float(vkospi_df[close_col].dropna().iloc[-1])

        if current < 15:
            score = -30
            level = "과열(안일)"
            note = "시장 안일 — 변동성 급등 리스크"
        elif current <= 20:
            score = 30
            level = "안정"
            note = "정상 변동성"
        elif current <= 25:
            score = -10
            level = "경계"
            note = "변동성 확대 초기"
        elif current <= 35:
            score = -50
            level = "공포"
            note = "투매 가능성 — 역투자 관찰 구간"
        elif current <= 50:
            score = -30
            level = "극단적 공포"
            note = "역투자 매수 검토 구간 (공포가 극대화)"
        else:
            score = -10
            level = "패닉"
            note = "시장 패닉 — 역사적 매수 기회 가능성"

        return {
            "score": score,
            "level": level,
            "current": current,
            "details": f"V-KOSPI: {current:.2f} ({level}) — {note}",
        }

    def analyze_interest_rate_diff(
        self, us_rate_df: pd.DataFrame, kr_rate_df: pd.DataFrame
    ) -> dict:
        """
        한미 금리차 분석
        금리차 축소 = 긍정, 확대 = 부정

        Returns:
            dict with score, details
        """
        if us_rate_df is None or us_rate_df.empty or kr_rate_df is None or kr_rate_df.empty:
            return {"score": 0, "details": "금리 데이터 없음"}

        us_col = us_rate_df.columns[0] if len(us_rate_df.columns) > 0 else None
        kr_col = kr_rate_df.columns[0] if len(kr_rate_df.columns) > 0 else None

        if us_col is None or kr_col is None:
            return {"score": 0, "details": "금리 데이터 컬럼 없음"}

        us_rate = float(us_rate_df[us_col].dropna().iloc[-1])
        kr_rate = float(kr_rate_df[kr_col].dropna().iloc[-1])

        diff = us_rate - kr_rate  # 양수 = 미국 금리가 높음 = 자금 이탈 압력

        # 금리차 축소 = 긍정
        score = np.clip(-diff * 30, -100, 100)

        return {
            "score": round(float(score)),
            "us_rate": us_rate,
            "kr_rate": kr_rate,
            "diff": round(diff, 2),
            "details": f"미국 {us_rate:.2f}% / 한국 {kr_rate:.2f}% (차이: {diff:+.2f}%p)",
        }

    def analyze_global_markets(self, indices: dict, us_futures: dict = None) -> dict:
        """
        글로벌 시장 동향 분석 (미국 선물 실시간 포함)

        Args:
            indices: dict of {name: DataFrame} for global indices (전일 종가)
            us_futures: dict of {SP500_futures: pct, NASDAQ_futures: pct} (실시간 선물 변동률)

        Returns:
            dict with score, details
        """
        if not indices and not us_futures:
            return {"score": 0, "details": "글로벌 시장 데이터 없음"}

        changes = []
        details_parts = []

        # 전일 종가 기반
        for name, df in (indices or {}).items():
            if df is None or df.empty:
                continue
            close_col = "Close" if "Close" in df.columns else df.columns[0]
            values = df[close_col].dropna()
            if len(values) < 2:
                continue
            change = ((values.iloc[-1] - values.iloc[-2]) / values.iloc[-2]) * 100
            changes.append(change)
            details_parts.append(f"{name}: {change:+.2f}%")

        # 미국 선물 실시간 (전일 종가와 블렌딩)
        futures_changes = []
        if us_futures:
            for key, pct in us_futures.items():
                if pct != 0:
                    name = key.replace("_futures", " 선물")
                    futures_changes.append(pct)
                    details_parts.append(f"{name}: {pct:+.2f}%")

        if not changes and not futures_changes:
            return {"score": 0, "details": "글로벌 시장 변동 데이터 부족"}

        # 블렌딩: 전일 종가 60% + 실시간 선물 40%
        if changes and futures_changes:
            close_avg = np.mean(changes)
            futures_avg = np.mean(futures_changes)
            blended = close_avg * 0.6 + futures_avg * 0.4
        elif changes:
            blended = np.mean(changes)
        else:
            blended = np.mean(futures_changes)

        score = np.clip(blended * 30, -100, 100)

        return {
            "score": round(float(score)),
            "details": " | ".join(details_parts),
        }
