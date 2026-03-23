"""AlphaPulse CLI - AI 기반 투자 인텔리전스 플랫폼."""

import logging
import warnings

# requests/urllib3 버전 불일치 경고 억제
warnings.filterwarnings("ignore", message="urllib3.*chardet.*charset_normalizer")

import click
from alphapulse import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ap")
@click.option("--debug/--no-debug", default=False, help="디버그 로깅")
@click.pass_context
def cli(ctx, debug):
    """AlphaPulse - AI 기반 투자 인텔리전스 플랫폼."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")


@cli.group()
def market():
    """시장 정량 분석 (Market Pulse)."""
    pass


# ── Market 헬퍼 ──────────────────────────────────────────────────


def _get_engine():
    from alphapulse.market.engine.signal_engine import SignalEngine
    return SignalEngine()


def _parse_date(date_str):
    """날짜 문자열 파싱 (Config.parse_date 위임)."""
    from alphapulse.core.config import Config
    return Config.parse_date(date_str)


# ── Market 서브커맨드 ────────────────────────────────────────────


@market.command()
@click.option("--date", default=None, help="분석 날짜 (YYYY-MM-DD 또는 YYYYMMDD)")
@click.option("--period", type=click.Choice(["daily", "weekly", "monthly"]), default="daily", help="분석 기간")
def pulse(date, period):
    """종합 시황 분석 (기본 명령)"""
    from alphapulse.market.reporters.terminal import print_pulse_report

    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target, period=period)
    print_pulse_report(result)


@market.command()
@click.option("--date", default=None, help="분석 날짜")
@click.option("--type", "investor_type", type=click.Choice(["all", "foreign", "institutional", "individual"]), default="all")
def investor(date, investor_type):
    """투자자별 수급 상세"""
    from alphapulse.market.reporters.terminal import print_investor_detail

    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)
    print_investor_detail(result)


@market.command()
@click.option("--date", default=None, help="분석 날짜")
def program(date):
    """프로그램 매매 동향"""
    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)

    detail = result.get("details", {}).get("program_trade", {})
    click.echo(f"\n프로그램 매매: {detail.get('details', '데이터 없음')}")
    click.echo(f"점수: {detail.get('score', 'N/A')}")


@market.command()
@click.option("--date", default=None, help="분석 날짜")
def sector(date):
    """업종별/시총 상위 동향"""
    from alphapulse.market.reporters.terminal import print_sector_detail

    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)
    print_sector_detail(result)


@market.command()
@click.option("--date", default=None, help="분석 날짜")
def macro(date):
    """매크로 환경 (환율/금리/글로벌)"""
    from alphapulse.market.reporters.terminal import print_macro_detail

    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)
    print_macro_detail(result)


@market.command()
@click.option("--date", default=None, help="분석 날짜")
def fund(date):
    """증시 자금 동향"""
    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)

    detail = result.get("details", {}).get("fund_flow", {})
    click.echo(f"\n증시 자금: {detail.get('details', '데이터 없음')}")
    click.echo(f"점수: {detail.get('score', 'N/A')}")


@market.command()
@click.option("--date", default=None, help="분석 날짜")
@click.option("--output", default="report.html", help="출력 파일 경로")
def report(date, output):
    """HTML 리포트 생성"""
    from alphapulse.market.reporters.html_report import generate_html_report

    engine = _get_engine()
    target = _parse_date(date) if date else None
    result = engine.run(date=target)

    path = generate_html_report(result, output)
    click.echo(f"리포트 생성 완료: {path}")


@market.command()
@click.option("--days", default=30, help="조회 기간 (일)")
def history(days):
    """과거 시황 판단 이력"""
    from alphapulse.market.reporters.terminal import print_history
    from alphapulse.core.storage import PulseHistory
    from alphapulse.core.config import Config

    cfg = Config()
    h = PulseHistory(str(cfg.HISTORY_DB))
    records = h.get_recent(days)
    print_history(records)


# ── 기타 최상위 커맨드 ───────────────────────────────────────────


@cli.group()
def content():
    """콘텐츠 정성 분석 (Content Intelligence)."""
    pass


@cli.command()
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--daemon", is_flag=True, help="데몬 모드 (매일 자동 실행)")
@click.option("--time", "briefing_time", default=None, help="브리핑 시간 (HH:MM)")
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def briefing(no_telegram, daemon, briefing_time, date):
    """일일 종합 브리핑 생성 + 전송."""
    click.echo("Briefing not yet implemented")


@cli.command()
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def commentary(date):
    """AI 시장 해설 생성."""
    click.echo("Commentary not yet implemented")


@cli.group()
def cache():
    """캐시 관리."""
    pass


@cache.command("clear")
def cache_clear():
    """캐시 초기화."""
    from alphapulse.core.config import Config
    from alphapulse.core.storage import DataCache
    cfg = Config()
    cfg.ensure_data_dir()
    cache_db = DataCache(cfg.CACHE_DB)
    cache_db.clear()
    click.echo("캐시가 초기화되었습니다.")
