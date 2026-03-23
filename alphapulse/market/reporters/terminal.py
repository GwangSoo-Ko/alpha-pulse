"""rich 기반 터미널 리포터"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.layout import Layout

from alphapulse.core.config import Config

_config = Config()
WEIGHTS = _config.WEIGHTS

console = Console()

SCORE_COLORS = {
    "strong_bullish": "bold bright_green",
    "moderately_bullish": "green",
    "neutral": "yellow",
    "moderately_bearish": "red",
    "strong_bearish": "bold bright_red",
}

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


def _get_score_style(score: float) -> str:
    if score >= 60:
        return SCORE_COLORS["strong_bullish"]
    elif score >= 20:
        return SCORE_COLORS["moderately_bullish"]
    elif score >= -19:
        return SCORE_COLORS["neutral"]
    elif score >= -59:
        return SCORE_COLORS["moderately_bearish"]
    else:
        return SCORE_COLORS["strong_bearish"]


def _score_bar(score: float, width: int = 20) -> str:
    """점수를 시각적 바로 표현"""
    if score is None:
        return "N/A"
    normalized = (score + 100) / 200  # 0~1
    filled = int(normalized * width)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def print_pulse_report(result: dict):
    """종합 시황 보고서 터미널 출력"""
    score = result["score"]
    signal = result["signal"]
    date = result["date"]
    style = _get_score_style(score)

    # 헤더 패널
    score_text = Text()
    score_text.append(f"\n  Market Pulse Score: ", style="bold")
    score_text.append(f"{score:+.1f}", style=style)
    score_text.append(f"\n  {signal}\n", style=style)

    console.print()
    console.print(Panel(
        score_text,
        title=f"[bold]K-Market Pulse — {date[:4]}-{date[4:6]}-{date[6:]}[/bold]",
        subtitle=f"기간: {result['period']}",
        border_style=style,
        width=60,
    ))

    # 지표별 점수 테이블
    table = Table(title="지표별 분석 결과", expand=True)
    table.add_column("지표", style="cyan", min_width=14, no_wrap=True)
    table.add_column("가중치", justify="center", width=6)
    table.add_column("점수", justify="center", width=6)
    table.add_column("상세", ratio=1)

    indicator_scores = result.get("indicator_scores", {})
    details = result.get("details", {})

    for key, weight in WEIGHTS.items():
        name = INDICATOR_NAMES.get(key, key)
        ind_score = indicator_scores.get(key)
        detail_info = details.get(key, {})
        detail_text = detail_info.get("details", "") if isinstance(detail_info, dict) else ""

        if ind_score is not None:
            score_style = _get_score_style(ind_score)
            score_str = f"[{score_style}]{ind_score:+d}[/{score_style}]"
        else:
            score_str = "[dim]N/A[/dim]"

        table.add_row(
            name,
            f"{weight:.0%}",
            score_str,
            detail_text if detail_text else "-",
        )

    console.print(table)


def print_investor_detail(result: dict):
    """투자자 수급 상세 출력"""
    flow = result.get("details", {}).get("investor_flow", {})

    console.print()
    console.print("[bold cyan]투자자별 수급 현황[/bold cyan]")
    console.print()

    if "foreign_net" in flow:
        foreign = flow["foreign_net"]
        inst = flow["institutional_net"]

        table = Table(width=50)
        table.add_column("투자자", style="cyan")
        table.add_column("순매수", justify="right")
        table.add_column("방향", justify="center")

        for name, val in [("외국인", foreign), ("기관", inst)]:
            direction = "[green]매수[/green]" if val > 0 else "[red]매도[/red]"
            table.add_row(name, f"{val/100_000_000:,.0f}억", direction)

        console.print(table)

    # 현선물 방향
    align = result.get("details", {}).get("spot_futures_align", {})
    if "aligned" in align and align["aligned"] is not None:
        status = "[green]일치 ✓[/green]" if align["aligned"] else "[red]불일치 ✗[/red]"
        console.print(f"\n  현선물 방향: {status}")
        console.print(f"  {align.get('details', '')}")


def print_sector_detail(result: dict):
    """업종별 동향 상세 출력"""
    sector = result.get("details", {}).get("sector_momentum", {})
    adr = result.get("details", {}).get("adr_volume", {})

    console.print()
    console.print("[bold cyan]시장 체력 분석[/bold cyan]")

    if sector.get("details"):
        console.print(f"\n  {sector['details']}")

    if adr.get("details"):
        console.print(f"  {adr['details']}")


def print_macro_detail(result: dict):
    """매크로 환경 상세 출력"""
    console.print()
    console.print("[bold cyan]매크로 환경[/bold cyan]")

    for key in ["exchange_rate", "vkospi", "interest_rate_diff", "global_market"]:
        detail = result.get("details", {}).get(key, {})
        name = INDICATOR_NAMES.get(key, key)
        text = detail.get("details", "데이터 없음") if isinstance(detail, dict) else "데이터 없음"
        console.print(f"  {name}: {text}")


def print_history(records: list):
    """시황 이력 테이블 출력"""
    if not records:
        console.print("[dim]이력 데이터가 없습니다.[/dim]")
        return

    table = Table(title="시황 판단 이력")
    table.add_column("날짜", style="cyan")
    table.add_column("점수", justify="center")
    table.add_column("판단")

    for record in records:
        date = record["date"]
        score = record["score"]
        signal = record["signal"]
        style = _get_score_style(score)
        formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        table.add_row(formatted_date, f"[{style}]{score:+.1f}[/{style}]", signal)

    console.print(table)
