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
            "growth": calc.growth(s.code),
            "profit_growth": calc.quality_profit_growth(s.code),
            "debt_ratio": calc.quality_debt_ratio(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    # 팩터별 가중치 프리셋
    weight_presets = {
        "momentum": {
            "momentum": 0.5, "flow": 0.3, "volatility": 0.2,
        },
        "value": {
            "value": 0.4, "quality": 0.2, "momentum": 0.2,
            "flow": 0.15, "volatility": 0.05,
        },
        "quality": {
            "quality": 0.35, "growth": 0.2, "value": 0.15,
            "momentum": 0.2, "flow": 0.1,
        },
        "growth": {
            "growth": 0.4, "momentum": 0.25, "quality": 0.15,
            "flow": 0.15, "volatility": 0.05,
        },
        # 한국 시장 특화 (외국인 수급 + 모멘텀 50%)
        "balanced": {
            "momentum":   0.25,
            "flow":       0.25,
            "value":      0.20,
            "quality":    0.15,
            "growth":     0.10,
            "volatility": 0.05,
        },
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


# ── Trading Data 서브커맨드 ─────────────────────────────────────


@trading.group()
def data():
    """데이터 수집 관리"""
    pass


@data.command("collect")
@click.option("--market", default="ALL", help="시장 (KOSPI/KOSDAQ/ALL)")
@click.option("--years", default=3, type=int, help="수집 기간 (년)")
@click.option("--delay", default=0.5, type=float, help="요청 간 딜레이 (초)")
@click.option("--no-resume", is_flag=True, help="체크포인트 무시")
def data_collect(market, years, delay, no_resume):
    """전종목 데이터 수집 (OHLCV + 재무 + 수급)"""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.bulk_collector import BulkCollector

    cfg = Config()
    collector = BulkCollector(
        db_path=cfg.DATA_DIR / "trading.db", delay=delay, years=years
    )
    markets = ["KOSPI", "KOSDAQ"] if market == "ALL" else [market]

    click.echo(f"데이터 수집 시작: {', '.join(markets)} ({years}년치)")
    click.echo(f"딜레이: {delay}초, 재개: {'아니오' if no_resume else '예'}")
    click.echo()

    results = collector.collect_all(
        markets=markets, years=years, resume=not no_resume
    )

    click.echo(f"\n{'=' * 50}")
    click.echo(" 수집 완료")
    click.echo(f"{'=' * 50}")
    for r in results:
        click.echo(
            f" {r.market}: OHLCV {r.ohlcv_count}종목, "
            f"재무 {r.fundamentals_count}, 수급 {r.flow_count} "
            f"({r.elapsed_seconds:.0f}초)"
        )
        if r.skipped:
            click.echo(f"   (건너뜀: {r.skipped}종목)")


@data.command("update")
@click.option("--market", default="ALL", help="시장 (KOSPI/KOSDAQ/ALL)")
def data_update(market):
    """마지막 수집 이후 신규 데이터 업데이트"""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.bulk_collector import BulkCollector

    cfg = Config()
    collector = BulkCollector(db_path=cfg.DATA_DIR / "trading.db")
    markets = ["KOSPI", "KOSDAQ"] if market == "ALL" else [market]

    click.echo(f"증분 업데이트 시작: {', '.join(markets)}")
    click.echo()

    results = collector.update(markets=markets)

    click.echo(f"\n{'=' * 50}")
    click.echo(" 업데이트 완료")
    click.echo(f"{'=' * 50}")
    if not results:
        click.echo(" 이미 최신 상태입니다.")
    else:
        for r in results:
            click.echo(
                f" {r.market}: OHLCV {r.ohlcv_count}종목, "
                f"재무 {r.fundamentals_count}, 수급 {r.flow_count}, "
                f"wisereport {r.wisereport_count} "
                f"({r.elapsed_seconds:.0f}초)"
            )
            if r.skipped:
                click.echo(f"   (이미 최신: {r.skipped}종목)")


@data.command("status")
def data_status():
    """데이터 수집 현황"""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.bulk_collector import BulkCollector

    cfg = Config()
    collector = BulkCollector(db_path=cfg.DATA_DIR / "trading.db")
    s = collector.status()

    click.echo(
        f"\n종목 수: {s['total_stocks']} "
        f"(KOSPI: {s['kospi']}, KOSDAQ: {s['kosdaq']}, ETF: {s['etf']})"
    )
    click.echo()

    if not s["collection"]:
        click.echo(
            "수집 이력이 없습니다. "
            "'ap trading data collect'로 초기 수집을 시작하세요."
        )
        return

    click.echo(f"{'시장':<10} {'데이터':<15} {'최종 수집일':<12}")
    click.echo(f"{'-' * 40}")
    for row in s["collection"]:
        click.echo(
            f"{row['market']:<10} {row['data_type']:<15} {row['last_date']}"
        )


@data.command("schedule")
@click.option("--market", default="ALL", help="시장 (KOSPI/KOSDAQ/ALL)")
@click.option("--top-n", default=100, type=int, help="Stage 2 대상 종목 수")
@click.option("--force", is_flag=True, help="주기 무시하고 전체 실행")
def data_schedule(market, top_n, force):
    """자율 데이터 수집 (2단계: 전종목 기본 → 후보 상세).

    Stage 1: 전종목 OHLCV/수급/재무/wisereport (sync, 빠름)
    Stage 2: 스크리닝 상위 N종목 공매도/재무시계열/투자지표 (crawl4ai)
    """
    import asyncio

    from alphapulse.core.config import Config
    from alphapulse.trading.data.scheduler import DataScheduler

    cfg = Config()
    scheduler = DataScheduler(db_path=cfg.DATA_DIR / "trading.db", top_n=top_n)
    markets = ["KOSPI", "KOSDAQ"] if market == "ALL" else [market]

    click.echo(f"자율 수집 시작: {', '.join(markets)} (Stage 2: 상위 {top_n}종목)")
    if force:
        click.echo("  --force: 주기 무시, 전체 실행")
    click.echo()

    result = asyncio.run(scheduler.run(markets=markets, force=force))

    click.echo(f"\n{'='*50}")
    click.echo(f" 수집 완료 ({result.elapsed_seconds:.0f}초)")
    click.echo(f"{'='*50}")
    if result.executed:
        click.echo(f" 실행: {', '.join(result.executed)}")
    if result.skipped:
        click.echo(f" 스킵: {', '.join(result.skipped)}")
    if result.errors:
        click.echo(f" 에러: {', '.join(result.errors)}")
    if result.stage2_codes:
        click.echo(f" Stage 2 대상: {len(result.stage2_codes)}종목")


@data.command("schedule-status")
def data_schedule_status():
    """수집 스케줄 현황 조회."""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.scheduler import DataScheduler

    cfg = Config()
    scheduler = DataScheduler(db_path=cfg.DATA_DIR / "trading.db")
    status = scheduler.get_status()

    freq_labels = {"daily": "매일", "weekly": "주간", "monthly": "월간", "quarterly": "분기"}

    click.echo(f"\n{'데이터':<20} {'주기':<8} {'단계':<8} {'마지막 수집':<12} {'업데이트 필요'}")
    click.echo(f"{'-'*65}")
    for name, info in status.items():
        freq = freq_labels.get(info["frequency"], info["frequency"])
        stage = f"Stage {info['stage']}"
        last = info["last_collected"]
        needs = "예" if info["needs_update"] else "-"
        click.echo(f" {name:<19} {freq:<8} {stage:<8} {last:<12} {needs}")


@data.command("collect-financials")
@click.option("--code", default=None, help="종목코드 (단일 종목)")
@click.option("--market", default=None, help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=50, type=int, help="상위 N종목 (시가총액 기준)")
def data_collect_financials(code, market, top):
    """wisereport 재무 데이터 수집 (crawl4ai 기반).

    단일 종목 또는 시장 상위 N종목의 심층 재무 데이터를 수집한다.
    정적 데이터(시장정보, 주요지표, 컨센서스)를 requests로 빠르게 수집한다.
    """
    from alphapulse.core.config import Config
    from alphapulse.trading.data.wisereport_collector import WisereportCollector

    cfg = Config()
    db_path = cfg.DATA_DIR / "trading.db"
    collector = WisereportCollector(db_path)

    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")

    if code:
        click.echo(f"wisereport 수집: {code}")
        data = collector.collect_static(code, today)
        if data:
            click.echo(f"  수집 완료: {len(data)}개 필드")
            for k, v in sorted(data.items()):
                click.echo(f"    {k}: {v}")
        else:
            click.echo("  수집 실패 (데이터 없음)")
    elif market:
        from alphapulse.trading.data.store import TradingStore
        store = TradingStore(db_path)
        stocks = store.get_all_stocks(market=market)
        if not stocks:
            click.echo(f"{market} 종목 데이터가 없습니다.")
            return

        # 시가총액 기준 상위 N종목
        stocks.sort(key=lambda s: s.get("market_cap", 0), reverse=True)
        codes = [s["code"] for s in stocks[:top]]

        click.echo(f"wisereport 수집: {market} 상위 {len(codes)}종목")
        results = collector.collect_static_batch(codes, today)
        click.echo(f"수집 완료: {len(results)}/{len(codes)}종목")
    else:
        click.echo("--code 또는 --market 옵션을 지정하세요.")


@data.command("collect-wisereport")
@click.option("--code", default=None, help="종목코드 (단일 종목)")
@click.option("--market", default=None, help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=50, type=int, help="상위 N종목")
@click.option("--full", is_flag=True, help="crawl4ai 포함 전체 수집 (느림)")
def data_collect_wisereport(code, market, top, full):
    """wisereport 전체 탭 데이터 수집.

    정적 데이터: 기업현황 + 기업개요 + 주주현황 + 증권사 리포트 (빠름)
    동적 데이터(--full): 투자지표 + 컨센서스 + 업종분석 (crawl4ai, 느림)
    """
    from alphapulse.core.config import Config
    from alphapulse.trading.data.wisereport_collector import WisereportCollector

    cfg = Config()
    collector = WisereportCollector(cfg.DATA_DIR / "trading.db")

    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")

    if code:
        click.echo(f"wisereport 전체 수집: {code}")
        static = collector.collect_all_static(code, today)
        for tab, data in static.items():
            count = len(data) if isinstance(data, (dict, list)) else 0
            click.echo(f"  {tab}: {count}건")

        if full:
            import asyncio
            click.echo("  crawl4ai 수집 시작...")
            dynamic = asyncio.run(collector.collect_all_dynamic(code, today))
            for tab, data in dynamic.items():
                count = len(data) if isinstance(data, (dict, list)) else 0
                click.echo(f"  {tab}: {count}건")
    elif market:
        from alphapulse.trading.data.store import TradingStore
        store = TradingStore(cfg.DATA_DIR / "trading.db")
        stocks = store.get_all_stocks(market=market)
        if not stocks:
            click.echo(f"{market} 종목 데이터가 없습니다.")
            return

        stocks.sort(key=lambda s: s.get("market_cap", 0), reverse=True)
        codes = [s["code"] for s in stocks[:top]]

        click.echo(f"wisereport 전체 수집: {market} 상위 {len(codes)}종목")
        for i, c in enumerate(codes, 1):
            result = collector.collect_all_static(c, today)
            tabs_ok = sum(1 for v in result.values() if v)
            click.echo(f"  [{i}/{len(codes)}] {c}: {tabs_ok}/4 탭")
            import time
            time.sleep(0.5)

        click.echo(f"정적 수집 완료: {len(codes)}종목")

        if full:
            import asyncio
            click.echo("crawl4ai 수집 시작 (느림)...")
            for i, c in enumerate(codes, 1):
                result = asyncio.run(collector.collect_all_dynamic(c, today))
                tabs_ok = sum(1 for v in result.values() if v)
                click.echo(f"  [{i}/{len(codes)}] {c}: {tabs_ok}/4 탭")
    else:
        click.echo("--code 또는 --market 옵션을 지정하세요.")


@data.command("collect-short")
@click.option("--code", default=None, help="종목코드 (단일 종목)")
@click.option("--market", default=None, help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=50, type=int, help="상위 N종목")
def data_collect_short(code, market, top):
    """공매도 데이터 수집 (KRX crawl4ai 기반).

    KRX 공매도 통계 페이지에서 일별 공매도 수량/잔고를 수집한다.
    """
    import asyncio

    from alphapulse.core.config import Config
    from alphapulse.trading.data.short_collector import ShortCollector

    cfg = Config()
    collector = ShortCollector(cfg.DATA_DIR / "trading.db")

    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    async def _collect_codes(codes):
        total = 0
        for i, c in enumerate(codes, 1):
            count = await collector.collect_async(c, start, end)
            click.echo(f"  [{i}/{len(codes)}] {c}: {count}건")
            total += count
        return total

    if code:
        click.echo(f"공매도 수집: {code} ({start}~{end})")
        count = asyncio.run(collector.collect_async(code, start, end))
        click.echo(f"수집 완료: {count}건")
    elif market:
        from alphapulse.trading.data.store import TradingStore
        store = TradingStore(cfg.DATA_DIR / "trading.db")
        stocks = store.get_all_stocks(market=market)
        if not stocks:
            click.echo(f"{market} 종목 데이터가 없습니다.")
            return

        stocks.sort(key=lambda s: s.get("market_cap", 0), reverse=True)
        codes = [s["code"] for s in stocks[:top]]

        click.echo(f"공매도 수집: {market} 상위 {len(codes)}종목 ({start}~{end})")
        total = asyncio.run(_collect_codes(codes))
        click.echo(f"수집 완료: 총 {total}건")
    else:
        click.echo("--code 또는 --market 옵션을 지정하세요.")


# NOTE: `ap trading screen` 명령은 Phase 1에서 정의됨 (위 참조).


@trading.command()
@click.option("--strategy", default="momentum",
              type=click.Choice(["momentum", "value", "quality", "growth",
                                 "balanced", "topdown_etf"]),
              help="전략 preset")
@click.option("--market", default="KOSPI", help="시장")
@click.option("--top", default=20, type=int, help="상위 N종목")
def signals(strategy, market, top):
    """오늘의 전략 시그널 생성 — 실행 없이 확인만.

    screen과 유사하지만 전략별 프리셋을 자동 적용하고,
    시장 컨텍스트(Market Pulse)를 고려한다.
    """
    from alphapulse.core.config import Config
    from alphapulse.trading.core.adapters import PulseResultAdapter
    from alphapulse.trading.data.store import TradingStore
    from alphapulse.trading.data.universe import Universe
    from alphapulse.trading.screening.factors import FactorCalculator
    from alphapulse.trading.screening.ranker import MultiFactorRanker

    cfg = Config()
    store = TradingStore(cfg.TRADING_DB_PATH)
    universe = Universe(store)
    stocks = universe.get_by_market(market)

    if not stocks:
        click.echo(f"{market} 종목 데이터가 없습니다.")
        return

    # 전략별 가중치 프리셋 (screen과 동일)
    weight_presets = {
        "momentum": {
            "momentum": 0.5, "flow": 0.3, "volatility": 0.2,
        },
        "value": {
            "value": 0.4, "quality": 0.2, "momentum": 0.2,
            "flow": 0.15, "volatility": 0.05,
        },
        "quality": {
            "quality": 0.35, "growth": 0.2, "value": 0.15,
            "momentum": 0.2, "flow": 0.1,
        },
        "growth": {
            "growth": 0.4, "momentum": 0.25, "quality": 0.15,
            "flow": 0.15, "volatility": 0.05,
        },
        "balanced": {
            "momentum": 0.25, "flow": 0.25, "value": 0.20,
            "quality": 0.15, "growth": 0.10, "volatility": 0.05,
        },
        "topdown_etf": {
            "momentum": 0.5, "flow": 0.3, "volatility": 0.2,
        },
    }
    weights = weight_presets[strategy]

    # Market Pulse 조회 (선택적)
    market_context = {}
    try:
        from alphapulse.market.engine.signal_engine import SignalEngine
        engine = SignalEngine()
        pulse = engine.run()
        market_context = PulseResultAdapter.to_market_context(pulse)
        click.echo(
            f"\n[시장 상황] Pulse Score: {market_context['pulse_score']:+.1f} "
            f"({market_context['pulse_signal']})"
        )
    except Exception:
        click.echo("\n[시장 상황] Market Pulse 조회 실패 (중립으로 처리)")

    # 팩터 계산
    calc = FactorCalculator(store)
    factor_data = {}
    for s in stocks:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "growth": calc.growth(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    ranker = MultiFactorRanker(weights=weights)
    ranked = ranker.rank(stocks, factor_data, strategy_id=strategy)

    # 매도 우위 시 강도 축소 (momentum 전략 논리)
    pulse_signal = market_context.get("pulse_signal", "")
    is_bearish = "bearish" in pulse_signal.lower() or "매도" in pulse_signal
    if is_bearish and strategy == "momentum":
        click.echo("[경고] 시장 매도 우위 — 모멘텀 시그널 0.5배 축소")
        for sig in ranked:
            sig.score *= 0.5

    # 상위 N 출력
    signals_top = ranked[:top]
    click.echo(f"\n{'='*70}")
    click.echo(f" {market} {strategy} 전략 시그널 (상위 {len(signals_top)})")
    click.echo(f"{'='*70}")
    click.echo(f" {'순위':>4}  {'종목코드':>8}  {'종목명':<15}  {'점수':>7}  주요 팩터")
    click.echo(f" {'-'*68}")

    for i, sig in enumerate(signals_top, 1):
        top_factor = (
            max(sig.factors, key=sig.factors.get) if sig.factors else "-"
        )
        top_val = sig.factors.get(top_factor, 0) if sig.factors else 0
        click.echo(
            f" {i:>4}  {sig.stock.code:>8}  {sig.stock.name:<15}  "
            f"{sig.score:>+7.1f}  {top_factor}({top_val:.0f})"
        )

    # 매수/매도 액션 제안
    action_str = "매수" if not is_bearish else "관망/축소"
    click.echo(f"\n  권장 액션: {action_str}")


@trading.group(invoke_without_command=True)
@click.pass_context
def backtest(ctx):
    """백테스트 실행 및 결과 관리.

    서브커맨드 없이 실행하면 'run'이 기본 동작합니다.
    """
    if ctx.invoked_subcommand is None:
        click.echo("사용법: ap trading backtest [run|list|report|compare] [옵션]")
        click.echo()
        click.echo("  run      백테스트 실행 (기본)")
        click.echo("  list     과거 결과 목록")
        click.echo("  report   상세 리포트 조회")
        click.echo("  compare  두 결과 비교")


def _print_backtest_metrics(m: dict, snapshots: list) -> None:
    """백테스트 성과 지표를 터미널에 출력한다."""
    click.echo(f"{'='*60}")
    click.echo(" 성과 지표")
    click.echo(f"{'='*60}")
    click.echo(f" 총 수익률:        {m.get('total_return', 0):+.2f}%")
    click.echo(f" CAGR:             {m.get('cagr', 0):+.2f}%")
    click.echo(f" 샤프 비율:        {m.get('sharpe_ratio', 0):+.2f}")
    click.echo(f" 소르티노 비율:    {m.get('sortino_ratio', 0):+.2f}")
    click.echo(f" 최대 낙폭 (MDD):  {m.get('max_drawdown', 0):.2f}%")
    click.echo(f" 변동성 (연환산):  {m.get('volatility', 0):.2f}%")
    click.echo(
        f" 총 주문 체결:     "
        f"{m.get('total_orders', m.get('total_trades', 0))}건"
        f" (매수 {m.get('filled_buys', 0)} / 매도 {m.get('filled_sells', 0)})"
    )
    rt = m.get("round_trips", 0)
    if rt > 0:
        click.echo(
            f" 라운드트립:       {rt}건"
            f" (승률 {m.get('win_rate', 0):.1f}%)"
        )
    else:
        click.echo(f" 라운드트립:       {rt}건 (미청산 포지션)")
    click.echo(f" 턴오버:           {m.get('turnover', 0):.2f}x")
    click.echo(f" 스냅샷 수:        {len(snapshots)}")
    click.echo(f"{'='*60}")

    if snapshots:
        first = snapshots[0]
        last = snapshots[-1]
        click.echo(f" 시작 자산: {first.total_value:,.0f}원 ({first.date})")
        click.echo(f" 최종 자산: {last.total_value:,.0f}원 ({last.date})")


@backtest.command(name="run")
@click.option("--strategy", default="momentum",
              help="전략 ID (momentum/value/quality_momentum/topdown_etf)")
@click.option("--start", default=None, help="시작일 YYYYMMDD (기본 3년 전)")
@click.option("--end", default=None, help="종료일 YYYYMMDD (기본 오늘)")
@click.option("--capital", default=None, type=int, help="초기 자본 (원)")
@click.option("--market", default="KOSPI", help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=20, type=int, help="상위 N종목 편입")
@click.option("--name", default="", help="결과 이름 (선택)")
@click.option("--no-save", is_flag=True, help="결과를 DB에 저장하지 않음")
@click.option("--html", default=None, help="HTML 리포트 저장 경로 (선택)")
def backtest_run(strategy, start, end, capital, market, top, name, no_save,
                 html):
    """백테스트 실행 — 전략의 과거 성과 검증.

    예:
      ap trading backtest run --strategy momentum --start 20230101
      ap trading backtest run --strategy topdown_etf --market KOSPI
      ap trading backtest run --strategy value --html report.html
    """
    from datetime import datetime, timedelta

    from alphapulse.core.config import Config
    from alphapulse.trading.backtest.engine import (
        BacktestConfig,
        BacktestEngine,
    )
    from alphapulse.trading.backtest.order_gen import (
        make_default_order_generator,
    )
    from alphapulse.trading.backtest.store_feed import TradingStoreDataFeed
    from alphapulse.trading.core.cost_model import CostModel
    from alphapulse.trading.screening.factors import FactorCalculator
    from alphapulse.trading.screening.ranker import MultiFactorRanker
    from alphapulse.trading.strategy.momentum import MomentumStrategy
    from alphapulse.trading.strategy.quality_momentum import (
        QualityMomentumStrategy,
    )
    from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy
    from alphapulse.trading.strategy.value import ValueStrategy

    cfg = Config()
    db_path = cfg.TRADING_DB_PATH

    if end is None:
        end = datetime.now().strftime("%Y%m%d")
    if start is None:
        start = (datetime.now() - timedelta(days=3 * 365)).strftime("%Y%m%d")
    if capital is None:
        capital = cfg.BACKTEST_INITIAL_CAPITAL

    click.echo(f"\n{'='*60}")
    click.echo(" 백테스트 시작")
    click.echo(f"{'='*60}")
    click.echo(f" 전략:    {strategy}")
    click.echo(f" 기간:    {start} ~ {end}")
    click.echo(f" 자본금:  {capital:,}원")
    click.echo(f" 시장:    {market}")
    click.echo(f" 상위 N:  {top}")
    click.echo(f"{'='*60}\n")

    click.echo("[1/4] 데이터 피드 로드...")
    data_feed = TradingStoreDataFeed(db_path=db_path, market=market)
    if not data_feed.codes:
        click.echo(f"  ERROR: {market} 종목 데이터가 없습니다.")
        return
    click.echo(f"  -> {len(data_feed.codes)}종목")

    click.echo("[2/4] 전략 초기화...")
    ranker = MultiFactorRanker(weights={
        "momentum": 0.25, "flow": 0.25, "value": 0.20,
        "quality": 0.15, "growth": 0.10, "volatility": 0.05,
    })
    strategy_map = {
        "momentum": MomentumStrategy,
        "value": ValueStrategy,
        "quality_momentum": QualityMomentumStrategy,
        "topdown_etf": TopDownETFStrategy,
    }
    if strategy not in strategy_map:
        click.echo(f"  ERROR: 지원하지 않는 전략: {strategy}")
        click.echo(f"  사용 가능: {list(strategy_map.keys())}")
        return

    strat_cls = strategy_map[strategy]
    try:
        factor_calc = FactorCalculator(data_feed.store)
        strat = strat_cls(
            ranker=ranker,
            factor_calc=factor_calc,
            config={"top_n": top},
        )
    except TypeError:
        strat = strat_cls(config={"top_n": top})

    click.echo(f"  -> {strat.strategy_id} 로드")

    click.echo("[3/4] 엔진 실행...")
    cost_model = CostModel(
        commission_rate=cfg.BACKTEST_COMMISSION,
        tax_rate_stock=cfg.BACKTEST_TAX,
    )
    order_gen = make_default_order_generator(top_n=top, initial_capital=capital)

    bt_config = BacktestConfig(
        initial_capital=capital,
        start_date=start,
        end_date=end,
        cost_model=cost_model,
    )
    engine = BacktestEngine(
        config=bt_config,
        data_feed=data_feed,
        strategies=[strat],
        order_generator=order_gen,
    )

    import sys

    def _bt_progress(current: int, total: int, date: str) -> None:
        if total == 0:
            return
        pct = current / total * 100
        filled = int(25 * current / total)
        bar = "█" * filled + "░" * (25 - filled)
        sys.stderr.write(
            f"\r  [{bar}] {pct:5.1f}%  {current}/{total}  {date}"
            f"{'':10}"
        )
        sys.stderr.flush()

    try:
        result = engine.run(progress_callback=_bt_progress)
        sys.stderr.write("\n")
    except Exception as e:
        sys.stderr.write("\n")
        click.echo(f"\n  ERROR: 백테스트 실패 - {e}")
        import traceback
        traceback.print_exc()
        return

    click.echo("\n[4/4] 결과 리포트\n")
    _print_backtest_metrics(result.metrics, result.snapshots)

    # DB 저장
    if not no_save:
        from alphapulse.trading.backtest.store import BacktestStore

        bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")
        run_id = bt_store.save_run(
            result, name=name or f"{strategy}_{start}_{end}",
            strategies=[strategy],
        )
        click.echo(f"\n  결과 저장: {run_id[:8]}...")

    # HTML 리포트
    if html:
        from alphapulse.trading.backtest.report import BacktestReport

        BacktestReport().save_html(result, html)
        click.echo(f"  HTML 리포트: {html}")


@backtest.command(name="list")
@click.option("--limit", default=20, type=int, help="표시 건수")
def backtest_list(limit):
    """과거 백테스트 결과 목록을 조회한다."""
    import json

    from alphapulse.core.config import Config
    from alphapulse.trading.backtest.store import BacktestStore

    cfg = Config()
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")
    runs = bt_store.list_runs()

    if not runs:
        click.echo("저장된 백테스트 결과가 없습니다.")
        click.echo("'ap trading backtest run' 으로 백테스트를 실행하세요.")
        return

    click.echo(f"\n{'='*80}")
    click.echo(" 백테스트 결과 목록")
    click.echo(f"{'='*80}")
    click.echo(
        f" {'ID':>8}  {'이름':<25}  {'기간':<21}  "
        f"{'수익률':>8}  {'샤프':>6}  {'MDD':>8}"
    )
    click.echo(f" {'-'*78}")

    for run in runs[:limit]:
        rid = run["run_id"][:8]
        run_name = run.get("name", "")[:24]
        period = f"{run['start_date']}~{run['end_date']}"
        metrics = json.loads(run.get("metrics", "{}"))
        total_ret = metrics.get("total_return", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        mdd = metrics.get("max_drawdown", 0)
        click.echo(
            f" {rid:>8}  {run_name:<25}  {period:<21}  "
            f"{total_ret:>+7.2f}%  {sharpe:>+5.2f}  {mdd:>+7.2f}%"
        )

    if len(runs) > limit:
        click.echo(f"\n  ({len(runs)}건 중 {limit}건 표시)")


@backtest.command(name="report")
@click.argument("run_id")
@click.option("--html", default=None, help="HTML 리포트 저장 경로 (선택)")
def backtest_report(run_id, html):
    """특정 백테스트 결과의 상세 리포트를 조회한다.

    RUN_ID는 전체 UUID 또는 앞 8자리 접두사.
    """
    import json

    from alphapulse.core.config import Config
    from alphapulse.trading.backtest.store import BacktestStore

    cfg = Config()
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")

    run = _resolve_run(bt_store, run_id)
    if not run:
        click.echo(f"결과를 찾을 수 없습니다: {run_id}")
        return

    metrics = json.loads(run.get("metrics", "{}"))
    strategies = json.loads(run.get("strategies", "[]"))
    snapshots = bt_store.get_snapshots(run["run_id"])

    click.echo(f"\n{'='*60}")
    click.echo(" 백테스트 상�� 리포트")
    click.echo(f"{'='*60}")
    click.echo(f" ID:       {run['run_id'][:8]}...")
    click.echo(f" 이름:     {run.get('name', '')}")
    click.echo(f" 전략:     {', '.join(strategies)}")
    click.echo(f" 기간:     {run['start_date']} ~ {run['end_date']}")
    click.echo(
        f" 자본금:   {run['initial_capital']:,.0f}원 → "
        f"{run['final_value']:,.0f}원"
    )
    click.echo(f" 벤치마크: {run.get('benchmark', 'KOSPI')}")
    click.echo()

    # 수익률
    click.echo("--- 수익률 ---")
    click.echo(f" 총 수익률:     {metrics.get('total_return', 0):+.2f}%")
    click.echo(f" CAGR:          {metrics.get('cagr', 0):+.2f}%")
    click.echo(f" 변동성:        {metrics.get('volatility', 0):.2f}%")
    click.echo()

    # 리스크
    click.echo("--- 리스크 ---")
    click.echo(f" 최대 낙폭:     {metrics.get('max_drawdown', 0):.2f}%")
    click.echo(f" MDD 지속:      {metrics.get('max_drawdown_duration', 0)}일")
    click.echo()

    # 리스크 조정
    click.echo("--- 리스크 조정 ---")
    click.echo(f" 샤프 비율:     {metrics.get('sharpe_ratio', 0):+.2f}")
    click.echo(f" 소르티노:      {metrics.get('sortino_ratio', 0):+.2f}")
    click.echo(f" 칼마 비율:     {metrics.get('calmar_ratio', 0):+.2f}")
    click.echo()

    # 거래
    click.echo("--- 거래 ---")
    click.echo(f" 총 거래:       {metrics.get('total_trades', 0)}건")
    click.echo(f" 승률:          {metrics.get('win_rate', 0):.1f}%")
    click.echo(f" 이익 팩터:     {metrics.get('profit_factor', 0):.2f}")
    click.echo(f" 턴오버:        {metrics.get('turnover', 0):.2f}x")
    click.echo()

    # 벤치마크
    click.echo(f"--- 벤치마크 ({run.get('benchmark', 'KOSPI')}) ---")
    click.echo(f" 벤치마크 수익: {metrics.get('benchmark_return', 0):.2f}%")
    click.echo(f" 초과 수익:     {metrics.get('excess_return', 0):+.2f}%")
    click.echo(f" 베타:          {metrics.get('beta', 0):.2f}")
    click.echo(f" 알파:          {metrics.get('alpha', 0):+.2f}%")
    click.echo(f"{'='*60}")

    # 월별 수익률
    monthly = metrics.get("monthly_returns", [])
    if monthly:
        click.echo("\n--- 월별 수익률 ---")
        for entry in monthly:
            click.echo(f" {entry['month']}:  {entry['return']:+.2f}%")

    # 스냅샷 요약
    if snapshots:
        click.echo(f"\n  스냅샷: {len(snapshots)}개")
        click.echo(
            f"  첫 날: {snapshots[0]['date']} "
            f"({snapshots[0]['total_value']:,.0f}원)"
        )
        click.echo(
            f"  마지막: {snapshots[-1]['date']} "
            f"({snapshots[-1]['total_value']:,.0f}원)"
        )

    # HTML 리포트
    if html:
        from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
        from alphapulse.trading.backtest.report import BacktestReport
        from alphapulse.trading.core.cost_model import CostModel
        from alphapulse.trading.core.models import PortfolioSnapshot

        snap_objs = [
            PortfolioSnapshot(
                date=s["date"], cash=s["cash"], positions=[],
                total_value=s["total_value"],
                daily_return=s["daily_return"],
                cumulative_return=s["cumulative_return"],
                drawdown=s["drawdown"],
            )
            for s in snapshots
        ]
        bt_result = BacktestResult(
            snapshots=snap_objs, trades=[], metrics=metrics,
            config=BacktestConfig(
                initial_capital=run["initial_capital"],
                start_date=run["start_date"],
                end_date=run["end_date"],
                cost_model=CostModel(),
                benchmark=run.get("benchmark", "KOSPI"),
            ),
        )
        BacktestReport().save_html(bt_result, html)
        click.echo(f"\n  HTML 리포트: {html}")


@backtest.command(name="compare")
@click.argument("run_id_1")
@click.argument("run_id_2")
def backtest_compare(run_id_1, run_id_2):
    """두 백테스트 결과를 비교한다.

    RUN_ID는 전체 UUID 또는 앞 8자리 접두사.
    """
    import json

    from alphapulse.core.config import Config
    from alphapulse.trading.backtest.store import BacktestStore

    cfg = Config()
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")

    run1 = _resolve_run(bt_store, run_id_1)
    run2 = _resolve_run(bt_store, run_id_2)
    if not run1:
        click.echo(f"결과를 찾을 수 없습니다: {run_id_1}")
        return
    if not run2:
        click.echo(f"결과를 찾을 수 없습니다: {run_id_2}")
        return

    m1 = json.loads(run1.get("metrics", "{}"))
    m2 = json.loads(run2.get("metrics", "{}"))
    n1 = run1.get("name", run1["run_id"][:8])
    n2 = run2.get("name", run2["run_id"][:8])

    click.echo(f"\n{'='*70}")
    click.echo(" 백테스트 비교")
    click.echo(f"{'='*70}")
    click.echo(f" {'지표':<20}  {n1:>20}  {n2:>20}")
    click.echo(f" {'-'*68}")

    compare_keys = [
        ("기간", None, None),
        ("총 수익률 (%)", "total_return", ".2f"),
        ("CAGR (%)", "cagr", ".2f"),
        ("샤프 비율", "sharpe_ratio", ".2f"),
        ("소르티노 비율", "sortino_ratio", ".2f"),
        ("MDD (%)", "max_drawdown", ".2f"),
        ("변동성 (%)", "volatility", ".2f"),
        ("승률 (%)", "win_rate", ".1f"),
        ("이익 팩터", "profit_factor", ".2f"),
        ("총 거래", "total_trades", "d"),
        ("턴오버", "turnover", ".2f"),
        ("벤치마크 수익 (%)", "benchmark_return", ".2f"),
        ("알파 (%)", "alpha", ".2f"),
        ("베타", "beta", ".2f"),
    ]

    for label, key, fmt in compare_keys:
        if key is None:
            v1 = f"{run1['start_date']}~{run1['end_date']}"
            v2 = f"{run2['start_date']}~{run2['end_date']}"
        else:
            val1 = m1.get(key, 0)
            val2 = m2.get(key, 0)
            v1 = f"{val1:{fmt}}"
            v2 = f"{val2:{fmt}}"
        click.echo(f" {label:<20}  {v1:>20}  {v2:>20}")

    click.echo(f"{'='*70}")


@backtest.command(name="trades")
@click.argument("run_id")
@click.option("--code", default=None, help="종목코드 필터")
@click.option("--winner/--loser", default=None, help="승/패 필터")
@click.option("--limit", default=50, type=int, help="표시 건수")
def backtest_trades(run_id, code, winner, limit):
    """백테스트의 개별 거래(라운드트립)를 조회한다.

    RUN_ID는 전체 UUID 또는 앞 8자리 접두사.

    예:
      ap trading backtest trades abc12345
      ap trading backtest trades abc12345 --code 005930
      ap trading backtest trades abc12345 --winner --limit 10
    """
    from alphapulse.core.config import Config
    from alphapulse.trading.backtest.store import BacktestStore

    cfg = Config()
    bt_store = BacktestStore(db_path=cfg.DATA_DIR / "backtest.db")

    run = _resolve_run(bt_store, run_id)
    if not run:
        click.echo(f"결과를 찾을 수 없습니다: {run_id}")
        return

    rts = bt_store.get_round_trips(run["run_id"])
    if not rts:
        trades = bt_store.get_trades(run["run_id"])
        if trades:
            click.echo(
                f"체결 {len(trades)}건 있으나 라운드트립(매수→매도 쌍) 없음."
            )
            click.echo("(매수만 있고 매도가 없는 경우)")
        else:
            click.echo("거래 기록이 없습니다.")
        return

    if code:
        rts = [r for r in rts if r["code"] == code]
    if winner is True:
        rts = [r for r in rts if r["pnl"] > 0]
    elif winner is False:
        rts = [r for r in rts if r["pnl"] <= 0]

    total = len(rts)
    rts = rts[:limit]

    click.echo(f"\n{'='*90}")
    click.echo(
        f" 거래 이력 — {run.get('name', '')} "
        f"({run['start_date']}~{run['end_date']})"
    )
    click.echo(f"{'='*90}")
    click.echo(
        f" {'#':>3}  {'종목':>8}  {'종목명':<10}  "
        f"{'매수일':>8}  {'매수가':>10}  {'매도일':>8}  {'매도가':>10}  "
        f"{'수익률':>7}  {'보유':>4}  {'손익':>12}"
    )
    click.echo(f" {'-'*88}")

    for i, rt in enumerate(rts, 1):
        name = rt.get("name", "")[:9]
        ret_str = f"{rt['return_pct']:+.1f}%"
        pnl_str = f"{rt['pnl']:+,.0f}"
        click.echo(
            f" {i:>3}  {rt['code']:>8}  {name:<10}  "
            f"{rt['buy_date']:>8}  {rt['buy_price']:>10,.0f}  "
            f"{rt['sell_date']:>8}  {rt['sell_price']:>10,.0f}  "
            f"{ret_str:>7}  {rt['holding_days']:>3}일  {pnl_str:>12}"
        )

    # 요약
    click.echo(f"\n{'-'*90}")
    wins = [r for r in rts if r["pnl"] > 0]
    losses = [r for r in rts if r["pnl"] <= 0]
    total_pnl = sum(r["pnl"] for r in rts)
    avg_hold = (
        sum(r["holding_days"] for r in rts) / len(rts) if rts else 0
    )
    click.echo(
        f" 합계: {len(rts)}건 (승 {len(wins)} / 패 {len(losses)})  "
        f"총 손익: {total_pnl:+,.0f}원  "
        f"평균 보유: {avg_hold:.0f}일"
    )
    if total > limit:
        click.echo(f" ({total}건 중 {limit}건 표시)")
    click.echo(f"{'='*90}")


def _resolve_run(bt_store, run_id: str) -> dict | None:
    """run_id 전체 또는 접두사로 백테스트 결과를 찾는다."""
    run = bt_store.get_run(run_id)
    if run:
        return run
    runs = bt_store.list_runs()
    for r in runs:
        if r["run_id"].startswith(run_id):
            return r
    return None


@trading.command()
@click.option("--mode", type=click.Choice(["paper", "live"]), default="paper",
              help="실행 모드 (paper: 모의투자, live: 실매매)")
@click.option("--daemon", is_flag=True, help="데몬 모드로 실행 (스케줄 기반)")
def run(mode, daemon):
    """매매 파이프라인을 실행한다."""
    import asyncio

    from alphapulse.trading.core.enums import TradingMode
    from alphapulse.trading.orchestrator.factory import build_trading_engine

    trading_mode = TradingMode(mode)

    click.echo(f"매매 모드: {mode}")
    click.echo(f"데몬: {'예' if daemon else '아니오 (1회 실행)'}")

    click.echo("TradingEngine 초기화 중...")
    try:
        engine = build_trading_engine(trading_mode)
    except Exception as e:
        click.echo(f"엔진 초기화 실패: {e}")
        return

    try:
        if daemon:
            from alphapulse.trading.core.calendar import KRXCalendar
            from alphapulse.trading.orchestrator.scheduler import TradingScheduler

            click.echo("데몬 모드 시작 — Ctrl+C로 종료")
            scheduler = TradingScheduler(engine=engine, calendar=KRXCalendar())
            asyncio.run(scheduler.run_daemon())
        else:
            click.echo("1회 실행 시작")
            result = asyncio.run(engine.run_daily())
            click.echo(
                f"실행 완료: {result.get('signals', 0)}개 전략 시그널 / "
                f"{result.get('orders_submitted', 0)}건 주문"
            )
    except KeyboardInterrupt:
        click.echo("\n매매 중단")
    except Exception as e:
        click.echo(f"오류: {e}")


@trading.command()
def status():
    """시스템 상태를 확인한다."""
    from alphapulse.core.config import Config
    from alphapulse.trading.portfolio.store import PortfolioStore

    click.echo("Trading System Status")
    click.echo("=" * 40)

    cfg = Config()
    click.echo(f"모드: {'모의투자' if cfg.KIS_IS_PAPER else '실전'}")
    click.echo(f"실매매: {'활성화' if cfg.LIVE_TRADING_ENABLED else '비활성화'}")
    click.echo(f"일일 한도: {cfg.MAX_DAILY_ORDERS}회 / {cfg.MAX_DAILY_AMOUNT:,}원")
    click.echo(f"전략 배분: {cfg.STRATEGY_ALLOCATIONS}")
    click.echo(f"초기 자본: {cfg.BACKTEST_INITIAL_CAPITAL:,}원")
    click.echo(
        f"리스크 한도: 종목당 {cfg.MAX_POSITION_WEIGHT:.0%} / "
        f"DD soft {cfg.MAX_DRAWDOWN_SOFT:.0%} / hard {cfg.MAX_DRAWDOWN_HARD:.0%}"
    )
    click.echo("-" * 40)

    # 최신 포트폴리오 스냅샷
    try:
        store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
        mode_str = "paper" if cfg.KIS_IS_PAPER else "live"
        snapshot = store.get_latest_snapshot(mode=mode_str)
        if snapshot:
            click.echo(f"최신 스냅샷 ({mode_str}): {snapshot['date']}")
            click.echo(f"  총자산: {snapshot['total_value']:,.0f}원")
            click.echo(f"  현금: {snapshot['cash']:,.0f}원")
            click.echo(f"  일간: {snapshot['daily_return']:+.2f}%")
            click.echo(f"  누적: {snapshot['cumulative_return']:+.2f}%")
            click.echo(f"  드로다운: {snapshot['drawdown']:.2f}%")
        else:
            click.echo("스냅샷 없음 (매매 이력 없음).")
    except Exception as e:
        click.echo(f"스냅샷 조회 실패: {e}")


@trading.command()
def reconcile():
    """DB와 증권사 잔고를 대사한다."""
    from alphapulse.core.config import Config
    from alphapulse.trading.broker.kis_client import KISClient
    from alphapulse.trading.orchestrator.recovery import RecoveryManager

    click.echo("DB/증권사 잔고 대사 실행")

    cfg = Config()
    if not cfg.KIS_APP_KEY:
        click.echo("KIS_APP_KEY가 설정되지 않았습니다.")
        return

    client = KISClient(
        app_key=cfg.KIS_APP_KEY,
        app_secret=cfg.KIS_APP_SECRET,
        account_no=cfg.KIS_ACCOUNT_NO,
        is_paper=cfg.KIS_IS_PAPER,
    )

    # Broker 선택: 모의투자/실전에 따라
    if cfg.KIS_IS_PAPER:
        from alphapulse.trading.broker.paper_broker import PaperBroker
        from alphapulse.trading.core.audit import AuditLogger

        broker = PaperBroker(client=client, audit=AuditLogger())
    else:
        from alphapulse.trading.broker.kis_broker import KISBroker
        from alphapulse.trading.core.audit import AuditLogger

        broker = KISBroker(client=client, audit=AuditLogger())

    # 포트폴리오 저장소는 기존 인프라 사용
    from alphapulse.trading.portfolio.store import PortfolioStore

    store = PortfolioStore()

    mgr = RecoveryManager(broker=broker, store=store, alert=None)
    click.echo("대사 진행 중...")
    warnings = mgr.reconcile()

    if warnings:
        click.echo(f"불일치 {len(warnings)}건 발견:")
        for w in warnings:
            click.echo(f"  - {w}")
    else:
        click.echo("대사 완료: 불일치 없음")


@trading.group()
def portfolio():
    """포트폴리오 관리."""
    pass


@portfolio.command(name="show")
@click.option("--mode", default="paper",
              type=click.Choice(["paper", "live", "backtest"]))
def portfolio_show(mode):
    """현재 포트폴리오 상태를 표시한다."""
    import json

    from alphapulse.core.config import Config
    from alphapulse.trading.portfolio.store import PortfolioStore

    cfg = Config()
    store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
    snapshot = store.get_latest_snapshot(mode=mode)

    click.echo(f"포트폴리오 현황 ({mode})")
    click.echo("=" * 40)
    if not snapshot:
        click.echo("스냅샷 없음.")
        return

    click.echo(f"날짜: {snapshot['date']}")
    click.echo(f"총자산: {snapshot['total_value']:,.0f}원")
    click.echo(f"현금: {snapshot['cash']:,.0f}원")
    click.echo(f"일간 수익률: {snapshot['daily_return']:+.2f}%")
    click.echo(f"누적 수익률: {snapshot['cumulative_return']:+.2f}%")
    click.echo(f"드로다운: {snapshot['drawdown']:.2f}%")

    positions = snapshot.get("positions", "[]")
    try:
        positions_list = json.loads(positions) if isinstance(positions, str) else positions
    except (TypeError, json.JSONDecodeError):
        positions_list = []
    if positions_list:
        click.echo("-" * 40)
        click.echo(f"보유 종목: {len(positions_list)}개")
        for p in positions_list[:20]:
            click.echo(
                f"  {p.get('code', '')} {p.get('name', ''):12s} "
                f"{p.get('quantity', 0):>6}주 "
                f"@{p.get('current_price', 0):>10,.0f}"
            )


@portfolio.command(name="history")
@click.option("--days", default=30, help="조회 기간 (일)")
@click.option("--mode", default="paper",
              type=click.Choice(["paper", "live", "backtest"]))
def portfolio_history(days, mode):
    """포트폴리오 성과 이력을 조회한다."""
    from datetime import datetime, timedelta

    from alphapulse.core.config import Config
    from alphapulse.trading.portfolio.store import PortfolioStore

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    cfg = Config()
    store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
    rows = store.get_snapshots(start=start, end=end, mode=mode)

    click.echo(f"최근 {days}일 포트폴리오 이력 ({mode})")
    click.echo("=" * 60)
    if not rows:
        click.echo("이력 없음.")
        return

    click.echo(f"{'날짜':<10} {'총자산':>15} {'일간':>8} {'누적':>8} {'DD':>8}")
    click.echo("-" * 60)
    for r in rows:
        click.echo(
            f"{r['date']:<10} {r['total_value']:>15,.0f} "
            f"{r['daily_return']:>+7.2f}% "
            f"{r['cumulative_return']:>+7.2f}% "
            f"{r['drawdown']:>+7.2f}%"
        )


@portfolio.command(name="attribution")
@click.option("--days", default=30, help="분석 기간 (일)")
@click.option("--mode", default="paper",
              type=click.Choice(["paper", "live", "backtest"]))
def portfolio_attribution(days, mode):
    """성과 귀속 분석을 실행한다."""
    import json
    from datetime import datetime

    from alphapulse.core.config import Config
    from alphapulse.trading.portfolio.store import PortfolioStore

    cfg = Config()
    store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
    date = datetime.now().strftime("%Y%m%d")
    attr = store.get_attribution(date=date, mode=mode)

    click.echo(f"최근 {days}일 성과 귀속 분석 ({mode})")
    click.echo("=" * 40)
    if not attr:
        click.echo(
            "attribution 데이터 없음. "
            "TradingEngine 실행 후 다시 시도하세요."
        )
        return

    for key in ("strategy_returns", "factor_returns", "sector_returns"):
        raw = attr.get(key) or "{}"
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            parsed = {}
        click.echo(f"\n[{key}]")
        for k, v in parsed.items():
            click.echo(f"  {k}: {v:+.2f}%")


@trading.group()
def risk():
    """리스크 관리."""
    pass


@risk.command(name="report")
@click.option("--mode", default="paper",
              type=click.Choice(["paper", "live", "backtest"]))
def risk_report(mode):
    """리스크 리포트를 생성한다."""
    from alphapulse.core.config import Config
    from alphapulse.trading.core.models import PortfolioSnapshot
    from alphapulse.trading.portfolio.store import PortfolioStore
    from alphapulse.trading.risk.drawdown import DrawdownManager
    from alphapulse.trading.risk.limits import RiskLimits
    from alphapulse.trading.risk.manager import RiskManager
    from alphapulse.trading.risk.var import VaRCalculator

    cfg = Config()
    store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
    snapshot_row = store.get_latest_snapshot(mode=mode)

    click.echo(f"리스크 리포트 ({mode})")
    click.echo("=" * 40)
    if not snapshot_row:
        click.echo("스냅샷 없음 — 리포트 생성 불가.")
        return

    snapshot = PortfolioSnapshot(
        date=snapshot_row["date"],
        cash=snapshot_row["cash"],
        positions=[],
        total_value=snapshot_row["total_value"],
        daily_return=snapshot_row["daily_return"],
        cumulative_return=snapshot_row["cumulative_return"],
        drawdown=snapshot_row["drawdown"],
    )

    limits = RiskLimits(
        max_position_weight=cfg.MAX_POSITION_WEIGHT,
        max_drawdown_soft=cfg.MAX_DRAWDOWN_SOFT,
        max_drawdown_hard=cfg.MAX_DRAWDOWN_HARD,
    )
    mgr = RiskManager(
        limits=limits,
        var_calc=VaRCalculator(),
        drawdown_mgr=DrawdownManager(limits=limits),
    )
    report = mgr.daily_report(snapshot)

    click.echo(f"드로다운 상태: {report.drawdown_status}")
    click.echo(f"VaR(95%): {report.var_95:+.2f}%")
    click.echo(f"CVaR(95%): {report.cvar_95:+.2f}%")
    if getattr(report, "alerts", None):
        click.echo("-" * 40)
        for alert in report.alerts:
            click.echo(f"  [{alert.level}] {alert.message}")


@risk.command(name="stress")
@click.option("--mode", default="paper",
              type=click.Choice(["paper", "live", "backtest"]))
def risk_stress(mode):
    """스트레스 테스트를 실행한다."""
    from alphapulse.core.config import Config
    from alphapulse.trading.core.models import PortfolioSnapshot
    from alphapulse.trading.portfolio.store import PortfolioStore
    from alphapulse.trading.risk.stress_test import StressTest

    cfg = Config()
    store = PortfolioStore(db_path=str(cfg.PORTFOLIO_DB_PATH))
    snapshot_row = store.get_latest_snapshot(mode=mode)

    click.echo(f"스트레스 테스트 ({mode})")
    click.echo("=" * 40)
    if not snapshot_row:
        click.echo("스냅샷 없음 — 테스트 불가.")
        return

    snapshot = PortfolioSnapshot(
        date=snapshot_row["date"],
        cash=snapshot_row["cash"],
        positions=[],
        total_value=snapshot_row["total_value"],
        daily_return=snapshot_row["daily_return"],
        cumulative_return=snapshot_row["cumulative_return"],
        drawdown=snapshot_row["drawdown"],
    )
    tester = StressTest()
    results = tester.run_all(snapshot)
    for name, value in results.items():
        click.echo(f"  {name}: {value:+.2f}%")


@risk.command(name="limits")
def risk_limits():
    """현재 리스크 리밋 설정을 표시한다."""
    from alphapulse.core.config import Config

    cfg = Config()
    click.echo("리스크 리밋 설정")
    click.echo("=" * 40)
    click.echo(f"종목당 최대 비중: {cfg.MAX_POSITION_WEIGHT:.0%}")
    click.echo(f"드로다운 soft: {cfg.MAX_DRAWDOWN_SOFT:.0%}")
    click.echo(f"드로다운 hard: {cfg.MAX_DRAWDOWN_HARD:.0%}")
    click.echo(f"일일 주문 한도: {cfg.MAX_DAILY_ORDERS}회")
    click.echo(f"일일 금액 한도: {cfg.MAX_DAILY_AMOUNT:,}원")
