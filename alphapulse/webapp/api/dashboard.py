"""Dashboard home — 여러 도메인 aggregate 1회 호출."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from alphapulse.core.config import Config
from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.core.storage.history import PulseHistory
from alphapulse.feedback.evaluator import FeedbackEvaluator
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class HighlightBadge(BaseModel):
    name: str
    direction: str   # up | down | neutral
    sentiment: str   # positive | negative | neutral


class BriefingHeroData(BaseModel):
    date: str                          # YYYYMMDD
    created_at: int                    # epoch seconds
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


class HomeResponse(BaseModel):
    portfolio: dict | None
    portfolio_history: list
    risk: dict | None
    data_status: dict
    recent_backtests: list
    recent_audits: list


def _select_top3_indicators(pulse_result: dict) -> list[dict]:
    """pulse_result 의 지표 목록에서 score 절대값 TOP3 을 반환한다.

    indicator_descriptions 가 있으면 우선 사용, 없으면 indicators 사용.
    각 지표의 value 는 `{score: float}` 또는 scalar 숫자 둘 다 허용.
    """
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
    top = scored[:3]

    result: list[dict] = []
    for name, score in top:
        if score > 0:
            direction, sentiment = "up", "positive"
        elif score < 0:
            direction, sentiment = "down", "negative"
        else:
            direction, sentiment = "neutral", "neutral"
        result.append({"name": name, "direction": direction, "sentiment": sentiment})
    return result


def _build_briefing_hero(store: BriefingStore) -> BriefingHeroData | None:
    """최신 브리핑 한 건을 `BriefingHeroData` 로 변환한다. 없으면 None."""
    records = store.get_recent(days=1)
    if not records:
        return None
    record = records[0]
    payload = record.get("payload") or {}
    pulse_result = payload.get("pulse_result") or {}

    score = float(pulse_result.get("score", 0.0))
    signal = str(pulse_result.get("signal", "neutral"))

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
    """최근 7일 Pulse 이력을 위젯 데이터로 변환한다."""
    records = history.get_recent(days=7)
    if not records:
        return PulseWidgetData(latest=None, history7=[])

    latest = PulseLatest(
        date=str(records[0]["date"]),
        score=float(records[0]["score"]),
        signal=str(records[0]["signal"]),
    )
    chronological = list(reversed(records))
    history7 = [
        PulseHistoryPoint(
            date=str(r["date"]),
            score=float(r["score"]),
            signal=str(r["signal"]),
        )
        for r in chronological
    ]
    return PulseWidgetData(latest=latest, history7=history7)


def _build_feedback_widget(evaluator: FeedbackEvaluator) -> FeedbackWidgetData | None:
    """최근 7일 피드백 요약 (적중률 + 지표 TOP2)."""
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
    top = qualified[:2]

    return FeedbackWidgetData(
        hit_rate_7d=float(rates.get("hit_rate_1d", 0.0)),
        top_indicators=[FeedbackIndicator(name=n, hit_rate=r) for n, r in top],
    )


def _build_content_widget(reader: ContentReader) -> ContentWidgetData:
    """최근 3건 리포트를 위젯 데이터로 변환한다."""
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


def get_audit(request: Request) -> AuditReader:
    return request.app.state.audit_reader


@router.get("/home", response_model=HomeResponse)
async def home(
    request: Request,
    _: User = Depends(get_current_user),
    portfolio: PortfolioReader = Depends(get_portfolio),
    risk: RiskReader = Depends(get_risk),
    data: DataStatusReader = Depends(get_data),
    audit: AuditReader = Depends(get_audit),
):
    mode = "paper"
    snap = portfolio.get_latest(mode=mode)
    history = portfolio.get_history(mode=mode, days=30)
    risk_data = risk.get_report(mode=mode) if snap else None
    bt_store = request.app.state.backtest_reader
    recent_bt = bt_store.list_runs(page=1, size=3)
    audit_result = audit.query(page=1, size=10)

    return HomeResponse(
        portfolio=snap.__dict__ if snap else None,
        portfolio_history=[s.__dict__ for s in history],
        risk=risk_data,
        data_status={
            "tables": [t.__dict__ for t in data.get_status()],
            "gaps_count": len(data.detect_gaps(days=5)),
        },
        recent_backtests=[s.__dict__ for s in recent_bt.items],
        recent_audits=[e.__dict__ for e in audit_result["items"]],
    )
