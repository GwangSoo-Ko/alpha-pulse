"""Dashboard home — 여러 도메인 aggregate 1회 호출."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from alphapulse.core.config import Config
from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.core.storage.history import PulseHistory
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class HighlightBadge(BaseModel):
    name: str
    direction: str
    sentiment: str


class BriefingHeroData(BaseModel):
    date: str
    created_at: int
    score: float
    signal: str
    summary_line: str
    highlight_badges: list[HighlightBadge]
    is_today: bool


class PulseLatest(BaseModel):
    date: str
    score: float
    signal: str


class PulseHistoryPoint(BaseModel):
    date: str
    score: float
    signal: str


class PulseWidgetData(BaseModel):
    latest: PulseLatest | None
    history7: list[PulseHistoryPoint]


class FeedbackIndicator(BaseModel):
    name: str
    hit_rate: float


class FeedbackWidgetData(BaseModel):
    hit_rate_7d: float | None
    top_indicators: list[FeedbackIndicator]


class ContentRecentItem(BaseModel):
    date: str
    filename: str
    title: str


class ContentWidgetData(BaseModel):
    recent: list[ContentRecentItem]


class PortfolioPosition(BaseModel):
    code: str
    name: str
    quantity: float
    current_price: float


class PortfolioSnapshotData(BaseModel):
    date: str
    cash: float
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions: list[PortfolioPosition]


class PortfolioHistoryPoint(BaseModel):
    date: str
    total_value: float


class RiskAlert(BaseModel):
    level: str
    message: str


class RiskReportBody(BaseModel):
    drawdown_status: str | None = None
    var_95: float | None = None
    cvar_95: float | None = None
    alerts: list[RiskAlert] = []


class RiskReportData(BaseModel):
    report: RiskReportBody
    # stress: 스트레스 시나리오별 StressResult dict — 이종 구조라 dict 로 유지
    stress: dict = {}
    cached: bool = False
    computed_at: float | None = None


class TableStatusData(BaseModel):
    name: str
    row_count: int
    latest_date: str | None
    distinct_codes: int


class DataStatusData(BaseModel):
    tables: list[TableStatusData]
    gaps_count: int


class HomeResponse(BaseModel):
    briefing: BriefingHeroData | None
    pulse: PulseWidgetData | None
    feedback: FeedbackWidgetData | None
    content: ContentWidgetData
    portfolio: PortfolioSnapshotData | None
    portfolio_history: list[PortfolioHistoryPoint]
    risk: RiskReportData | None
    data_status: DataStatusData


def _score_to_signal_key(score: float) -> str:
    """score 값 → SignalLevel enum key (FE market-labels 의 scoreToSignal 과 대칭).

    백엔드 DB 에는 Korean 라벨("강한 매수 (Strong Bullish)")로 저장되어 있으나,
    FE 는 enum key("strong_bullish")로 스타일 매칭한다. API 응답에서는 키로
    변환해 내린다. 기준: Config.SIGNAL_THRESHOLDS 와 일치.
    """
    if score >= 60:
        return "strong_bullish"
    if score >= 20:
        return "moderately_bullish"
    if score >= -19:
        return "neutral"
    if score >= -59:
        return "moderately_bearish"
    return "strong_bearish"


def _select_top3_indicators(pulse_result: dict) -> list[dict]:
    source = pulse_result.get("indicator_descriptions") or pulse_result.get("indicators")
    if not isinstance(source, dict) or not source:
        return []
    scored: list[tuple[str, float]] = []
    for name, value in source.items():
        if isinstance(value, dict):
            raw = value.get("score")
        else:
            raw = value
        if raw is None:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        scored.append((name, score))
    scored.sort(key=lambda t: abs(t[1]), reverse=True)
    result: list[dict] = []
    for name, score in scored[:3]:
        if score > 0:
            direction, sentiment = "up", "positive"
        elif score < 0:
            direction, sentiment = "down", "negative"
        else:
            direction, sentiment = "neutral", "neutral"
        result.append({"name": name, "direction": direction, "sentiment": sentiment})
    return result


def _build_briefing_hero(store: BriefingStore) -> BriefingHeroData | None:
    records = store.get_recent(days=1)
    if not records:
        return None
    record = records[0]
    payload = record.get("payload") or {}
    pulse_result = payload.get("pulse_result") or {}

    score = float(pulse_result.get("score", 0.0))
    # DB 에 저장된 signal 은 Korean 라벨 → 항상 score 기반 enum key 로 재계산
    signal = _score_to_signal_key(score)

    daily = payload.get("daily_result_msg") or ""
    first_line = daily.split("\n", 1)[0].strip() if daily else ""
    if not first_line:
        commentary = payload.get("commentary") or ""
        first_line = commentary.split(".", 1)[0].strip()
        if first_line:
            first_line += "."

    badges = [HighlightBadge(**b) for b in _select_top3_indicators(pulse_result)]

    today = Config.get_today_str()
    return BriefingHeroData(
        date=str(record["date"]),
        created_at=int(record.get("created_at") or 0),
        score=score,
        signal=signal,
        summary_line=first_line,
        highlight_badges=badges,
        is_today=(str(record["date"]) == today),
    )


def _build_pulse_widget(history: PulseHistory) -> PulseWidgetData:
    records = history.get_recent(days=7)
    if not records:
        return PulseWidgetData(latest=None, history7=[])
    latest_score = float(records[0]["score"])
    latest = PulseLatest(
        date=str(records[0]["date"]),
        score=latest_score,
        signal=_score_to_signal_key(latest_score),
    )
    chronological = list(reversed(records))
    history7 = [
        PulseHistoryPoint(
            date=str(r["date"]),
            score=float(r["score"]),
            signal=_score_to_signal_key(float(r["score"])),
        )
        for r in chronological
    ]
    return PulseWidgetData(latest=latest, history7=history7)


def _build_feedback_widget(evaluator: FeedbackEvaluator) -> FeedbackWidgetData | None:
    rates = evaluator.get_hit_rates(days=7)
    if rates.get("total_evaluated", 0) == 0:
        return None
    acc = evaluator.get_indicator_accuracy(days=7, threshold=50.0)
    qualified = [
        (name, float(v["accuracy"]))
        for name, v in acc.items()
        if v.get("total", 0) >= 3
    ]
    qualified.sort(key=lambda t: t[1], reverse=True)
    return FeedbackWidgetData(
        hit_rate_7d=float(rates.get("hit_rate_1d", 0.0)),
        top_indicators=[FeedbackIndicator(name=n, hit_rate=r) for n, r in qualified[:2]],
    )


def _build_content_widget(reader: ContentReader) -> ContentWidgetData:
    result = reader.list_reports(size=3, sort="newest")
    items = result.get("items", [])
    recent = [
        ContentRecentItem(
            date=str(m.get("analyzed_at") or "")[:10],
            filename=str(m.get("filename") or ""),
            title=str(m.get("title") or ""),
        )
        for m in items
    ]
    return ContentWidgetData(recent=recent)


def get_portfolio(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


def get_risk(request: Request) -> RiskReader:
    return request.app.state.risk_reader


def get_data(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_briefing_store(request: Request) -> BriefingStore:
    return request.app.state.briefing_store


def get_pulse_history(request: Request) -> PulseHistory:
    return request.app.state.pulse_history


def get_feedback_evaluator(request: Request) -> FeedbackEvaluator:
    """매 요청마다 새 FeedbackEvaluator 인스턴스를 생성한다.

    Evaluator 내부 record 캐시가 인스턴스 생명주기 = 요청 생명주기 내에서만
    유효하도록 request-scoped 로 구성. 싱글턴 대신 store 만 공유.
    """
    store = request.app.state.feedback_store
    return FeedbackEvaluator(store=store)


def get_content_reader(request: Request) -> ContentReader:
    return request.app.state.content_reader


@router.get("/home", response_model=HomeResponse)
async def home(
    _: User = Depends(get_current_user),
    portfolio: PortfolioReader = Depends(get_portfolio),
    risk: RiskReader = Depends(get_risk),
    data: DataStatusReader = Depends(get_data),
    briefing_store: BriefingStore = Depends(get_briefing_store),
    pulse_history: PulseHistory = Depends(get_pulse_history),
    feedback_evaluator: FeedbackEvaluator = Depends(get_feedback_evaluator),
    content_reader: ContentReader = Depends(get_content_reader),
):
    mode = "paper"

    briefing = None
    try:
        briefing = _build_briefing_hero(briefing_store)
    except Exception as e:
        logger.warning("home: briefing fetch failed: %s", e)

    pulse = None
    try:
        pulse = _build_pulse_widget(pulse_history)
    except Exception as e:
        logger.warning("home: pulse fetch failed: %s", e)

    feedback = None
    try:
        feedback = _build_feedback_widget(feedback_evaluator)
    except Exception as e:
        logger.warning("home: feedback fetch failed: %s", e)

    content = ContentWidgetData(recent=[])
    try:
        content = _build_content_widget(content_reader)
    except Exception as e:
        logger.warning("home: content fetch failed: %s", e)

    portfolio_snap = None
    portfolio_hist: list = []
    try:
        portfolio_snap = portfolio.get_latest(mode=mode)
        portfolio_hist = portfolio.get_history(mode=mode, days=30)
    except Exception as e:
        logger.warning("home: portfolio fetch failed: %s", e)

    risk_data = None
    if portfolio_snap is not None:
        try:
            risk_data = risk.get_report(mode=mode)
        except Exception as e:
            logger.warning("home: risk fetch failed: %s", e)

    data_status_data = DataStatusData(tables=[], gaps_count=0)
    try:
        data_status_data = DataStatusData(
            tables=[TableStatusData(**t.__dict__) for t in data.get_status()],
            gaps_count=len(data.detect_gaps(days=5)),
        )
    except Exception as e:
        logger.warning("home: data_status fetch failed: %s", e)

    return HomeResponse(
        briefing=briefing,
        pulse=pulse,
        feedback=feedback,
        content=content,
        portfolio=(
            PortfolioSnapshotData(**portfolio_snap.__dict__) if portfolio_snap else None
        ),
        portfolio_history=[
            PortfolioHistoryPoint(date=s.date, total_value=s.total_value)
            for s in portfolio_hist
        ],
        risk=RiskReportData(**risk_data) if risk_data else None,
        data_status=data_status_data,
    )
