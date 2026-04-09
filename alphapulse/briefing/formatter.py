"""브리핑 메시지 포맷팅 (Telegram HTML)."""

from datetime import datetime

from alphapulse.core.constants import INDICATOR_NAMES


class BriefingFormatter:
    """브리핑 데이터를 Telegram HTML 메시지로 변환."""

    def _score_emoji(self, score: float) -> str:
        if score >= 60:
            return "\U0001f7e2"  # green circle
        elif score >= 20:
            return "\U0001f535"  # blue circle
        elif score >= -19:
            return "\u26aa"  # white circle
        elif score >= -59:
            return "\U0001f7e0"  # orange circle
        else:
            return "\U0001f534"  # red circle

    def _format_date(self, date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            weekdays = ["월", "화", "수", "목", "금", "토", "일"]
            return f"{dt.strftime('%Y-%m-%d')} ({weekdays[dt.weekday()]})"
        except (ValueError, TypeError):
            return date_str

    def format_quantitative(self, pulse_result: dict, daily_result_msg: str = "") -> str:
        """정량 리포트 HTML 포맷팅."""
        score = pulse_result["score"]
        signal = pulse_result["signal"]
        date_str = self._format_date(pulse_result.get("date", ""))
        indicator_scores = pulse_result.get("indicator_scores", {})
        lines = [
            f"<b>📊 AlphaPulse 정량 리포트 — {date_str}</b>",
            "━" * 28,
            f"<b>Market Pulse Score: {score:+.0f} ({signal})</b>",
            "대상: KOSPI/KOSDAQ (한국시장)",
            "",
        ]
        for key, name in INDICATOR_NAMES.items():
            s = indicator_scores.get(key)
            if s is not None:
                emoji = self._score_emoji(s)
                lines.append(f"{emoji} {name}: <b>{s:+.0f}</b>")

        # Append yesterday's result if available
        if daily_result_msg:
            lines.append("")
            lines.append(daily_result_msg)

        return "\n".join(lines)

    def format_synthesis(
        self,
        pulse_result: dict,
        content_summaries: list[str],
        commentary: str | None,
        weekly_summary: str = "",
    ) -> str:
        """종합 리포트 HTML 포맷팅."""
        signal = pulse_result.get("signal", "")
        date_str = self._format_date(pulse_result.get("date", ""))
        lines = [
            f"<b>📋 AlphaPulse 종합 리포트 — {date_str}</b>",
            "━" * 28,
            f"<b>[종합 판단: {signal}]</b>",
            "",
        ]
        if commentary:
            lines.append(commentary)
            lines.append("")
        if content_summaries:
            lines.append("<b>[참고 정성 분석]</b>")
            for s in content_summaries[:3]:
                lines.append(f"• {s}")
        else:
            lines.append("<i>최근 콘텐츠 분석 없음 — 정량 데이터 기반 판단</i>")

        # Append weekly summary if available (Monday only — caller decides)
        if weekly_summary:
            lines.append("")
            lines.append(weekly_summary)

        return "\n".join(lines)
