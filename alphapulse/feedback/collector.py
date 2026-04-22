"""피드백 데이터 수집 — 시장 결과 수집 + 수익률 계산 + 적중 판정."""

import logging
from datetime import datetime, timedelta

from alphapulse.core.config import Config
from alphapulse.core.storage.feedback import FeedbackStore

logger = logging.getLogger(__name__)


def calculate_hit(score: float, return_pct: float) -> int:
    """시그널 방향 적중 판정.

    - bullish (score >= 20) + positive return = hit
    - bearish (score <= -20) + negative return = hit
    - neutral (-19 < score < 20) + small move (±0.5%) = hit
    """
    if score >= 20:  # bullish
        return 1 if return_pct > 0 else 0
    elif score <= -20:  # bearish
        return 1 if return_pct < 0 else 0
    else:  # neutral
        return 1 if abs(return_pct) < 0.5 else 0


class FeedbackCollector:
    """시장 결과 수집 + 과거 시그널 평가."""

    def __init__(self, db_path=None):
        self.config = Config()
        db = db_path or (self.config.DATA_DIR / "feedback.db")
        self.store = FeedbackStore(db)

    def _get_index_data(self, date: str, symbol: str, label: str) -> dict:
        """지수 종가/등락률 수집 (FinanceDataReader Yahoo 백엔드).

        pykrx 1.2.x 는 KRX 로그인 요구하고 KOSPI/KOSDAQ 지수 조회 시 '지수명'
        KeyError 발생. FDR 의 Yahoo 백엔드(^KS11/^KQ11)는 인증 불필요.
        """
        try:
            import FinanceDataReader as fdr

            # FDR 은 YYYY-MM-DD 형식을 받음
            iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            df = fdr.DataReader(symbol, iso, iso)
            if not df.empty:
                close = float(df["Close"].iloc[-1])
                open_ = float(df["Open"].iloc[-1])
                change_pct = (close / open_ - 1) * 100 if open_ else 0.0
                return {"close": close, "change_pct": round(change_pct, 2)}
        except Exception as e:
            logger.warning(f"{label} 데이터 수집 실패 ({date}): {e}")
        return {"close": None, "change_pct": None}

    def _get_kospi_data(self, date: str) -> dict:
        """KOSPI 종가/등락률 수집."""
        return self._get_index_data(date, "^KS11", "KOSPI")

    def _get_kosdaq_data(self, date: str) -> dict:
        """KOSDAQ 종가/등락률 수집."""
        return self._get_index_data(date, "^KQ11", "KOSDAQ")

    def _get_kospi_close_series(self, start: str, end: str) -> dict:
        """기간 내 KOSPI 일별 종가 dict (YYYYMMDD -> float)."""
        try:
            import FinanceDataReader as fdr

            start_iso = f"{start[:4]}-{start[4:6]}-{start[6:]}"
            end_iso = f"{end[:4]}-{end[4:6]}-{end[6:]}"
            df = fdr.DataReader("^KS11", start_iso, end_iso)
            if not df.empty:
                return {
                    d.strftime("%Y%m%d"): float(row["Close"])
                    for d, row in df.iterrows()
                }
        except Exception as e:
            logger.warning(f"KOSPI 시계열 수집 실패: {e}")
        return {}

    def collect_market_result(self, date: str) -> dict:
        """특정 날짜의 KOSPI/KOSDAQ 결과 수집."""
        kospi = self._get_kospi_data(date)
        kosdaq = self._get_kosdaq_data(date)
        return {
            "kospi_close": kospi["close"],
            "kospi_change_pct": kospi["change_pct"],
            "kosdaq_close": kosdaq["close"],
            "kosdaq_change_pct": kosdaq["change_pct"],
        }

    def calculate_returns(self, signal_date: str, base_close: float) -> dict:
        """시그널 발행일 기준 1d/3d/5d 수익률 계산."""
        # 시그널 발행일 이후 10거래일 종가 가져오기
        dt = datetime.strptime(signal_date, "%Y%m%d")
        end_dt = dt + timedelta(days=15)  # 충분한 기간
        series = self._get_kospi_close_series(
            signal_date, end_dt.strftime("%Y%m%d")
        )

        if not series or base_close is None or base_close == 0:
            return {"return_1d": None, "return_3d": None, "return_5d": None}

        # 거래일 기준으로 정렬 (시그널 발행일 제외)
        sorted_dates = sorted(d for d in series.keys() if d > signal_date)

        def get_return(n_days):
            if len(sorted_dates) >= n_days:
                future_close = series[sorted_dates[n_days - 1]]
                return round((future_close / base_close - 1) * 100, 2)
            return None

        return {
            "return_1d": get_return(1),
            "return_3d": get_return(3),
            "return_5d": get_return(5),
        }

    def collect_and_evaluate(self):
        """미평가 시그널에 대해 시장 결과 수집 + 적중 판정."""
        pending = self.store.get_pending_evaluation()
        if not pending:
            logger.info("평가 대기 중인 시그널 없음")
            return

        for signal in pending:
            date = signal["date"]
            score = signal["score"]
            logger.info(f"시그널 평가 중: {date} (score={score})")

            # 시장 결과 수집
            result = self.collect_market_result(date)
            if result["kospi_close"] is None:
                logger.info(f"시장 데이터 미확인 (아직 거래일 아님?): {date}")
                continue

            # 1d 수익률 = 당일 KOSPI 등락률
            return_1d = result["kospi_change_pct"]
            hit_1d = (
                calculate_hit(score, return_1d) if return_1d is not None else None
            )

            self.store.update_result(
                date=date,
                kospi_close=result["kospi_close"],
                kospi_change_pct=result["kospi_change_pct"],
                kosdaq_close=result["kosdaq_close"],
                kosdaq_change_pct=result["kosdaq_change_pct"],
                return_1d=return_1d,
                hit_1d=hit_1d,
            )

            # 3d/5d 수익률 (부분 평가)
            returns = self.calculate_returns(date, result["kospi_close"])
            if returns["return_3d"] is not None:
                self.store.update_returns(
                    date=date,
                    return_3d=returns["return_3d"],
                    hit_3d=calculate_hit(score, returns["return_3d"]),
                )
            if returns["return_5d"] is not None:
                self.store.update_returns(
                    date=date,
                    return_5d=returns["return_5d"],
                    hit_5d=calculate_hit(score, returns["return_5d"]),
                )

        logger.info(f"{len(pending)}개 시그널 평가 완료")
