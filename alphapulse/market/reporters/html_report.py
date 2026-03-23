"""HTML 리포트 생성기"""

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from jinja2 import Environment, FileSystemLoader

from alphapulse.core.config import Config

_config = Config()
WEIGHTS = _config.WEIGHTS

TEMPLATE_DIR = Path(__file__).parent / "templates"

INDICATOR_NAMES = {
    "investor_flow": "외국인+기관 수급",
    "spot_futures_align": "선물 베이시스",
    "program_trade": "프로그램 비차익",
    "sector_momentum": "업종 모멘텀",
    "exchange_rate": "환율 (USD/KRW)",
    "vkospi": "V-KOSPI",
    "interest_rate_diff": "한미 금리차",
    "global_market": "글로벌 시장",
    "fund_flow": "증시 자금",
    "adr_volume": "ADR + 거래량",
}


def _score_color(score: float) -> str:
    if score >= 20:
        return "#4ade80"
    elif score >= -19:
        return "#fbbf24"
    else:
        return "#f87171"


def _generate_chart(indicator_scores: dict) -> str | None:
    """지표별 점수 바 차트를 base64 PNG로 생성"""
    active = {k: v for k, v in indicator_scores.items() if v is not None}
    if not active:
        return None

    names = [INDICATOR_NAMES.get(k, k) for k in active]
    scores = list(active.values())
    colors = [_score_color(s) for s in scores]

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    bars = ax.barh(names, scores, color=colors, height=0.6)
    ax.set_xlim(-100, 100)
    ax.axvline(x=0, color="#64748b", linewidth=0.8)
    ax.tick_params(colors="#94a3b8")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#334155")
    ax.spines["left"].set_color("#334155")

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_width() + (3 if score >= 0 else -3),
            bar.get_y() + bar.get_height() / 2,
            f"{score:+d}",
            ha="left" if score >= 0 else "right",
            va="center",
            color="#e2e8f0",
            fontsize=9,
        )

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_html_report(result: dict, output_path: str = "report.html"):
    """시황 분석 결과를 HTML 리포트로 생성"""
    date = result["date"]
    score = result["score"]
    signal = result["signal"]
    indicator_scores = result.get("indicator_scores", {})
    details = result.get("details", {})

    score_color = _score_color(score)

    indicators = []
    for key, weight in WEIGHTS.items():
        ind_score = indicator_scores.get(key)
        detail_info = details.get(key, {})
        detail_text = detail_info.get("details", "-") if isinstance(detail_info, dict) else "-"

        if ind_score is not None:
            score_class = "score-positive" if ind_score >= 20 else ("score-neutral" if ind_score >= -19 else "score-negative")
            score_display = f"{ind_score:+d}"
            bar_width = (ind_score + 100) / 2  # 0~100%
            bar_color = _score_color(ind_score)
        else:
            score_class = "score-na"
            score_display = "N/A"
            bar_width = 50
            bar_color = "#64748b"

        indicators.append({
            "name": INDICATOR_NAMES.get(key, key),
            "weight": f"{weight:.0%}",
            "score_display": score_display,
            "score_class": score_class,
            "bar_width": bar_width,
            "bar_color": bar_color,
            "details": detail_text[:50],
        })

    chart_base64 = _generate_chart(indicator_scores)

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    html = template.render(
        date_formatted=f"{date[:4]}-{date[4:6]}-{date[6:]}",
        period=result.get("period", "daily"),
        score=f"{score:+.1f}",
        signal=signal,
        score_color=score_color,
        score_border_color=score_color,
        indicators=indicators,
        chart_base64=chart_base64,
    )

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
