"""AlphaPulse CLI - AI 기반 투자 인텔리전스 플랫폼."""

import logging
import warnings

import click

from alphapulse import __version__

# requests/urllib3 버전 불일치 경고 억제
warnings.filterwarnings("ignore", message="urllib3.*chardet.*charset_normalizer")


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
    from alphapulse.core.config import Config
    from alphapulse.core.storage import PulseHistory
    from alphapulse.market.reporters.terminal import print_history

    cfg = Config()
    h = PulseHistory(str(cfg.HISTORY_DB))
    records = h.get_recent(days)
    print_history(records)


# ── 기타 최상위 커맨드 ───────────────────────────────────────────


@cli.group()
def content():
    """콘텐츠 정성 분석 (Content Intelligence)."""
    pass


@content.command("monitor")
@click.option("--daemon", is_flag=True, help="데몬 모드")
@click.option("--interval", type=int, default=None, help="체크 주기 (초)")
@click.option("--force-latest", type=int, default=0, help="최근 N개 강제 처리")
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--blog-only", is_flag=True, help="블로그만 모니터링")
@click.option("--channel-only", is_flag=True, help="채널만 모니터링")
def content_monitor(daemon, interval, force_latest, no_telegram, blog_only, channel_only):
    """블로그/채널 콘텐츠 모니터링."""
    import asyncio

    from alphapulse.content.monitor import BlogMonitor
    from alphapulse.core.config import Config
    cfg = Config()
    monitor = BlogMonitor()
    if daemon:
        asyncio.run(monitor.run_daemon(
            interval=interval or cfg.CHECK_INTERVAL,
            send_telegram=not no_telegram,
        ))
    else:
        asyncio.run(monitor.run_once(
            force_latest=force_latest,
            send_telegram=not no_telegram,
        ))


@content.command("test-telegram")
def content_test_telegram():
    """텔레그램 연결 테스트."""
    import asyncio

    from alphapulse.core.notifier import TelegramNotifier
    notifier = TelegramNotifier()
    asyncio.run(notifier.send_test())


@content.command("list-channels")
def content_list_channels():
    """구독 텔레그램 채널 목록."""
    from alphapulse.core.config import Config
    cfg = Config()
    if cfg.CHANNEL_IDS:
        for ch in cfg.CHANNEL_IDS:
            click.echo(f"  - {ch}")
    else:
        click.echo("구독 중인 채널이 없습니다. CHANNEL_IDS 환경변수를 설정하세요.")


@cli.command()
@click.option("--no-telegram", is_flag=True, help="텔레그램 전송 안 함")
@click.option("--daemon", is_flag=True, help="데몬 모드 (매일 자동 실행)")
@click.option("--time", "briefing_time", default=None, help="브리핑 시간 (HH:MM)")
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def briefing(no_telegram, daemon, briefing_time, date):
    """일일 종합 브리핑 생성 + 전송."""
    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    orch = BriefingOrchestrator()
    if daemon:
        from alphapulse.briefing.scheduler import run_scheduler
        run_scheduler(orch, briefing_time=briefing_time, send_telegram=not no_telegram)
    else:
        result = orch.run(date=date, send_telegram=not no_telegram)
        score = result['pulse_result']['score']
        signal = result['pulse_result']['signal']
        click.echo(f"브리핑 완료: Score {score:+.0f} ({signal})")


@cli.command()
@click.option("--date", default=None, help="날짜 (YYYY-MM-DD)")
def commentary(date):
    """AI 시장 해설 생성."""
    import asyncio

    from alphapulse.agents.commentary import MarketCommentaryAgent
    from alphapulse.briefing.orchestrator import BriefingOrchestrator
    from alphapulse.market.engine.signal_engine import SignalEngine

    engine = SignalEngine()
    pulse_result = engine.run(date)

    orch = BriefingOrchestrator()
    content_summaries = orch.collect_recent_content(hours=24)

    agent = MarketCommentaryAgent()
    result = asyncio.run(agent.generate(pulse_result, content_summaries))
    click.echo(result)


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


# ── Feedback 서브커맨드 ────────────────────────────────────────────


@cli.group()
def feedback():
    """피드백 시스템 — 시그널 검증 + 적중률."""
    pass


@feedback.command("evaluate")
def feedback_evaluate():
    """미확정 시그널에 대해 시장 결과 수집 + 평가."""
    from alphapulse.feedback.collector import FeedbackCollector
    collector = FeedbackCollector()
    collector.collect_and_evaluate()
    click.echo("피드백 평가 완료")


@feedback.command("report")
@click.option("--days", default=30, help="분석 기간 (일)")
def feedback_report(days):
    """적중률 리포트."""
    from alphapulse.feedback.evaluator import FeedbackEvaluator
    evaluator = FeedbackEvaluator()
    rates = evaluator.get_hit_rates(days)
    corr = evaluator.get_correlation(days)

    click.echo(f"\n📊 피드백 리포트 (최근 {days}일)")
    click.echo(f"평가 건수: {rates['total_evaluated']}")
    click.echo(f"1일 적중률: {rates['hit_rate_1d']:.0%} ({rates['count_1d']}건)")
    click.echo(f"3일 적중률: {rates['hit_rate_3d']:.0%} ({rates['count_3d']}건)")
    click.echo(f"5일 적중률: {rates['hit_rate_5d']:.0%} ({rates['count_5d']}건)")
    if corr is not None:
        click.echo(f"상관계수: {corr:.3f}")
    else:
        click.echo("상관계수: 데이터 부족")


