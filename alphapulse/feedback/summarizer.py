"""피드백 요약 — AI 프롬프트용 컨텍스트 + 텔레그램 메시지 포맷."""

import logging
from alphapulse.core.storage.feedback import FeedbackStore
from alphapulse.feedback.evaluator import FeedbackEvaluator

logger = logging.getLogger(__name__)


class FeedbackSummarizer:
    def __init__(self, store: FeedbackStore | None = None, evaluator: FeedbackEvaluator | None = None):
        if store is None:
            from alphapulse.core.config import Config
            cfg = Config()
            store = FeedbackStore(cfg.DATA_DIR / "feedback.db")
        self.store = store
        self.evaluator = evaluator or FeedbackEvaluator(store=store)

    def generate_ai_context(self, days: int = 30) -> str:
        """AI 에이전트 프롬프트 주입용 피드백 요약 텍스트."""
        rates = self.evaluator.get_hit_rates(days)
        if rates["total_evaluated"] == 0:
            return "=== 피드백 컨텍스트 === \n피드백 데이터 부족 (평가된 시그널 없음)"

        corr = self.evaluator.get_correlation(days)
        accuracy = self.evaluator.get_indicator_accuracy(days)

        lines = [
            f"=== 피드백 컨텍스트 (최근 {days}일 기준) ===",
            "",
            "[적중률]",
            f"전체: 1일 {rates['hit_rate_1d']:.0%} ({rates['count_1d']}건)"
            f" | 3일 {rates['hit_rate_3d']:.0%} ({rates['count_3d']}건)"
            f" | 5일 {rates['hit_rate_5d']:.0%} ({rates['count_5d']}건)",
        ]
        if corr is not None:
            lines.append(f"상관계수: {corr:.2f} (시그널 강도↔1일 수익률)")

        if accuracy:
            lines.append("")
            lines.append("[지표별 신뢰도] (극단값 기준)")
            sorted_acc = sorted(accuracy.items(), key=lambda x: x[1]["accuracy"], reverse=True)
            for key, val in sorted_acc:
                level = "높음" if val["accuracy"] >= 0.7 else "보통" if val["accuracy"] >= 0.5 else "낮음"
                lines.append(f"  {level}: {key} {val['accuracy']:.0%} ({val['total']}건)")

        return "\n".join(lines)

    def format_daily_result(self, yesterday_signal: dict | None) -> str:
        """텔레그램 매일 한 줄: 어제 시그널 결과."""
        if not yesterday_signal or yesterday_signal.get("return_1d") is None:
            return ""

        score = yesterday_signal["score"]
        signal = yesterday_signal["signal"]
        ret = yesterday_signal["return_1d"]
        hit = yesterday_signal.get("hit_1d")
        emoji = "✅" if hit == 1 else "❌"

        return f"📊 어제 시그널 결과: {signal}({score:+.0f}) → KOSPI {ret:+.1f}% {emoji}"

    def format_weekly_summary(self) -> str:
        """텔레그램 주간 피드백 요약."""
        rates = self.evaluator.get_hit_rates(days=7)
        if rates["total_evaluated"] == 0:
            return ""

        accuracy = self.evaluator.get_indicator_accuracy(days=7)
        corr = self.evaluator.get_correlation(days=7)

        lines = [
            "<b>📈 주간 피드백</b>",
            f"적중률: 1일 {rates['hit_rate_1d']:.0%} ({rates['count_1d']}건)"
            f" | 3일 {rates['hit_rate_3d']:.0%} ({rates['count_3d']}건)"
            f" | 5일 {rates['hit_rate_5d']:.0%} ({rates['count_5d']}건)",
        ]

        if accuracy:
            best = max(accuracy.items(), key=lambda x: x[1]["accuracy"], default=None)
            worst = min(accuracy.items(), key=lambda x: x[1]["accuracy"], default=None)
            if best and worst:
                lines.append(f"최고 지표: {best[0]} ({best[1]['accuracy']:.0%}) | 최저: {worst[0]} ({worst[1]['accuracy']:.0%})")

        if corr is not None:
            lines.append(f"상관계수: {corr:.2f}")

        return "\n".join(lines)
