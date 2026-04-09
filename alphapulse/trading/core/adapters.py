"""기존 AlphaPulse 시스템 → Trading 데이터 모델 변환 어댑터."""


class PulseResultAdapter:
    """기존 SignalEngine dict → trading 데이터 모델 변환."""

    @staticmethod
    def to_market_context(pulse_result: dict) -> dict:
        """SignalEngine.run() 결과를 전략이 소비하는 형태로 변환한다.

        Args:
            pulse_result: SignalEngine.run() 반환 딕셔너리.

        Returns:
            market_context 딕셔너리.
        """
        return {
            "date": pulse_result["date"],
            "pulse_score": pulse_result["score"],
            "pulse_signal": pulse_result["signal"],
            "indicator_scores": pulse_result["indicator_scores"],
            "details": pulse_result.get("details", {}),
        }

    @staticmethod
    def to_feedback_context(hit_rates: dict,
                            correlation: float | None) -> str:
        """FeedbackEvaluator 결과를 AI 입력 문자열로 변환한다.

        Args:
            hit_rates: 적중률 딕셔너리 (hit_rate_1d, total_evaluated 등).
            correlation: 시그널-수익률 상관계수.

        Returns:
            AI 프롬프트에 주입할 피드백 컨텍스트 문자열.
        """
        total = hit_rates.get("total_evaluated", 0)
        if total < 5:
            return "피드백 데이터가 부족합니다 (5건 미만). 정량 시그널 기반으로 판단하세요."

        rate_1d = hit_rates.get("hit_rate_1d", 0)
        rate_3d = hit_rates.get("hit_rate_3d", 0)
        rate_5d = hit_rates.get("hit_rate_5d", 0)
        corr_str = f"{correlation:.2f}" if correlation is not None else "N/A"

        return (
            f"과거 시그널 성과 ({total}건 평가): "
            f"1일 적중률 {rate_1d * 100:.1f}%, "
            f"3일 {rate_3d * 100:.1f}%, "
            f"5일 {rate_5d * 100:.1f}%. "
            f"시그널-수익률 상관계수: {corr_str}."
        )