@feedback.command("indicators")
@click.option("--days", default=30, help="분석 기간 (일)")
def feedback_indicators(days):
    """지표별 적중률 순위."""
    from alphapulse.feedback.evaluator import FeedbackEvaluator
    evaluator = FeedbackEvaluator()
    accuracy = evaluator.get_indicator_accuracy(days)

    if not accuracy:
        click.echo("지표별 적중률 데이터가 없습니다.")
        return

    click.echo(f"\n📊 지표별 적중률 (최근 {days}일, 극단값 기준)")
    sorted_acc = sorted(accuracy.items(), key=lambda x: x[1]["accuracy"], reverse=True)
    for key, val in sorted_acc:
        bar = "█" * int(val["accuracy"] * 10)
        click.echo(f"  {key:25s} {val['accuracy']:5.0%} {bar} ({val['total']}건)")


@feedback.command("history")
@click.option("--days", default=7, help="표시 기간 (일)")
def feedback_history(days):
    """최근 시그널 vs 실제 결과 테이블."""
    from alphapulse.core.config import Config
    from alphapulse.core.storage.feedback import FeedbackStore
    cfg = Config()
    store = FeedbackStore(cfg.DATA_DIR / "feedback.db")
    records = store.get_recent(days=days)

    if not records:
        click.echo("피드백 데이터가 없습니다.")
        return

    click.echo(f"\n📊 시그널 이력 (최근 {days}일)")
    click.echo(f"{'날짜':>10} {'점수':>6} {'시그널':>12} {'KOSPI':>8} {'1일':>6} {'적중':>4}")
    click.echo("-" * 52)
    for r in records:
        date = r["date"]
        score = f"{r['score']:+.0f}" if r["score"] is not None else "N/A"
        signal = r.get("signal", "")[:8]
        kospi = f"{r['kospi_change_pct']:+.1f}%" if r.get("kospi_change_pct") is not None else "-"
        ret1d = f"{r['return_1d']:+.1f}%" if r.get("return_1d") is not None else "-"
        hit = "✅" if r.get("hit_1d") == 1 else "❌" if r.get("hit_1d") == 0 else "-"
        click.echo(f"{date:>10} {score:>6} {signal:>12} {kospi:>8} {ret1d:>6} {hit:>4}")


@feedback.command("analyze")
@click.option("--date", default=None, help="분석 날짜 (YYYY-MM-DD)")
def feedback_analyze(date):
    """특정 날짜 사후 분석 실행."""
    click.echo("사후 분석은 Phase B에서 구현 예정")


# ── Trading 명령어 ──────────────────────────────────────────────
@cli.group()
def trading():
    """자동 매매 시스템"""
    pass


@trading.command()
@click.option("--market", default="KOSPI", help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=20, help="상위 N종목")
@click.option("--factor", default="momentum", help="주요 팩터")
def screen(market, top, factor):
    """종목 스크리닝 — 팩터 기반 종목 랭킹"""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.store import TradingStore
    from alphapulse.trading.data.universe import Universe
    from alphapulse.trading.screening.factors import FactorCalculator
    from alphapulse.trading.screening.ranker import MultiFactorRanker

    cfg = Config()
    db_path = cfg.DATA_DIR / "trading.db"
    store = TradingStore(db_path)
    universe = Universe(store)

    stocks = universe.get_by_market(market)
    if not stocks:
        click.echo(f"{market} 종목 데이터가 없습니다. 먼저 데이터를 수집하세요.")
        return

    calc = FactorCalculator(store)
    factor_data = {}
    for s in stocks:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    # 팩터별 가중치 프리셋
    weight_presets = {
        "momentum": {"momentum": 0.6, "flow": 0.3, "volatility": 0.1},
        "value": {"value": 0.4, "quality": 0.3, "momentum": 0.2, "flow": 0.1},
        "quality": {"quality": 0.4, "momentum": 0.3, "value": 0.2, "flow": 0.1},
        "balanced": {"momentum": 0.25, "value": 0.25, "quality": 0.2, "flow": 0.15, "volatility": 0.15},
    }
    weights = weight_presets.get(factor, weight_presets["balanced"])

    ranker = MultiFactorRanker(weights=weights)
    signals = ranker.rank(stocks, factor_data, strategy_id=factor)

    click.echo(f"\n{'='*60}")
    click.echo(f" {market} 종목 스크리닝 (팩터: {factor}, 상위 {top})")
    click.echo(f"{'='*60}")
    click.echo(f" {'순위':>4}  {'종목코드':>8}  {'종목명':<12}  {'점수':>6}  {'주요팩터'}")
    click.echo(f" {'-'*56}")

    for i, sig in enumerate(signals[:top], 1):
        top_factor = max(sig.factors, key=sig.factors.get) if sig.factors else "-"
        click.echo(
            f" {i:>4}  {sig.stock.code:>8}  {sig.stock.name:<12}  "
            f"{sig.score:>+6.1f}  {top_factor}"
        )
