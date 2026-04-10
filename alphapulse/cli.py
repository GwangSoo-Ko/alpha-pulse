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

    results = collector.update(markets=markets)

    if not results:
        click.echo("이미 최신 상태입니다.")
    else:
        for r in results:
            click.echo(
                f"{r.market}: {r.ohlcv_count}종목 업데이트 "
                f"({r.elapsed_seconds:.0f}초)"
            )


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


# NOTE: `ap trading backtest` 명령은 Phase 3에서 정의됨.
#       `ap trading screen` 명령은 Phase 1에서 정의됨 (위 참조).


@trading.command()
@click.option("--mode", type=click.Choice(["paper", "live"]), default="paper",
              help="실행 모드 (paper: 모의투자, live: 실매매)")
@click.option("--daemon", is_flag=True, help="데몬 모드로 실행 (스케줄 기반)")
def run(mode, daemon):
    """매매 파이프라인을 실행한다."""
    import asyncio

    from alphapulse.trading.core.enums import TradingMode
    from alphapulse.trading.orchestrator.engine import TradingEngine

    trading_mode = TradingMode(mode)

    click.echo(f"매매 모드: {mode}")
    click.echo(f"데몬: {'예' if daemon else '아니오 (1회 실행)'}")

    click.echo("TradingEngine 초기화 중...")
    engine = TradingEngine(mode=trading_mode)

    try:
        if daemon:
            from alphapulse.trading.core.calendar import KRXCalendar
            from alphapulse.trading.orchestrator.scheduler import TradingScheduler

            click.echo("데몬 모드 시작 — Ctrl+C로 종료")
            scheduler = TradingScheduler(engine=engine, calendar=KRXCalendar())
            asyncio.run(scheduler.run_daemon())
        else:
            click.echo("1회 실행 시작")
            asyncio.run(engine.run_daily())
    except KeyboardInterrupt:
        click.echo("\n매매 중단")
    except Exception as e:
        click.echo(f"오류: {e}")


@trading.command()
def status():
    """시스템 상태를 확인한다."""
    from alphapulse.core.config import Config

    click.echo("Trading System Status")
    click.echo("=" * 40)

    cfg = Config()
    click.echo(f"모드: {'모의투자' if cfg.KIS_IS_PAPER else '실전'}")
    click.echo(f"실매매: {'활성화' if cfg.LIVE_TRADING_ENABLED else '비활성화'}")
    click.echo(f"일일 한도: {cfg.MAX_DAILY_ORDERS}회 / {cfg.MAX_DAILY_AMOUNT:,}원")
    click.echo(f"전략 배분: {cfg.STRATEGY_ALLOCATIONS}")


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
def portfolio_show():
    """현재 포트폴리오 상태를 표시한다."""
    click.echo("포트폴리오 현황")
    click.echo("=" * 40)
    click.echo("(포트폴리오 저장소에서 최신 스냅샷 로드)")


@portfolio.command(name="history")
@click.option("--days", default=30, help="조회 기간 (일)")
def portfolio_history(days):
    """포트폴리오 성과 이력을 조회한다."""
    click.echo(f"최근 {days}일 포트폴리오 이력")


@portfolio.command(name="attribution")
@click.option("--days", default=30, help="분석 기간 (일)")
def portfolio_attribution(days):
    """성과 귀속 분석을 실행한다."""
    click.echo(f"최근 {days}일 성과 귀속 분석")


@trading.group()
def risk():
    """리스크 관리."""
    pass


@risk.command(name="report")
def risk_report():
    """리스크 리포트를 생성한다."""
    click.echo("리스크 리포트")
    click.echo("=" * 40)


@risk.command(name="stress")
def risk_stress():
    """스트레스 테스트를 실행한다."""
    click.echo("스트레스 테스트 실행")


@risk.command(name="limits")
def risk_limits():
    """현재 리스크 리밋 설정을 표시한다."""
    click.echo("리스크 리밋 설정")
    click.echo("=" * 40)
